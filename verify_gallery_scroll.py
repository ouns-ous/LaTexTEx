"""Verify wheel delivery over gallery children and precision touchpad deltas."""
from pathlib import Path
from types import SimpleNamespace
import tempfile
import tkinter as tk
from project_studio import App, ROOT

with tempfile.TemporaryDirectory(dir=ROOT) as directory:
    app = App(data_dir=Path(directory) / 'data', legacy=Path(directory) / 'absent')
    app.update()
    canvas = app.gallery_canvas
    gallery = canvas.winfo_children()[0]
    card = gallery.winfo_children()[0]
    thumbnail = next(w for w in card.winfo_children() if isinstance(w, tk.Label))
    button = next(w for w in card.winfo_children() if hasattr(w, 'label'))
    start = canvas.xview()[0]
    thumbnail.event_generate('<MouseWheel>', delta=-120)
    app.update()
    assert canvas.xview()[0] > start, 'Wheel over thumbnail did not scroll'
    current = canvas.xview()[0]
    button.event_generate('<Shift-MouseWheel>', delta=-120)
    app.update()
    assert canvas.xview()[0] > current, 'Shift wheel over button did not scroll'
    current = canvas.xview()[0]
    button.event_generate('<MouseWheel>', delta=120)
    app.update()
    assert canvas.xview()[0] < current, 'Reverse scrolling failed'
    canvas.xview_moveto(0)
    app.gallery_remainder = 0
    for _ in range(8):
        app.scroll_templates(SimpleNamespace(delta=-1))
    assert canvas.xview()[0] > 0, 'Small touchpad deltas were discarded'
    canvas.xview_moveto(0)
    app.gallery_next.invoke()
    assert canvas.xview()[0] > 0, 'Next arrow did not scroll'
    app.gallery_previous.invoke()
    assert canvas.xview()[0] == 0, 'Previous arrow did not scroll'
    canvas.xview_moveto(1)
    app.scroll_templates(SimpleNamespace(delta=-120))
    assert canvas.xview()[1] <= 1, 'Scroll exceeded final template'
    app.destroy()
print('Wheel over images/buttons, shift wheel, touchpad deltas, arrows and boundaries: OK')
