import multiprocessing
from argparse import ArgumentParser

if __name__ == '__main__':

    from kivy.app import App

    # Kv imports
    from sb.sbview import SBView
    from sb.sbscatter import SBScatter
    from sb.sbcanvas import SBCanvas
    from sb.uix import RootView

    class SBApp(App):
        def __init__(self):
            super(SBApp, self).__init__()
            self.initial_images_dir_path = None
            self.initial_thumbnails_dir_path = None

        def on_start(self):
            root_view = self.root
            assert(isinstance(root_view, RootView))
            root_view.on_start()
            root_view.load_directory(
                self.initial_images_dir_path,
                self.initial_thumbnails_dir_path
            )

        def on_stop(self):
            root_view = self.root()
            assert (isinstance(root_view, RootView))
            root_view.on_stop()


    def main():
        parser = ArgumentParser()
        parser.add_argument('--images', type=str)
        parser.add_argument('--thumbnail-images', type=str)
        args = parser.parse_args()

        images_path = args.images
        thumbnails_path = args.thumbnail_images

        app = SBApp()

        if images_path:
            app.initial_images_dir_path = images_path
            app.initial_thumbnails_dir_path = thumbnails_path

        app.run()

    multiprocessing.freeze_support()
    main()
