import numpy as np
from scipy.spatial import Delaunay
from math import exp, log
from .math import soft_minimum
from multiprocessing import Process, Value, Array
from ctypes import Structure, c_long, c_float
from sb.utilities import spin, acquire_timeout
from copy import copy

class Vector2(Structure):
    _fields_ = [('x', c_float), ('y', c_float)]

    def __iter__(self):
        yield from (self.x, self.y)

def delaunay_relax_points(
        indices, points, points_relaxed, neighbor_divs, neighbors,
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
        points_relaxed[idx] = tuple(p + delta)

def delaunay_loop(
        n_relax_procs,
        points_io,
        points_io_var,
        cancellation,
        relax_var,
        relax_completed_var,
        n_points,
        points,
        points_relaxed,
        neighbor_divs,
        neighbors):
    while True:
        with cancellation.get_lock():
            if cancellation.value:
                return

        # Wait for all relaxation workers to complete
        skip = False
        with relax_completed_var.get_lock():
            skip = relax_completed_var.value > 0
            if not skip:
                if not n_points.value:
                    skip = True
                else:
                    with points_io.get_lock():
                        # TODO: can this be optimized?
                        if points_io_var.value:  # Write in
                            for idx in range(n_points.value):
                                points[idx] = points_io[idx]
                            points_io_var.value = 0
                        else:
                            for idx in range(n_points.value):
                                r = points_relaxed[idx]
                                points[idx] = r
                                points_io[idx] = r


        if skip:
            continue

        # Calculate Delaunay
        with relax_completed_var.get_lock():
            # Get np view from points array
            array = np.frombuffer(
                points,
                dtype=Vector2,
                count=n_points.value).view('<f4').reshape(-1, 2)

            try:
                delaunay = Delaunay(array)
            except Exception as ex:
                continue

            # Copy neighbor data into lists
            nds, ns = delaunay.vertex_neighbor_vertices
            for i, nd in enumerate(nds):
                neighbor_divs[i] = nd
            for i, n in enumerate(ns):
                neighbors[i] = n
            # Set relax counter

            relax_var.value = n_relax_procs
            relax_completed_var.value = n_relax_procs

def relax_points_loop(
        offset,
        stride,
        alpha,
        beta,
        cancellation,
        relax_var,
        relax_completed_var,
        n_points,
        points,
        points_relaxed,
        neighbor_divs,
        neighbors):
    while True:
        with cancellation.get_lock():
            if cancellation.value:
                return
        # Wait for Delaunay worker
        skip = False
        with relax_var.get_lock():
            if relax_var.value > 0:
                relax_var.value = relax_var.value - 1
            else:
                skip = True
        if skip:
            continue

        points_indices = range(offset, n_points.value, stride)

        with alpha.get_lock():
            _alpha = alpha.value
        with beta.get_lock():
            _beta = beta.value

        delaunay_relax_points(
            points_indices, points, points_relaxed, neighbor_divs,
            neighbors, _alpha, _beta)

        with relax_completed_var.get_lock():
            relax_completed_var.value = relax_completed_var.value - 1


class PointRelaxer():
    def __init__(self):
        self.n_relaxation_workers = 8
        # self.points_array = None
        # self.work_array = None
        self.cancellation = Value('i', 0, lock=True)
        self.relax_var = Value('i', 0, lock=True)
        self.relax_completed_var = Value('i', 0, lock=True)
        self.n_points = Value('i', 0, lock=False)
        self.points_io_var = Value('i', 0, lock=False)

        self._buffer_size = None
        self.neighors_array_buffer_multiplier = 4

        self.points = None
        self.points_relaxed = None
        self.points_io = None
        self.neighbor_divs = None
        self.neighbors = None

        self.delaunay_process = None
        self.relax_processes = []

        self.alpha = Value('f', 0.1, lock=True)
        self.beta = Value('f', 0.04, lock=True)

    def init_processes(self, buffer_size):
        self._buffer_size = buffer_size
        if self.points:
            del self.points
        if self.points_relaxed:
            del self.points_relaxed
        if self.points_io:
            del self.points_io
        if self.neighbor_divs:
            del self.neighbor_divs
        if self.neighbors:
            del self.neighbors

        n_neighbors = self.neighors_array_buffer_multiplier * buffer_size
        self.points = Array(Vector2, buffer_size, lock=False)
        self.points_relaxed = Array(Vector2, buffer_size, lock=False)
        self.points_io = Array(Vector2, buffer_size, lock=True)
        self.neighbor_divs = Array(c_long, buffer_size + 1, lock=False)
        self.neighbors = Array(c_long, n_neighbors, lock=False)


        args_common = (self.cancellation, self.relax_var,
                       self.relax_completed_var, self.n_points,
                       self.points, self.points_relaxed,
                       self.neighbor_divs, self.neighbors)
        d_args = (self.n_relaxation_workers, self.points_io,
                  self.points_io_var) + args_common
        r_args_suffix = (self.n_relaxation_workers, self.alpha, self.beta) + \
                        args_common

        self.delaunay_process = Process(target=delaunay_loop, args=d_args)
        self.relax_processes = [
            Process(target=relax_points_loop, args=(i,) + r_args_suffix)
            for i in range(self.n_relaxation_workers)]

    def set_points(self, points):
        with self.points_io.get_lock():
            n_points = len(points)
            for idx in range(n_points):
                p = points[idx]
                # Dithering prevents issues with Delaunay calculation
                r = 0.00001 * np.random.rand(2)
                p = (p[0] + r[0], p[1] + r[1])
                self.points_io[idx] = tuple(p)
            self.n_points.value = n_points
            self.points_io_var.value = 1

    def get_points(self):
        with self.points_io.get_lock():
            return [tuple(self.points[i]) for i in
                    range(self.n_points.value)]

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
