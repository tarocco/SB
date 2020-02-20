import numpy as np
from iteration_utilities import grouper
from scipy.spatial import Delaunay
from math import exp, log
from .math import soft_minimum
from multiprocessing import Process, Value, Array
from ctypes import Structure, c_long, c_float
import time


class Vector2(Structure):
    _fields_ = [('x', c_float), ('y', c_float)]

    def __getitem__(self, i):
        if i == 0:
            return self.x
        if i == 1:
            return self.y
        return super(Vector2, self).__getitem__(i)


def spin(cycles):
    end = time.clock()
    while time.clock() < end:
        continue


def batch_delaunay_relax_points(delaunay, alpha, beta, batch_size=None):
    def find_neighbors(point_index, delaunay):
        neighbor_divisions, neighbors = delaunay.vertex_neighbor_vertices
        a = neighbor_divisions[point_index]
        b = neighbor_divisions[point_index + 1]
        return neighbors[a:b]

    indices = range(len(delaunay.points))

    if batch_size:
        groups = grouper(indices, batch_size)
    else:
        groups = [indices]

    for batch_indices in groups:
        batch_points_relaxed = np.empty(
            (len(batch_indices), delaunay.points.shape[1]))
        for i, idx in enumerate(batch_indices):
            p = delaunay.points[idx]
            neighbors = delaunay.points[find_neighbors(idx, delaunay)]
            delta = np.zeros_like(p)
            for neighbor in neighbors:
                n = neighbor - p
                n_norm = np.linalg.norm(n)
                n = n / (n_norm + 0.0001)
                s = n_norm - beta
                s = soft_minimum(0, s) + log(2)
                delta = delta + alpha * s * n
            batch_points_relaxed[i] = p + delta
        yield batch_indices, batch_points_relaxed


def delaunay_relax_points(
        indices, points, neighbor_divs, neighbors,
        alpha, beta):

    def get_neighbors(point_index):
        a = neighbor_divs[point_index]
        b = neighbor_divs[point_index + 1]
        return neighbors[a:b]

    points_out = []

    for idx in indices:
        p = np.frombuffer(points[idx]).view('<f4')
        neighbors = [points[i] for i in get_neighbors(idx)]
        delta = np.zeros_like(p)
        for neighbor in neighbors:
            n = np.frombuffer(neighbor).view('<f4') - p
            n_norm = np.linalg.norm(n)
            n = n / (n_norm + 0.0001)
            s = n_norm - beta
            s = soft_minimum(0, s) + log(2)
            delta = delta + alpha * s * n
        points_out.append(p + delta)
    return points_out


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
                spin(1000)

                with points_write_var.get_lock():
                    points_write_var.value = 1
                    # Calculate Delaunay
                    array = np.frombuffer(
                        points.get_obj(),
                        dtype=Vector2,
                        count=n_points.value)
                    array = array.view('<f4').reshape(-1, 2)
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
                spin(1000)
                continue
        points_indices = range(offset, n_points.value, stride)
        relaxed = delaunay_relax_points(
            points_indices, points, neighbor_divs, neighbors,
            0.1, 0.08)
        with points_out.get_lock():
            for idx, p in zip(points_indices, relaxed):
                points_out[idx] = tuple(p)
        with relax_completed_var.get_lock():
            relax_completed_var.value = relax_completed_var.value - 1


class PointRelaxer():
    def __init__(self):
        self.n_relaxation_workers = 1
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
        while True:
            with self.relax_completed_var.get_lock():
                if self.relax_completed_var.value == 0:
                    return [self.points[i] for i in range(self.n_points.value)]
                spin(1000)
                continue

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

