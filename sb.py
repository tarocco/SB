
import multiprocessing

if __name__ == '__main__':
    import pathlib
    from itertools import islice
    from argparse import ArgumentParser
    from kivy.config import Config
    Config.set('graphics', 'maxfps', 240)
    Config.set('kivy', 'kivy_clock', 'interrupt')
    Config.set('kivy', 'log_level', 'info')
    Config.write()
    from kivy.app import App
    from kivy.uix.image import CoreImage
    from sb.analysis import Analysis, process_batch_analysis_to_2d
    from sb.files import get_image_paths
    from sb.images import prepare_thumbnails
    from sb.sbview import SBView
    from sb.sbobject import SBObject
    from sb.sbcanvas import Image as SBImage

    MAX_IMAGES = 3000

    class SBApp(App):
        def __init__(self):
            super(SBApp, self).__init__()
            self.images = []
            self.coordinates = []

        def on_start(self):
            view = self.root.ids.scatter_view
            assert(isinstance(view, SBView))
            scatter = view.scatter
            n_images = len(self.images)
            objects = [SBObject() for _ in range(n_images)]
            for o, img, c in zip(objects, self.images, self.coordinates):
                sb_img = o.add_component(SBImage)
                sb_img.texture = img.texture
                sb_img.transform.width, sb_img.transform.height = \
                    tuple(0.1 * i for i in img.size)
                scatter.add_root_transform(sb_img.transform)

            scatter.set_target_anchors(self.coordinates)
            view.size = view.parent.size
            view.scatter.size = view.size


    def main():
        parser = ArgumentParser()
        parser.add_argument('--images', type=str)
        parser.add_argument('--thumbnail-images', type=str)
        args = parser.parse_args()

        thumbnails_path = pathlib.Path(args.thumbnail_images)
        thumbnails_path.mkdir(parents=True, exist_ok=True)
        thumbnails = list(prepare_thumbnails(
            islice(get_image_paths(args.images), 0, MAX_IMAGES),
            thumbnails_path))

        thumbnail_paths, thumbnail_ios, thumbnail_images = zip(*thumbnails)

        analyses = list(map(Analysis.process_image, thumbnail_images))
        points = process_batch_analysis_to_2d(analyses)
        points = 0.8 * points + 0.5

        # Reset stream positions after generating analyses (PIL affects it)
        for thumb_io in thumbnail_ios:
            thumb_io.seek(0)

        imgs = [CoreImage(thumb_io, ext='png', filename=str(thumb_path))
                 for thumb_io, thumb_path in zip(thumbnail_ios, thumbnail_paths)]

        # Free some memory
        del thumbnail_images

        app = SBApp()
        app.images = imgs
        app.coordinates = points
        app.run()

    multiprocessing.freeze_support()
    main()
