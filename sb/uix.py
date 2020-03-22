from kivy.app import App
from kivy.uix.button import Button

class SelectDirectoryBtn(Button):
    def on_press(self):
        pass


class CenterViewBtn(Button):
    def on_press(self):
        pass


class Export2DBtn(Button):
    def on_press(self):
        pass


class Export1DBtn(Button):
    def on_press(self):
        App.get_running_app().export_1d()
