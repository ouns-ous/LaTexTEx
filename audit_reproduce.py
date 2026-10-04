from pathlib import Path
import tempfile
from unittest.mock import patch
from project_studio import App, ROOT
source='\\documentclass{article}\n\\begin{document}\n\\section{Test}\nTARGET\n\\end{document}\n'
with tempfile.TemporaryDirectory(dir=ROOT) as folder:
    app=App(data_dir=Path(folder)/'data',legacy=Path(folder)/'absent');app.withdraw();app.autosave.set(False)
    app.open_project(app.store.create('Audit reproduction',source));app.update()
    doc=app.active_doc(); doc.text.mark_set('insert','4.0')
    with patch('editor_options.simpledialog.askstring',return_value='https://example.com'):
        app.insert_link()
    print('Link inserted before end document:',doc.content().find('\\href') < doc.content().find('\\end{document}'))
    app.set_edit_mode('Visual');app.update();app.update_outline()
    app.outline.selection_set(app.outline.get_children()[0]);app.jump_outline()
    print('Outline reveals source:',app.edit_mode.get()=='Code')
    app.set_edit_mode('Code');app.set_readonly(True);app.search_dialog();app.update()
    dialog=next(w for w in app.winfo_children() if w.winfo_class()=='Toplevel')
    top=dialog.winfo_children()[0]; entries=[w for w in top.winfo_children() if w.winfo_class()=='TEntry']
    entries[0].insert(0,'TARGET');entries[1].insert(0,'REPLACED')
    button=next(w for w in dialog.winfo_children() if w.winfo_class()=='Canvas');button.invoke()
    print('Read-only replacement reports:',app.status.get())
    dialog.destroy();app.set_readonly(False);app.save_all();app.close_documents();app.destroy()
