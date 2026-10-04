"""Local LaTeX editor, compiler and PDF library for Windows."""
from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

ROOT = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / '.vendor'))
import pymupdf
from PIL import Image, ImageTk

STATE = ROOT / 'workspace.json'
SAMPLE = r'''\documentclass[12pt]{article}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\title{Mon premier document}
\author{Votre nom}
\date{\today}
\begin{document}
\maketitle
\section{Bienvenue}
Voici votre espace LaTeX local. Modifiez ce texte puis cliquez sur Compiler.
\[
  E = mc^2
\]
\section{Notes}
Vos fichiers restent sur votre ordinateur.
\end{document}
'''


def find_engine(name):
    found = shutil.which(name)
    if found:
        return found
    for base in (Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs' / 'MiKTeX',
                 Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'MiKTeX'):
        exe = base / 'miktex' / 'bin' / 'x64' / (name + '.exe')
        if exe.exists():
            return str(exe)
    return None


class Studio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('LaTexTEx — Atelier LaTeX local')
        if (ROOT / 'app.ico').exists():
            self.iconbitmap(str(ROOT / 'app.ico'))
        self.geometry(f'{min(1420, self.winfo_screenwidth() - 70)}x{min(860, self.winfo_screenheight() - 100)}+25+25')
        self.minsize(1000, 640)
        self.configure(bg='#101827')
        self.path = None
        self.pdf = None
        self.page = 0
        self.zoom = 1.0
        self.busy = False
        self.proc = None
        self.events = queue.Queue()
        self.recent = []
        self.items = {}
        self.render_timer = None
        self.highlight_timer = None
        self.closing = False
        try:
            self.recent = json.loads(STATE.read_text(encoding='utf-8')).get('recent', [])
        except (OSError, ValueError):
            pass
        self.build_ui()
        self.set_text(SAMPLE)
        self.refresh_library()
        latest = next((Path(p) for p in self.recent if Path(p).suffix.lower() == '.tex' and Path(p).exists()), None)
        if latest:
            self.load_tex(latest)
        self.bind('<Control-s>', lambda e: self.save())
        self.bind('<Control-o>', lambda e: self.open_file())
        self.bind('<Control-n>', lambda e: self.new_file())
        self.bind('<F5>', lambda e: self.compile())
        self.protocol('WM_DELETE_WINDOW', self.on_close)
        self.after(100, self.poll)

    def build_ui(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TButton', font=('Segoe UI', 10), padding=(12, 7))
        style.configure('Treeview', font=('Segoe UI', 10), rowheight=30,
                        background='#172234', foreground='#dce5ef', fieldbackground='#172234', borderwidth=0)
        style.map('Treeview', background=[('selected', '#285b85')])
        style.configure('TCombobox', padding=5)
        top = tk.Frame(self, bg='#101827', padx=18, pady=12)
        top.pack(fill='x')
        tk.Label(top, text='LaTexTEx', font=('Segoe UI', 21, 'bold'), fg='#f2f6fc', bg='#101827').pack(side='left')
        tk.Label(top, text='ATELIER LOCAL', font=('Segoe UI', 9), fg='#83c7d8', bg='#101827', padx=15).pack(side='left')
        self.compile_button = ttk.Button(top, text='▶ Compiler  F5', command=self.compile)
        self.compile_button.pack(side='right', padx=5)
        self.engine = tk.StringVar(value='pdflatex')
        ttk.Combobox(top, textvariable=self.engine, values=['pdflatex', 'xelatex', 'lualatex'], state='readonly', width=12).pack(side='right', padx=8)
        ttk.Button(top, text='Enregistrer', command=self.save).pack(side='right', padx=5)
        ttk.Button(top, text='Ouvrir', command=self.open_file).pack(side='right', padx=5)
        ttk.Button(top, text='+ Nouveau', command=self.new_file).pack(side='right', padx=5)
        panes = tk.PanedWindow(self, orient='horizontal', bg='#273449', sashwidth=6, borderwidth=0)
        panes.pack(fill='both', expand=True, padx=12)
        library = tk.Frame(panes, bg='#172234')
        panes.add(library, minsize=180, width=225)
        tk.Label(library, text='BIBLIOTHÈQUE', bg='#172234', fg='#91a7c2', font=('Segoe UI', 10, 'bold'), pady=16).pack(fill='x')
        self.tree = ttk.Treeview(library, show='tree', selectmode='browse')
        self.tree.pack(fill='both', expand=True, padx=8)
        self.tree.bind('<Double-1>', self.open_recent)
        self.tree.bind('<Return>', self.open_recent)
        ttk.Button(library, text='+ Ajouter un PDF', command=self.import_pdf).pack(fill='x', padx=10, pady=6)
        tk.Label(library, text='Double-clic pour ouvrir\nCtrl+S  •  Ctrl+O  •  F5', font=('Segoe UI', 9), fg='#91a7c2', bg='#172234', pady=14).pack()
        middle = tk.PanedWindow(panes, orient='vertical', bg='#273449', sashwidth=5)
        panes.add(middle, minsize=330, width=590)
        edit_frame = tk.Frame(middle, bg='#172234')
        middle.add(edit_frame, minsize=250, stretch='always')
        self.filename = tk.StringVar(value='Nouveau document')
        tk.Label(edit_frame, textvariable=self.filename, anchor='w', font=('Segoe UI', 10), fg='#dce5ef', bg='#172234', padx=12, pady=10).pack(fill='x')
        text_frame = tk.Frame(edit_frame, bg='#111b2b')
        text_frame.pack(fill='both', expand=True)
        self.lines = tk.Text(text_frame, width=4, padx=5, borderwidth=0, bg='#172234', fg='#627c99', font=('Consolas', 11), state='disabled', takefocus=False)
        self.lines.pack(side='left', fill='y')
        scrollbar = ttk.Scrollbar(text_frame, orient='vertical', command=self.scroll_editor)
        scrollbar.pack(side='right', fill='y')
        self.editor = tk.Text(text_frame, undo=True, wrap='none', font=('Consolas', 11), bg='#111b2b', fg='#dce5ef', insertbackground='#ffffff', selectbackground='#285b85', padx=12, pady=8, borderwidth=0, tabs=('4c',))
        self.editor.pack(fill='both', expand=True)
        self.editor.configure(yscrollcommand=lambda a, b: (scrollbar.set(a, b), self.lines.yview_moveto(a)))
        xscroll = ttk.Scrollbar(edit_frame, orient='horizontal', command=self.editor.xview)
        xscroll.pack(fill='x')
        self.editor.configure(xscrollcommand=xscroll.set)
        for name, color in [('command', '#7dd3fc'), ('comment', '#6d927f'), ('brace', '#e7b76d')]:
            self.editor.tag_configure(name, foreground=color)
        self.editor.bind('<<Modified>>', self.changed)
        self.editor.bind('<KeyRelease>', self.changed)
        self.editor.bind('<Tab>', self.insert_tab)
        log_frame = tk.Frame(middle, bg='#172234')
        middle.add(log_frame, minsize=90, height=145, stretch='never')
        tk.Label(log_frame, text='COMPILATION & ERREURS', anchor='w', font=('Segoe UI', 9, 'bold'), bg='#172234', fg='#91a7c2', padx=12, pady=7).pack(fill='x')
        self.log = tk.Text(log_frame, height=6, wrap='word', font=('Consolas', 9), bg='#0c1421', fg='#aebfd3', borderwidth=0, padx=12, pady=6, state='disabled')
        self.log.pack(fill='both', expand=True)
        right = tk.Frame(panes, bg='#e2e8f0')
        panes.add(right, minsize=330, width=555)
        pdf_toolbar = tk.Frame(right, bg='#172234', padx=7, pady=6)
        pdf_toolbar.pack(fill='x')
        ttk.Button(pdf_toolbar, text='‹', width=3, command=lambda: self.turn_page(-1)).pack(side='left')
        self.page_label = tk.StringVar(value='PDF')
        tk.Label(pdf_toolbar, textvariable=self.page_label, bg='#172234', fg='#e2e8f0', width=12).pack(side='left')
        ttk.Button(pdf_toolbar, text='›', width=3, command=lambda: self.turn_page(1)).pack(side='left')
        ttk.Button(pdf_toolbar, text='−', width=3, command=lambda: self.change_zoom(-0.2)).pack(side='right')
        ttk.Button(pdf_toolbar, text='+', width=3, command=lambda: self.change_zoom(0.2)).pack(side='right')
        ttk.Button(pdf_toolbar, text='Adapter', command=self.fit_page).pack(side='right', padx=4)
        pdf_body = tk.Frame(right)
        pdf_body.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(pdf_body, bg='#ccd5e1', highlightthickness=0)
        ybar = ttk.Scrollbar(pdf_body, orient='vertical', command=self.canvas.yview)
        ybar.pack(side='right', fill='y')
        self.canvas.pack(fill='both', expand=True)
        xbar = ttk.Scrollbar(right, orient='horizontal', command=self.canvas.xview)
        xbar.pack(fill='x')
        self.canvas.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.canvas.bind('<MouseWheel>', lambda e: self.canvas.yview_scroll(int(-e.delta / 120) * 3, 'units'))
        self.canvas.bind('<Configure>', self.schedule_render)
        self.canvas.create_text(200, 160, text='Votre PDF apparaîtra ici\naprès la compilation.', fill='#56667b', font=('Segoe UI', 13), justify='center')
        self.status = tk.StringVar(value='Prêt • Les fichiers restent sur votre ordinateur')
        tk.Label(self, textvariable=self.status, anchor='w', bg='#101827', fg='#a4b6ce', font=('Segoe UI', 9), padx=16, pady=9).pack(fill='x')

    def insert_tab(self, event):
        self.editor.insert('insert', '    ')
        return 'break'

    def scroll_editor(self, *args):
        self.editor.yview(*args)
        self.lines.yview(*args)

    def changed(self, event=None):
        if not self.editor.edit_modified():
            return
        self.title('LaTexTEx — ' + (self.path.name if self.path else 'Nouveau document') + ' *')
        if self.highlight_timer:
            self.after_cancel(self.highlight_timer)
        self.highlight_timer = self.after(200, self.highlight)

    def highlight(self):
        self.highlight_timer = None
        source = self.editor.get('1.0', 'end-1c')
        for tag in ('command', 'comment', 'brace'):
            self.editor.tag_remove(tag, '1.0', 'end')
        for tag, pattern in [('command', r'\\[a-zA-Z@]+\*?'), ('brace', r'[{}]'), ('comment', r'(?<!\\)%[^\n]*')]:
            for match in re.finditer(pattern, source):
                self.editor.tag_add(tag, f'1.0+{match.start()}c', f'1.0+{match.end()}c')
        self.editor.tag_raise('comment')
        self.lines.configure(state='normal')
        self.lines.delete('1.0', 'end')
        self.lines.insert('1.0', '\n'.join(str(i) for i in range(1, source.count('\n') + 2)))
        self.lines.configure(state='disabled')
        self.lines.yview_moveto(self.editor.yview()[0])

    def set_text(self, text):
        self.editor.delete('1.0', 'end')
        self.editor.insert('1.0', text)
        self.editor.edit_reset()
        self.editor.edit_modified(False)
        self.highlight()
        self.title('LaTexTEx — ' + (self.path.name if self.path else 'Nouveau document'))
        self.filename.set(str(self.path) if self.path else 'Nouveau document • .tex')

    def confirm_changes(self):
        if not self.editor.edit_modified():
            return True
        answer = messagebox.askyesnocancel('Document modifié', 'Enregistrer vos modifications ?')
        return self.save() if answer else answer is not None

    def new_file(self):
        if self.confirm_changes():
            self.path = None
            self.set_text(SAMPLE)
            self.clear_pdf()

    def open_file(self):
        path = filedialog.askopenfilename(filetypes=[('Documents LaTeX', '*.tex'), ('Tous les fichiers', '*.*')])
        if path:
            self.load_tex(Path(path))

    def load_tex(self, path):
        if not self.confirm_changes():
            return
        try:
            text = path.read_text(encoding='utf-8-sig')
        except (OSError, UnicodeError) as exc:
            messagebox.showerror('Ouverture impossible', str(exc))
            return
        self.path = path.resolve()
        self.set_text(text)
        self.remember(self.path)
        self.clear_pdf()
        pdf = self.path.with_suffix('.pdf')
        if pdf.exists():
            self.load_pdf(pdf)

    def save(self):
        if self.path is None:
            selected = filedialog.asksaveasfilename(defaultextension='.tex', initialdir=str(ROOT / 'documents'), filetypes=[('Document LaTeX', '*.tex')])
            if not selected:
                return False
            self.path = Path(selected).resolve()
        try:
            self.path.write_text(self.editor.get('1.0', 'end-1c'), encoding='utf-8')
        except OSError as exc:
            messagebox.showerror('Sauvegarde impossible', str(exc))
            return False
        self.editor.edit_modified(False)
        self.filename.set(str(self.path))
        self.title('LaTexTEx — ' + self.path.name)
        self.remember(self.path)
        self.status.set('Enregistré • ' + str(self.path))
        return True

    def remember(self, path):
        value = str(path.resolve())
        self.recent = [value] + [p for p in self.recent if p != value]
        self.recent = self.recent[:60]
        try:
            STATE.write_text(json.dumps({'recent': self.recent}, ensure_ascii=False, indent=2), encoding='utf-8')
        except OSError as exc:
            self.status.set('Bibliothèque non enregistrée : ' + str(exc))
        self.refresh_library()

    def refresh_library(self):
        self.tree.delete(*self.tree.get_children())
        self.items = {}
        for label, suffix in [('PROJETS LATEX', '.tex'), ('PDF RÉCENTS', '.pdf')]:
            parent = self.tree.insert('', 'end', text=label, open=True)
            for raw in self.recent:
                path = Path(raw)
                if path.suffix.lower() == suffix:
                    item = self.tree.insert(parent, 'end', text=('  ' if path.exists() else '⚠ ') + path.name)
                    self.items[item] = path

    def open_recent(self, event=None):
        selected = self.tree.selection()
        path = self.items.get(selected[0]) if selected else None
        if path:
            if path.suffix.lower() == '.tex':
                self.load_tex(path)
            else:
                self.load_pdf(path)

    def import_pdf(self):
        selected = filedialog.askopenfilename(filetypes=[('PDF', '*.pdf')])
        if selected:
            self.load_pdf(Path(selected))

    def clear_pdf(self):
        if self.pdf:
            self.pdf.close()
        self.pdf = None
        self.canvas.delete('all')
        self.page_label.set('PDF')

    def load_pdf(self, path):
        try:
            # Read into memory so the compiler can replace the file on Windows.
            document = pymupdf.open(stream=path.read_bytes(), filetype='pdf')
            if document.needs_pass or document.page_count == 0:
                document.close()
                raise ValueError('PDF protégé ou sans pages.')
        except Exception as exc:
            messagebox.showerror('PDF impossible à ouvrir', str(exc))
            return
        old_page = self.page
        self.clear_pdf()
        self.pdf = document
        self.page = min(old_page, document.page_count - 1)
        self.remember(path)
        self.render_pdf()

    def schedule_render(self, event=None):
        if self.render_timer:
            self.after_cancel(self.render_timer)
        self.render_timer = self.after(150, self.render_pdf)

    def render_pdf(self):
        self.render_timer = None
        if not self.pdf:
            return
        page = self.pdf[self.page]
        scale = min(3.0, max(0.2, (max(300, self.canvas.winfo_width()) - 30) / page.rect.width * self.zoom))
        pix = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False)
        page_image = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
        if getattr(self, 'pdf_dark', False):
            from PIL import ImageOps
            page_image = ImageOps.invert(page_image)
        self.photo = ImageTk.PhotoImage(page_image)
        self.canvas.delete('all')
        x = max(15, (self.canvas.winfo_width() - pix.width) // 2)
        self.canvas.create_image(x, 15, image=self.photo, anchor='nw')
        self.canvas.configure(scrollregion=(0, 0, max(self.canvas.winfo_width(), pix.width + 30), pix.height + 30))
        self.page_label.set(f'{self.page + 1} / {self.pdf.page_count}')

    def turn_page(self, delta):
        if self.pdf:
            self.page = max(0, min(self.pdf.page_count - 1, self.page + delta))
            self.canvas.yview_moveto(0)
            self.render_pdf()

    def change_zoom(self, delta):
        self.zoom = max(0.4, min(3.0, self.zoom + delta))
        self.render_pdf()

    def fit_page(self):
        self.zoom = 1.0
        self.render_pdf()

    def set_log(self, text):
        self.log.configure(state='normal')
        self.log.delete('1.0', 'end')
        self.log.insert('1.0', text)
        self.log.see('end')
        self.log.configure(state='disabled')

    def compile(self):
        if self.busy or not self.save():
            return
        exe = find_engine(self.engine.get())
        if not exe:
            messagebox.showerror('Compilateur absent', 'Installez MiKTeX ou TeX Live pour compiler ce document.')
            return
        self.busy = True
        self.compile_button.configure(state='disabled', text='Compilation…')
        self.status.set('Compilation en cours • ' + self.path.name)
        self.set_log('Compilation en cours…\nLa première utilisation peut nécessiter des packages MiKTeX.')
        path = self.path

        def worker():
            output = ''
            code = 1
            try:
                for _ in range(2):
                    self.proc = subprocess.Popen([exe, '-interaction=nonstopmode', '-halt-on-error', '-synctex=1', '-no-shell-escape', path.name], cwd=str(path.parent), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                    if self.closing:
                        self.proc.terminate()
                    try:
                        data, _ = self.proc.communicate(timeout=180)
                    except subprocess.TimeoutExpired:
                        self.proc.kill()
                        data, _ = self.proc.communicate()
                        output += data.decode('utf-8', errors='replace') + '\nDélai dépassé (180 s). Vérifiez MiKTeX Console et les packages.'
                        code = 1
                        break
                    output += data.decode('utf-8', errors='replace') + '\n'
                    code = self.proc.returncode
                    if code:
                        break
            except Exception as exc:
                output += str(exc)
            finally:
                self.proc = None
                self.events.put((code, output, path))

        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            code, output, path = self.events.get_nowait()
            self.busy = False
            self.compile_button.configure(state='normal', text='▶ Compiler  F5')
            self.set_log(output)
            pdf = path.with_suffix('.pdf')
            if code == 0 and pdf.exists():
                self.status.set('Compilation réussie • ' + pdf.name)
                if self.path == path:
                    self.load_pdf(pdf)
            else:
                self.status.set('Échec de compilation • Consultez les erreurs ci-dessus')
        except queue.Empty:
            pass
        self.after(100, self.poll)

    def on_close(self):
        if not self.confirm_changes():
            return
        self.closing = True
        if self.proc:
            self.proc.terminate()
        self.clear_pdf()
        self.destroy()


if __name__ == '__main__':
    (ROOT / 'documents').mkdir(exist_ok=True)
    app = Studio()
    if '--self-test' in sys.argv:
        app.withdraw()
        app.load_pdf(ROOT / 'documents' / 'Bienvenue.pdf')
        app.update()
        assert app.pdf and app.pdf.page_count > 0
        assert app.photo.width() > 100
        assert find_engine('pdflatex')
        (ROOT / 'self-test.json').write_text(json.dumps({'pdf_pages': app.pdf.page_count, 'render_width': app.photo.width(), 'compiler': find_engine('pdflatex'), 'frozen': bool(getattr(sys, 'frozen', False))}), encoding='utf-8')
        app.on_close()
    else:
        app.mainloop()
