import json
import pathlib
from itertools import islice
from os import path

from kivy.properties import ObjectProperty
from kivy.uix.floatlayout import FloatLayout

from kivy.uix.image import CoreImage
from kivy.uix.popup import Popup

from kivy.clock import Clock

from sb import analysis
from sb.analysis import Analysis
from sb.files import get_image_paths
from sb.image_metadata import ImageMetadata
from sb.image import Image as SBImage
from sb.image_processing import ImageProcessor
from sb.sbmetadata import SBMetadata
from sb.sbcontroller import SBController

MAX_IMAGES = 3000


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
        self.nodes = []

    def on_start(self):
        # Set up controller
        sb_view = self.ids.sb_view
        sb_canvas = sb_view.ids.sb_canvas
        controller = SBController(sb_canvas)
        controller.on_app_start()
        self.controller = controller
        Clock.schedule_interval(self.update, 1 / 60)

    def image_load_update(self, dt):
        if self.image_processor:
            assert(isinstance(self.image_processor, ImageProcessor))
            for index, img_array in self.image_processor.img_array_queue:
                node = self.nodes[index]

                # Add image component
                sb_img = node.add_component(SBImage)

                # TODO
                #sb_img.texture = img.texture
                #sb_img.transform.width, sb_img.transform.height = \
                #    tuple(0.1 * i for i in img.size)
            for index, analysis in self.image_processor.analysis_queue:
                node = self.nodes[index]
                md = node.get_component(ImageMetadata)
                # TODO: set target anchors
                md.analysis = analysis

            for index, ea in self.image_processor.extended_analysis_queue:
                node = self.nodes[index]
                md = node.get_component(ImageMetadata)
                md.analysis = ea

            for index, result in self.image_processor.results_queue:
                node = self.nodes[index]
                # TODO: set target anchors


    def on_stop(self):
        self.controller.on_app_stop()

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
        image_processor = ImageProcessor()
        image_processor.init_processes()
        self.image_processor = image_processor
        self.images_dir_path = dir_path
        if thumbnails_dir_path:
            self.thumbnails_dir_path = thumbnails_dir_path
        else:
            thumbnails_dir_path = self.thumbnails_dir_path

        thumbnails_dir_path = pathlib.Path(thumbnails_dir_path)
        thumbnails_dir_path.mkdir(parents=True, exist_ok=True)
        file_paths = get_image_paths(dir_path)

        self.nodes = [self.controller.add_node()
                      for _ in range(len(file_paths))]

        for node, file_path in zip(self.nodes, file_paths):
            sb_md = node.add_component(SBMetadata)
            sb_md.value = ImageMetadata(thumbnail_file_path=file_path)

        image_processor.start_all(file_paths)

        """

        thumbnail_paths, thumbnail_ios, thumbnail_images = zip(*thumbnails)

        analyses = list(map(Analysis.process_image, thumbnail_images))

        # Calculate points
        points = analysis.process_batch_analysis_to_2d(analyses)
        points = 0.8 * points + 0.5

        # Reset stream positions after generating analyses (PIL affects it)
        for thumb_io in thumbnail_ios:
            thumb_io.seek(0)

        imgs = [CoreImage(thumb_io, ext='png', filename=str(thumb_path))
                for thumb_io, thumb_path in
                zip(thumbnail_ios, thumbnail_paths)]

        # Free some memory
        del thumbnail_images

        # Clear controller nodes
        self.controller.clear_nodes()
        # Add nodes to controller
        for img, p, a in zip(imgs, points, analyses):
            self.controller.add_node(img, p, a)
        """

    def export_1d(self):
        transforms = self.controller.get_root_transforms()
        anchors = self.controller.get_target_anchors()
        values = analysis.process_nd_to_1d(anchors)
        metadata_components = [t.get_object().get_component(SBMetadata) for t
                               in transforms]
        metadata = [m.value['image-filename'] for m in metadata_components]
        data = {m: v for m, v in zip(metadata, values)}
        print(json.dumps(data))

