import pathlib
from os import path
from queue import Empty
from time import sleep

from PIL import Image as PILImageM
from PIL.Image import Image as PILImage

from multiprocessing import Process, Value, Queue
import numpy as np

from sb.analysis import \
    get_basic_analysis, \
    extend_analysis, \
    incremental_batch_fit_transform,\
    get_2d_ipca
from sb.utilities import flush_queue


def get_image_array(img):
    if isinstance(img, np.ndarray):
        array = img.astype('float32')
    elif isinstance(img, PILImage):
        array = np.array(img, dtype='float32') / 255.0
    else:
        raise ValueError("Image must be a supported type")
    # Add channel dimension
    if len(array.shape) < 3:
        array = array[..., None]
    # Remove extra channels
    if array.shape[2] > 3:
        array = array[..., :3]
    # Replace missing channels
    elif array.shape[2] < 3:  # TODO
        repeats = 3 - array.shape[2]
        padding = array[:, :, -1, None]
        array = np.concatenate((array,) + (padding,) * repeats, axis=2)
    return array


def get_thumbnail_image(image_file_path, thumbnails_directory_path):
    if isinstance(image_file_path, str):
        image_file_path = pathlib.Path(image_file_path)
    if isinstance(thumbnails_directory_path, str):
        thumbnails_directory_path = pathlib.Path(thumbnails_directory_path)
    title, ext = path.splitext(image_file_path.name)
    thumbnail_name = 'thumbnail-' + title + '.png'  # TODO
    thumbnail_path = thumbnails_directory_path.joinpath(thumbnail_name)
    if thumbnail_path.exists():
        # Load existing thumbnail image
        thumbnail_img = PILImageM.open(thumbnail_path)
    else:
        # Generate the thumbnail image
        try:
            img = PILImageM.open(str(image_file_path))
        except:
            print("Warning: could not open image file", image_file_path)
            return None
        assert(isinstance(img, PILImage))
        try:
            img.thumbnail((64, 64))
        except:
            print("Warning: could not create thumbnail image for image",
                  image_file_path)
            return None
        thumbnail_img = img
        thumbnail_img.save(thumbnail_path)
    return thumbnail_img


# N workers
def producer_1(cancellation,
               file_path_queue,
               img_array_queue,
               analysis_queue,
               extended_analysis_queue,
               n_total,
               thumbnails_dir_path):
    while not cancellation.value:
        try:
            node_id, file_name = file_path_queue.get(False)
        except Empty:
            sleep(0.1)
            continue
        thumbnail_image = get_thumbnail_image(file_name, thumbnails_dir_path)
        if thumbnail_image:
            image_array = get_image_array(thumbnail_image)
            img_array_queue.put((node_id, image_array))
            analysis = get_basic_analysis(image_array)
            analysis_queue.put((node_id, analysis))

            # "Flatten" the image array
            array_pixels_shape = (image_array.shape[0] * image_array.shape[1],
                                  *image_array.shape[2:])
            array_pixels = np.reshape(image_array, array_pixels_shape)

            extend_analysis(array_pixels, analysis)
            extended_analysis_queue.put((node_id, analysis))
        else:
            # Kind of hacky but this should work just fine
            with n_total.get_lock():
                n_total.value -= 1

    # Flush the queues
    flush_queue(file_path_queue)
    flush_queue(img_array_queue)
    flush_queue(analysis_queue)
    flush_queue(extended_analysis_queue)

# 1 worker only!!!
def producer_2(cancellation,
               extended_analysis_queue,
               results_queue,
               n_total,
               chunk_size):
    ipca = get_2d_ipca()
    counter = 0
    complete = False

    prior_node_ids = []
    prior_data = []

    while not cancellation.value:
        n_pending = extended_analysis_queue.qsize()
        with n_total.get_lock():
            complete = counter + n_pending >= n_total.value
        chunk_ready = n_pending >= chunk_size
        # Finish up the rest of the queue
        if chunk_ready or complete:
            chunk = []
            for _ in range(chunk_size):
                try:
                    index, analysis = extended_analysis_queue.get(False)
                except Empty:
                    sleep(0.1)
                    break
                e = (index, analysis.get_data())
                chunk.append(e)
                counter += 1
            if chunk:
                node_ids, chunk_data = zip(*chunk)
                prior_node_ids.extend(node_ids)
                prior_data.extend(chunk_data)
                results = incremental_batch_fit_transform(
                    ipca, prior_data, chunk_data)
                for r in zip(prior_node_ids, results):
                    results_queue.put(r)
    # Flush the queues
    flush_queue(extended_analysis_queue)
    flush_queue(results_queue)

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

    def init_processes(self, thumbnails_dir_path, n_workers=4, p2_chunk_size=16):
        p1_args = (self.cancellation, self.file_path_queue, self.img_array_queue, self.analysis_queue, self.extended_analysis_queue, self.n_total, thumbnails_dir_path)
        p2_args = (self.cancellation, self.extended_analysis_queue, self.results_queue, self.n_total, p2_chunk_size)

        self.producer_1s = [Process(target=producer_1, args=p1_args)
                            for _ in range(n_workers)]
        self.producer_2 = Process(target=producer_2, args=p2_args)

    def start_all(self, file_paths):
        for node_id, file_path in file_paths:
            self.file_path_queue.put((node_id, file_path))
        with self.n_total.get_lock():
            self.n_total.value = len(file_paths)
        for p1 in self.producer_1s:
            p1.start()
        self.producer_2.start()

    def stop_all(self):
        with self.cancellation.get_lock():
            self.cancellation.value = 1

        for p1 in self.producer_1s:
            p1.join()
        #print('joined p1s')
        self.producer_2.join()
        #print('joined p2')

        #with self.cancellation.get_lock():
        #    self.cancellation.value = 0

