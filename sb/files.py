import pathlib
from os import path, walk


def get_image_paths(parent_path):
    suffixes = {'png', 'jpg', 'gif', 'webp'}
    for root, dirs, files in walk(parent_path):
        for file in files:
            name, ext = path.splitext(file)
            if ext[1:].lower() in suffixes:
                yield pathlib.PurePath(root, file)


def get_abs_path(path):
    assert(isinstance(path, pathlib.PurePath))
    if path.is_absolute():
        return path
    return pathlib.Path.cwd().joinpath(path)


def get_path_uri(path):
    assert (isinstance(path, pathlib.PurePath))
    return get_abs_path(path).as_uri()
