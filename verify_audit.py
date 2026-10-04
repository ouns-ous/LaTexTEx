"""Extended functional audit, isolated from personal projects."""
from pathlib import Path
import json, tempfile, time, zipfile, traceback
from unittest.mock import patch
from PIL import Image
from project_studio import App, ROOT, find_engine, pymupdf

checks=[]
def ok(name, condition=True):
    assert condition, name
    checks.append(name)
    print('PASS:',name,flush=True)

def children(widget):
    for child in widget.winfo_children():
        yield child
        yield from children(child)

def button(dialog,label):
    return next(w for w in children(dialog) if w.winfo_class()=='Canvas' and getattr(w,'label','')==label)

def dialog(app):
    app.update()
    return next(w for w in app.winfo_children() if w.winfo_class()=='Toplevel')

def close_dialogs(app):
    for w in app.winfo_children():
        if w.winfo_class()=='Toplevel':w.destroy()
    app.update()

def select_file(app,path):
    app.refresh_files()
    item=next(key for key,value in app.file_items.items() if value==path)
    app.file_tree.selection_set(item)

def pump(app, predicate, seconds=30):
    until=time.monotonic()+seconds
    while not predicate() and time.monotonic()<until:
        app.update();time.sleep(.03)
    assert predicate(),'Operation timed out'

source='\\documentclass{article}\n\\begin{document}\n\\section{Audit}\nTARGET\n\\end{document}\n'
errors=[]
with tempfile.TemporaryDirectory(prefix='audit-',dir=ROOT) as folder:
    base=Path(folder);data=base/'data'
    app=App(data_dir=data,legacy=base/'absent');app.autosave.set(False)
    app.report_callback_exception=lambda *args:errors.append(''.join(traceback.format_exception(*args)))
    with patch('project_studio.messagebox.showerror',side_effect=lambda *args,**kw:errors.append(str(args))), patch('project_studio.messagebox.showinfo'), patch('project_studio.messagebox.askyesno',return_value=True):
        project=app.store.create('Audit complet',source);app.open_project(project);app.update()
        main=Path(project['path'])/'main.tex';doc=app.active_doc()
        ok('No Upgrade button',not any(getattr(w,'label','')=='Upgrade' for w in children(app)))
        ok('All toolbar icons are bundled',bool(doc.mode_buttons) and (ROOT/'assets/fontawesome/fa-solid-900.ttf').exists())
        with patch('project_studio.simpledialog.askstring',return_value='chapters'):
            app.new_folder()
        chapter_folder=main.parent/'chapters';ok('Create folder',chapter_folder.is_dir())
        select_file(app,chapter_folder)
        with patch('project_studio.simpledialog.askstring',return_value='intro.tex'):app.new_file()
        chapter=chapter_folder/'intro.tex';ok('Create file in selected folder',chapter.exists() and app.active_doc().path==chapter)
        select_file(app,chapter)
        with patch('project_studio.simpledialog.askstring',return_value='chapters/renamed.tex'):app.rename_file()
        chapter=chapter_folder/'renamed.tex';ok('Rename open file and keep tab',chapter.exists() and chapter in app.docs)
        select_file(app,chapter);app.trash_file();ok('Trash file',not chapter.exists())
        app.trash_dialog();d=dialog(app);table=next(w for w in children(d) if w.winfo_class()=='Treeview');table.selection_set(table.get_children()[0]);button(d,'Restaurer').invoke()
        ok('Restore file through dialog',chapter.exists())
        app.file_tree.selection_remove(*app.file_tree.selection())
        imported=base/'notes.txt';imported.write_text('resource',encoding='utf-8')
        with patch('project_studio.filedialog.askopenfilenames',return_value=[str(imported)]):app.import_files()
        ok('Import resource',(main.parent/'notes.txt').read_text()=='resource')
        app.open_document(main);doc=app.active_doc()
        doc.text.mark_set('insert','4.0');doc.text.tag_add('sel','4.0','4.6')
        app.format_text('bold');ok('Bold selection','\\textbf{TARGET}' in doc.content())
        app.update();app.edit_action('edit_undo');ok('Undo',doc.content()==source)
        app.edit_action('edit_redo');ok('Redo','\\textbf{TARGET}' in doc.content())
        doc.text.edit_separator();doc.text.mark_set('insert','4.0');app.indent_lines(1);app.indent_lines(-1)
        ok('Indent and outdent',doc.text.get('4.0','4.end').startswith('\\textbf'))
        app.toggle_comment();ok('Comment line',doc.text.get('4.0','4.end').startswith('%'))
        app.toggle_comment();ok('Uncomment line',not doc.text.get('4.0','4.end').startswith('%'))
        app.toggle_wrap();ok('Line wrap',doc.text.cget('wrap')=='word');app.toggle_wrap()
        app.save_all();old=doc.content();doc.text.insert('4.end',' HISTORY');app.save_all()
        app.history_dialog();d=dialog(app);table=next(w for w in children(d) if w.winfo_class()=='Treeview');table.selection_set(table.get_children()[0]);button(d,'Restaurer la version sélectionnée').invoke()
        ok('Restore historical source through dialog',app.active_doc().content()==old)
        app.search_dialog();d=dialog(app);entries=[w for w in children(d) if w.winfo_class()=='TEntry'];entries[0].insert(0,'TARGET');entries[1].insert(0,'AUDITED')
        button(d,'Dans tout le projet').invoke();table=next(w for w in children(d) if w.winfo_class()=='Treeview');ok('Search whole project',len(table.get_children())>0)
        app.set_readonly(True);before=doc.content();button(d,'Remplacer tout dans l’onglet actif').invoke();ok('Read-only blocks replace and does not report success',doc.content()==before and 'lecture seule' in app.status.get())
        app.set_readonly(False);button(d,'Remplacer tout dans l’onglet actif').invoke();ok('Replace active source','AUDITED' in doc.content());d.destroy()
        app.set_edit_mode('Visual');app.update();app.update_outline();app.outline.selection_set(app.outline.get_children()[0]);app.jump_outline();ok('Outline navigation exits Visual mode',app.edit_mode.get()=='Code')
        doc.text.mark_set('insert','4.0')
        with patch('editor_options.simpledialog.askstring',return_value='https://example.com/a?q=1#anchor'):app.insert_link()
        ok('Link and package insertion preserve cursor',doc.content().index('\\href')<doc.content().index('\\end{document}') and doc.content().count('\\usepackage{hyperref}')==1)
        doc.text.mark_set('insert','4.end');doc.text.insert('insert','\n')
        with patch('editor_options.simpledialog.askinteger',side_effect=[2,2]):app.table_dialog()
        ok('Table insertion','\\begin{tabular}{|l|l|}' in doc.content())
        image=base/'photo #1%.png';Image.new('RGB',(100,60),'#07845e').save(image)
        doc.text.mark_set('insert',doc.text.search('\\end{document}','1.0'))
        with patch('editor_options.filedialog.askopenfilename',return_value=str(image)):app.insert_image()
        ok('Image insertion with safe filename','images/photo-1.png' in doc.content() and '\\usepackage{graphicx}' in doc.content())
        app.comments_dialog();d=dialog(app);entry=next(w for w in children(d) if w.winfo_class()=='Text');entry.insert('1.0','Audit comment');button(d,'Ajouter à la ligne du curseur').invoke()
        table=next(w for w in children(d) if w.winfo_class()=='Treeview');table.selection_set(table.get_children()[0]);button(d,'Résoudre / rouvrir').invoke();ok('Comment add and resolve',app.store.comments(project)[0]['resolved']);d.destroy()
        app.preferences_dialog();d=dialog(app);spin=next(w for w in children(d) if w.winfo_class()=='TSpinbox');spin.set(14);button(d,'Appliquer et enregistrer').invoke();ok('Preferences persist',json.loads(app.preferences_path.read_text())['font_size']==14)
        app.save_all();export=base/'export.tex'
        with patch('editor_options.filedialog.asksaveasfilename',return_value=str(export)):app.export_active_source()
        ok('Source export matches active source',export.read_text(encoding='utf-8')==doc.content())
        archive=base/'export.zip'
        with patch('project_studio.filedialog.asksaveasfilename',return_value=str(archive)):app.export_zip()
        with zipfile.ZipFile(archive) as zipped:ok('ZIP includes resources and excludes internal data','images/photo-1.png' in zipped.namelist() and not any(n.startswith('.latextex/') for n in zipped.namelist()))
        app.show_home();app.projects_table.selection_set(project['id'])
        with patch('project_studio.simpledialog.askstring',return_value='Audit renamed'):app.rename_project()
        ok('Rename project',project['name']=='Audit renamed')
        app.projects_table.selection_set(project['id']);app.duplicate_project();ok('Duplicate project',len(app.store.projects)==2)
        app.projects_table.selection_set(project['id']);app.project_state('archived');app.filter_home('archived');ok('Archive project filter',project['id'] in app.projects_table.get_children())
        app.projects_table.selection_set(project['id']);app.project_state('trash');app.filter_home('trash');ok('Project trash filter',project['id'] in app.projects_table.get_children())
        app.projects_table.selection_set(project['id']);app.project_state('active');app.filter_home('active');app.open_project(project);doc=app.active_doc()
        for mode in ['editor','pdf','split']:app.set_layout(mode);app.update()
        app.toggle_sidebar();app.update();ok('Hide file panel',not app.file_sidebar.winfo_ismapped());app.toggle_sidebar()
        app.compile();pump(app,lambda:not app.busy,60);ok('Compile document with inserted link, table and image','réussie' in app.status.get())
        good_pdf=main.with_suffix('.pdf').read_bytes()
        pdf_export=base/'export.pdf'
        with patch('project_studio.filedialog.asksaveasfilename',return_value=str(pdf_export)):app.export_pdf()
        ok('Export PDF',pdf_export.read_bytes()==good_pdf)
        app.zoom_to('25%');app.change_zoom(-.2);ok('Zoom lower bound',abs(app.photo.width()/app.pdf[app.page].rect.width-.25)<.02)
        app.zoom_to('125%');ok('125 percent zoom',abs(app.photo.width()/app.pdf[app.page].rect.width-1.25)<.02)
        app.zoom_to('Page entière');app.toggle_pdf_dark();ok('Page fit and night mode',app.pdf_dark)
        bad=base/'bad.pdf';bad.write_text('broken')
        try:app.load_pdf(bad)
        except ValueError:pass
        else:raise AssertionError('Invalid PDF not rejected')
        ok('Invalid PDF preserves previous preview',app.pdf is not None)
        pages=pymupdf.open()
        for i in range(3):p=pages.new_page();p.insert_text((60,60),f'Audit page {i+1}')
        multi=base/'multi.pdf';pages.save(multi);pages.close();app.load_pdf(multi)
        app.turn_page(1);app.page_input.set('3');app.jump_page();ok('PDF next and direct page navigation',app.page==2)
        with patch('project_studio.simpledialog.askstring',return_value='Audit page 1'):app.search_pdf()
        ok('Search all PDF pages',app.page==0 and app.pdf_search_term=='Audit page 1')
        app.preview_resource(image);ok('Image preview',app.pdf is None and app.photo.width()>0)
        app.set_layout('editor');app.show_pdf(multi);app.update();ok('PDF library opens visible PDF from editor-only layout',app.pdf_panel.winfo_ismapped())
        app.open_project(project);app.update();ok('Project editor restored after PDF library',app.middle_panes.winfo_ismapped())
        app.open_document(main);doc=app.active_doc();doc.text.delete('1.0','end');doc.text.insert('1.0',source);app.save_all()
        engines={name:bool(find_engine(name)) for name in ['pdflatex','xelatex','lualatex','bibtex','biber']}
        for name in ['xelatex','lualatex']:
            if engines[name]:
                app.engine.set(name);app.compile();pump(app,lambda:not app.busy,60);ok('Compile '+name,'réussie' in app.status.get())
        app.engine.set('pdflatex');doc.text.delete('1.0','end');doc.text.insert('1.0','\\documentclass{article}\n\\begin{document}\n\\loop\\iftrue\\repeat\n\\end{document}')
        app.compile();pump(app,lambda:app.proc is not None,10);app.stop_compile();pump(app,lambda:not app.busy,15);ok('Stop real LaTeX process','annulée' in app.status.get())
        doc.text.delete('1.0','end');doc.text.insert('1.0',source);app.save_all();app.autosave.set(True);doc.text.insert('4.end',' AUTO');pump(app,lambda:doc.path.read_text(encoding='utf-8')==doc.content(),5);ok('Automatic save', 'AUTO' in doc.path.read_text(encoding='utf-8'))
        for action in [app.symbols_dialog,app.image_library,app.share_dialog,app.compilation_settings]:action();ok('Dialog '+action.__name__);close_dialogs(app)
        app.assistant_dialog();app.upgrade_dialog();app.help_dialog();ok('Local helper and help callbacks')
        app.save_all();app.close_documents();app.destroy()
    if errors:
        print('UNEXPECTED ERRORS:',json.dumps(errors,ensure_ascii=False),flush=True)
    ok('No Tk callback errors or unexpected error dialogs',not errors)
    restarted=App(data_dir=data,legacy=base/'absent');restarted.withdraw();ok('Restart restores preferences and projects',restarted.font_size==14 and len(restarted.store.projects)==2);restarted.destroy()
report={'passed':len(checks),'checks':checks,'engines_available':engines,'unexpected_errors':errors,'personal_projects_modified':False}
(ROOT/'audit-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('AUDIT COMPLETE:',len(checks),'checks',flush=True)

