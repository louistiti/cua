import importlib.util
import json
import os
from pathlib import Path

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

spec = importlib.util.spec_from_file_location("canonical_fixture", os.environ["CUA_PROBE_FIXTURE"])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
window = module.HarnessWindow()
journal = Path(os.environ["CUA_PROBE_JOURNAL"])
keys = []


def find_button(widget):
    if widget.get_accessible().get_name() == "btn-increment":
        return widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            found = find_button(child)
            if found is not None:
                return found
    return None


button = find_button(window)
button.set_name("cua-probe-increment")
css = Gtk.CssProvider()
css.load_from_data(b"#cua-probe-increment {background-image:none; background-color:#ff00ff; color:#000000;}")
Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_USER)


def on_key(widget, event):
    if event.state & Gdk.ModifierType.CONTROL_MASK:
        name = Gdk.keyval_name(event.keyval)
        if name in ("comma", "slash", "question"):
            keys.append({"key": name, "shift": bool(event.state & Gdk.ModifierType.SHIFT_MASK)})
    return False


def record():
    journal.write_text(json.dumps({"pid": os.getpid(), "counter": window.counter, "keys": keys}))
    return True


window.connect("key-press-event", on_key)
window.connect("destroy", Gtk.main_quit)
window.show_all()
window.present()
GLib.timeout_add(100, record)
GLib.timeout_add_seconds(180, lambda: (Gtk.main_quit(), False)[1])
Gtk.main()
