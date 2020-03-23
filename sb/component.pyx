cdef class Component:
    def __init__(self, _object):
        self._object = _object
        self._transform = _object.transform

    @property
    def transform(self):
        return self._transform

    def get_object(self):
        return self._object

    def update(self, dt):
        pass

    def destroy(self):
        self._object.remove_component(self)
