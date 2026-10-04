"""LaTexTEx 2: project dashboard and multi-file local LaTeX workspace."""
from __future__ import annotations
from datetime import datetime
import json
import difflib
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import zipfile
import tkinter as tk
from tkinter import font as tkfont
from tkinter import filedialog, messagebox, simpledialog, ttk

from latex_studio import ROOT, SAMPLE, Studio, find_engine, pymupdf, Image, ImageTk
from project_store import ProjectStore, TEXT_SUFFIXES, HIDDEN_DIRS, sources, inside, write_json

from soft_ui import SoftDialog, SoftCard
from ui_icons import ICONS, TIPS, CAPTIONS, draw_icon

BG = '#f3f6fa'
PANEL = '#ffffff'
GREEN = '#07845e'
FG = '#203149'
MUTED = '#728198'
NAV = '#182a38'


class ModernButton(tk.Canvas):
    """Flat, rounded, keyboard-accessible buttons with consistent hover states."""
    def __init__(self, parent, text, command, accent=False, width=None):
        self.label, self.action = text, command
        self.icon_name = ICONS.get(text)
        self.icon_caption = ''
        if text in CAPTIONS:
            self.icon_name, self.icon_caption = CAPTIONS[text]
        self.tooltip = TIPS.get(self.icon_name, '')
        self.accent, self.variant, self.selected = accent, 'normal', False
        self.hover, self.disabled, self.small = False, False, False
        self.tip, self.tip_timer = None, None
        self.fixed_width = width
        self.face = tkfont.Font(family='Segoe UI', size=11, weight='bold' if accent else 'normal')
        try:
            background = parent.cget('bg')
        except tk.TclError:
            background = PANEL
        super().__init__(parent, bg=background, highlightthickness=0, borderwidth=0, takefocus=1, cursor='hand2')
        self.resize()
        self.bind('<Configure>', lambda e: self.draw())
        self.bind('<Enter>', lambda e: self.set_hover(True))
        self.bind('<Leave>', lambda e: self.set_hover(False))
        self.bind('<Button-1>', lambda e: self.invoke())
        self.bind('<Return>', lambda e: self.invoke())
        self.bind('<space>', lambda e: self.invoke())
        self.bind('<FocusIn>', lambda e: self.draw())
        self.bind('<FocusOut>', lambda e: self.draw())
        self.bind('<Destroy>', lambda e: self.hide_tip())

    def resize(self):
        width = self.fixed_width * 8 + 20 if self.fixed_width else (self.face.measure(self.icon_caption) + 42 if self.icon_caption else 36 if self.icon_name else self.face.measure(self.label) + (16 if self.small else 32))
        super().configure(width=width, height=32 if self.small else 42)
        self.draw()

    def configure(self, cnf=None, **kwargs):
        if cnf:
            kwargs.update(cnf)
        if 'text' in kwargs:
            self.label = kwargs.pop('text')
            self.icon_name = ICONS.get(self.label)
            self.icon_caption = ''
            self.tooltip = TIPS.get(self.icon_name, '')
        if 'state' in kwargs:
            self.disabled = kwargs.pop('state') == 'disabled'
        if 'style' in kwargs:
            style = kwargs.pop('style')
            self.small = style == 'Mini.TButton'
            self.variant = 'nav' if style == 'Nav.TButton' else self.variant
            self.face.configure(size=10 if self.small else 11)
        if kwargs:
            super().configure(**kwargs)
        self.resize()
    config = configure

    def cget(self, key):
        return self.label if key == 'text' else super().cget(key)

    def invoke(self):
        if not self.disabled:
            self.focus_set()
            return self.action()

    def set_hover(self, value):
        self.hover = value
        self.draw()
        self.hide_tip()
        if value and self.tooltip:
            self.tip_timer = self.after(550, self.show_tip)

    def hide_tip(self):
        if self.tip_timer:
            self.after_cancel(self.tip_timer)
            self.tip_timer = None
        if self.tip:
            self.tip.destroy()
            self.tip = None

    def show_tip(self):
        self.tip_timer = None
        description = self.tooltip
        self.tip = tk.Toplevel(self)
        self.tip.overrideredirect(True)
        self.tip.geometry(f'+{self.winfo_rootx()}+{self.winfo_rooty() + self.winfo_height() + 7}')
        tk.Label(self.tip, text=description, bg=NAV, fg='white', font=('Segoe UI', 10), padx=12, pady=7).pack()

    def draw(self):
        self.delete('all')
        width, height = max(self.winfo_width(), self.winfo_reqwidth()), max(self.winfo_height(), self.winfo_reqheight())
        fill, ink, border = ('#edf3f7' if self.hover else PANEL), FG, '#dce5ee'
        if self.variant == 'nav':
            fill, ink, border = ('#28414f' if self.hover else NAV), '#d1dce5', NAV
        if self.accent or self.selected:
            fill, ink, border = ('#096f52' if self.hover else GREEN), 'white', GREEN
        if self.disabled:
            fill, ink, border = '#e4ece9', '#8d9d96', '#e4ece9'
        if self.focus_get() == self:
            border = '#58bfa5'
        radius = 14 if not self.small else 9
        points = [2+radius,2,width-2-radius,2,width-2,2,width-2,2+radius,width-2,height-2-radius,width-2,height-2,width-2-radius,height-2,2+radius,height-2,2,height-2,2,height-2-radius,2,2+radius,2,2]
        self.create_polygon(points, smooth=True, splinesteps=20, fill=fill, outline=border)
        if self.icon_name:
            draw_icon(self, self.icon_name, 17 if self.icon_caption else width/2, height/2, ink)
            if self.icon_caption:
                self.create_text(32, height/2, text=self.icon_caption, font=self.face, fill=ink, anchor='w')
        else:
            self.create_text(width/2, height/2, text=self.label, font=self.face, fill=ink)

TEMPLATES = {
    'Article': SAMPLE,
    'Document vide': '\\documentclass{article}\n\\begin{document}\n\n\\end{document}\n',
    'Rapport': r'''\documentclass[12pt]{report}
\usepackage[T1]{fontenc}
\title{Mon rapport}
\author{Votre nom}
\begin{document}
\maketitle
\tableofcontents
\chapter{Introduction}
Votre texte ici.
\end{document}
''',
    'Présentation': r'''\documentclass{beamer}
\title{Ma présentation}
\author{Votre nom}
\begin{document}
\frame{\titlepage}
\begin{frame}{Introduction}
Votre contenu ici.
\end{frame}
\end{document}
''',
}


from template_catalog import EXTRA_TEMPLATES, DESCRIPTIONS, preview_asset
TEMPLATES.update(EXTRA_TEMPLATES)


class Document:
    def __init__(self, app, path):
        self.app, self.path = app, Path(path).resolve()
        self.saved = self.path.read_text(encoding='utf-8-sig')
        self.dirty = False
        self.timer = None
        self.frame = tk.Frame(app.tabs, bg='#fafbfc')
        self.visual = None
        self.mode_buttons = app.build_document_toolbar(self.frame)
        self.body = tk.Frame(self.frame, bg=PANEL)
        self.body.pack(fill='both', expand=True)
        self.lines = tk.Text(self.body, width=4, padx=5, borderwidth=0, bg='#edf0f4', fg='#8792a2', font=('Consolas', 11), state='disabled', takefocus=False)
        self.lines.pack(side='left', fill='y')
        scroll = ttk.Scrollbar(self.body, orient='vertical')
        scroll.pack(side='right', fill='y')
        bottom = ttk.Scrollbar(self.body, orient='horizontal')
        bottom.pack(side='bottom', fill='x')
        self.text = tk.Text(self.body, wrap='none', undo=True, font=('Consolas', 11), bg='#fafbfc', fg='#253247', insertbackground='#101827', selectbackground='#bad6f3', borderwidth=0, padx=10, pady=8, tabs=('4c',))
        self.text.pack(fill='both', expand=True)
        scroll.configure(command=self.scroll)
        bottom.configure(command=self.text.xview)
        self.text.configure(xscrollcommand=bottom.set, yscrollcommand=lambda a, b: (scroll.set(a, b), self.lines.yview_moveto(a)))
        for tag, color in [('command', '#0058c7'), ('brace', '#a25e00'), ('comment', '#498553'), ('math', '#9331a2')]:
            self.text.tag_configure(tag, foreground=color)
        self.text.tag_configure('search', background='#ffe49a')
        self.text.insert('1.0', self.saved)
        self.text.edit_reset()
        self.text.edit_modified(False)
        self.text.bind('<<Modified>>', self.changed)
        self.text.bind('<KeyRelease>', self.keyup)
        self.text.bind('<ButtonRelease>', self.keyup)
        self.text.bind('<Tab>', self.tab)
        self.text.bind('<Control-space>', self.complete)
        self.highlight()
        app.tabs.add(self.frame, text=self.path.name)

    def scroll(self, *args):
        self.text.yview(*args)
        self.lines.yview(*args)

    def tab(self, event):
        self.text.insert('insert', '    ')
        return 'break'

    def changed(self, event=None):
        if not self.text.edit_modified():
            return
        self.text.edit_modified(False)
        self.dirty = self.content() != self.saved
        self.app.tabs.tab(self.frame, text=self.path.name + (' *' if self.dirty else ''))
        if self.timer:
            self.app.after_cancel(self.timer)
        self.timer = self.app.after(220, self.highlight)

    def keyup(self, event=None):
        if self.app.active_doc() == self:
            line, col = self.text.index('insert').split('.')
            self.app.cursor.set(f'Ligne {line} · Colonne {int(col) + 1} · {len(self.content().split())} mots')

    def replace_range(self, first, last, value):
        """Keep a toolbar replacement together as one undoable edit."""
        automatic = self.text.cget('autoseparators')
        self.text.edit_separator()
        self.text.configure(autoseparators=False)
        try:
            self.text.delete(first, last)
            self.text.insert(first, value)
        finally:
            self.text.configure(autoseparators=automatic)
            self.text.edit_separator()

    def content(self):
        return self.text.get('1.0', 'end-1c')

    def highlight(self):
        if self.timer:
            self.app.after_cancel(self.timer)
        self.timer = None
        if not self.text.winfo_exists():
            return
        source = self.content()
        for tag in ('command', 'brace', 'comment', 'math'):
            self.text.tag_remove(tag, '1.0', 'end')
        for tag, pattern in [('command', r'\\[a-zA-Z@]+\*?'), ('brace', r'[{}]'), ('math', r'\$[^$\n]*\$'), ('comment', r'(?<!\\)%[^\n]*')]:
            for match in re.finditer(pattern, source):
                self.text.tag_add(tag, f'1.0+{match.start()}c', f'1.0+{match.end()}c')
        self.text.tag_raise('comment')
        self.lines.configure(state='normal')
        self.lines.delete('1.0', 'end')
        self.lines.insert('1.0', '\n'.join(str(i) for i in range(1, source.count('\n') + 2)))
        self.lines.configure(state='disabled')
        self.lines.yview_moveto(self.text.yview()[0])
        if self.app.active_doc() == self:
            self.app.update_outline()

    def complete(self, event=None):
        prefix = self.text.get('insert linestart', 'insert')
        match = re.search(r'\\([A-Za-z]*)$', prefix)
        if not match:
            return 'break'
        choices = [word for word in ('section', 'subsection', 'subsubsection', 'chapter', 'begin', 'end', 'textbf', 'textit', 'includegraphics', 'frac', 'sqrt', 'label', 'ref', 'cite', 'input', 'include', 'item', 'bibliography', 'documentclass', 'usepackage') if word.startswith(match.group(1))]
        if choices:
            menu = tk.Menu(self.app, tearoff=False)
            for word in choices:
                def choose(value=word):
                    self.text.delete(f'insert-{len(match.group(1))}c', 'insert')
                    self.text.insert('insert', value + '{}')
                    self.text.mark_set('insert', 'insert-1c')
                menu.add_command(label='\\' + word, command=choose)
            box = self.text.bbox('insert')
            if box:
                menu.tk_popup(self.text.winfo_rootx() + box[0], self.text.winfo_rooty() + box[1] + 20)
        return 'break'

    def save(self):
        if self.visual:
            self.visual.flush()
        if self.content() != self.saved:
            self.app.store.save_file(self.app.project, self.path, self.content())
            self.saved = self.content()
        self.dirty = False
        self.app.tabs.tab(self.frame, text=self.path.name)

    def reload(self):
        if self.visual:
            self.visual.dispose()
            self.visual = None
        self.text.configure(state="normal")
        self.saved = self.path.read_text(encoding='utf-8-sig')
        self.text.delete('1.0', 'end')
        self.text.insert('1.0', self.saved)
        self.text.edit_reset()
        self.text.edit_modified(False)
        self.dirty = False
        self.app.tabs.tab(self.frame, text=self.path.name)
        self.highlight()

    def dispose(self):
        if self.visual:
            self.visual.dispose()
        if self.timer:
            self.app.after_cancel(self.timer)
        self.app.tabs.forget(self.frame)
        self.frame.destroy()


from editor_options import EditorOptions


class App(EditorOptions, tk.Tk):
    def __init__(self, data_dir=None, legacy=None):
        super().__init__()
        self.withdraw()
        self.title('LaTexTEx — Vos projets')
        if (ROOT / 'app.ico').exists():
            self.iconbitmap(str(ROOT / 'app.ico'))
        window_width = min(1450, self.winfo_screenwidth() - 60)
        window_height = min(900, self.winfo_screenheight() - 95)
        window_x = (self.winfo_screenwidth() - window_width) // 2
        window_y = max(30, (self.winfo_screenheight() - window_height) // 2 - 20)
        self.geometry(f'{window_width}x{window_height}+{window_x}+{window_y}')
        self.minsize(1020, 610)
        self.configure(bg=BG)
        self.option_add('*Frame.background', PANEL)
        self.option_add('*Label.background', PANEL)
        self.option_add('*Label.foreground', FG)
        self.option_add('*Font', ('Segoe UI', 11))
        self.store = ProjectStore(data_dir or ROOT / 'user-data', legacy or ROOT / 'workspace.json')
        self.preferences_path = self.store.root / 'preferences.json'
        self.preferences = json.loads(self.preferences_path.read_text(encoding='utf-8')) if self.preferences_path.exists() else {}
        self.font_size = int(self.preferences.get('font_size', 12))
        self.project = None
        self.docs = {}
        self.file_items = {}
        self.pdf = None
        self.pdf_path = None
        self.page = 0
        self.zoom = 1.0
        self.render_timer = None
        self.busy = False
        self.proc = None
        self.cancel_compile = False
        self.closing = False
        self.auto_preview_on_open = True
        self.events = queue.Queue()
        self.home_filter = 'active'
        self.autosave = tk.BooleanVar(value=self.preferences.get('autosave', True))
        self.autocompile = tk.BooleanVar(value=False)
        self.wrap = tk.BooleanVar(value=self.preferences.get('wrap', False))
        self.touchpad_zoom = tk.BooleanVar(value=self.preferences.get('touchpad_zoom', False))
        self.wheel_zoom_timer = None
        self.wheel_zoom_target = None
        self.wheel_scroll_remainder = {'x': 0.0, 'y': 0.0}
        self.edit_mode = tk.StringVar(value="Code")
        self.readonly = False
        self.sidebar_visible = True
        self.layout_mode = "split"
        self.pdf_dark = False
        self.pdf_zoom = tk.StringVar(value="Largeur")
        self.build_ui()
        self.refresh_home()
        self.bind('<Control-n>', lambda e: self.new_file() if self.editor_view.winfo_ismapped() and self.project else self.new_project())
        self.bind('<Control-s>', lambda e: self.save_all())
        self.bind('<Control-o>', lambda e: self.open_existing_file())
        self.bind('<Control-f>', lambda e: self.search_dialog())
        self.bind('<Control-h>', lambda e: self.search_dialog())
        self.bind('<Control-Return>', lambda e: self.guard(self.source_to_pdf))
        self.bind('<F5>', lambda e: self.compile())
        self.bind('<F11>', lambda e: self.attributes('-fullscreen', not self.attributes('-fullscreen')))
        self.bind('<Escape>', lambda e: self.attributes('-fullscreen', False))
        self.protocol('WM_DELETE_WINDOW', self.on_close)
        self.after(100, self.poll)
        self.after(2000, self.auto_save)
        self.deiconify()

    def button(self, parent, text, command, accent=False, **kwargs):
        return ModernButton(parent, text, lambda: self.guard(command), accent=accent, **kwargs)

    def guard(self, callback):
        try:
            return callback()
        except (OSError, ValueError, RuntimeError, zipfile.BadZipFile, tk.TclError, subprocess.SubprocessError) as exc:
            messagebox.showerror('LaTexTEx', str(exc), parent=self)

    def action_menu(self, items):
        menu = tk.Menu(self, tearoff=False, bg=PANEL, fg=FG, activebackground='#e0f4ed', activeforeground=GREEN, font=('Segoe UI', 11), borderwidth=0)
        for label, callback in items:
            menu.add_command(label=label, command=lambda action=callback: self.guard(action))
        widget = self.focus_get()
        x = widget.winfo_rootx() if widget else self.winfo_pointerx()
        y = widget.winfo_rooty() + widget.winfo_height() if widget else self.winfo_pointery()
        menu.tk_popup(x, y)

    def build_ui(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('.', font=('Segoe UI', 11))
        style.configure('TButton', background=PANEL, foreground=FG, font=('Segoe UI', 10), padding=(10, 6), borderwidth=0)
        style.map('TButton', background=[('active', '#43516a')])
        style.configure('Accent.TButton', background=GREEN, foreground='white', font=('Segoe UI', 10, 'bold'))
        style.map('Accent.TButton', background=[('active', '#0a9a4f'), ('disabled', '#426955')])
        style.configure('Mini.TButton', font=('Segoe UI', 9), padding=(4, 5))
        style.layout('Treeview', [('Treeview.treearea', {'sticky': 'nswe'})])
        style.layout('Treeview.Heading', [('Treeheading.padding', {'sticky': 'nswe', 'children': [('Treeheading.text', {'sticky': 'w'})]})])
        style.configure('Treeview', background=PANEL, fieldbackground=PANEL, foreground=FG, rowheight=34, borderwidth=0, font=('Segoe UI', 11))
        style.configure('Treeview.Heading', background='#f5f8fb', foreground=MUTED, font=('Segoe UI', 10, 'bold'), padding=(14, 16), relief='flat')
        style.map('Treeview', background=[('selected', '#e0f4ed')], foreground=[('selected', '#087452')])
        style.configure('Projects.Treeview', rowheight=62, font=('Segoe UI', 12))
        style.configure('TNotebook', background=PANEL, borderwidth=0, tabmargins=0)
        style.configure('TNotebook.Tab', background='#edf2f7', foreground=MUTED, padding=(16, 11), font=('Segoe UI', 10), borderwidth=0)
        style.map('TNotebook.Tab', background=[('selected', PANEL)], foreground=[('selected', GREEN)])
        style.configure('TNotebook.Tab', bordercolor=PANEL, lightcolor=PANEL, darkcolor=PANEL)
        style.configure('TCheckbutton', background=PANEL, foreground=FG)
        style.configure('TCombobox', fieldbackground=PANEL, background=PANEL, foreground=FG, bordercolor='#dce5ee', arrowcolor=MUTED, padding=7, relief='flat')
        style.map('TCombobox', fieldbackground=[('readonly', PANEL)], foreground=[('readonly', FG)])
        style.configure('TEntry', fieldbackground='#f8fafc', foreground=FG, bordercolor='#e4ebf2', lightcolor='#e4ebf2', darkcolor='#e4ebf2', padding=9)
        style.map('TEntry', bordercolor=[('focus', '#62bca7')], lightcolor=[('focus', '#62bca7')], darkcolor=[('focus', '#62bca7')])
        style.configure('TFrame', background=PANEL)
        style.configure('TLabel', background=PANEL, foreground=FG)
        for orientation in ('Vertical', 'Horizontal'):
            style.layout(orientation + '.TScrollbar', [(orientation + '.Scrollbar.trough', {'sticky': 'nswe', 'children': [(orientation + '.Scrollbar.thumb', {'expand': '1', 'sticky': 'nswe'})]})])
            style.configure(orientation + '.TScrollbar', background='#c6d2df', troughcolor='#f1f5f9', borderwidth=0, arrowsize=10, width=10)
        self.home_view = tk.Frame(self, bg=BG)
        self.home_view.pack(fill='both', expand=True)
        nav = tk.Frame(self.home_view, bg=NAV, width=228, padx=18, pady=26)
        nav.pack(side='left', fill='y')
        nav.pack_propagate(False)
        tk.Label(nav, text='LaTexTEx', font=('Segoe UI', 23, 'bold'), bg=NAV, fg='#60dfb8', anchor='w').pack(fill='x')
        tk.Label(nav, text='Votre espace de rédaction', font=('Segoe UI', 10), fg='#97afbe', bg=NAV, pady=10, anchor='w').pack(fill='x', pady=(0, 26))
        self.nav_buttons = {}
        for label, state in [('Tous les projets', 'active'), ('Projets archivés', 'archived'), ('Corbeille', 'trash'), ('Bibliothèque PDF', 'pdf')]:
            button = self.button(nav, label, lambda value=state: self.filter_home(value))
            button.configure(style='Nav.TButton')
            button.selected = state == 'active'
            button.pack(fill='x', pady=4)
            self.nav_buttons[state] = button
        for label, callback, placement in [('Ouvrir un fichier .tex', self.open_existing_file, 'top'), ('Ajouter un PDF', self.import_pdf, 'top'), ('Guide & raccourcis', self.help_dialog, 'bottom'), ('Préférences', self.preferences_dialog, 'bottom')]:
            button = self.button(nav, label, callback)
            button.configure(style='Nav.TButton')
            button.pack(side=placement, fill='x', pady=5)
        content = tk.Frame(self.home_view, bg=BG, padx=30, pady=18)
        content.pack(fill='both', expand=True)
        self.home_title = tk.StringVar(value='Tous les projets')
        tk.Label(content, textvariable=self.home_title, font=('Segoe UI', 24, 'bold'), fg=FG, bg=BG, anchor='w').pack(fill='x')
        tk.Label(content, text='Retrouvez vos documents et reprenez là où vous en étiez.', fg=MUTED, bg=BG, anchor='w', font=('Segoe UI', 11)).pack(fill='x', pady=(5, 12))
        actions = tk.Frame(content, bg=BG)
        actions.pack(fill='x', pady=(0, 12))
        self.query = tk.StringVar()
        search = tk.Frame(actions, bg=PANEL, highlightbackground='#dce5ee', highlightthickness=1, padx=12, pady=9)
        search.pack(side='left')
        tk.Label(search, text='⌕', bg=PANEL, fg=MUTED, font=('Segoe UI', 16)).pack(side='left', padx=(0, 8))
        query_box = tk.Entry(search, textvariable=self.query, bg=PANEL, fg=FG, insertbackground=FG, font=('Segoe UI', 11), relief='flat', width=25)
        query_box.pack(side='left')
        self.search_placeholder = tk.Label(search, text='Rechercher un projet…', font=('Segoe UI', 10), bg=PANEL, fg=MUTED, anchor='w', cursor='xterm')
        self.search_placeholder.place(in_=query_box, x=0, y=2)
        self.search_placeholder.bind('<Button-1>', lambda e: query_box.focus_set())
        query_box.bind('<FocusIn>', lambda e: self.search_placeholder.place_forget())
        query_box.bind('<FocusOut>', lambda e: self.search_placeholder.place(in_=query_box, x=0, y=2) if not self.query.get() else None)
        self.query.trace_add('write', lambda *_: self.refresh_home())
        self.button(actions, '+ Nouveau projet', self.new_project, accent=True).pack(side='right')
        self.button(actions, 'Importer ▾', lambda: self.action_menu([('Projet ZIP / Overleaf', self.import_zip), ('Dossier local', self.import_folder), ('Fichier LaTeX', self.open_existing_file)])).pack(side='right', padx=10)
        tk.Label(content, text='Choisissez un modèle', bg=BG, fg=FG, font=('Segoe UI', 13, 'bold'), anchor='w').pack(fill='x')
        gallery_canvas = tk.Canvas(content, bg=BG, height=224, highlightthickness=0)
        gallery_canvas.pack(fill='x', pady=(8, 0))
        gallery_scroll = ttk.Scrollbar(content, orient='horizontal', command=gallery_canvas.xview)
        gallery_scroll.pack(fill='x', pady=(0, 16))
        gallery_canvas.configure(xscrollcommand=gallery_scroll.set)
        gallery = tk.Frame(gallery_canvas, bg=BG)
        gallery_canvas.create_window((0, 0), window=gallery, anchor='nw')
        gallery.bind('<Configure>', lambda e: gallery_canvas.configure(scrollregion=gallery_canvas.bbox('all')))
        self.template_photos = {}
        for index, title in enumerate(TEMPLATES):
            card = SoftCard(gallery)
            card.grid(row=0, column=index, sticky='nsew', padx=5, pady=3)
            image_path = preview_asset(ROOT, TEMPLATES[title], '.png')
            if image_path:
                with Image.open(image_path) as image:
                    image.thumbnail((130, 125), Image.Resampling.LANCZOS)
                    self.template_photos[title] = ImageTk.PhotoImage(image.copy())
                thumbnail = tk.Label(card, image=self.template_photos[title], bg='#e8eef4', width=160, height=128, cursor='hand2')
                thumbnail.pack()
                thumbnail.bind('<Button-1>', lambda e, key=title: self.new_project(key))
            else:
                tk.Label(card, text='Aperçu indisponible', bg='#e8eef4', fg=MUTED, width=22, height=9).pack()
            self.button(card, title, lambda key=title: self.new_project(key)).pack(fill='x', pady=(4, 0))
            tk.Label(card, text=DESCRIPTIONS[title], bg=PANEL, fg=MUTED, font=('Segoe UI', 9), wraplength=165).pack()
        table_frame = tk.Frame(content, bg=BG)
        table_frame.pack(fill='both', expand=True)
        self.projects_table = ttk.Treeview(table_frame, columns=('name', 'main', 'engine', 'date'), show='headings', selectmode='browse', style='Projects.Treeview')
        for key, label, width in [('name', 'Titre', 330), ('main', 'Document principal', 190), ('engine', 'Compilateur', 110), ('date', 'Dernière modification', 175)]:
            self.projects_table.heading(key, text=label, command=lambda k=key: self.sort_home(k))
            self.projects_table.column(key, width=width, minwidth=70)
        scroll = ttk.Scrollbar(table_frame, command=self.projects_table.yview)
        scroll.pack(side='right', fill='y')
        self.projects_table.configure(yscrollcommand=scroll.set)
        self.projects_table.pack(fill='both', expand=True)
        self.empty_label = tk.Label(table_frame, text='Aucun projet pour le moment.\nCréez votre premier document avec « Nouveau projet ».', bg=PANEL, fg=MUTED, font=('Segoe UI', 12), pady=20)
        self.projects_table.bind('<Double-1>', lambda e: self.guard(self.open_selected_project))
        self.projects_table.bind('<Return>', lambda e: self.guard(self.open_selected_project))
        self.projects_table.bind('<Button-3>', self.project_menu)
        bottom = tk.Frame(content, bg=BG)
        bottom.pack(side='bottom', fill='x', pady=(14, 0), before=table_frame)
        self.button(bottom, 'Ouvrir le projet', self.open_selected_project, accent=True).pack(side='left')
        self.button(bottom, 'Actions du projet ▾', lambda: self.action_menu([('Renommer', self.rename_project), ('Dupliquer', self.duplicate_project), ('Archiver', lambda: self.project_state('archived')), ('Déplacer dans la corbeille', lambda: self.project_state('trash')), ('Restaurer', lambda: self.project_state('active')), ('Exporter ZIP', self.export_zip)])).pack(side='left', padx=10)
        self.home_count = tk.StringVar()
        tk.Label(content, textvariable=self.home_count, bg=BG, fg=MUTED, anchor='w', pady=12, font=('Segoe UI', 10)).pack(side='bottom', fill='x', before=table_frame)
        self.build_editor()
        self.status = tk.StringVar(value='Bienvenue · Créez un projet ou importez votre projet Overleaf en ZIP')
        tk.Label(self, textvariable=self.status, bg=BG, fg=MUTED, anchor='w', font=('Segoe UI', 9), padx=16, pady=7).pack(side='bottom', fill='x', before=self.home_view)

    def build_editor(self):
        self.editor_view = tk.Frame(self, bg=BG)
        header = tk.Frame(self.editor_view, bg=NAV, padx=5, pady=3)
        header.pack(fill='x')
        for label, action in [('Share', self.share_dialog), ('Layout', self.layout_menu), ('History', self.history_dialog)]:
            button = self.button(header, label, action, accent=label == 'Share')
            button.configure(style='Nav.TButton')
            button.pack(side='right', padx=2)
        home = self.button(header, '‹', self.show_home, width=2)
        home.configure(style='Nav.TButton')
        home.pack(side='left')
        self.build_main_menus(header)
        self.project_name = tk.StringVar(value='Bibliothèque PDF')
        tk.Label(header, textvariable=self.project_name, fg='white', bg=NAV, font=('Segoe UI', 11, 'bold'), width=1).pack(side='left', fill='x', expand=True, padx=8)
        bar = tk.Frame(self.editor_view, bg=PANEL, padx=10, pady=6)
        # Compilation preferences are available from the PDF dropdown.
        self.engine = tk.StringVar(value='pdflatex')
        tk.Label(bar, text='Principal', bg=PANEL, fg=MUTED).pack(side='left', padx=(8, 4))
        self.main_var = tk.StringVar()
        self.main_combo = ttk.Combobox(bar, textvariable=self.main_var, width=22, state='readonly')
        self.main_combo.pack(side='left')
        self.main_combo.bind('<<ComboboxSelected>>', lambda e: self.guard(self.change_main))
        self.bib = tk.StringVar(value='auto')
        self.button(bar, 'Paramètres de compilation', self.compilation_settings).pack(side='left', padx=12)
        tk.Label(bar, text='Ctrl+Entrée : code ↔ PDF', fg=MUTED, bg=PANEL, font=('Segoe UI', 9)).pack(side='left', padx=5)
        self.compile_button = self.button(bar, '▶ Recompiler  F5', self.compile, accent=True)
        self.compile_button.pack(side='right', padx=5, before=bar.winfo_children()[0])
        self.button(bar, 'Arrêter', self.stop_compile).pack(side='right', before=bar.winfo_children()[0])
        panes = tk.PanedWindow(self.editor_view, orient='horizontal', sashwidth=5, bg='#dfe7ef', borderwidth=0)
        panes.pack(side='right', fill='both', expand=True, pady=(2, 5))
        self.horizontal_panes = panes
        self.build_activity_rail(self.editor_view, panes)
        left = tk.Frame(panes, bg=PANEL)
        self.file_sidebar = left
        panes.add(left, width=242, minsize=160)
        tk.Label(left, text='Fichiers du projet', bg=PANEL, fg=FG, font=('Segoe UI', 11, 'bold'), pady=12).pack(fill='x')
        filebar = tk.Frame(left, bg=PANEL)
        filebar.pack(fill='x', padx=4, pady=3)
        for label, callback in [('＋ Fichier', self.new_file), ('Nouveau dossier', self.new_folder), ('↑', self.import_files), ('×', self.toggle_sidebar)]:
            button = self.button(filebar, label, callback)
            if callback == self.new_folder:
                button.icon_name, button.tooltip = 'folder', TIPS['folder']
            button.configure(style='Mini.TButton')
            button.pack(side='left', padx=2)
        self.file_tree = ttk.Treeview(left, show='tree', selectmode='browse')
        self.file_tree.pack(fill='both', expand=True, padx=5)
        self.file_tree.tag_configure('main', foreground=GREEN)
        self.file_tree.bind('<Double-1>', lambda e: self.guard(self.open_selected_file))
        self.file_tree.bind('<ButtonRelease-1>', lambda e: self.guard(self.open_selected_file) if self.file_tree.identify_region(e.x, e.y) == 'tree' and 'indicator' not in self.file_tree.identify_element(e.x, e.y) else None)
        self.file_tree.bind('<Return>', lambda e: self.guard(self.open_selected_file))
        self.file_tree.bind('<Button-3>', self.file_menu)
        outline_area = tk.Frame(left, bg=PANEL)
        outline_area.pack(side='bottom', fill='x', before=self.file_tree)
        refresh = self.button(outline_area, '↻ Actualiser', self.refresh_files)
        refresh.configure(style='Mini.TButton')
        refresh.pack(fill='x', padx=7, pady=4)
        tk.Label(outline_area, text='Plan du document', fg=MUTED, bg=PANEL, font=('Segoe UI', 10, 'bold'), pady=10).pack(fill='x')
        self.outline = ttk.Treeview(outline_area, show='tree', height=3)
        self.outline.pack(fill='x', padx=5, pady=(0, 5))
        self.outline.bind('<<TreeviewSelect>>', self.jump_outline)
        middle = tk.PanedWindow(panes, orient='vertical', bg='#dfe7ef', sashwidth=5, borderwidth=0)
        self.middle_panes = middle
        panes.add(middle, width=525, minsize=320)
        editor_frame = tk.Frame(middle, bg=PANEL)
        middle.add(editor_frame, minsize=190, stretch='always')
        self.tabs = ttk.Notebook(editor_frame)
        self.tabs.pack(fill='both', expand=True)
        self.tabs.bind('<<NotebookTabChanged>>', self.tab_changed)
        self.tabs.bind('<Button-3>', lambda e: self.action_menu([('Fermer cet onglet', self.close_tab)]))
        self.cursor = tk.StringVar(value='Ctrl+Espace : complétion · Ctrl+F : rechercher')
        footer = tk.Frame(editor_frame, bg=PANEL, pady=4)
        footer.pack(side='bottom', fill='x', before=self.tabs)
        self.log_toggle = self.button(footer, 'Journal & erreurs', self.toggle_log)
        self.log_toggle.configure(style='Mini.TButton')
        self.log_toggle.pack(side='left', padx=4)
        tk.Label(footer, textvariable=self.cursor, bg=PANEL, fg=MUTED, anchor='e', font=('Segoe UI', 9), padx=6).pack(side='right')
        log_frame = tk.Frame(middle, bg=BG)
        self.log_frame = log_frame
        self.log_visible = False
        log_tabs = ttk.Notebook(log_frame)
        log_tabs.pack(fill='both', expand=True)
        console = tk.Frame(log_tabs, bg=BG)
        self.log = tk.Text(console, height=5, bg='#111924', fg='#c4cedc', font=('Consolas', 9), wrap='word', state='disabled', borderwidth=0, padx=8)
        self.log.pack(fill='both', expand=True)
        log_tabs.add(console, text='Journal de compilation')
        self.errors = ttk.Treeview(log_tabs, columns=('file', 'line', 'message'), show='headings', height=4)
        for key, label, width in [('file', 'Fichier', 120), ('line', 'Ligne', 50), ('message', 'Erreur', 330)]:
            self.errors.heading(key, text=label)
            self.errors.column(key, width=width)
        log_tabs.add(self.errors, text='Erreurs (double-clic pour ouvrir)')
        self.errors.bind('<Double-1>', lambda e: self.guard(self.jump_error))
        right = tk.Frame(panes, bg='#cbd4df')
        self.pdf_panel = right
        panes.add(right, width=570, minsize=320)
        compile_bar = tk.Frame(right, bg=PANEL, padx=4, pady=3)
        compile_bar.pack(fill='x')
        self.compile_button = self.button(compile_bar, 'Recompile', self.compile, accent=True)
        self.compile_button.configure(style='Mini.TButton')
        self.compile_button.pack(side='left')
        for label, action in [('▾', lambda: self.action_menu([('Paramètres de compilation', self.compilation_settings), ('Arrêter la compilation', self.stop_compile), ('Journal et erreurs', self.toggle_log)])), ('▤', self.toggle_log), ('↓', self.export_pdf), ('◐', self.toggle_pdf_dark)]:
            button = self.button(compile_bar, label, action, width=2)
            button.configure(style='Mini.TButton')
            button.pack(side='left', padx=1)
        pdf_bar = tk.Frame(right, bg=PANEL, padx=4, pady=3)
        pdf_bar.pack(fill='x')
        self.button(pdf_bar, '‹', lambda: self.turn_page(-1), width=2).pack(side='left')
        self.page_input = tk.StringVar(value='1')
        page_entry = ttk.Entry(pdf_bar, textvariable=self.page_input, width=4)
        page_entry.pack(side='left', padx=2)
        page_entry.bind('<Return>', lambda e: self.guard(self.jump_page))
        self.page_label = tk.StringVar(value='/ 0')
        tk.Label(pdf_bar, textvariable=self.page_label, bg=PANEL, fg=FG).pack(side='left', padx=3)
        self.button(pdf_bar, '›', lambda: self.turn_page(1), width=2).pack(side='left')
        self.button(pdf_bar, '−', lambda: self.change_zoom(-0.2), width=2).pack(side='left', padx=(8, 1))
        self.button(pdf_bar, '+', lambda: self.change_zoom(0.2), width=2).pack(side='left')
        zoom_entry = ttk.Combobox(pdf_bar, textvariable=self.pdf_zoom, values=['Largeur', 'Page entière', '50%', '75%', '100%', '125%', '150%', '200%'], width=9)
        zoom_entry.pack(side='right', padx=3)
        zoom_entry.bind('<<ComboboxSelected>>', lambda e: self.guard(lambda: self.zoom_to(self.pdf_zoom.get())))
        zoom_entry.bind('<Return>', lambda e: self.guard(lambda: self.zoom_to(self.pdf_zoom.get())))
        self.button(pdf_bar, '⌕', self.search_pdf, width=2).pack(side='left')

        body = tk.Frame(right)
        body.pack(fill='both', expand=True)
        self.canvas = tk.Canvas(body, bg='#e9eef5', highlightthickness=0)
        ybar = ttk.Scrollbar(body, command=self.canvas.yview)
        ybar.pack(side='right', fill='y')
        self.canvas.pack(fill='both', expand=True)
        xbar = ttk.Scrollbar(right, orient='horizontal', command=self.canvas.xview)
        xbar.pack(fill='x')
        self.canvas.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.canvas.bind('<Configure>', self.schedule_render)
        self.canvas.bind('<MouseWheel>', self.pdf_wheel)
        self.canvas.bind('<Control-Button-1>', lambda e: self.guard(lambda: self.pdf_to_source(e)))

    def filter_home(self, state):
        self.home_filter = state
        for key, button in self.nav_buttons.items():
            button.selected = key == state
            button.draw()
        self.query.set('')
        self.refresh_home()

    def toggle_log(self, force=False):
        if self.log_visible and not force:
            self.middle_panes.forget(self.log_frame)
            self.log_visible = False
            self.log_toggle.configure(text='Journal & erreurs')
        elif not self.log_visible:
            self.middle_panes.add(self.log_frame, minsize=95, height=165, stretch='never')
            self.log_visible = True
            self.log_toggle.configure(text='Masquer le journal')

    def compilation_settings(self):
        dialog = SoftDialog(self)
        dialog.title('Paramètres de compilation')
        dialog.configure(bg=PANEL)
        dialog.transient(self)
        dialog.resizable(False, False)
        tk.Label(dialog, text='Compiler votre projet', bg=PANEL, fg=FG, font=('Segoe UI', 18, 'bold')).pack(padx=28, pady=(24, 16))
        ttk.Combobox(dialog, values=self.main_combo.cget('values'), textvariable=self.main_var, state='readonly', width=30).pack(padx=28, pady=8)
        tk.Label(dialog, text='Compilateur LaTeX', bg=PANEL, fg=MUTED).pack(anchor='w', padx=28)
        ttk.Combobox(dialog, values=['pdflatex', 'xelatex', 'lualatex'], textvariable=self.engine, state='readonly', width=30).pack(padx=28, pady=(6, 16))
        tk.Label(dialog, text='Bibliographie', bg=PANEL, fg=MUTED).pack(anchor='w', padx=28)
        ttk.Combobox(dialog, values=['auto', 'aucune', 'bibtex', 'biber'], textvariable=self.bib, state='readonly', width=30).pack(padx=28, pady=(6, 16))
        ttk.Checkbutton(dialog, text='Sauvegarder automatiquement', variable=self.autosave).pack(anchor='w', padx=28, pady=8)
        ttk.Checkbutton(dialog, text='Recompiler après mes modifications', variable=self.autocompile).pack(anchor='w', padx=28, pady=8)
        self.button(dialog, 'Terminé', lambda: (self.change_main(), self.save_all(), dialog.destroy()), accent=True).pack(fill='x', padx=28, pady=22)

    def refresh_home(self):
        if not hasattr(self, 'projects_table'):
            return
        selected = self.projects_table.selection()
        self.projects_table.delete(*self.projects_table.get_children())
        self.home_title.set({'active': 'Tous les projets', 'archived': 'Projets archivés', 'trash': 'Corbeille des projets', 'pdf': 'Bibliothèque PDF'}[self.home_filter])
        query = self.query.get().casefold().strip()
        if self.home_filter == 'pdf':
            for i, raw in enumerate(self.store.pdfs):
                path = Path(raw)
                if query in path.name.casefold():
                    self.projects_table.insert('', 'end', iid='pdf-' + str(i), values=(path.name, 'PDF', '', self.format_date(datetime.fromtimestamp(path.stat().st_mtime).isoformat()) if path.exists() else 'Introuvable'))
        else:
            for project in sorted(self.store.projects, key=lambda p: p['modified'], reverse=True):
                if project['state'] == self.home_filter and query in project['name'].casefold():
                    self.projects_table.insert('', 'end', iid=project['id'], values=(project['name'], project['main'] or 'À choisir', project['engine'], self.format_date(project['modified'])))
        if selected and self.projects_table.exists(selected[0]):
            self.projects_table.selection_set(selected)
        count = len(self.projects_table.get_children())
        if count:
            self.empty_label.place_forget()
        else:
            self.empty_label.configure(text='Aucun résultat pour cette recherche.' if query else 'Aucun document ici.\nCréez un projet ou importez vos fichiers.')
            self.empty_label.place(relx=0.5, rely=0.5, anchor='center')
        self.home_count.set(f'{count} élément(s) · Double-clic pour ouvrir')

    @staticmethod
    def format_date(value):
        return datetime.fromisoformat(value).astimezone().strftime('%d/%m/%Y %H:%M')

    def sort_home(self, column):
        reverse = not getattr(self, '_sort_reverse', False) if getattr(self, '_sort_column', None) == column else column == 'date'
        self._sort_column, self._sort_reverse = column, reverse
        items = []
        for item in self.projects_table.get_children():
            key = self.projects_table.set(item, column).casefold()
            if column == 'date':
                if item.startswith('pdf-'):
                    path = Path(self.store.pdfs[int(item[4:])])
                    key = path.stat().st_mtime if path.exists() else 0
                else:
                    project = next(p for p in self.store.projects if p['id'] == item)
                    key = datetime.fromisoformat(project['modified']).timestamp()
            items.append((key, item))
        for index, (_, item) in enumerate(sorted(items, reverse=reverse)):
            self.projects_table.move(item, '', index)

    def selected_project(self):
        selected = self.projects_table.selection()
        if selected:
            return next((p for p in self.store.projects if p['id'] == selected[0]), None)
        return None

    def open_selected_project(self):
        selected = self.projects_table.selection()
        if not selected:
            return
        if selected[0].startswith('pdf-'):
            self.show_pdf(Path(self.store.pdfs[int(selected[0][4:])]))
        else:
            project = self.selected_project()
            if project['state'] == 'trash':
                self.project_state('active')
            self.open_project(project)

    def new_project(self, selected_template='Article'):
        dialog = SoftDialog(self)
        dialog.title('Nouveau projet')
        dialog.configure(bg=PANEL)
        dialog.resizable(False, False)
        dialog.transient(self)
        tk.Label(dialog, text='Créer un projet LaTeX', bg=PANEL, fg=FG, font=('Segoe UI', 17, 'bold')).pack(padx=24, pady=(20, 12))
        tk.Label(dialog, text='Choisissez un modèle, donnez-lui un nom et commencez.', fg=MUTED, font=('Segoe UI', 10)).pack(padx=24, pady=(0, 16))
        name = tk.StringVar(value='Mon projet')
        tk.Label(dialog, text='Nom du projet', font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=24)
        entry = ttk.Entry(dialog, textvariable=name, width=42, font=('Segoe UI', 12))
        entry.pack(padx=24, pady=7)
        template = tk.StringVar(value=selected_template)
        tk.Label(dialog, text='Modèle', font=('Segoe UI', 10, 'bold')).pack(anchor='w', padx=24, pady=(10, 0))
        selector = ttk.Combobox(dialog, values=list(TEMPLATES), textvariable=template, state='readonly', width=40)
        selector.pack(padx=24, pady=8)
        selected_preview = tk.Label(dialog, bg='#f5f8fb', padx=18, pady=12)
        selected_preview.pack(fill='x', padx=24, pady=(8, 4))
        description = tk.StringVar()
        tk.Label(dialog, textvariable=description, fg=MUTED, font=('Segoe UI', 10)).pack(pady=(4, 8))
        def update_preview(event=None):
            image_path = preview_asset(ROOT, TEMPLATES[template.get()], '.png')
            if image_path:
                with Image.open(image_path) as image:
                    image.thumbnail((160, 145), Image.Resampling.LANCZOS)
                    selected_preview.photo = ImageTk.PhotoImage(image.copy())
                selected_preview.configure(image=selected_preview.photo)
            description.set(DESCRIPTIONS[template.get()])
        selector.bind('<<ComboboxSelected>>', update_preview)
        update_preview()
        tk.Label(dialog, text='Un dossier et un main.tex seront créés immédiatement.', bg=PANEL, fg=MUTED).pack(padx=24, pady=8)
        def create():
            project = self.store.create(name.get(), TEMPLATES[template.get()])
            if template.get() == 'العربية — Article':
                project['engine'] = 'xelatex'
                self.store.touch(project)
            preview = preview_asset(ROOT, TEMPLATES[template.get()], '.pdf')
            if preview:
                shutil.copy2(preview, Path(project['path']) / 'main.pdf')
            dialog.destroy()
            self.open_project(project)
            self.status.set('Projet créé · main.tex enregistré sur le disque')
        self.button(dialog, 'Créer le projet', create, accent=True).pack(pady=(8, 22))
        entry.focus_set()
        entry.select_range(0, 'end')
        dialog.bind('<Return>', lambda e: self.guard(create))
        dialog.grab_set()

    def import_folder(self):
        folder = filedialog.askdirectory(title='Ouvrir un dossier de projet LaTeX')
        if folder:
            self.open_project(self.store.register(folder))

    def import_zip(self):
        path = filedialog.askopenfilename(title='Importer un projet Overleaf / LaTeX', filetypes=[('Projet ZIP', '*.zip')])
        if path:
            self.open_project(self.store.import_zip(path))
            self.status.set('Projet ZIP importé · Vérifiez le document principal avant compilation')

    def open_existing_file(self):
        selected = filedialog.askopenfilename(filetypes=[('Source LaTeX', '*.tex'), ('Fichiers texte', '*.bib *.sty *.cls *.txt')])
        if selected:
            path = Path(selected).resolve()
            if self.project and path.is_relative_to(Path(self.project['path'])):
                self.open_document(path)
            else:
                project = self.store.register(path.parent, main=path.name if path.suffix.lower() == '.tex' else None)
                self.open_project(project)
                self.open_document(path)

    def rename_project(self):
        project = self.selected_project()
        if project:
            value = simpledialog.askstring('Renommer le projet', 'Nouveau titre :', initialvalue=project['name'], parent=self)
            if value and value.strip():
                project['name'] = value.strip()
                self.store.touch(project)
                self.refresh_home()

    def duplicate_project(self):
        project = self.selected_project()
        if project:
            self.store.duplicate(project)
            self.refresh_home()

    def project_state(self, state):
        project = self.selected_project()
        if project:
            project['state'] = state
            self.store.touch(project)
            self.refresh_home()
            self.status.set('Projet déplacé · Les fichiers restent conservés sur le disque')

    def project_menu(self, event):
        item = self.projects_table.identify_row(event.y)
        if item:
            self.projects_table.selection_set(item)
            menu = tk.Menu(self, tearoff=False)
            for label, callback in [('Ouvrir', self.open_selected_project), ('Renommer', self.rename_project), ('Dupliquer', self.duplicate_project), ('Archiver', lambda: self.project_state('archived')), ('Déplacer dans la corbeille', lambda: self.project_state('trash')), ('Restaurer', lambda: self.project_state('active')), ('Exporter ZIP', self.export_zip)]:
                menu.add_command(label=label, command=lambda cb=callback: self.guard(cb))
            menu.tk_popup(event.x_root, event.y_root)

    def open_project(self, project):
        if getattr(self, 'inline_panel', None):
            self.inline_panel.destroy()
        if self.busy:
            raise ValueError('Attendez la fin de compilation ou cliquez sur Arrêter avant de changer de projet.')
        if not self.save_all():
            return
        if not Path(project['path']).is_dir():
            raise ValueError('Le dossier a été déplacé. Rouvrez-le avec Ouvrir dossier.')
        if self.project is None and self.layout_mode == 'pdf':
            self.set_layout('split')
        self.close_documents()
        self.clear_pdf()
        self.project = project
        self.project_name.set(project['name'])
        self.title('LaTexTEx — ' + project['name'])
        self.engine.set(project['engine'])
        self.bib.set(project.get('bibliography', 'auto'))
        self.main_var.set(project['main'])
        self.home_view.pack_forget()
        self.editor_view.pack(fill='both', expand=True)
        self.refresh_files()
        if project['main'] and inside(project['path'], project['main']).is_file():
            self.open_document(inside(project['path'], project['main']))
            pdf = inside(project['path'], project['main']).with_suffix('.pdf')
            if pdf.exists():
                self.load_pdf(pdf)
            else:
                source = inside(project['path'], project['main']).read_text(encoding='utf-8-sig')
                preview = preview_asset(ROOT, source, '.pdf')
                if preview:
                    shutil.copy2(preview, pdf)
                    self.load_pdf(pdf)
                else:
                    project_id = project['id']
                    def initial_preview():
                        if self.auto_preview_on_open and not self.closing and not self.busy and self.project and self.project['id'] == project_id and self.editor_view.winfo_ismapped() and not self.pdf:
                            self.guard(self.compile)
                    self.after(250, initial_preview)
        self.status.set('Projet ouvert · ' + project['path'])

    def show_home(self):
        if getattr(self, 'inline_panel', None):
            self.inline_panel.destroy()
        if not self.save_all():
            return
        self.editor_view.pack_forget()
        self.home_view.pack(fill='both', expand=True)
        self.refresh_home()
        self.title('LaTexTEx — Vos projets')

    def close_documents(self):
        for doc in list(self.docs.values()):
            doc.dispose()
        self.docs.clear()

    def active_doc(self):
        if not hasattr(self, 'tabs'):
            return None
        current = self.tabs.select()
        return next((d for d in self.docs.values() if str(d.frame) == current), None)

    def open_document(self, path, line=None):
        path = Path(path).resolve()
        if not self.project or not path.is_relative_to(Path(self.project['path']).resolve()):
            raise ValueError('Le fichier doit appartenir au projet ouvert.')
        if path.suffix.lower() not in TEXT_SUFFIXES:
            return self.preview_resource(path)
        if path.stat().st_size > 5 * 1024 * 1024:
            raise ValueError('Fichier texte trop grand pour cet éditeur (5 Mo).')
        if path not in self.docs:
            self.docs[path] = Document(self, path)
        doc = self.docs[path]
        doc.text.configure(font=('Consolas', self.font_size))
        doc.lines.configure(font=('Consolas', self.font_size))
        self.tabs.select(doc.frame)
        doc.text.configure(wrap='word' if self.wrap.get() else 'none')
        if line:
            self.set_edit_mode('Code')
            doc.text.mark_set('insert', f'{line}.0')
            doc.text.see(f'{line}.0')
        doc.text.focus_set()
        self.tab_changed()

    def tab_changed(self, event=None):
        doc = self.active_doc()
        if doc:
            if self.edit_mode.get() == 'Visual' and not doc.visual:
                self.set_edit_mode('Visual')
            elif self.edit_mode.get() == 'Code' and doc.visual:
                self.set_edit_mode('Code')
            self.set_readonly(self.readonly)
            doc.keyup()
            self.update_outline()

    def close_tab(self):
        self.flush_visual()
        doc = self.active_doc()
        if doc:
            if doc.content() != doc.saved:
                answer = messagebox.askyesnocancel('Fermer le fichier', 'Enregistrer les modifications ?', parent=self)
                if answer is None:
                    return
                if answer:
                    doc.save()
            del self.docs[doc.path]
            doc.dispose()

    def save_all(self):
        try:
            for doc in self.docs.values():
                doc.save()
            if self.project:
                self.project.update(engine=self.engine.get(), bibliography=self.bib.get())
                self.store.persist()
            if hasattr(self, 'status'):
                self.status.set('Tous les fichiers sont enregistrés')
            return True
        except (OSError, ValueError) as exc:
            messagebox.showerror('Sauvegarde impossible', str(exc), parent=self)
            return False

    def auto_save(self):
        if not self.closing and not self.busy and self.autosave.get() and any(d.content() != d.saved for d in self.docs.values()):
            if self.save_all() and self.autocompile.get() and self.project and self.editor_view.winfo_ismapped():
                self.guard(self.compile)
        if not self.closing:
            self.after(2000, self.auto_save)

    def selected_file(self):
        selected = self.file_tree.selection()
        return self.file_items.get(selected[0]) if selected else None

    def selected_folder(self):
        if not self.project:
            raise ValueError('Ouvrez ou créez un projet d’abord.')
        path = self.selected_file()
        return path if path and path.is_dir() else path.parent if path else Path(self.project['path'])

    def refresh_files(self):
        if not self.project:
            return
        opened = {str(path) for item, path in self.file_items.items() if self.file_tree.item(item, 'open')}
        self.file_tree.delete(*self.file_tree.get_children())
        self.file_items = {}
        base = Path(self.project['path'])
        def add(folder, parent=''):
            for path in sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.casefold())):
                if path.is_symlink() or path.name in HIDDEN_DIRS or path.suffix.lower() in {'.aux', '.log', '.toc', '.out', '.gz', '.bcf', '.blg', '.nav', '.snm', '.fls'} or path.name.endswith('.latextex-tmp'):
                    continue
                relative = str(path.relative_to(base)).replace('\\', '/')
                main = relative == self.project['main']
                item = self.file_tree.insert(parent, 'end', text=('▸ ' if path.is_dir() else '● ' if main else '') + path.name, open=str(path) in opened, tags=('main',) if main else ())
                self.file_items[item] = path
                if path.is_dir():
                    add(path, item)
        add(base)
        self.main_combo.configure(values=[str(p.relative_to(base)).replace('\\', '/') for p in sources(base) if p.suffix.lower() == '.tex'])

    def new_file(self):
        folder = self.selected_folder()
        name = simpledialog.askstring('Nouveau fichier', 'Nom du fichier (ex. chapitre.tex ou refs.bib) :', initialvalue='nouveau.tex', parent=self)
        if name:
            if not Path(name).suffix:
                name += '.tex'
            relative = str(folder.relative_to(Path(self.project['path'])) / name).replace('\\', '/')
            path = self.store.new_file(self.project, relative, '% Nouveau fichier\n' if name.lower().endswith('.tex') else '')
            self.refresh_files()
            self.open_document(path)
            self.status.set('Fichier créé et enregistré · ' + relative)

    def new_folder(self):
        folder = self.selected_folder()
        name = simpledialog.askstring('Nouveau dossier', 'Nom du dossier :', parent=self)
        if name:
            relative = str(folder.relative_to(Path(self.project['path'])) / name).replace('\\', '/')
            self.store.new_folder(self.project, relative)
            self.refresh_files()

    def import_files(self):
        folder = self.selected_folder()
        selected = filedialog.askopenfilenames(title='Ajouter des fichiers au projet')
        targets = []
        for raw in selected:
            source = Path(raw)
            destination = inside(self.project['path'], str(folder.relative_to(Path(self.project['path'])) / source.name))
            if destination.exists():
                raise FileExistsError(f'{source.name} existe déjà. Renommez le fichier avant de l’importer.')
            if any(dst == destination for _, dst in targets):
                raise FileExistsError('Plusieurs fichiers sélectionnés portent le même nom.')
            targets.append((source, destination))
        for source, destination in targets:
            shutil.copy2(source, destination)
        if selected:
            self.store.touch(self.project)
            self.refresh_files()

    def open_selected_file(self):
        path = self.selected_file()
        if path and path.is_file():
            self.open_document(path)

    def rename_file(self):
        if self.busy:
            raise ValueError('Arrêtez la compilation avant de renommer un fichier.')
        path = self.selected_file()
        if not path or not self.save_all():
            return
        base = Path(self.project['path'])
        relative = str(path.relative_to(base)).replace('\\', '/')
        name = simpledialog.askstring('Renommer', 'Nouveau nom / chemin relatif au projet :', initialvalue=relative, parent=self)
        if name and name != relative:
            new = self.store.rename_file(self.project, relative, name.replace('\\', '/'))
            for key, doc in list(self.docs.items()):
                if key == path or key.is_relative_to(path):
                    suffix = key.relative_to(path)
                    del self.docs[key]
                    doc.path = new / suffix if suffix.parts else new
                    self.docs[doc.path] = doc
                    self.tabs.tab(doc.frame, text=doc.path.name)
            self.main_var.set(self.project['main'])
            self.refresh_files()

    def trash_file(self):
        if self.busy:
            raise ValueError('Arrêtez la compilation avant de retirer un fichier.')
        path = self.selected_file()
        if path and messagebox.askyesno('Corbeille des fichiers', f'Déplacer {path.name} dans la corbeille locale ?\nVous pourrez le restaurer.', parent=self):
            if not self.save_all():
                return
            self.store.trash_file(self.project, str(path.relative_to(Path(self.project['path']))).replace('\\', '/'))
            for key, doc in list(self.docs.items()):
                if key == path or key.is_relative_to(path):
                    del self.docs[key]
                    doc.dispose()
            self.refresh_files()

    def change_main(self):
        if self.project:
            path = inside(self.project['path'], self.main_var.get())
            if not path.is_file() or path.suffix.lower() != '.tex':
                raise ValueError('Choisissez un fichier .tex existant.')
            self.project['main'] = self.main_var.get()
            self.store.touch(self.project)
            self.refresh_files()

    def set_selected_main(self):
        path = self.selected_file()
        if path and path.suffix.lower() == '.tex':
            self.main_var.set(str(path.relative_to(Path(self.project['path']))).replace('\\', '/'))
            self.change_main()

    def file_menu(self, event):
        item = self.file_tree.identify_row(event.y)
        if item:
            self.file_tree.selection_set(item)
        menu = tk.Menu(self, tearoff=False)
        for label, callback in [('Ouvrir', self.open_selected_file), ('Nouveau fichier', self.new_file), ('Nouveau dossier', self.new_folder), ('Importer des fichiers', self.import_files), ('Définir comme document principal', self.set_selected_main), ('Renommer', self.rename_file), ('Déplacer dans la corbeille', self.trash_file), ('Restaurer un fichier supprimé', self.trash_dialog)]:
            menu.add_command(label=label, command=lambda cb=callback: self.guard(cb))
        menu.tk_popup(event.x_root, event.y_root)

    def update_outline(self):
        self.outline.delete(*self.outline.get_children())
        doc = self.active_doc()
        if doc:
            for index, line in enumerate(doc.content().splitlines(), 1):
                match = re.search(r'\\(chapter|section|subsection|subsubsection)\*?(?:\[[^\]]*\])?\{([^}]+)\}', line.split('%')[0])
                if match:
                    self.outline.insert('', 'end', iid=str(index), text=('  ' if 'sub' in match.group(1) else '') + match.group(2))

    def jump_outline(self, event=None):
        doc = self.active_doc()
        selected = self.outline.selection()
        if doc and selected:
            line = selected[0]
            self.set_edit_mode('Code')
            doc.text.mark_set('insert', line + '.0')
            doc.text.see('insert')
            doc.text.focus_set()

    def update_wrap(self):
        for doc in self.docs.values():
            doc.text.configure(wrap='word' if self.wrap.get() else 'none')

    def edit_action(self, method):
        doc = self.active_doc()
        if doc and doc.visual and not self.readonly:
            doc.visual.flush()
            try:
                getattr(doc.text, method)()
            except tk.TclError:
                return
            doc.visual.rebuilding = True
            self.set_edit_mode('Visual')
            return
        target = self.editor_target()
        if target and not self.readonly:
            try:
                getattr(target, method)()
            except tk.TclError:
                pass

    def prepare_source_edit(self):
        doc=self.active_doc()
        was_visual=bool(doc and doc.visual and self.edit_mode.get()=='Visual')
        if was_visual:
            selection=doc.visual.source_selection()
            self.set_edit_mode('Code')
            doc.text.tag_remove('sel','1.0','end')
            doc.text.mark_set('insert',f'1.0+{selection[0]}c')
            if selection[0]!=selection[1]:doc.text.tag_add('sel',f'1.0+{selection[0]}c',f'1.0+{selection[1]}c')
        return was_visual

    def return_to_visual(self):
        doc=self.active_doc()
        offset=int(doc.text.count('1.0','insert','chars')[0]) if doc else 0
        self.set_edit_mode('Visual')
        if doc and doc.visual:doc.visual.focus_source_offset(offset)

    def insert_latex(self, before, after):
        if self.readonly:return
        was_visual=self.prepare_source_edit()
        doc = self.active_doc()
        if doc:
            try:
                selected = doc.text.get('sel.first', 'sel.last')
                index = doc.text.index('sel.first')
                end = doc.text.index('sel.last')
            except tk.TclError:
                selected, index = '', doc.text.index('insert')
                end = index
            doc.replace_range(index, end, before + selected + after)
            doc.text.mark_set('insert', f'{index}+{len(before) + len(selected)}c')
            doc.text.focus_set()
            if was_visual:self.return_to_visual()

    def search_dialog(self):
        self.set_edit_mode('Code')
        if not self.project:
            return
        dialog = SoftDialog(self)
        dialog.title('Rechercher / remplacer')
        dialog.geometry('780x460')
        query, replace = tk.StringVar(), tk.StringVar()
        top = ttk.Frame(dialog, padding=12)
        top.pack(fill='x')
        ttk.Label(top, text='Rechercher').grid(row=0, column=0, padx=5)
        entry = ttk.Entry(top, textvariable=query, width=38)
        entry.grid(row=0, column=1, padx=5)
        ttk.Label(top, text='Remplacer par').grid(row=1, column=0, padx=5, pady=8)
        ttk.Entry(top, textvariable=replace, width=38).grid(row=1, column=1, padx=5)
        case = tk.BooleanVar(value=False)
        ttk.Checkbutton(top, text='Respecter la casse', variable=case).grid(row=0, column=2)
        result = ttk.Treeview(dialog, columns=('file', 'line', 'text'), show='headings')
        for key, label, width in [('file', 'Fichier', 170), ('line', 'Ligne', 60), ('text', 'Texte', 500)]:
            result.heading(key, text=label)
            result.column(key, width=width)
        result.pack(fill='both', expand=True, padx=12, pady=10)
        found = {}
        def search():
            result.delete(*result.get_children())
            found.clear()
            if not query.get():
                return
            needle = query.get() if case.get() else query.get().casefold()
            for path in sources(self.project['path']):
                if path.suffix.lower() not in TEXT_SUFFIXES or path.stat().st_size > 5 * 1024 * 1024:
                    continue
                text = self.docs[path].content() if path in self.docs else path.read_text(encoding='utf-8', errors='replace')
                for number, line in enumerate(text.splitlines(), 1):
                    if needle in (line if case.get() else line.casefold()):
                        item = result.insert('', 'end', values=(path.relative_to(Path(self.project['path'])), number, line.strip()[:160]))
                        found[item] = (path, number)
                        if len(found) >= 1000:
                            return
        def jump(event=None):
            selected = result.selection()
            if selected and selected[0] in found:
                path, line = found[selected[0]]
                self.open_document(path, line)
                doc = self.active_doc()
                doc.text.tag_remove('search', '1.0', 'end')
                doc.text.tag_add('search', f'{line}.0', f'{line}.end')
        def replace_current():
            if self.readonly:
                self.status.set('Viewing · remplacement désactivé en lecture seule')
                return
            doc = self.active_doc()
            if doc and query.get():
                pattern = re.compile(re.escape(query.get()), 0 if case.get() else re.I)
                text, count = pattern.subn(lambda _: replace.get(), doc.content())
                if count:
                    doc.replace_range('1.0', 'end', text)
                    self.status.set(f'{count} occurrence(s) remplacée(s) dans {doc.path.name}')
                search()
        self.button(top, 'Dans tout le projet', search).grid(row=1, column=2, padx=5)
        self.button(dialog, 'Remplacer tout dans l’onglet actif', replace_current).pack(pady=(0, 12))
        result.bind('<Double-1>', jump)
        entry.bind('<Return>', lambda e: search())
        entry.focus_set()

    def history_dialog(self):
        if not self.project or not self.save_all():
            return
        project = self.project
        dialog = SoftDialog(self)
        dialog.title('Versions — aperçu, comparaison et restauration')
        dialog.geometry('850x560')
        table = ttk.Treeview(dialog, columns=('date', 'file'), show='headings', height=8)
        table.heading('date', text='Date de sauvegarde de la version précédente')
        table.heading('file', text='Fichier')
        table.pack(fill='x', padx=10, pady=10)
        versions = self.store.history(project)
        for item in versions:
            table.insert('', 'end', iid=item['id'], values=(self.format_date(item['date']), item['file']))
        preview = tk.Text(dialog, bg='#fafbfc', font=('Consolas', 10), wrap='none', state='disabled')
        preview.pack(fill='both', expand=True, padx=10)
        def selected():
            ids = table.selection()
            return next((v for v in versions if ids and v['id'] == ids[0]), None)
        def show(event=None):
            item = selected()
            if item:
                text = (Path(project['path']) / '.latextex' / 'history' / (item['id'] + '.txt')).read_text(encoding='utf-8-sig')
                preview.configure(state='normal')
                preview.delete('1.0', 'end')
                preview.insert('1.0', text)
                preview.configure(state='disabled')
        def restore():
            item = selected()
            if item and messagebox.askyesno('Restaurer cette version', 'Remplacer le contenu actuel par cette version ?\nLe contenu actuel sera conservé dans l’historique.', parent=dialog):
                if not self.save_all():
                    return
                path = self.store.restore_version(project, item)
                if path in self.docs:
                    self.docs[path].reload()
                self.open_document(path)
                self.refresh_files()
                dialog.destroy()
        table.bind('<<TreeviewSelect>>', show)
        def compare():
            item = selected()
            if not item:
                return
            old = (Path(project['path']) / '.latextex' / 'history' / (item['id'] + '.txt')).read_text(encoding='utf-8-sig')
            current = inside(project['path'], item['file'])
            text = current.read_text(encoding='utf-8-sig') if current.exists() else ''
            diff = ''.join(difflib.unified_diff(old.splitlines(True), text.splitlines(True), fromfile='Version sauvegardée', tofile='Version actuelle'))
            preview.configure(state='normal')
            preview.delete('1.0', 'end')
            preview.insert('1.0', diff or 'Aucune différence.')
            preview.configure(state='disabled')
        def checkpoint():
            if not self.save_all():
                return
            for path in sources(project['path']):
                self.store.snapshot(project, path)
            dialog.destroy()
            self.history_dialog()
        actions = tk.Frame(dialog)
        actions.pack(fill='x', padx=10, pady=10)
        self.button(actions, 'Comparer avec maintenant', compare).pack(side='left')
        self.button(actions, 'Sauvegarder une version', checkpoint).pack(side='left', padx=6)
        self.button(actions, 'Restaurer', restore, accent=True).pack(side='right')

    def preferences_dialog(self):
        dialog = SoftDialog(self)
        dialog.title('Préférences de l’éditeur')
        dialog.configure(bg=PANEL)
        tk.Label(dialog, text='Taille du texte', bg=PANEL, fg=FG).pack(padx=25, pady=(20, 7))
        size = tk.IntVar(value=self.font_size)
        ttk.Spinbox(dialog, from_=9, to=24, textvariable=size, width=8).pack(pady=5)
        ttk.Checkbutton(dialog, text='Sauvegarde automatique', variable=self.autosave).pack(padx=25, pady=8)
        ttk.Checkbutton(dialog, text='Retour à la ligne', variable=self.wrap).pack(padx=25, pady=8)
        ttk.Checkbutton(dialog, text='Zoom PDF avec deux doigts, sans Ctrl', variable=self.touchpad_zoom).pack(padx=25, pady=8)
        tk.Label(dialog, text='Par défaut : Ctrl + deux doigts pour zoomer.\nDeux doigts seuls font défiler le PDF.', bg=PANEL, fg=MUTED, justify='left').pack(padx=25, pady=8)
        def apply():
            if not 9 <= size.get() <= 24:
                raise ValueError('Choisissez une taille entre 9 et 24.')
            self.font_size = size.get()
            write_json(self.preferences_path, {'font_size': self.font_size, 'autosave': self.autosave.get(), 'wrap': self.wrap.get(), 'touchpad_zoom': self.touchpad_zoom.get()})
            for doc in self.docs.values():
                doc.text.configure(font=('Consolas', self.font_size))
                doc.lines.configure(font=('Consolas', self.font_size))
            self.update_wrap()
            dialog.destroy()
        self.button(dialog, 'Appliquer et enregistrer', apply, accent=True).pack(padx=25, pady=20)

    def comments_dialog(self):
        if not self.project:
            return
        project = self.project
        dialog = SoftDialog(self)
        dialog.title('Commentaires locaux du projet')
        dialog.geometry('780x520')
        table = ttk.Treeview(dialog, columns=('state', 'file', 'line', 'text'), show='headings')
        for key, label, width in [('state', 'État', 85), ('file', 'Fichier', 180), ('line', 'Ligne', 50), ('text', 'Commentaire', 440)]:
            table.heading(key, text=label)
            table.column(key, width=width)
        table.pack(fill='both', expand=True, padx=12, pady=12)
        entry = tk.Text(dialog, height=4, font=('Segoe UI', 11), wrap='word')
        entry.pack(fill='x', padx=12)
        items = {}
        def refresh():
            table.delete(*table.get_children())
            items.clear()
            for item in self.store.comments(project):
                items[item['id']] = item
                table.insert('', 'end', iid=item['id'], values=('Résolu' if item['resolved'] else 'Ouvert', item['file'], item['line'], item['text'].replace('\n', ' ')[:180]))
        def selected():
            ids = table.selection()
            return items.get(ids[0]) if ids else None
        def add():
            doc = self.active_doc()
            if not doc:
                raise ValueError('Ouvrez un fichier source pour y attacher un commentaire.')
            self.store.add_comment(project, str(doc.path.relative_to(Path(project['path']))), int(doc.text.index('insert').split('.')[0]), entry.get('1.0', 'end-1c'))
            entry.delete('1.0', 'end')
            refresh()
        def show(event=None):
            item = selected()
            if item:
                entry.delete('1.0', 'end')
                entry.insert('1.0', item['text'])
        def jump(event=None):
            item = selected()
            if item:
                self.open_document(inside(project['path'], item['file']), item['line'])
        def toggle():
            item = selected()
            if item:
                self.store.resolve_comment(project, item['id'], not item['resolved'])
                refresh()
        bar = ttk.Frame(dialog)
        bar.pack(fill='x', padx=12, pady=12)
        self.button(bar, 'Ajouter à la ligne du curseur', add, accent=True).pack(side='left', padx=4)
        self.button(bar, 'Aller à la source', jump).pack(side='left', padx=4)
        self.button(bar, 'Résoudre / rouvrir', toggle).pack(side='left', padx=4)
        table.bind('<<TreeviewSelect>>', show)
        table.bind('<Double-1>', jump)
        refresh()

    def synctex_output(self):
        if not self.project:
            raise ValueError('Ouvrez un projet et compilez-le d’abord.')
        main = inside(self.project['path'], self.project['main'])
        output = Path(self.project['path']) / '.latextex' / 'build' / (main.stem + '.pdf')
        if not output.exists() or not output.with_suffix('.synctex.gz').exists():
            raise ValueError('Recompilez le projet pour activer la synchronisation code / PDF.')
        return output

    def run_synctex(self, args):
        exe = find_engine('synctex')
        if not exe:
            raise ValueError('SyncTeX est absent de votre installation LaTeX.')
        result = subprocess.run([exe] + args, cwd=self.project['path'], capture_output=True, timeout=10, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        text = result.stdout.decode('utf-8', errors='replace')
        if result.returncode:
            raise ValueError('SyncTeX n’a pas trouvé de correspondance. Recompilez le document.')
        return dict(re.findall(r'^([A-Za-z]+):(.+)$', text, re.M))

    def source_to_pdf(self):
        if self.edit_mode.get() == 'Visual':
            doc = self.active_doc()
            offset = doc.visual.model.offset(doc.visual.active) if doc and doc.visual and doc.visual.active is not None else None
            self.set_edit_mode('Code')
            if doc and offset is not None:
                doc.text.mark_set('insert', f'1.0+{offset}c')
        doc = self.active_doc()
        if not doc:
            return
        if doc.content() != doc.saved:
            raise ValueError('Enregistrez et recompilez vos modifications avant la synchronisation.')
        output = self.synctex_output()
        line = doc.text.index('insert').split('.')[0]
        result = self.run_synctex(['view', '-i', f'{line}:0:{doc.path}', '-o', str(output)])
        if 'Page' not in result:
            raise ValueError('Cette ligne n’a pas de position visible dans le PDF.')
        self.load_pdf(output)
        self.page = int(result['Page']) - 1
        self.render_pdf()
        scale = self.photo.width() / self.pdf[self.page].rect.width
        y = float(result.get('y', result.get('v', '0'))) * scale + 15
        self.canvas.yview_moveto(max(0, y - 80) / (self.photo.height() + 30))
        self.status.set('Code → PDF · Page ' + str(self.page + 1))

    def pdf_to_source(self, event):
        if not self.pdf or not self.project:
            return
        output = self.synctex_output()
        # Synchronization coordinates only apply to the project's current build.
        if self.pdf_path not in {output, inside(self.project['path'], self.project['main']).with_suffix('.pdf')}:
            raise ValueError('Affichez le PDF du projet compilé avant la synchronisation.')
        scale = self.photo.width() / self.pdf[self.page].rect.width
        offset = max(15, (self.canvas.winfo_width() - self.photo.width()) // 2)
        x = (self.canvas.canvasx(event.x) - offset) / scale
        y = (self.canvas.canvasy(event.y) - 15) / scale
        result = self.run_synctex(['edit', '-o', f'{self.page + 1}:{x}:{y}:{output}'])
        if 'Input' not in result or 'Line' not in result:
            raise ValueError('Aucune ligne source à cet endroit du PDF.')
        path = Path(result['Input'].strip())
        if not path.is_absolute():
            path = inside(self.project['path'], str(path))
        self.open_document(path, int(result['Line']))
        self.status.set('PDF → Code · ' + path.name + ', ligne ' + result['Line'])

    def trash_dialog(self):
        if not self.project:
            return
        dialog = SoftDialog(self)
        dialog.title('Corbeille des fichiers')
        table = ttk.Treeview(dialog, columns=('file', 'date'), show='headings')
        table.heading('file', text='Fichier / dossier')
        table.heading('date', text='Date')
        table.pack(fill='both', expand=True, padx=12, pady=12)
        entries = self.store.trashed_files(self.project)
        for item in entries:
            table.insert('', 'end', iid=item['id'], values=(item['file'], self.format_date(item['date'])))
        def restore():
            ids = table.selection()
            item = next((i for i in entries if ids and i['id'] == ids[0]), None)
            if item:
                self.store.restore_file(self.project, item)
                self.refresh_files()
                dialog.destroy()
        self.button(dialog, 'Restaurer', restore, accent=True).pack(pady=10)

    def export_zip(self):
        project = self.project if self.editor_view.winfo_ismapped() else self.selected_project()
        if project:
            if self.project == project and not self.save_all():
                return
            destination = filedialog.asksaveasfilename(initialfile=re.sub(r'[<>:"/\\|?*]', '_', project['name']) + '.zip', defaultextension='.zip', filetypes=[('Projet ZIP', '*.zip')])
            if destination:
                self.store.export_zip(project, destination)
                self.status.set('Projet exporté · ' + destination)

    def reveal_project(self):
        if self.project:
            os.startfile(self.project['path'])

    def import_pdf(self):
        selected = filedialog.askopenfilename(filetypes=[('PDF', '*.pdf')])
        if selected:
            self.show_pdf(Path(selected))

    def show_pdf(self, path):
        if not self.save_all():
            return
        self.close_documents()
        self.project = None
        self.project_name.set('Bibliothèque PDF · ' + path.name)
        self.file_tree.delete(*self.file_tree.get_children())
        self.file_items = {}
        self.main_var.set('')
        self.home_view.pack_forget()
        self.editor_view.pack(fill='both', expand=True)
        self.set_layout('pdf')
        self.load_pdf(path)

    def preview_resource(self, path):
        if path.suffix.lower() == '.pdf':
            self.load_pdf(path)
        elif path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.gif', '.bmp'}:
            self.clear_pdf()
            with Image.open(path) as image:
                image.thumbnail((max(300, self.canvas.winfo_width() - 30), 1200))
                self.photo = ImageTk.PhotoImage(image.copy())
            self.canvas.create_image(15, 15, image=self.photo, anchor='nw')
            self.canvas.configure(scrollregion=(0, 0, self.photo.width() + 30, self.photo.height() + 30))
        else:
            self.status.set('Ressource · ' + str(path) + ' · Ouvrez le dossier pour utiliser une application externe')

    def remember(self, path):
        self.store.add_pdf(path)

    def cancel_wheel_zoom(self):
        if self.wheel_zoom_timer:
            self.after_cancel(self.wheel_zoom_timer)
            self.wheel_zoom_timer = None
        self.wheel_zoom_target = None

    def pdf_wheel(self, event):
        """Windows touchpads and wheels share MouseWheel, including small deltas."""
        delta = float(event.delta)
        if not delta:
            return 'break'
        if self.pdf and (event.state & 0x4 or self.touchpad_zoom.get()):
            percent = self.wheel_zoom_target or self.photo.width() / self.pdf[self.page].rect.width * 100
            self.wheel_zoom_target = max(25, min(300, percent * 1.1 ** max(-8, min(8, delta / 120))))
            self.wheel_zoom_position = (event.x, event.y)
            if self.wheel_zoom_timer:
                self.after_cancel(self.wheel_zoom_timer)
            self.wheel_zoom_timer = self.after(35, self.apply_wheel_zoom)
        else:
            axis = 'x' if event.state & 0x1 else 'y'
            self.wheel_scroll_remainder[axis] -= delta / 40
            units = int(self.wheel_scroll_remainder[axis])
            self.wheel_scroll_remainder[axis] -= units
            if units:
                getattr(self.canvas, axis + 'view_scroll')(units, 'units')
        return 'break'

    def apply_wheel_zoom(self):
        self.wheel_zoom_timer = None
        percent = self.wheel_zoom_target
        self.wheel_zoom_target = None
        if not self.pdf or percent is None:
            return
        pointer_x, pointer_y = self.wheel_zoom_position
        old_x = max(15, (self.canvas.winfo_width() - self.photo.width()) // 2)
        page_x = (self.canvas.canvasx(pointer_x) - old_x) / self.photo.width()
        page_y = (self.canvas.canvasy(pointer_y) - 15) / self.photo.height()
        self.zoom_to(str(percent))
        new_x = max(15, (self.canvas.winfo_width() - self.photo.width()) // 2)
        region_width = max(self.canvas.winfo_width(), self.photo.width() + 30)
        self.canvas.xview_moveto(max(0, (new_x + page_x * self.photo.width() - pointer_x) / region_width))
        self.canvas.yview_moveto(max(0, (15 + page_y * self.photo.height() - pointer_y) / (self.photo.height() + 30)))

    def clear_pdf(self):
        self.cancel_wheel_zoom()
        Studio.clear_pdf(self)
        self.pdf_path = None
        self.page_input.set('1')

    def load_pdf(self, path):
        path = Path(path)
        try:
            document = pymupdf.open(stream=path.read_bytes(), filetype='pdf')
            if document.needs_pass or document.page_count == 0:
                document.close()
                raise ValueError('PDF protégé ou sans pages.')
        except Exception as exc:
            raise ValueError('PDF impossible à ouvrir : ' + str(exc)) from exc
        page = self.page if self.pdf_path == path else 0
        self.clear_pdf()
        self.pdf, self.pdf_path = document, path
        self.pdf_search_term = ''
        self.page = min(page, document.page_count - 1)
        self.remember(path)
        self.render_pdf()

    schedule_render = Studio.schedule_render
    def change_zoom(self, delta):
        if self.pdf:
            percent = self.photo.width() / self.pdf[self.page].rect.width * 100
            self.zoom_to(str(max(25, min(300, percent + delta * 100))))

    fit_page = Studio.fit_page
    set_log = Studio.set_log

    def render_pdf(self):
        if self.render_timer:
            self.after_cancel(self.render_timer)
            self.render_timer = None
        Studio.render_pdf(self)
        if self.pdf:
            self.pdf_zoom.set(f'{round(self.photo.width() / self.pdf[self.page].rect.width * 100)}%')
            self.page_input.set(str(self.page + 1))
            self.page_label.set('/ ' + str(self.pdf.page_count))
            x = max(15, (self.canvas.winfo_width() - self.photo.width()) // 2)
            shadow = self.canvas.create_rectangle(x + 4, 19, x + self.photo.width() + 4, self.photo.height() + 19, fill='#cfd9e4', outline='')
            self.canvas.tag_lower(shadow)
            term = getattr(self, 'pdf_search_term', '')
            if term:
                scale = self.photo.width() / self.pdf[self.page].rect.width
                x = max(15, (self.canvas.winfo_width() - self.photo.width()) // 2)
                for rect in self.pdf[self.page].search_for(term):
                    self.canvas.create_rectangle(x + rect.x0 * scale, 15 + rect.y0 * scale, x + rect.x1 * scale, 15 + rect.y1 * scale, outline='#d88700', fill='#ffe080', stipple='gray50')

    def search_pdf(self):
        if self.pdf:
            term = simpledialog.askstring('Rechercher dans le PDF', 'Texte à rechercher :', parent=self)
            if term:
                for index in list(range(self.page, self.pdf.page_count)) + list(range(self.page)):
                    if self.pdf[index].search_for(term):
                        self.page = index
                        self.pdf_search_term = term
                        self.render_pdf()
                        return
                self.status.set('Aucun résultat dans le PDF pour : ' + term)

    def turn_page(self, delta):
        Studio.turn_page(self, delta)

    def jump_page(self):
        if self.pdf:
            number = int(self.page_input.get())
            if not 1 <= number <= self.pdf.page_count:
                raise ValueError('Cette page n’existe pas.')
            self.page = number - 1
            self.canvas.yview_moveto(0)
            self.render_pdf()

    def export_pdf(self):
        if self.pdf_path and self.pdf_path.exists():
            target = filedialog.asksaveasfilename(initialfile=self.pdf_path.name, defaultextension='.pdf', filetypes=[('PDF', '*.pdf')])
            if target and Path(target).resolve() != self.pdf_path.resolve():
                shutil.copy2(self.pdf_path, target)

    def compile(self):
        if self.busy or not self.project or not self.save_all():
            return
        main = inside(self.project['path'], self.main_var.get())
        if not main.is_file():
            raise ValueError('Sélectionnez un document principal .tex existant.')
        exe = find_engine(self.engine.get())
        if not exe:
            raise ValueError('Compilateur absent. Installez MiKTeX ou TeX Live.')
        self.project.update(main=self.main_var.get(), engine=self.engine.get(), bibliography=self.bib.get())
        self.store.persist()
        project = dict(self.project)
        root = Path(project['path'])
        build = root / '.latextex' / 'build'
        build.mkdir(parents=True, exist_ok=True)
        for source in sources(root):
            if source.suffix.lower() == '.tex':
                (build / source.parent.relative_to(root)).mkdir(parents=True, exist_ok=True)
        self.busy = True
        self.cancel_compile = False
        self.compile_button.configure(state='disabled', text='Compilation…')
        self.errors.delete(*self.errors.get_children())
        self.status.set('Compilation · ' + project['name'] + ' / ' + project['main'])
        self.set_log('Compilation du document principal : ' + project['main'] + '\n')
        started = time.time()

        def worker():
            output = []
            code = 1
            environment = os.environ.copy()
            for key in ('TEXINPUTS', 'BIBINPUTS', 'BSTINPUTS'):
                environment[key] = str(root) + '//' + os.pathsep + str(main.parent) + '//' + os.pathsep + environment.get(key, '')
            def run(command):
                if self.cancel_compile:
                    raise RuntimeError('Compilation annulée.')
                output.append('> ' + ' '.join(command) + '\n')
                self.proc = subprocess.Popen(command, cwd=str(root), env=environment, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if self.cancel_compile:
                    self.proc.terminate()
                try:
                    data, _ = self.proc.communicate(timeout=180)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    data, _ = self.proc.communicate()
                    output.append(data.decode('utf-8', errors='replace'))
                    raise RuntimeError('Délai dépassé (180 s). Vérifiez les packages dans MiKTeX Console.')
                output.append(data.decode('utf-8', errors='replace'))
                if self.proc.returncode:
                    raise RuntimeError('Compilation annulée.' if self.cancel_compile else 'Le compilateur a signalé une erreur.')
            try:
                args = [exe, '-interaction=nonstopmode', '-halt-on-error', '-file-line-error', '-synctex=1', '-no-shell-escape', '-output-directory=' + str(build), project['main']]
                if 'miktex' in exe.lower():
                    args.insert(1, '--enable-installer')
                run(args)
                mode = project.get('bibliography', 'auto')
                bcf = build / (main.stem + '.bcf')
                aux = build / (main.stem + '.aux')
                if mode == 'auto':
                    mode = 'biber' if bcf.exists() and bcf.stat().st_mtime >= started - 1 else 'bibtex' if aux.exists() and '\\bibdata' in aux.read_text(encoding='utf-8', errors='replace') else 'aucune'
                if mode in {'bibtex', 'biber'}:
                    tool = find_engine(mode)
                    if not tool:
                        raise RuntimeError(mode + ' est introuvable dans votre installation LaTeX.')
                    run([tool, str(build / main.stem)])
                    run(args)
                run(args)
                pdf = build / (main.stem + '.pdf')
                if not pdf.exists():
                    raise RuntimeError('Aucun PDF n’a été produit.')
                shutil.copy2(pdf, main.with_suffix('.pdf'))
                code = 0
            except Exception as exc:
                output.append('\n' + str(exc))
            finally:
                self.proc = None
                self.events.put((code, '\n'.join(output), project, main))
        threading.Thread(target=worker, daemon=True).start()

    def stop_compile(self):
        if self.busy:
            self.cancel_compile = True
            if self.proc:
                self.proc.terminate()
            self.status.set('Arrêt de la compilation…')

    def poll(self):
        try:
            code, output, project, main = self.events.get_nowait()
            self.busy = False
            self.compile_button.configure(state='normal', text='Recompile')
            self.set_log(output)
            for match in re.finditer(r'^(.+?\.tex):(\d+):\s*(.+)$', output, re.M):
                self.errors.insert('', 'end', values=(match.group(1), match.group(2), match.group(3)))
            if code == 0:
                self.status.set('Compilation réussie · ' + main.with_suffix('.pdf').name)
                if self.project and self.project['id'] == project['id']:
                    self.load_pdf(main.with_suffix('.pdf'))
                    self.refresh_files()
            else:
                self.toggle_log(force=True)
                self.status.set('Compilation annulée' if self.cancel_compile else 'Échec de compilation · Consultez le journal et les erreurs')
        except queue.Empty:
            pass
        if not self.closing:
            self.after(100, self.poll)

    def jump_error(self):
        selected = self.errors.selection()
        if selected and self.project:
            raw, line, _ = self.errors.item(selected[0], 'values')
            path = Path(raw)
            if not path.is_absolute():
                path = inside(self.project['path'], raw.lstrip('./'))
            if path.exists() and path.resolve().is_relative_to(Path(self.project['path']).resolve()):
                self.open_document(path, int(line))

    def help_dialog(self):
        messagebox.showinfo('LaTexTEx 2 — Guide', 'Accueil : créez un projet ou importez un ZIP Overleaf.\nChaque projet contient un main.tex réel.\nDans le projet : + Fichier, + Dossier, import de ressources.\nRecompile ▾ : paramètres et document principal.\nClic droit sur un fichier : renommer, corbeille, restaurer.\nAutosave toutes les 2 secondes ; historique des versions précédentes.\n\nCtrl+N : nouveau projet / fichier\nCtrl+S : enregistrer tous les onglets\nCtrl+O : ouvrir un fichier\nCtrl+F / Ctrl+H : rechercher / remplacer\nCtrl+Espace : compléter une commande LaTeX\nF5 : compiler · F11 : plein écran\nCtrl + deux doigts / molette : zoom PDF\nShift + deux doigts : défilement horizontal\nPréférences : zoom sans Ctrl optionnel\n\nTout reste local. Visual : textes et titres éditables, blocs avancés en code. Share : export ZIP/PDF. La collaboration cloud n’est pas connectée.', parent=self)

    def on_close(self):
        self.flush_visual()
        if any(d.content() != d.saved for d in self.docs.values()):
            answer = messagebox.askyesnocancel('Quitter LaTexTEx', 'Enregistrer les fichiers modifiés ?', parent=self)
            if answer is None or answer and not self.save_all():
                return
        self.closing = True
        self.cancel_wheel_zoom()
        self.stop_compile()
        if self.render_timer:
            self.after_cancel(self.render_timer)
        self.close_documents()
        if self.pdf:
            self.pdf.close()
        self.destroy()


def self_test():
    import tempfile
    with tempfile.TemporaryDirectory(prefix='latextex-', dir=ROOT) as temp:
        app = App(data_dir=Path(temp) / 'data', legacy=Path(temp) / 'absent.json')
        app.withdraw()
        assert app.home_view.winfo_exists() and not app.project
        assert len(app.template_photos) == len(TEMPLATES), 'Missing bundled template images'
        project = app.store.create('Test Windows', TEMPLATES['Article'])
        app.open_project(project)
        assert app.pdf and app.pdf.page_count > 0, 'Missing immediate template PDF'
        file = app.store.new_file(project, 'chapitre.tex', '% Chapitre\n')
        app.refresh_files()
        app.open_document(file)
        app.update()
        assert file in app.docs and len(app.docs) == 2
        app.load_pdf(ROOT / 'documents' / 'Bienvenue.pdf')
        app.update()
        assert app.pdf.page_count > 0 and app.photo.width() > 100
        assert find_engine('pdflatex')
        app.open_document(Path(project['path']) / project['main'])
        original = app.active_doc().content()
        app.set_edit_mode('Visual')
        visual = app.active_doc().visual
        deadline = time.monotonic() + 30
        while len(visual.images) < len(visual.render_labels) and time.monotonic() < deadline:
            app.update()
            time.sleep(.03)
        assert len(visual.images) == len(visual.render_labels), 'Visual previews failed'
        visual.flush()
        assert app.active_doc().content() == original, 'Visual changed source'
        report = {'dashboard': True, 'real_file_created': file.exists(), 'tabs': len(app.docs), 'pdf_pages': app.pdf.page_count, 'frozen': bool(getattr(sys, 'frozen', False)), 'visual_previews': len(visual.images), 'visual_source_preserved': True}
        (ROOT / 'self-test.json').write_text(json.dumps(report), encoding='utf-8')
        app.on_close()


if __name__ == '__main__':
    if '--self-test' in sys.argv:
        self_test()
    else:
        App().mainloop()
