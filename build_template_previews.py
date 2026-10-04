"""Build bundled thumbnails and PDFs from the actual template sources."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

from project_studio import TEMPLATES, ROOT, find_engine, pymupdf

sys.stdout.reconfigure(encoding='utf-8')
destination = ROOT / 'assets' / 'templates'
destination.mkdir(parents=True, exist_ok=True)
manifest = {}
with tempfile.TemporaryDirectory(dir=ROOT) as directory:
    for index, (name, source) in enumerate(TEMPLATES.items()):
        token = hashlib.sha256(source.encode('utf-8')).hexdigest()
        folder = Path(directory) / str(index)
        folder.mkdir()
        # An empty document has no pages; its gallery shows a blank sheet.
        render_source = source
        if name == 'Document vide':
            render_source = source.replace('\\begin{document}', '\\begin{document}\n\\null', 1)
        (folder / 'main.tex').write_text(render_source, encoding='utf-8')
        engine = 'xelatex' if name == 'العربية — Article' else 'pdflatex'
        print('Rendering', name, flush=True)
        command = [find_engine(engine), '--disable-installer', '-interaction=nonstopmode', '-halt-on-error', '-no-shell-escape', 'main.tex']
        for _ in range(2):
            result = subprocess.run(command, cwd=folder, capture_output=True, timeout=60)
            if result.returncode:
                raise RuntimeError(name + '\n' + result.stdout.decode(errors='replace')[-3000:])
        pdf = folder / 'main.pdf'
        shutil.copy2(pdf, destination / (token + '.pdf'))
        with pymupdf.open(pdf) as document:
            page = document[0]
            page.get_pixmap(matrix=pymupdf.Matrix(260 / page.rect.width, 260 / page.rect.width), alpha=False).save(destination / (token + '.png'))
        manifest[name] = {'key': token, 'engine': engine, 'blank': name == 'Document vide'}
(destination / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print('Built', len(manifest), 'real template previews.')
