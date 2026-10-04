from pathlib import Path
import tempfile,time
from unittest.mock import patch
from project_studio import App,ROOT
from preview_projects import capture
source=r'''\documentclass[12pt]{article}
\usepackage{amsmath}
\title{Robotique — étude cinématique}
\author{Votre nom}
\begin{document}
\maketitle
\section{Intégration temporelle}
On suppose que la vitesse linéaire $v$ et la vitesse angulaire $\Omega$ sont constantes. Les conditions initiales sont notées :
\[
x(0)=x_0,\qquad y(0)=y_0,\qquad \theta(0)=\theta_0
\]
Puisque le mouvement est orienté suivant l'axe longitudinal, les équations différentielles s'écrivent :
\begin{equation}
\boxed{\begin{cases}
\dot{x}(t)=-v\sin\theta(t)\\
\dot{y}(t)=v\cos\theta(t)\\
\dot{\theta}(t)=\Omega
\end{cases}}
\end{equation}
\subsection{Cas 1 : Mouvement rectiligne}
Lorsque la vitesse angulaire est nulle, l'orientation du robot demeure constante.
\end{document}
'''
with tempfile.TemporaryDirectory(prefix='visual-v2-',dir=ROOT) as folder:
    app=App(data_dir=Path(folder)/'data',legacy=Path(folder)/'absent');app.autosave.set(False)
    errors=[];app.report_callback_exception=lambda *args:errors.append(str(args[1]))
    project=app.store.create('Visual — aperçu',source);app.open_project(project);app.set_layout('editor');app.set_edit_mode('Visual');app.update()
    doc=app.active_doc();view=doc.visual;view.flush();assert doc.content()==source,'Opening Visual modified source'
    limit=time.monotonic()+45
    while len(view.images)<len(view.render_labels) and time.monotonic()<limit:app.update();time.sleep(.03)
    assert len(view.images)==len(view.render_labels),(len(view.images),len(view.render_labels),[(k,getattr(w,'preview_error',None)) for k,w in view.render_labels.items()])
    assert not any(getattr(w,'cget',lambda key:'')('text')=='BLOC LATEX' for w in view.body.winfo_children() if w.winfo_class()=='Label')
    capture(app,ROOT/'preview-visual.png')
    index=next(i for i,b in enumerate(view.model.blocks) if b.kind=='paragraph' and '$v$' in b.content)
    field=view.fields[index][0];view.active=index;field.mark_set('insert','1.0');field.insert('insert','Texte édité. ');view.flush()
    assert 'Texte édité. On suppose' in doc.content() and '$v$' in doc.content() and '$\\Omega$' in doc.content()
    field.tag_add('sel','1.0','1.5');app.format_text('bold');assert '\\textbf{Texte}' in doc.content()
    app.edit_action('edit_undo');assert '\\textbf{Texte}' not in doc.content() and app.edit_mode.get()=='Visual'
    app.edit_action('edit_redo');assert '\\textbf{Texte}' in doc.content()
    view=doc.visual;index=next(i for i,b in enumerate(view.model.blocks) if b.kind=='paragraph' and '$v$' in b.content);field=view.fields[index][0];view.active=index;field.tag_remove('sel','1.0','end');field.mark_set('insert','end-1c')
    app.insert_latex('\\cite{','audit}')
    assert doc.content().index('\\cite{audit}') < doc.content().index('\\[\n') and '\\dot{x}' in doc.content(),'Tool inserted into wrong block'
    app.set_edit_mode('Visual');view=doc.visual;equation=next(i for i,b in enumerate(view.model.blocks) if '\\boxed' in b.raw)
    view.replace_block(equation,'\\[x(t)=x_0+vt\\]')
    assert '\\[x(t)=x_0+vt\\]' in doc.content() and '\\boxed' not in doc.content()
    view=doc.visual;view.edit_title();app.update()
    dialog=next(w for w in app.winfo_children() if w.winfo_class()=='Toplevel')
    entry=next(w for w in dialog.winfo_children() if w.winfo_class()=='TEntry')
    entry.delete(0,'end');entry.insert(0,'Titre visuel corrigé')
    next(w for w in dialog.winfo_children() if getattr(w,'label','')=='Appliquer').invoke()
    assert '\\title{Titre visuel corrigé}' in doc.content() and '\\[x(t)=x_0+vt\\]' in doc.content()
    view=doc.visual;key=next(key for key,(raw,kind,index) in view.objects.items() if raw=='$v$')
    view.edit_inline(key);app.update();dialog=next(w for w in app.winfo_children() if w.winfo_class()=='Toplevel')
    text=next(w for w in dialog.winfo_children() if w.winfo_class()=='Text');text.delete('1.0','end');text.insert('1.0','$v_0$')
    next(w for w in dialog.winfo_children() if getattr(w,'label','')=='Appliquer').invoke()
    assert '$v_0$' in doc.content() and '$\\Omega$' in doc.content()
    doc.save();assert doc.path.read_text(encoding='utf-8')==doc.content()
    assert not errors,errors
    app.on_close()
print('PASS: Continuous Visual, rendered inline/display math and title, source preservation, rich edits, undo/redo, tool caret and equation replacement')
