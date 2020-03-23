class ImageMetadata:
    def __init__(self, *args, **kwargs):
        self.file_path = kwargs.get('file_path', None)
        self.thumbnail_file_path = kwargs.get('thumbnail_file_path', None)
        self.analysis = kwargs.get('analysis', None)
