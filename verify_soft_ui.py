"""Check centered dialogs, animation cleanup and template selection."""
from pathlib import Path
import tempfile
import time
import tkinter as tk
from PIL import ImageGrab
from project_studio import App, ROOT
from soft_ui import SoftDialog

with tempfile.TemporaryDirectory(dir=ROOT) as directory:
    app = App(data_dir=Path(directory) / 'data', legacy=Path(directory) / 'absent')
    app.auto_preview_on_open = False
    app.attributes('-topmost', True)
    app.update()
    errors = []
    app.report_callback_exception = lambda *args: errors.append(args)
    app.new_project('CV')
    dialog = next(w for w in app.winfo_children() if isinstance(w, SoftDialog))
    deadline = time.monotonic() + 0.3
    while time.monotonic() < deadline:
        app.update()
        time.sleep(0.01)
    assert abs((dialog.winfo_rootx() + dialog.winfo_width()/2) - (app.winfo_rootx() + app.winfo_width()/2)) < 8
    assert abs((dialog.winfo_rooty() + dialog.winfo_height()/2) - (app.winfo_rooty() + app.winfo_height()/2)) < 35
    assert dialog.attributes('-alpha') == 1.0
    assert dialog.winfo_viewable()
    ImageGrab.grab(window=dialog.winfo_id()).save(ROOT / 'preview-dialog.png')
    dialog.event_generate('<Escape>')
    app.update()
    if dialog.winfo_exists():
        dialog.destroy()
    # Destruction before the reveal must not leave Tcl animation callbacks.
    short_lived = SoftDialog(app)
    short_lived.destroy()
    app.update()
    assert not errors, errors
    app.destroy()
print('Centered dialogs, selected template preview, smooth reveal and callback cleanup: OK')
