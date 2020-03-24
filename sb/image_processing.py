import pathlib
from os import path, walk

import io
import shutil

from PIL import Image as PILImageM
from PIL.Image import Image as PILImage

from multiprocessing import Process, Value, Queue
import numpy as np

from sb.analysis import *

def get_image_array(img):
    if isinstance(img, np.ndarray):
        array = img
    elif isinstance(img, PILImage):
        array = np.concatenate(np.array(img)) / 255.0
    else:
        raise ValueError("img must be a supported type")

    # Add channel dimension
    if len(array.shape) < 2:
        array = array[..., None]
    # Remove extra channels
    if array.shape[1] > 3:
        array = array[..., :3]
    # Replace missing channels
    elif array.shape[1] < 3:  # TODO
        fill = np.tile(array[..., -1, None], 3 - array.shape[1])
        array = np.concatenate((array, fill), 1)

    return array


def prepare_thumbnails(image_paths, thumbnails_path):
    if not image_paths:
        return
    if isinstance(thumbnails_path, str):
        thumbnails_path = pathlib.Path(thumbnails_path)
    for image_path in image_paths:
        assert(isinstance(image_path, pathlib.PurePath))
        title, ext = path.splitext(image_path.name)
        thumbnail_name = 'thumbnail-' + title + '.png'
        thumbnail_path = thumbnails_path.joinpath(thumbnail_name)
        if thumbnail_path.exists():
            # Load thumbnail image
            with open(thumbnail_path, 'rb') as thumbnail_file:
                thumbnail_io = io.BytesIO(thumbnail_file.read())
            thumbnail_io.seek(0)
            img = PILImageM.open(thumbnail_io)
            thumbnail_io.seek(0)
        else:
            # Generate thumbnail image
            try:
                img = PILImageM.open(str(image_path))
            except Exception as ex:
                print("Warning: could not open file", image_path)
                print(ex)
                continue
            assert(isinstance(img, PILImage))
            try:
                img.thumbnail((64, 64))
            except OSError:
                print("Warning: could not create thumbnail image for",
                      image_path)
                continue
            thumbnail_io = io.BytesIO()
            try:
                img.save(thumbnail_io, 'PNG')
            except:
                print('BAD FILE:', image_path)
                raise
            thumbnail_io.seek(0)
            # Caching handled by Kivy
            with open(thumbnail_path, 'wb') as thumbnail_file:
                shutil.copyfileobj(thumbnail_io, thumbnail_file)
            thumbnail_io.seek(0)
        yield thumbnail_path, thumbnail_io, img


def get_thumbnail_image(file_name):
    pass

# N workers
def producer_1(cancellation,
               file_path_queue,
               img_array_queue,
               analysis_queue,
               extended_analysis_queue):
    while not file_path_queue.empty() and not cancellation:
        index, file_name = file_path_queue.get()
        thumbnail_image = get_thumbnail_image(file_name)
        image_array = get_image_array(thumbnail_image)
        img_array_queue.put((index, image_array))
        analysis = get_basic_analysis(image_array)
        analysis_queue.put((index, analysis))
        extend_analysis(analysis)
        extended_analysis_queue.put((index, analysis))

# 1 worker only!!!
def producer_2(cancellation,
               extended_analysis_queue,
               results_queue,
               n_total,
               chunk_size):
    ipca = get_2d_ipca()
    counter = 0
    complete = False
    while not complete and not cancellation:
        n_pending = len(extended_analysis_queue)
        complete = counter + n_pending >= n_total
        chunk_ready = n_pending >= chunk_size
        if chunk_ready or complete:
            chunk = []
            for _ in range(min(n_pending, chunk_size)):
                chunk.append(extended_analysis_queue.get())
            indices, analyses = zip(*chunk)
            results = incremental_batch_fit_transform(ipca, analyses)
            for r in zip(indices, results):
                results_queue.put(r)


class ImageProcessor:
    def __init__(self):
        self.cancellation = Value('i', 0, lock=True)
        self.n_total = Value('i', 0, lock=True)
        self.file_path_queue = Queue()
        self.img_array_queue = Queue()
        self.analysis_queue = Queue()
        self.extended_analysis_queue = Queue()
        self.results_queue = Queue()

        self.producer_1s = []
        self.producer_2 = None

    def init_processes(self, n_workers=4, p2_chunk_size=16):
        p1_args = (self.cancellation, self.file_path_queue, self.img_array_queue, self.analysis_queue, self.extended_analysis_queue)
        p2_args = (self.cancellation, self.extended_analysis_queue, self.results_queue, self.n_total, p2_chunk_size)

        self.producer_1s = [Process(target=producer_1, args=p1_args)
                            for _ in range(n_workers)]
        self.producer_2 = Process(target=producer_1, args=p2_args)

    def start_all(self, file_paths):
        for index, file_path in enumerate(file_paths):
            self.file_path_queue.put((index, file_path))
        with self.n_total.get_lock():
            self.n_total.value = len(file_paths)
        for p1 in self.producer_1s:
            p1.start()
        self.producer_2.start()

    def stop_all(self):
        with self.cancellation.get_lock():
            self.cancellation.value = 1

        with self.cancellation.get_lock():
            self.cancellation.value = 0

