
import multiprocessing

if __name__ == '__main__':
    import pathlib
    from itertools import islice
    from argparse import ArgumentParser
    from kivy.app import App
    from kivy.uix.image import Image as kImage, CoreImage
    from sb.analysis import Analysis, process_batch_analysis_to_2d
    from sb.files import get_image_paths
    from sb.images import prepare_thumbnails
    from sb.uix import SBView

    MAX_IMAGES = 100

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
            kimages = [kImage() for _ in range(n_images)]
            for kimg, img, c in zip(kimages, self.images, self.coordinates):
                kimg.texture = img.texture
                kimg.size_hint = (None, None)
                kimg.size = tuple(0.2 * i for i in kimg.texture_size)
                view.add_widget(kimg)

            scatter.set_widget_pos_hints(scatter.get_widgets(), self.coordinates)
            scatter.set_cached_widget_pos_hints(range(n_images), self.coordinates)
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
        points = 0.7 * points + 0.5

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

if __name__ == '__main__':
    #multiprocessing.freeze_support()
    main()
