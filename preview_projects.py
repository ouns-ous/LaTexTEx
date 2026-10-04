"""Capture only this app's own windows for layout verification."""
import ctypes
from pathlib import Path
import tempfile
import time
import win32gui
import win32ui
from PIL import Image
from project_studio import App, ROOT, TEMPLATES


def capture(app, target):
    app.update()
    hwnd = win32gui.GetAncestor(app.winfo_id(), 2)
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    width, height = right - left, bottom - top
    window_dc = win32gui.GetWindowDC(hwnd)
    dc = win32ui.CreateDCFromHandle(window_dc)
    memory = dc.CreateCompatibleDC()
    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(dc, width, height)
    memory.SelectObject(bitmap)
    result = ctypes.windll.user32.PrintWindow(hwnd, memory.GetSafeHdc(), 2)
    assert result, 'Window capture failed'
    info = bitmap.GetInfo()
    image = Image.frombuffer('RGB', (info['bmWidth'], info['bmHeight']), bitmap.GetBitmapBits(True), 'raw', 'BGRX', 0, 1)
    image.save(target)
    win32gui.DeleteObject(bitmap.GetHandle())
    memory.DeleteDC()
    dc.DeleteDC()
    win32gui.ReleaseDC(hwnd, window_dc)


if __name__ == '__main__':
    with tempfile.TemporaryDirectory(prefix='preview-', dir=ROOT) as folder:
        app = App(data_dir=Path(folder) / 'data', legacy=Path(folder) / 'none.json')
        app.autosave.set(False)
        for name, template in [('Robotique — étude cinématique', 'Article'), ('Rapport de stage', 'Rapport'), ('Présentation du projet', 'Présentation')]:
            app.store.create(name, TEMPLATES[template])
        app.refresh_home()
        app.update()
        capture(app, ROOT / 'preview-home.png')
        project = app.store.projects[0]
        app.store.new_file(project, 'chapitres/introduction.tex', '\\section{Introduction}\nTexte de votre chapitre.\n')
        app.store.new_file(project, 'references.bib', '% Votre bibliographie\n')
        app.open_project(project)
        app.open_document(Path(project['path']) / 'chapitres/introduction.tex')
        app.load_pdf(ROOT / 'documents/Bienvenue.pdf')
        app.update()
        app.render_pdf()
        capture(app, ROOT / 'preview-editor.png')
        app.geometry('1020x610')
        app.update()
        assert app.compile_button.winfo_ismapped() and app.compile_button.winfo_width() > 70
        assert app.log_toggle.winfo_ismapped()
        app.toggle_log()
        assert app.log_visible
        app.toggle_log()
        assert not app.log_visible
        app.on_close()
    print('Own-window previews created')
