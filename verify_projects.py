"""Integration test of project creation, tabs, real compilation and failure handling."""
from pathlib import Path
import tempfile
import time
from unittest.mock import patch
from types import SimpleNamespace
from project_studio import App, ROOT

with tempfile.TemporaryDirectory(prefix='verify-', dir=ROOT) as folder:
    app = App(data_dir=Path(folder) / 'data', legacy=Path(folder) / 'none.json')
    app.withdraw()
    app.autosave.set(False)
    assert app.project is None
    source = r'''\documentclass{article}
\begin{document}
\section{Document principal}
\input{chapitres/intro}
Citation \cite{knuth}.
\bibliographystyle{plain}
\bibliography{refs}
\end{document}
'''
    app.new_project()
    dialog = next(w for w in app.winfo_children() if w.winfo_class() == 'Toplevel')
    entry = next(w for w in dialog.winfo_children() if w.winfo_class() == 'TEntry')
    entry.delete(0, 'end')
    entry.insert(0, 'Projet intégration')
    create = next(w for w in dialog.winfo_children() if w.winfo_class() == 'Canvas')
    create.invoke()
    project = app.project
    assert project and (Path(project['path']) / 'main.tex').exists()
    main_doc = app.active_doc()
    main_doc.text.delete('1.0', 'end')
    main_doc.text.insert('1.0', source)
    app.save_all()
    app.store.new_file(project, 'chapitres/intro.tex', 'Texte du chapitre.\n')
    app.store.new_file(project, 'refs.bib', '@book{knuth,author={Donald Knuth},title={The TeXbook},year={1984},publisher={Addison-Wesley}}\n')
    app.open_project(project)
    with patch('project_studio.simpledialog.askstring', return_value='nouveau.tex'):
        app.new_file()
    new = Path(project['path']) / 'nouveau.tex'
    assert new.exists() and new in app.file_items.values() and new in app.docs
    main = Path(project['path']) / 'main.tex'
    doc = app.docs[new]
    doc.text.insert('end', 'Modification non perdue')
    app.update()
    app.open_document(main)
    app.open_document(new)
    assert 'Modification non perdue' in app.active_doc().content()
    assert len(app.docs) == 2
    app.save_all()
    assert 'Modification non perdue' in new.read_text(encoding='utf-8')
    app.compile()  # The active file is nouveau.tex; compilation must use main.tex.
    limit = time.monotonic() + 240
    while app.busy and time.monotonic() < limit:
        app.update()
        time.sleep(0.05)
    assert not app.busy, 'Compile timeout'
    assert app.pdf, app.log.get('1.0', 'end')
    pdf = main.with_suffix('.pdf')
    assert pdf.exists()
    content = ''.join(page.get_text() for page in app.pdf)
    assert 'Texte du chapitre' in content and 'The TeXbook' in content, content
    good_pdf = pdf.read_bytes()
    app.open_document(main)
    app.active_doc().text.mark_set('insert', '3.0')
    app.source_to_pdf()
    assert 'Code → PDF' in app.status.get()
    position = app.run_synctex(['view', '-i', f'3:0:{main}', '-o', str(app.synctex_output())])
    scale = app.photo.width() / app.pdf[app.page].rect.width
    offset = max(15, (app.canvas.winfo_width() - app.photo.width()) // 2)
    event = SimpleNamespace(x=offset + float(position['x']) * scale - app.canvas.canvasx(0), y=15 + float(position['y']) * scale - app.canvas.canvasy(0))
    app.pdf_to_source(event)
    assert app.active_doc().path == main and 'PDF → Code' in app.status.get()
    app.store.add_comment(project, 'main.tex', 3, 'Test commentaire')
    assert app.store.comments(project)[0]['line'] == 3
    app.active_doc().text.insert('1.0', '\\undefinedcommand\n')
    app.update()
    app.compile()
    limit = time.monotonic() + 200
    while app.busy and time.monotonic() < limit:
        app.update()
        time.sleep(0.05)
    assert not app.busy
    assert 'Échec' in app.status.get(), app.status.get()
    assert app.errors.get_children(), app.log.get('1.0', 'end')
    assert pdf.read_bytes() == good_pdf, 'Failed compilation replaced the good PDF'
    app.show_home()
    assert app.projects_table.exists(project['id'])
    app.save_all()
    app.on_close()
print('PASS: project/file buttons, tabs, compile, BibTeX, SyncTeX, comments, error links, last good PDF')
