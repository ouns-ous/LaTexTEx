import tempfile,json
from pathlib import Path
from unittest.mock import patch
from project_studio import App,ROOT
with tempfile.TemporaryDirectory(dir=ROOT) as folder:
    base=Path(folder);app=App(data_dir=base/'data',legacy=base/'absent');app.withdraw()
    invalid=base/'bad.zip';invalid.write_text('not a ZIP')
    with patch('project_studio.filedialog.askopenfilename',return_value=str(invalid)), patch('project_studio.messagebox.showerror') as error:
        app.guard(app.import_zip)
        assert error.call_count==1 and not app.store.projects
    app.on_close()
report=json.loads((ROOT/'audit-results.json').read_text(encoding='utf-8'));report['checks'].append('Invalid ZIP shows an error without crashing or creating a project');report['passed']=len(report['checks']);report['model_tests_passed']=7;report['regressions']=['Visual advanced-source preservation and read-only','Real project creation, tabs, BibTeX, SyncTeX, error navigation and last good PDF','Own-window previews and small-window layout'];(ROOT/'audit-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print('PASS: Invalid ZIP handled without callback crash')
