from sb.component cimport Component
import numpy as np

def walk_transforms(transform):
    yield transform
    for t in transform.children:
        yield from walk_transforms(t)

def get_model_hierarchy(transform, index=0, parent_index=-1):
        next_index = index + len(transform.children) + 1
        yield transform, parent_index
        for t in transform.children:
            yield from get_model_hierarchy(t, next_index, index)

cdef class TransformBase(Component):
    def __init__(self, _object):
        self._object = _object
        self._transform = self
        self._parent = None
        self._children = []
        self._descendants = None
        self._descendant_hierarchy = None

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

    def _clear_model(self):
        # Implemented in subclasses
        pass

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, new_parent):
        assert(isinstance(new_parent, TransformBase))
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
                    new_parent._clear_model()
                # If new parent is not a descendant of this transform
                else:
                    new_parent._children.append(self)
                    new_parent._clear_ancestor_descendants()
                    self._clear_model()
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

    def destroy(self):
        self._object.destroy()