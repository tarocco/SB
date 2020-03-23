#from sb.component import Component
from cython.parallel import prange
from sb.component cimport Component
import numpy as np

from libc.stdlib cimport malloc, free


def walk_transforms(transform):
    yield transform
    for t in transform.children:
        yield from walk_transforms(t)

def get_model_hierarchy(transform, index=0, parent_index=-1):
        next_index = index + len(transform.children) + 1
        yield transform, parent_index
        for t in transform.children:
            yield from get_model_hierarchy(t, next_index, index)


cdef inline float calculate_dimension(
        float parent_p,
        float parent_s,
        float anchor,
        float pivot,
        float s,
        float delta) nogil:
    return parent_p + anchor * parent_s + pivot * s + delta

cdef struct RectTransformModel:
    float x_delta, y_delta, width, height, x_anchor, y_anchor, x_pivot, y_pivot, x, y
    int x_is_set, y_is_set


cdef class RectTransform(Component):
    cdef RectTransformModel _model
    cdef public object _parent
    cdef public list _children
    cdef public float _x, _y
    cdef public int _x_is_set, _y_is_set
    cdef public list _descendants
    cdef public int[:] _descendant_hierarchy

    def __init__(self, _object, *args, **kwargs):
        self._object = _object
        self._transform = self

        self._model.x_delta = kwargs.get('x_delta', 0)
        self._model.y_delta = kwargs.get('y_delta', 0)
        self._model.width = kwargs.get('width', 100)
        self._model.height = kwargs.get('height', 100)
        self._model.x_anchor = kwargs.get('x_anchor', 0.0)
        self._model.y_anchor = kwargs.get('y_anchor', 0.0)
        self._model.x_pivot = kwargs.get('x_pivot', 0.5)
        self._model.y_pivot = kwargs.get('y_pivot', 0.5)

        self._parent = None
        self._children = list()
        self._model.x = 0
        self._model.y = 0
        self._model.x_is_set = 0
        self._model.y_is_set = 0
        self._descendants = None
        self._descendant_hierarchy = None

    def _clear_x(self):
        self._model.x_is_set = 0
        for child in self._children:
            child._clear_x()

    def _clear_y(self):
        self._model.y_is_set = 0
        for child in self._children:
            child._clear_y()

    def _clear_xy(self):
        self._model.x_is_set = 0
        self._model.y_is_set = 0
        for child in self._children:
            child._clear_xy()

    def path(self):
        transform = self
        while transform is not None:
            yield transform
            transform = transform.parent

    def _clear_ancestor_descendants(self):
        for xf in self.path():
            xf._clear_descendants()

    def _clear_descendants(self):
        self._descendants = None
        self._descendant_hierarchy = None

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, new_parent):
        assert(isinstance(new_parent, RectTransform))
        assert(new_parent != self)  # Cannot be own parent
        # If new_parent not (already) parent
        if new_parent is not self._parent:
            # If current parent is set
            if self._parent:
                # Remove this transform from parent
                self._parent._children.remove(self)
                # Clear descendants
                self._parent._clear_ancestor_descendants()
            if new_parent is not None:
                # If new parent is a descendant of this transform,
                # then rotate the new parent with this transform
                if self in new_parent.path():
                    # If the new parent has a parent
                    if new_parent.parent is not None:
                        new_parent._parent._children.remove(new_parent)
                        new_parent._parent._clear_ancestor_descendants()
                    # Set the new parent's parent to this transform's parent
                    new_parent._parent = self._parent
                    # If this transform's parent is not None (not root)
                    if self._parent is not None:
                        self._parent._children.append(new_parent)
                        self._parent._clear_ancestor_descendants()
                    new_parent._children.append(self)
                    new_parent._clear_ancestor_descendants()
                    new_parent._clear_xy()
                # If new parent is not a descendant of this transform
                else:
                    new_parent._children.append(self)
                    new_parent._clear_ancestor_descendants()
                    self._clear_xy()
            self._parent = new_parent

    @property
    def children(self):
        return [child for child in self._children]

    def _calculate_descendants_and_hierarchy(self):
        descendants, hierarchy = zip(*get_model_hierarchy(self))
        self._descendants = list(descendants)
        self._descendant_hierarchy = np.array(hierarchy, dtype='int')


    @property
    def descendants(self):
        if self._descendants is None:
            self._calculate_descendants_and_hierarchy()
        return self._descendants

    @property
    def descendant_hierarchy(self):
        if self._descendants is None:
            self._calculate_descendants_and_hierarchy()
        return self._descendant_hierarchy

    @property
    def x_delta(self): return self._model.x_delta

    @x_delta.setter
    def x_delta(self, value):
        self._model.x_delta = value
        self._clear_x()

    @property
    def y_delta(self): return self._model.y_delta

    @y_delta.setter
    def y_delta(self, value):
        self._model.y_delta = value
        self._clear_y()

    @property
    def width(self): return self._model.width

    @width.setter
    def width(self, value):
        self._model.width = value
        self._clear_x()

    @property
    def height(self): return self._model.height

    @height.setter
    def height(self, value):
        self._model.height = value
        self._clear_y()

    @property
    def x_anchor(self): return self._model.x_anchor

    @x_anchor.setter
    def x_anchor(self, value):
        self._model.x_anchor = value
        self._clear_x()

    @property
    def y_anchor(self): return self._model.y_anchor

    @y_anchor.setter
    def y_anchor(self, value):
        self._model.y_anchor = value
        self._clear_y()

    @property
    def x_pivot(self): return self._model.x_pivot

    @x_pivot.setter
    def x_pivot(self, value):
        self._model.x_pivot = value
        self._clear_x()

    @property
    def y_pivot(self): return self._model.y_pivot

    @y_pivot.setter
    def y_pivot(self, value):
        self._model.y_pivot = value
        self._clear_y()

    @property
    def _parent_x(self):
        return self.parent.x if self.parent is not None else 0

    @property
    def _parent_y(self):
        return self.parent.y if self.parent is not None else 0

    @property
    def _parent_width(self):
        return self.parent.width if self.parent is not None else 0

    @property
    def _parent_height(self):
        return self.parent.height if self.parent is not None else 0

    @property
    def x(self):
        if not self._model.x_is_set:
            self._model.x = calculate_dimension(self._parent_x, self._parent_width, self._model.x_anchor, self._model.x_pivot, self._model.width, self._model.x_delta)
            self._model.x_is_set = 1
            return self._model.x
        else:
            return self._model.x

    @property
    def y(self):
        if not self._model.y_is_set:
            self._model.y = calculate_dimension(self._parent_y, self._parent_height, self._model.y_anchor, self._model.y_pivot, self._model.height, self._model.y_delta)
            self._model.y_is_set = 1
            return self._model.y
        else:
            return self._model.y

    def destroy(self):
        self._object.destroy()

cdef inline RectTransformModel* get_transform_model_pointer(RectTransform transform):
    return &transform._model

cpdef void transform_model_calc(list transforms, int[:] lut):
    '''
    :param transforms: must be a preorder traversal
    '''

    cdef RectTransformModel** models
    cdef int n_models
    cdef RectTransformModel* model
    cdef RectTransformModel* parent
    cdef int parent_idx
    cdef int i

    n_models = len(transforms)
    models = <RectTransformModel**>malloc(n_models * sizeof(RectTransformModel*))

    for i in range(n_models):
        models[i] = get_transform_model_pointer(transforms[i])

    for i in prange(n_models, nogil=True):
        model = models[i]
        parent_idx = lut[i]
        if parent_idx >= 0:
            parent = models[parent_idx]
            model.x = calculate_dimension(parent.x, parent.width, model.x_anchor, model.x_pivot, model.width, model.x_delta)
            model.y = calculate_dimension(parent.y, parent.height, model.y_anchor, model.y_pivot, model.width, model.y_delta)
        else:
            model.x = calculate_dimension(0, 0, model.x_anchor, model.x_pivot, model.width, model.x_delta)
            model.y = calculate_dimension(0, 0, model.y_anchor, model.y_pivot, model.width, model.y_delta)
        model.x_is_set = 1
        model.y_is_set = 1
    free(models)
