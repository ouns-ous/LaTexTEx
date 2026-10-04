from pathlib import Path
import tempfile,time,json
from unittest.mock import patch
from project_studio import App,ROOT
source=r'''\documentclass{article}
\usepackage[backend=biber]{biblatex}
\addbibresource{refs.bib}
\begin{document}
Biber audit \cite{audit}.
\printbibliography
\end{document}
'''
with tempfile.TemporaryDirectory(prefix='audit-biber-',dir=ROOT) as folder:
    base=Path(folder);app=App(data_dir=base/'data',legacy=base/'absent');app.withdraw();app.autosave.set(False)
    project=app.store.create('Audit Biber',source);app.store.new_file(project,'refs.bib','@book{audit,author={Donald Knuth},title={Biber Audit Reference},year={1984},publisher={Test}}')
    app.open_project(project);app.compile()
    limit=time.monotonic()+180
    while app.busy and time.monotonic()<limit:app.update();time.sleep(.05)
    assert not app.busy,'Biber audit timed out'
    if 'réussie' not in app.status.get():
        print(app.log.get('1.0','end')[-4000:]);raise AssertionError(app.status.get())
    assert 'Biber Audit Reference' in ''.join(page.get_text() for page in app.pdf)
    print('PASS: Real Biber bibliography and PDF output',flush=True)
    archive=base/'project.zip';app.store.export_zip(project,archive)
    with patch('project_studio.filedialog.askopenfilename',return_value=str(archive)):app.import_zip()
    assert app.project['id']!=project['id'] and (Path(app.project['path'])/'refs.bib').exists()
    print('PASS: Import ZIP through interface',flush=True)
    with patch('project_studio.filedialog.askdirectory',return_value=project['path']):app.import_folder()
    assert app.project['id']==project['id']
    print('PASS: Open existing project folder through interface',flush=True)
    app.save_all();app.on_close()
report=json.loads((ROOT/'audit-results.json').read_text(encoding='utf-8'));report['checks']+=['Real Biber bibliography and PDF output','Import ZIP through interface','Open existing project folder through interface'];report['passed']=len(report['checks']);(ROOT/'audit-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
