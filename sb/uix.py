import json
import pathlib
from itertools import islice
from os import path

from kivy.properties import ObjectProperty
from kivy.uix.floatlayout import FloatLayout

from kivy.uix.image import CoreImage
from kivy.uix.popup import Popup

from sb import analysis
from sb.analysis import Analysis
from sb.files import get_image_paths
from sb.image_processing import prepare_thumbnails
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

    def dismiss_popup(self):
        self.popup.dismiss()
        self.popup = None

    def open_directory_chooser(self):
        if self.popup:
            self.dismiss_popup()
        content = LoadDirectoryDialog(
            choose=self.load_directory,
            cancel=self.cancel_choose_directory)
        self.popup = Popup(
            title='Choose directory',
            content=content,
            size_hint=(0.9, 0.9)
        )
        self.popup.open()

    def on_start(self):
        # Set up controller
        sb_view = self.ids.sb_view
        sb_canvas = sb_view.ids.sb_canvas
        controller = SBController(sb_canvas)
        controller.on_app_start()
        self.controller = controller

    def cancel_choose_directory(self):
        self.dismiss_popup()

    def load_directory(self, dir_path, thumbnails_dir_path=None):
        self.images_dir_path = dir_path
        if thumbnails_dir_path:
            self.thumbnails_dir_path = thumbnails_dir_path
        else:
            thumbnails_dir_path = self.thumbnails_dir_path

        # Create thumbnail images (cache)
        thumbnails_dir_path = pathlib.Path(thumbnails_dir_path)
        thumbnails_dir_path.mkdir(parents=True, exist_ok=True)
        thumbnails = list(prepare_thumbnails(
            islice(get_image_paths(dir_path), 0, MAX_IMAGES),
            thumbnails_dir_path))

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

    def on_stop(self):
        self.controller.on_app_stop()

    def export_1d(self):
        transforms = self.controller.get_root_transforms()
        anchors = self.controller.get_target_anchors()
        values = analysis.process_nd_to_1d(anchors)
        metadata_components = [t.get_object().get_component(SBMetadata) for t
                               in transforms]
        metadata = [m.value['image-filename'] for m in metadata_components]
        data = {m: v for m, v in zip(metadata, values)}
        print(json.dumps(data))

