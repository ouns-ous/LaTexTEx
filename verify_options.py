from pathlib import Path
import tempfile
from project_studio import App, ROOT
from visual_editor import VisualModel
source = '\\documentclass{article}\n\\begin{document}\n\\section{Titre}\nBonjour \\textbf{monde}.\n\n\\begin{equation}\nx^2=1\n\\end{equation}\n\\end{document}\n'
model = VisualModel(source)
assert model.render_source() == source
assert [b.kind for b in model.blocks] == ['section', 'paragraph', 'source']
with tempfile.TemporaryDirectory(dir=ROOT) as directory:
    app = App(data_dir=Path(directory)/'data', legacy=Path(directory)/'absent')
    app.autosave.set(False)
    app.auto_preview_on_open = False  # Automatic compilation has its own integration test.
    project = app.store.create('Options', source)
    app.open_project(project); app.update()
    doc = app.active_doc()
    app.set_edit_mode('Visual'); app.update()
    doc.visual.flush(); assert doc.content() == source
    field = doc.visual.fields[1][0]
    field.insert('end-1c', ' Ajout 100%.')
    doc.save()
    edited = doc.path.read_text(encoding='utf-8')
    assert 'Ajout 100\\%.' in edited
    assert '\\begin{equation}\nx^2=1\n\\end{equation}' in edited
    app.set_edit_mode('Code'); assert doc.content() == edited
    app.set_readonly(True); before=doc.content(); app.insert_latex('oops',''); assert doc.content()==before
    app.set_readonly(False)
    for layout in ['editor', 'pdf', 'split']:
        app.set_layout(layout); app.update()
        assert app.middle_panes.winfo_ismapped() == (layout != 'pdf')
        assert app.pdf_panel.winfo_ismapped() == (layout != 'editor')
    app.load_pdf(ROOT/'documents'/'Bienvenue.pdf'); app.update()
    app.zoom_to('100%'); assert abs(app.photo.width()/app.pdf[app.page].rect.width-1)<0.02
    app.toggle_pdf_dark(); assert app.pdf_dark
    assert len(app.main_menus['Insert']) >= 10
    app.close_documents(); app.destroy()
print('Visual source preservation, rich editing, saving, read-only, layouts, PDF zoom and night mode: OK')
