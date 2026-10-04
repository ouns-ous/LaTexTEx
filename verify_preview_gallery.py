"""Verify bundled gallery, immediate previews, and compilation on first open."""
from pathlib import Path
import tempfile
import time
from unittest.mock import patch
from PIL import ImageGrab
from project_studio import App, ROOT, TEMPLATES
from template_catalog import preview_asset

with tempfile.TemporaryDirectory(dir=ROOT) as directory:
    app = App(data_dir=Path(directory) / 'data', legacy=Path(directory) / 'absent')
    app.autosave.set(False)
    app.geometry('1240x690+20+20')
    app.update()
    assert len(app.template_photos) == len(TEMPLATES)
    with patch('template_catalog.sys._MEIPASS', str(ROOT), create=True):
        assert preview_asset(ROOT / 'absent', TEMPLATES['Article'], '.png')
    for name, source in TEMPLATES.items():
        assert preview_asset(ROOT, source, '.png')
        assert preview_asset(ROOT, source, '.pdf')
        project = app.store.create(name, source)
        if name == 'العربية — Article':
            project['engine'] = 'xelatex'
        app.open_project(project)
        app.update()
        assert app.pdf and app.pdf.page_count >= 1, name
        assert not app.busy, name
    source = '\\documentclass{article}\n\\begin{document}\nFirst automatic preview.\n\\end{document}\n'
    project = app.store.create('Automatic preview', source)
    with patch.object(app, 'compile') as compile_mock:
        app.open_project(project)
        deadline = time.monotonic() + 0.6
        while time.monotonic() < deadline:
            app.update()
            time.sleep(0.01)
        compile_mock.assert_called_once()
    app.open_project(project)
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline and not app.pdf:
        app.update()
        time.sleep(0.02)
    assert app.pdf and not app.busy, 'First compilation did not produce a PDF'
    assert 'First automatic preview.' in app.pdf[0].get_text()
    app.show_home()
    app.attributes('-topmost', True)
    app.lift()
    app.update()
    time.sleep(0.3)
    app.update()
    ImageGrab.grab(window=app.winfo_id()).save(ROOT / 'preview-gallery.png')
    app.close_documents()
    app.destroy()
print('9 real thumbnails, 9 immediate PDF previews and automatic first compilation: OK')
