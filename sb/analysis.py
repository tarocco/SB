from collections import deque

import numpy as np
from ekstrakto.helpers import peak_find_3d
from PIL.Image import Image as PILImage
from sklearn.decomposition import IncrementalPCA


class Analysis:
    def __init__(self, mean, contrast, *args, **kwargs):
        self.mean = mean
        self.contrast = contrast
        self.colors = kwargs.get('colors', [])

    def get_data(self):
        return [self.mean, self.contrast, *self.colors[:3].flatten()]

    def __repr__(self):
        return f'<Analysis mean = {self.mean}, contrast = {self.contrast}>'


def get_basic_analysis(array):
    flat = array.flatten()
    mean = np.sum(flat) / flat.size
    contrast = np.sum(np.abs(flat - mean)) / flat.size
    return Analysis(mean, contrast)


def extend_analysis(array, analysis):
    # Calculate dominant colors
    colors, _ = peak_find_3d(array, 7, 2.0)
    n_colors = 3
    if colors.shape[0] < n_colors:
        fill = np.repeat([colors[-1]], n_colors - colors.shape[0], axis=0)
        colors = np.concatenate((colors, fill), 0)
    analysis.colors = colors


def get_2d_ipca():
    return IncrementalPCA(n_components=2)


def incremental_batch_fit_transform(ipca, data, chunk):
    ipca.partial_fit(chunk)
    return ipca.transform(data)


def process_nd_to_1d(array):
    # TODO
    return IncrementalPCA(n_components=1).fit_transform(array)[:, 0]
