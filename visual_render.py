"""Local asynchronous LaTeX previews for the Visual editor."""
import hashlib, os, queue, subprocess, tempfile, threading
from pathlib import Path
from PIL import Image, ImageChops
from latex_studio import find_engine, pymupdf

class PreviewRenderer:
    def __init__(self, project, source):
        self.project, self.source = dict(project), source
        self.jobs, self.results = queue.Queue(), queue.Queue()
        self.closed = threading.Event()
        self.proc = None
        self.cache = Path(project['path']) / '.latextex' / 'visual-cache'
        self.cache.mkdir(parents=True, exist_ok=True)
        threading.Thread(target=self.worker, daemon=True).start()

    def request(self, token, raw, inline=False):
        self.jobs.put((token, raw, inline))

    def worker(self):
        while not self.closed.is_set():
            try: token, raw, inline = self.jobs.get(timeout=.2)
            except queue.Empty: continue
            if self.closed.is_set(): break
            try:
                image = self.render(raw, inline)
                if not self.closed.is_set(): self.results.put((token, image, None))
            except Exception as exc:
                if not self.closed.is_set(): self.results.put((token, None, str(exc)))

    def render(self, raw, inline):
        import re
        engine = self.project.get('engine', 'pdflatex')
        exe = find_engine(engine)
        if not exe: raise ValueError('Compilateur LaTeX introuvable.')
        preamble = self.source.split('\\begin{document}', 1)[0] if '\\begin{document}' in self.source else ''
        if not preamble:
            main = Path(self.project['path']) / self.project.get('main', 'main.tex')
            if main.exists(): preamble = main.read_text(encoding='utf-8-sig').split('\\begin{document}', 1)[0]
        preamble = re.sub(r'\\documentclass(?:\[[^\]]*\])?\{[^}]+\}', '', preamble)
        packages = ''.join('\\usepackage{' + name + '}\n' for name in ('amsmath','amssymb') if not re.search(r'\\usepackage(?:\[[^\]]*\])?\{[^}]*\b'+name+r'\b',preamble))
        document = '\\documentclass[12pt]{article}\n' + packages + preamble + '\n\\begin{document}\n\\pagestyle{empty}\n' + raw + '\n\\thispagestyle{empty}\n\\end{document}\n'
        key = hashlib.sha256((engine+document).encode()).hexdigest()
        target = self.cache / (key+'.png')
        if target.exists():
            with Image.open(target) as image: return image.copy()
        exe_args = [exe, '-interaction=nonstopmode', '-halt-on-error', '-no-shell-escape', 'preview.tex']
        if 'miktex' in exe.lower(): exe_args.insert(1, '--disable-installer')
        environment=os.environ.copy();root=Path(self.project['path'])
        environment['TEXINPUTS']=str(root)+'//'+os.pathsep+environment.get('TEXINPUTS','')
        with tempfile.TemporaryDirectory(prefix='latextex-visual-') as folder:
            folder=Path(folder);(folder/'preview.tex').write_text(document,encoding='utf-8')
            if self.closed.is_set(): raise RuntimeError('Aperçu annulé')
            self.proc=subprocess.Popen(exe_args,cwd=folder,env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            try:
                if self.closed.is_set(): self.proc.terminate()
                output,_=self.proc.communicate(timeout=20)
                if self.proc.returncode: raise ValueError('Aperçu indisponible : ' + output.decode('utf-8', errors='replace')[-1600:])
            except subprocess.TimeoutExpired:
                self.proc.kill();self.proc.communicate();raise ValueError('Aperçu trop long à calculer.')
            finally: self.proc=None
            pdf=pymupdf.open(folder/'preview.pdf')
            try:
                pix=pdf[0].get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False)
                image=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
            finally: pdf.close()
            box=ImageChops.difference(image,Image.new('RGB',image.size,'white')).getbbox()
            if not box: raise ValueError('Ce bloc ne produit pas de contenu visible.')
            left,top,right,bottom=box
            image=image.crop((max(0,left-4),max(0,top-4),min(image.width,right+4),min(image.height,bottom+4)))
            image.save(target)
            return image

    def close(self):
        self.closed.set()
        proc=self.proc
        if proc:
            try: proc.terminate()
            except OSError: pass
