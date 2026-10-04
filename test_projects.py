import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from project_store import ProjectStore, inside


class ProjectsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=Path(__file__).parent)
        self.base = Path(self.temp.name)
        self.store = ProjectStore(self.base / 'data')
        self.project = self.store.create('Mon projet', '\\documentclass{article}\n')

    def tearDown(self):
        self.temp.cleanup()

    def test_files_history_trash_and_restart(self):
        path = self.store.new_file(self.project, 'chapitres/intro.tex', 'Version 1')
        self.store.save_file(self.project, path, 'Version 2')
        version = self.store.history(self.project)[0]
        self.store.restore_version(self.project, version)
        self.assertEqual(path.read_text(encoding='utf-8'), 'Version 1')
        entry = self.store.trash_file(self.project, 'chapitres/intro.tex')
        self.assertFalse(path.exists())
        self.store.restore_file(self.project, entry)
        self.assertTrue(path.exists())
        restarted = ProjectStore(self.base / 'data')
        self.assertEqual(restarted.projects[0]['id'], self.project['id'])
        self.assertEqual(restarted.projects[0]['main'], 'main.tex')

    def test_main_rename_directory_and_duplicate(self):
        self.store.new_folder(self.project, 'src')
        self.store.rename_file(self.project, 'main.tex', 'src/document.tex')
        self.store.rename_file(self.project, 'src', 'source')
        self.assertEqual(self.project['main'], 'source/document.tex')
        copy = self.store.duplicate(self.project)
        self.assertNotEqual(copy['path'], self.project['path'])
        self.assertTrue((Path(copy['path']) / 'source/document.tex').exists())
        self.assertEqual(copy['main'], 'source/document.tex')

    def test_zip_round_trip_and_wrapped_project(self):
        self.store.new_file(self.project, 'sections/a.tex', 'Section A')
        archive = self.base / 'export.zip'
        self.store.export_zip(self.project, archive)
        imported = self.store.import_zip(archive)
        self.assertEqual(imported['main'], 'main.tex')
        self.assertEqual((Path(imported['path']) / 'sections/a.tex').read_text(), 'Section A')
        wrapped = self.base / 'wrapped.zip'
        with zipfile.ZipFile(wrapped, 'w') as z:
            z.writestr('project/source.tex', '\\documentclass{report}\n')
        self.assertEqual(self.store.import_zip(wrapped)['main'], 'source.tex')

    def test_unsafe_paths_and_zip_rejected_before_extraction(self):
        for name in ('../outside.tex', 'C:/outside.tex', '/absolute.tex', 'NUL.tex'):
            with self.assertRaises(ValueError):
                inside(self.project['path'], name)
        archive = self.base / 'bad.zip'
        with zipfile.ZipFile(archive, 'w') as z:
            z.writestr('main.tex', 'valid')
            z.writestr('../escape.tex', 'invalid')
        before = len(list((self.store.root / 'projects').iterdir()))
        with self.assertRaises(ValueError):
            self.store.import_zip(archive)
        self.assertEqual(len(list((self.store.root / 'projects').iterdir())), before)

    def test_migration_preserves_old_files_and_pdf_library(self):
        tex = self.base / 'old.tex'
        pdf = self.base / 'old.pdf'
        tex.write_text('legacy', encoding='utf-8')
        pdf.write_bytes(b'legacy pdf')
        legacy = self.base / 'workspace.json'
        legacy.write_text(json.dumps({'recent': [str(tex), str(pdf)]}))
        migrated = ProjectStore(self.base / 'migrated', legacy)
        self.assertEqual(migrated.projects[0]['main'], 'old.tex')
        self.assertEqual(migrated.pdfs, [str(pdf)])
        self.assertEqual(tex.read_text(), 'legacy')

    def test_comments_persist_and_resolve(self):
        item = self.store.add_comment(self.project, 'main.tex', 3, 'Clarifier cette équation')
        self.store.resolve_comment(self.project, item['id'], True)
        restarted = ProjectStore(self.base / 'data')
        comments = restarted.comments(restarted.projects[0])
        self.assertEqual(comments[0]['text'], 'Clarifier cette équation')
        self.assertTrue(comments[0]['resolved'])
        with self.assertRaises(ValueError):
            self.store.add_comment(self.project, '../outside.tex', 1, 'Invalid')

    def test_comments_follow_renamed_file_and_folder(self):
        self.store.new_file(self.project, 'src/intro.tex', 'Text')
        self.store.add_comment(self.project, 'src/intro.tex', 1, 'Note')
        self.store.rename_file(self.project, 'src/intro.tex', 'src/chapter.tex')
        self.assertEqual(self.store.comments(self.project)[0]['file'].replace('\\', '/'), 'src/chapter.tex')
        self.store.rename_file(self.project, 'src', 'chapters')
        self.assertEqual(self.store.comments(self.project)[0]['file'].replace('\\', '/'), 'chapters/chapter.tex')


if __name__ == '__main__':
    unittest.main()
