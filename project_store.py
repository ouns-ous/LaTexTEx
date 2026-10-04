"""Persistent projects and reversible file operations for LaTexTEx."""
from __future__ import annotations
from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import uuid
import zipfile

TEXT_SUFFIXES = {'.tex', '.bib', '.sty', '.cls', '.bst', '.txt', '.md', '.csv', '.tikz', '.cfg', '.def'}
GENERATED = {'.aux', '.log', '.toc', '.out', '.nav', '.snm', '.vrb', '.fls', '.fdb_latexmk', '.bcf', '.blg', '.synctex', '.gz'}
HIDDEN_DIRS = {'.latextex', '.git', '__pycache__', '_internal', '.vendor', '.build-tools', 'build', 'dist', 'node_modules', '.venv', 'venv'}


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)


def inside(root, relative):
    relative = str(relative).replace('\\', '/')
    parts = PurePosixPath(relative).parts
    if not parts or relative.startswith('/') or any(p in {'.', '..'} or ':' in p for p in parts):
        raise ValueError('Utilisez un chemin relatif au projet, sans ../ ni lecteur Windows.')
    for part in parts:
        if any(c in part for c in '<>"|?*') or part.endswith((' ', '.')) or re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', part, re.I):
            raise ValueError('Ce nom de fichier est réservé par Windows.')
    base = Path(root).resolve()
    path = (base / relative).resolve()
    if not path.is_relative_to(base) or path == base:
        raise ValueError('Le chemin doit rester dans le projet.')
    return path


def sources(root):
    root = Path(root)
    for folder, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in HIDDEN_DIRS and not (Path(folder) / d).is_symlink())
        for name in sorted(files):
            path = Path(folder) / name
            if not path.is_symlink() and path.suffix.lower() not in GENERATED and not name.endswith(('.synctex.gz', '.run.xml')):
                yield path


class ProjectStore:
    def __init__(self, data_dir, legacy=None):
        self.root = Path(data_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index = self.root / 'projects.json'
        self.projects = []
        self.pdfs = []
        if self.index.exists():
            data = json.loads(self.index.read_text(encoding='utf-8-sig'))
            self.projects = data.get('projects', [])
            self.pdfs = data.get('pdfs', [])
        elif legacy and Path(legacy).exists():
            data = json.loads(Path(legacy).read_text(encoding='utf-8-sig'))
            for raw in reversed(data.get('recent', [])):
                path = Path(raw)
                if path.is_file() and path.suffix.lower() == '.tex':
                    self.register(path.parent, main=path.name, name=path.stem)
                elif path.is_file() and path.suffix.lower() == '.pdf':
                    self.add_pdf(path)
        self.persist()

    def persist(self):
        write_json(self.index, {'version': 2, 'projects': self.projects, 'pdfs': self.pdfs})

    def touch(self, project):
        project['modified'] = now()
        self.persist()

    def register(self, folder, main=None, name=None):
        folder = Path(folder).resolve()
        if not folder.is_dir():
            raise ValueError('Le dossier du projet est introuvable.')
        for project in self.projects:
            if Path(project['path']).resolve() == folder:
                project['state'] = 'active'
                if main:
                    project['main'] = str(inside(folder, main).relative_to(folder)).replace('\\', '/')
                self.touch(project)
                return project
        tex_files = sorted(p for p in sources(folder) if p.suffix.lower() == '.tex')
        if main is None:
            preferred = folder / 'main.tex'
            main_path = preferred if preferred.exists() else next((p for p in tex_files if '\\documentclass' in p.read_text(encoding='utf-8', errors='replace')), tex_files[0] if tex_files else None)
            main = str(main_path.relative_to(folder)).replace('\\', '/') if main_path else ''
        elif main:
            inside(folder, main)
        project = {'id': uuid.uuid4().hex, 'name': name or folder.name, 'path': str(folder), 'main': main or '', 'engine': 'pdflatex', 'bibliography': 'auto', 'state': 'active', 'created': now(), 'modified': now()}
        self.projects.append(project)
        self.persist()
        return project

    def create(self, name, text):
        name = name.strip()
        if not name:
            raise ValueError('Donnez un nom au projet.')
        slug = re.sub(r'[^\w -]', '', name, flags=re.U).strip()[:50] or 'Projet'
        folder = self.root / 'projects' / (slug + '-' + uuid.uuid4().hex[:8])
        folder.mkdir(parents=True)
        (folder / 'main.tex').write_text(text, encoding='utf-8')
        return self.register(folder, 'main.tex', name)

    def new_file(self, project, relative, content=''):
        path = inside(project['path'], relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8') as stream:
            stream.write(content)
        self.touch(project)
        return path

    def new_folder(self, project, relative):
        path = inside(project['path'], relative)
        path.mkdir(parents=True, exist_ok=False)
        self.touch(project)
        return path

    def snapshot(self, project, path):
        path = Path(path).resolve()
        base = Path(project['path']).resolve()
        if not path.is_relative_to(base):
            raise ValueError('Fichier extérieur au projet.')
        if not path.exists() or path.suffix.lower() not in TEXT_SUFFIXES:
            return
        history = base / '.latextex' / 'history'
        history.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex
        copy = history / (token + '.txt')
        copy.write_bytes(path.read_bytes())
        write_json(history / (token + '.json'), {'id': token, 'file': str(path.relative_to(base)), 'date': now()})

    def save_file(self, project, path, text):
        path = inside(project['path'], str(Path(path).resolve().relative_to(Path(project['path']).resolve())))
        encoded = text.encode('utf-8')
        if path.exists() and path.read_bytes() == encoded:
            return
        self.snapshot(project, path)
        temp = path.with_name(path.name + '.latextex-tmp')
        temp.write_bytes(encoded)
        os.replace(temp, path)
        self.touch(project)

    def history(self, project):
        folder = Path(project['path']) / '.latextex' / 'history'
        result = []
        if folder.exists():
            for path in folder.glob('*.json'):
                try:
                    result.append(json.loads(path.read_text(encoding='utf-8')))
                except (OSError, ValueError):
                    continue
        return sorted(result, key=lambda x: x['date'], reverse=True)[:200]

    def restore_version(self, project, entry):
        token = entry['id']
        if not re.fullmatch('[a-f0-9]{32}', token):
            raise ValueError('Version invalide.')
        source = Path(project['path']) / '.latextex' / 'history' / (token + '.txt')
        target = inside(project['path'], entry['file'])
        target.parent.mkdir(parents=True, exist_ok=True)
        self.save_file(project, target, source.read_text(encoding='utf-8-sig'))
        return target

    def rename_file(self, project, relative, new_relative):
        old = inside(project['path'], relative)
        new = inside(project['path'], new_relative)
        if not old.exists():
            raise FileNotFoundError(old)
        if new.exists():
            raise FileExistsError('Un fichier porte déjà ce nom.')
        new.parent.mkdir(parents=True, exist_ok=True)
        old.rename(new)
        main = project['main']
        if main == relative or main.startswith(relative.rstrip('/') + '/'):
            project['main'] = new_relative + main[len(relative):]
        comments = self.comments(project)
        changed = False
        old_key = relative.replace('\\', '/').rstrip('/')
        new_key = new_relative.replace('\\', '/').rstrip('/')
        for comment in comments:
            file = comment['file'].replace('\\', '/')
            if file == old_key or file.startswith(old_key + '/'):
                comment['file'] = new_key + file[len(old_key):]
                changed = True
        if changed:
            write_json(Path(project['path']) / '.latextex' / 'comments.json', comments)
        self.touch(project)
        return new

    def trash_file(self, project, relative):
        old = inside(project['path'], relative)
        trash = Path(project['path']) / '.latextex' / 'trash'
        trash.mkdir(parents=True, exist_ok=True)
        token = uuid.uuid4().hex
        destination = trash / token
        old.rename(destination)
        entry = {'id': token, 'file': relative, 'date': now()}
        write_json(trash / (token + '.json'), entry)
        self.touch(project)
        return entry

    def restore_file(self, project, entry):
        token = entry['id']
        if not re.fullmatch('[a-f0-9]{32}', token):
            raise ValueError('Entrée invalide.')
        target = inside(project['path'], entry['file'])
        if target.exists():
            raise FileExistsError('Un fichier existe déjà à cet emplacement.')
        folder = Path(project['path']) / '.latextex' / 'trash'
        target.parent.mkdir(parents=True, exist_ok=True)
        (folder / token).rename(target)
        (folder / (token + '.json')).unlink()
        self.touch(project)
        return target

    def trashed_files(self, project):
        folder = Path(project['path']) / '.latextex' / 'trash'
        return sorted((json.loads(p.read_text(encoding='utf-8')) for p in folder.glob('*.json')), key=lambda x: x['date'], reverse=True)

    def duplicate(self, project):
        copy = self.create(project['name'] + ' — copie', '')
        for path in sources(project['path']):
            target = inside(copy['path'], str(path.relative_to(Path(project['path']))))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
        if not (Path(project['path']) / 'main.tex').exists():
            (Path(copy['path']) / 'main.tex').unlink()
        copy.update(main=project['main'], engine=project['engine'], bibliography=project.get('bibliography', 'auto'))
        self.touch(copy)
        return copy

    def export_zip(self, project, destination):
        destination = Path(destination).resolve()
        with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
            for path in sources(project['path']):
                if path.resolve() != destination:
                    archive.write(path, path.relative_to(Path(project['path'])))

    def import_zip(self, archive_path):
        # Validate the whole archive before creating a project or extracting data.
        staging = self.root / 'projects' / ('import-' + uuid.uuid4().hex[:8])
        with zipfile.ZipFile(archive_path) as archive:
            items = archive.infolist()
            if len(items) > 10000 or sum(i.file_size for i in items) > 512 * 1024 * 1024:
                raise ValueError('Archive trop volumineuse (limite 512 Mo / 10000 fichiers).')
            targets = []
            seen = set()
            for item in items:
                if stat.S_ISLNK(item.external_attr >> 16):
                    raise ValueError('Les liens symboliques ne sont pas acceptés dans une archive.')
                raw = item.filename.rstrip('/')
                if not raw:
                    continue
                target = inside(staging, raw)
                key = str(target).casefold()
                if key in seen:
                    raise ValueError('Archive avec noms de fichiers en double.')
                seen.add(key)
                if any(part in HIDDEN_DIRS for part in PurePosixPath(raw.replace('\\', '/')).parts):
                    continue
                targets.append((item, target))
            staging.mkdir(parents=True)
            for item, target in targets:
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.open(item) as src, target.open('wb') as dst:
                        shutil.copyfileobj(src, dst)
        children = list(staging.iterdir())
        folder = children[0] if len(children) == 1 and children[0].is_dir() else staging
        return self.register(folder, name=Path(archive_path).stem)

    def add_pdf(self, path):
        path = str(Path(path).resolve())
        self.pdfs = [path] + [p for p in self.pdfs if p != path]
        self.pdfs = self.pdfs[:100]
        self.persist()

    def comments(self, project):
        path = Path(project['path']) / '.latextex' / 'comments.json'
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else []

    def add_comment(self, project, file, line, text):
        inside(project['path'], file)
        if not text.strip():
            raise ValueError('Le commentaire est vide.')
        comments = self.comments(project)
        item = {'id': uuid.uuid4().hex, 'file': file, 'line': max(1, int(line)), 'text': text.strip(), 'date': now(), 'resolved': False}
        comments.append(item)
        write_json(Path(project['path']) / '.latextex' / 'comments.json', comments)
        return item

    def resolve_comment(self, project, token, resolved):
        comments = self.comments(project)
        for item in comments:
            if item['id'] == token:
                item['resolved'] = bool(resolved)
        write_json(Path(project['path']) / '.latextex' / 'comments.json', comments)
