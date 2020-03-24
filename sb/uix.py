import json
import pathlib
from os import path
from queue import Empty

import numpy as np

from kivy.properties import ObjectProperty
from kivy.uix.floatlayout import FloatLayout

from kivy.core.image import Texture
from kivy.uix.popup import Popup

from kivy.clock import Clock

from sb import analysis
from sb.files import get_image_paths
from sb.image_metadata import ImageMetadata
from sb.image import Image as SBImage
from sb.image_processing import ImageProcessor
from sb.sbmetadata import SBMetadata
from sb.sbcontroller import SBController


MAX_IMAGES = 3000

def get_texture_from_array(array):
    h, w, _ = array.shape
    texture = Texture.create(size=(w, h))
    texture.blit_buffer(np.flip(array, 0).flatten(), colorfmt='rgb', bufferfmt='float')
    return texture


class LoadDirectoryDialog(FloatLayout):
    choose = ObjectProperty(None)
    cancel = ObjectProperty(None)

    def is_dir(self, directory, filename):
        return path.isdir(path.join(directory, filename))


class RootView(FloatLayout):
    def __init__(self, *args, **kwargs):
        super(RootView, self).__init__(*args, **kwargs)
        self.controller = None
        self.popup = None
        self.images_dir_path = None
        self.thumbnails_dir_path = None
        self.image_processor = None
        self.nodes = {}
        self.update_batch_size = 400

    def on_start(self):
        # Set up controller
        sb_view = self.ids.sb_view
        sb_canvas = sb_view.ids.sb_canvas
        controller = SBController(sb_canvas)
        controller.pr_alpha = 0.0
        controller.pr_beta = 0.04
        controller.on_app_start()
        self.controller = controller
        Clock.schedule_interval(self.image_loader_update, 1 / 60)

    def image_loader_update(self, dt):
        if self.image_processor:
            assert(isinstance(self.image_processor, ImageProcessor))
            for _ in range(self.update_batch_size):
                try:
                    node_id, img_array = self.image_processor.img_array_queue.get_nowait()
                except Empty:
                    break
                node = self.nodes[node_id]
                self.controller.pr_alpha = 0.0
                # Add image component
                sb_img = node.add_component(SBImage)

                # TODO
                texture = get_texture_from_array(img_array)
                sb_img.texture = texture
                sb_img.transform.width, sb_img.transform.height = \
                    tuple(0.1 * i for i in texture.size)

            node_ids = []
            anchors = []

            for _ in range(self.update_batch_size):
                try:
                    node_id, analysis = self.image_processor.analysis_queue.get_nowait()
                except Empty:
                    break
                node = self.nodes[node_id]
                md = node.add_component(ImageMetadata)
                md.analysis = analysis
                anchor = (analysis.mean, analysis.contrast)
                node_ids.append(node_id)
                anchors.append(anchor)
            if node_ids:
                self.controller.set_node_target_anchors(node_ids, anchors)

            node_ids = []
            anchors = []
            if self.image_processor.results_queue.empty():
                self.controller.pr_alpha = 0.2

            for _ in range(self.update_batch_size):
                try:
                    node_id, result = self.image_processor.results_queue.get_nowait()
                except Empty:
                    break
                anchor = result
                node_ids.append(node_id)
                anchors.append(anchor)
            if node_ids:
                self.controller.set_node_target_anchors(node_ids, anchors)

    def on_stop(self):
        self.controller.on_app_stop()
        self.image_processor.stop_all()

    def dismiss_popup(self):
        self.popup.dismiss()
        self.popup = None

    def open_directory_chooser(self):
        if self.popup:
            self.dismiss_popup()
        content = LoadDirectoryDialog(
            choose=self.choose_directory,
            cancel=self.cancel_choose_directory)
        self.popup = Popup(
            title='Choose directory',
            content=content,
            size_hint=(0.9, 0.9)
        )
        self.popup.open()

    def choose_directory(self, dir_path, thumbnails_dir_path=None):
        self.dismiss_popup()
        self.load_directory(dir_path, thumbnails_dir_path)

    def cancel_choose_directory(self):
        self.dismiss_popup()

    def load_directory(self, dir_path, thumbnails_dir_path=None):
        if self.image_processor:
            self.image_processor.stop_all()

        self.images_dir_path = dir_path
        if thumbnails_dir_path:
            self.thumbnails_dir_path = thumbnails_dir_path
        else:
            thumbnails_dir_path = self.thumbnails_dir_path

        thumbnails_dir_path = pathlib.Path(thumbnails_dir_path)
        image_processor = ImageProcessor()
        image_processor.init_processes(str(thumbnails_dir_path), n_workers=8)
        self.image_processor = image_processor

        thumbnails_dir_path.mkdir(parents=True, exist_ok=True)
        file_paths = list(get_image_paths(dir_path))

        nodes = [self.controller.add_node() for _ in range(len(file_paths))]

        self.nodes = {id(n): n for n in nodes}

        for node, file_path in zip(nodes, file_paths):
            sb_md = node.add_component(SBMetadata)
            sb_md.value = ImageMetadata(thumbnail_file_path=file_path)

        image_processor.start_all(list(zip(self.nodes.keys(), file_paths)))

    def export_1d(self):
        transforms = self.controller.get_root_transforms()
        anchors = self.controller.get_target_anchors()
        values = analysis.process_nd_to_1d(anchors)
        metadata_components = [t.get_object().get_component(SBMetadata) for t
                               in transforms]
        metadata = [m.value['image-filename'] for m in metadata_components]
        data = {m: v for m, v in zip(metadata, values)}
        print(json.dumps(data))

