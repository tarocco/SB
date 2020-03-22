
import multiprocessing

if __name__ == '__main__':
    import pathlib
    from itertools import islice
    import json
    from argparse import ArgumentParser
    from kivy.app import App
    from kivy.uix.image import CoreImage
    from sb import analysis
    from sb.analysis import Analysis
    from sb.files import get_image_paths
    from sb.image_processing import prepare_thumbnails
    from sb.sbview import SBView
    from sb.sbobject import SBObject
    from sb.image import Image as SBImage
    from sb.sbmetadata import SBMetadata
    from sb.sbcontroller import SBController
    import sb.uix

    MAX_IMAGES = 3000

    class SBApp(App):
        def __init__(self):
            super(SBApp, self).__init__()
            self.images = []
            self.coordinates = []
            self.controller = None

        def on_start(self):
            view = self.root.ids.main_view
            assert(isinstance(view, SBView))
            scatter = view.scatter
            sb_canvas = scatter.inner_content

            controller = SBController(sb_canvas)
            controller.on_app_start()
            self.controller = controller

            # TODO
            n_images = len(self.images)
            objects = [SBObject() for _ in range(n_images)]
            for o, img in zip(objects, self.images):
                assert(isinstance(img, CoreImage))
                sb_img = o.add_component(SBImage)
                sb_img.texture = img.texture
                sb_img.transform.width, sb_img.transform.height = \
                    tuple(0.1 * i for i in img.size)
                sb_md = o.add_component(SBMetadata)
                sb_md.value = { 'image-filename': img.filename }
                sb_canvas.add_root_transform(sb_img.transform)

            # Controller sets all transform positions
            controller.set_target_anchors(self.coordinates)

            view.size = view.parent.size
            view.scatter.size = view.size

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

        thumbnails_path = pathlib.Path(args.thumbnail_images)
        thumbnails_path.mkdir(parents=True, exist_ok=True)
        thumbnails = list(prepare_thumbnails(
            islice(get_image_paths(args.images), 0, MAX_IMAGES),
            thumbnails_path))

        thumbnail_paths, thumbnail_ios, thumbnail_images = zip(*thumbnails)

        analyses = list(map(Analysis.process_image, thumbnail_images))
        points = analysis.process_batch_analysis_to_2d(analyses)
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
