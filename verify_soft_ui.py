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
    assert dialog.winfo_toplevel() == app
    assert not any(isinstance(w, tk.Toplevel) for w in app.winfo_children())
    assert dialog.winfo_viewable()
    assert app.grab_current() is None
    original_width = dialog.winfo_width()
    dialog.toggle_maximize()
    app.update()
    assert dialog.winfo_width() > original_width
    dialog.toggle_maximize()
    app.update()
    ImageGrab.grab(window=app.winfo_id()).save(ROOT / 'preview-dialog.png')
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
print('Embedded panels, maximize, non-modal navigation and callback cleanup: OK')
