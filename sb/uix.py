from kivy.app import App
from kivy.properties import ObjectProperty
from kivy.uix.button import Button
from kivy.uix.floatlayout import FloatLayout
from os import path

class ChooseDirectoryBtn(Button):
    def on_press(self):
        App.get_running_app().on_choose_directory()


class CenterViewBtn(Button):
    def on_press(self):
        pass


class Export2DBtn(Button):
    def on_press(self):
        pass


class Export1DBtn(Button):
    def on_press(self):
        App.get_running_app().export_1d()


class LoadDirectoryDialog(FloatLayout):
    load = ObjectProperty(None)
    cancel = ObjectProperty(None)

    def is_dir(self, directory, filename):
        return path.isdir(path.join(directory, filename))
