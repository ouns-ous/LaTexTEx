"""Compile every template and verify Arabic configuration and insert dialogs."""
from pathlib import Path
import subprocess
import tempfile
import tkinter as tk
import sys
sys.stdout.reconfigure(encoding='utf-8')
from project_studio import App, TEMPLATES, ROOT, find_engine
from unittest.mock import patch
from PIL import Image
from template_catalog import table_source

with tempfile.TemporaryDirectory(dir=ROOT) as directory:
    root = Path(directory)
    unavailable = []
    for number, (name, source) in enumerate(TEMPLATES.items()):
        folder = root / str(number)
        folder.mkdir()
        if name == 'Document vide':
            source = source.replace('\\end{document}', 'Test\n\\end{document}')
        if name == 'Article':
            source = source.replace('\\end{document}', table_source([['A & B', '100%'], ['x_y', '#1']], 'Table & test') + '\\end{document}')
        (folder / 'main.tex').write_text(source, encoding='utf-8')
        engine = 'xelatex' if name in {'العربية — Article'} else 'pdflatex'
        print('Compiling:', name, flush=True)
        result = subprocess.run([find_engine(engine), '--disable-installer', '-interaction=nonstopmode', '-halt-on-error', 'main.tex'], cwd=folder, capture_output=True, timeout=30)
        output = result.stdout.decode(errors='replace')
        if result.returncode and ('not found' in output or 'cannot be found' in output):
            unavailable.append(name)
            print('Missing local LaTeX dependency:', name, flush=True)
            continue
        assert result.returncode == 0, (name, output[-2500:])
        assert (folder / 'main.pdf').exists()
    app = App(data_dir=root / 'data', legacy=root / 'absent')
    app.autosave.set(False)
    app.new_project('العربية — Article')
    dialog = next(w for w in app.winfo_children() if isinstance(w, tk.Toplevel))
    button = next(w for w in dialog.winfo_children() if hasattr(w, 'label') and w.label == 'Créer le projet')
    button.invoke()
    assert app.project['engine'] == 'xelatex'
    app.table_dialog()
    dialog = next(w for w in app.winfo_children() if isinstance(w, tk.Toplevel))
    button = next(w for w in dialog.winfo_children() if hasattr(w, 'label') and w.label == 'Insérer le tableau')
    button.invoke()
    assert '\\begin{tabular}{|l|l|l|}' in app.active_doc().content()
    image = root / 'test image.png'
    Image.new('RGB', (20, 20), 'blue').save(image)
    def accept_image(dialog):
        button = next(w for w in dialog.winfo_children() if hasattr(w, 'label') and w.label == 'Insérer')
        button.invoke()
    with patch('editor_options.filedialog.askopenfilename', return_value=str(image)), patch.object(app, 'wait_window', side_effect=accept_image):
        app.insert_image()
    assert '\\includegraphics[width=0.8\\linewidth]{images/test-image.png}' in app.active_doc().content()
    assert (Path(app.project['path']) / 'images' / 'test-image.png').exists()
    app.save_all()
    app.history_dialog()
    app.update()
    dialog = next(w for w in app.winfo_children() if isinstance(w, tk.Toplevel))
    table = next(w for w in dialog.winfo_children() if isinstance(w, __import__('tkinter').ttk.Treeview))
    table.selection_set(table.get_children()[0])
    actions = next(w for w in dialog.winfo_children() if isinstance(w, tk.Frame))
    compare = next(w for w in actions.winfo_children() if hasattr(w, 'label') and w.label == 'Comparer avec maintenant')
    compare.invoke()
    preview = next(w for w in dialog.winfo_children() if isinstance(w, tk.Text))
    assert 'Version actuelle' in preview.get('1.0', 'end')
    dialog.destroy()
    app.close_documents()
    app.destroy()
print('Arabic engine, editable table and history dialogs: OK')
print('Compiled templates:', len(TEMPLATES) - len(unavailable), '/', len(TEMPLATES))
if unavailable:
    print('Compilation not verified (missing local packages):', ', '.join(unavailable))
