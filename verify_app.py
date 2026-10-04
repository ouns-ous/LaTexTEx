"""Smoke test: actual compilation, PDF rendering and recent-file persistence."""
import time
from pathlib import Path
from latex_studio import Studio, ROOT, SAMPLE

folder = ROOT / 'documents'
folder.mkdir(exist_ok=True)
sample = folder / 'Bienvenue.tex'
if not sample.exists():
    sample.write_text(SAMPLE, encoding='utf-8')
app = Studio()
app.load_tex(sample)
app.update()
app.compile()
deadline = time.monotonic() + 240
result = []

def check():
    if not app.busy:
        if not app.pdf:
            result.append(app.log.get('1.0', 'end'))
        else:
            assert app.pdf.page_count >= 1
            assert str(sample.resolve()) in app.recent
            app.change_zoom(0.2)
            app.fit_page()
            app.update()
            assert app.photo.width() > 100 and app.photo.height() > 100
        app.on_close()
    elif time.monotonic() > deadline:
        result.append('Compilation timed out')
        app.on_close()
    else:
        app.after(200, check)

app.after(200, check)
app.mainloop()
if result:
    raise RuntimeError(result[0])
print('PASS: real LaTeX compile, PDF rendering, zoom and library persistence')
