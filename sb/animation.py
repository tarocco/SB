import numpy as np
from scipy.spatial import Delaunay
from math import exp, log
from .math import soft_minimum
from multiprocessing import Process, Value, Array
from ctypes import Structure, c_long, c_float
from sb.utilities import spin


class Vector2(Structure):
    _fields_ = [('x', c_float), ('y', c_float)]

    def __iter__(self):
        yield from (self.x, self.y)

def delaunay_relax_points(
        indices, points, points_out, neighbor_divs, neighbors,
        alpha, beta):

    def get_neighbors(point_index):
        a = neighbor_divs[point_index]
        b = neighbor_divs[point_index + 1]
        return neighbors[a:b]

    for idx in indices:
        p = np.frombuffer(points[idx]).view('<f4')
        neighbor_indices = get_neighbors(idx)
        p_neighbors = [points[i] for i in neighbor_indices]
        delta = np.zeros_like(p)
        for neighbor in p_neighbors:
            n = np.frombuffer(neighbor).view('<f4') - p
            n_norm = np.linalg.norm(n)
            s = n_norm - beta
            s = soft_minimum(0, s) + log(2)
            #s = min(0, s)
            n = n / (n_norm + 0.0001)
            delta = delta + alpha * s * n
        points_out[idx] = tuple(p + delta)

def delaunay_loop(
        n_relax_procs,
        points_write_var,
        cancellation,
        relax_var,
        relax_completed_var,
        n_points,
        points,
        points_out,
        neighbor_divs,
        neighbors):
    while True:
        with cancellation.get_lock():
            if cancellation.value:
                return
        # Wait for relaxation workers
        with relax_completed_var.get_lock():
            if relax_completed_var.value == 0:
                # Notify work complete
                with points_write_var.get_lock():
                    points_write_var.value = 0
                    if not n_points:
                        continue
                    # Copy relaxed points back to main list
                    for idx in range(n_points.value):
                        points[idx] = points_out[idx]

                # Pause...
                spin(200)

                with points_write_var.get_lock():
                    points_write_var.value = 1
                    # Get np view from points array
                    array = np.frombuffer(
                        points.get_obj(),
                        dtype=Vector2,
                        count=n_points.value).view('<f4').reshape(-1, 2)
                    # Calculate Delaunay
                    delaunay = Delaunay(array)
                    # Copy neighbor data into lists
                    nds, ns = delaunay.vertex_neighbor_vertices
                    for i, nd in enumerate(nds):
                        neighbor_divs[i] = nd
                    for i, n in enumerate(ns):
                        neighbors[i] = n
                    # Set relax counter
                    relax_var.value = n_relax_procs
                    relax_completed_var.value = n_relax_procs
            else:
                spin(1000000)


def relax_points_loop(
        offset,
        stride,
        cancellation,
        relax_var,
        relax_completed_var,
        n_points,
        points,
        points_out,
        neighbor_divs,
        neighbors):
    while True:
        with cancellation.get_lock():
            if cancellation.value:
                return
        # Wait for Delaunay worker
        with relax_var.get_lock():
            if relax_var.value > 0:
                relax_var.value = relax_var.value - 1
            else:
                spin(200)
                continue
        points_indices = range(offset, n_points.value, stride)
        delaunay_relax_points(
            points_indices, points, points_out, neighbor_divs, neighbors,
            0.1, 0.04)
        #with points_out.get_lock():
        #    for idx, p in zip(points_indices, relaxed):
        #        points_out[idx] = tuple(p)
        with relax_completed_var.get_lock():
            relax_completed_var.value = relax_completed_var.value - 1


class PointRelaxer():
    def __init__(self):
        self.n_relaxation_workers = 4
        # self.points_array = None
        # self.work_array = None
        self.cancellation = Value('i', 0, lock=True)
        self.relax_var = Value('i', 0, lock=True)
        self.relax_completed_var = Value('i', 0, lock=True)
        self.points_write_var = Value('i', 0, lock=True)
        self.n_points = Value('i', 0, lock=False)

        self._buffer_size = None
        self.neighors_array_buffer_multiplier = 4

        self.points = None
        self.points_out = None
        self.neighbor_divs = None
        self.neighbors = None

        self.delaunay_process = None
        self.relax_processes = []

    def init_processes(self, buffer_size):
        self._buffer_size = buffer_size
        if self.points:
            del self.points
        if self.points_out:
            del self.points_out
        if self.neighbor_divs:
            del self.neighbor_divs
        if self.neighbors:
            del self.neighbors

        n_neighbors = self.neighors_array_buffer_multiplier * buffer_size
        self.points = Array(Vector2, buffer_size, lock=True)
        self.neighbor_divs = Array(c_long, buffer_size + 1, lock=False)
        self.neighbors = Array(c_long, n_neighbors, lock=False)
        self.points_out = Array(Vector2, buffer_size, lock=True)

        args_common = (self.cancellation, self.relax_var,
                       self.relax_completed_var, self.n_points,
                       self.points, self.points_out,
                       self.neighbor_divs, self.neighbors)
        d_args = (self.n_relaxation_workers,
                  self.points_write_var) + args_common
        r_args_suffix = (self.n_relaxation_workers,) + args_common

        self.delaunay_process = Process(target=delaunay_loop, args=d_args)
        self.relax_processes = [
            Process(target=relax_points_loop, args=(i,) + r_args_suffix)
            for i in range(self.n_relaxation_workers)]

    def set_points(self, points):
        while True:
            with self.points_write_var.get_lock():
                if self.points_write_var.value == 0:
                    n_points = len(points)
                    for idx in range(n_points):
                        p = points[idx]
                        self.points[idx] = tuple(p)
                        self.points_out[idx] = tuple(p)
                    self.n_points.value = n_points
                    return
            spin(1000)
            continue

    def get_points(self):
        with self.points.get_lock():
            return [tuple(self.points[i]) for i in range(self.n_points.value)]

    def start_all(self):
        self.delaunay_process.start()
        for r in self.relax_processes:
            r.start()

    def stop_all(self):
        with self.cancellation.get_lock():
            self.cancellation.value = 1

        if self.delaunay_process:
            self.delaunay_process.join()
        for r in self.relax_processes:
            r.join()

        with self.cancellation.get_lock():
            self.cancellation.value = 0
