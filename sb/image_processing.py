import pathlib
from os import path, walk

import io
import shutil

from PIL import Image as PILImageM
from PIL.Image import Image as PILImage


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
