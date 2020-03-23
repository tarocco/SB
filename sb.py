import multiprocessing
import pathlib
from itertools import islice
import json
from argparse import ArgumentParser

if __name__ == '__main__':

    from kivy.app import App
    from kivy.uix.image import CoreImage
    from kivy.uix.popup import Popup

    from sb import analysis
    from sb.analysis import Analysis
    from sb.files import get_image_paths
    from sb.image_processing import prepare_thumbnails
    from sb.sbmetadata import SBMetadata
    from sb.sbcontroller import SBController

    from sb.uix import LoadDirectoryDialog

    # Kv imports
    from sb.sbview import SBView
    from sb.sbscatter import SBScatter
    from sb.sbcanvas import SBCanvas

    MAX_IMAGES = 3000

    class SBApp(App):
        def __init__(self):
            super(SBApp, self).__init__()
            self._images_dir_path = None
            self._thumbnails_dir_path = None
            self._popup = None
            self.controller = None

        def on_start(self):
            # Set up controller
            main_view = self.root.ids.main_view
            print(main_view.size)
            sb_canvas = main_view.ids.sb_canvas
            controller = SBController(sb_canvas)
            controller.on_app_start()
            self.controller = controller
            self.load_directory(self._images_dir_path, self._thumbnails_dir_path)

        def dismiss_popup(self):
            self._popup.dismiss()
            self._popup = None

        def on_choose_directory(self):
            self.open_choose_directory()

        def on_load_directory(self, parent, selection):
            directory = selection[0]
            self.load_directory(directory, self._thumbnails_dir_path)

        def on_cancel_load_directory(self):
            self.dismiss_popup()

        def open_choose_directory(self):
            if self._popup:
                self.dismiss_popup()
            content = LoadDirectoryDialog(
                load=self.on_load_directory,
                cancel=self.on_cancel_load_directory)
            self._popup = Popup(
                title='Load directory',
                content=content,
                size_hint=(0.9, 0.9)
            )
            self._popup.open()

        def load_directory(self, dir_path, thumbnails_dir_path):
            self._images_dir_path = dir_path
            self._thumbnails_dir_path = thumbnails_dir_path

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

            for img, p, a in zip(imgs, points, analyses):
                self.controller.add_node(img, p, a)

        def on_stop(self):
            self.controller.on_app_stop()

        def export_1d(self):
            transforms = self.controller.get_root_transforms()
            anchors = self.controller.get_target_anchors()
            values = analysis.process_nd_to_1d(anchors)
            metadata_components = [t.get_object().get_component(SBMetadata) for t in transforms]
            metadata = [m.value['image-filename'] for m in metadata_components]
            data = {m: v for m, v in zip(metadata, values)}
            print(json.dumps(data))

    def main():
        parser = ArgumentParser()
        parser.add_argument('--images', type=str)
        parser.add_argument('--thumbnail-images', type=str)
        args = parser.parse_args()

        images_path = args.images
        thumbnails_path = args.thumbnail_images

        app = SBApp()

        if images_path:
            # TODO
            app._images_dir_path = images_path
            app._thumbnails_dir_path = thumbnails_path

        app.run()

    multiprocessing.freeze_support()
    main()
