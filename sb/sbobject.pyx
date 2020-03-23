from sb.recttransform import RectTransform


class SBObject:
    def __init__(self):
        self._transform = RectTransform(self)
        self._components = []
        self._alive = True

    @property
    def alive(self):
        return self._alive

    @property
    def transform(self):
        return self._transform

    def add_component(self, component_type):
        component = component_type(self)
        self._components.append(component)
        return component

    def get_component(self, component_type):
        match = [c for c in self._components
                 if issubclass(type(c), component_type)]
        return match[0] if match else None

    def get_components(self, component_type):
        match = [c for c in self._components
                 if issubclass(type(c), component_type)]
        return match

    def remove_component(self, component):
        self._components.remove(component)

    def update_components(self, dt):
        for component in self._components:
            component.update(dt)

    def destroy(self):
        # Mark for removal
        self._alive = False