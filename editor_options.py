"""Functional menu, toolbar and layout options for the local desktop editor."""
import os
from pathlib import Path
import re
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from template_catalog import table_source, escape_text
from PIL import ImageOps
from visual_editor import VisualView, escaped

PANEL, FG, GREEN, NAV = '#ffffff', '#203149', '#07845e', '#182a38'


class EditorOptions:
    def enable_arabic(self):
        if self.readonly or not self.project or not self.save_all():
            return
        from project_store import inside
        path = inside(self.project['path'], self.project['main'])
        doc = self.docs.get(path)
        source = doc.content() if doc else path.read_text(encoding='utf-8-sig')
        if '\\begin{document}' not in source:
            raise ValueError('Le document principal doit contenir \\begin{document}.')
        if '\\setdefaultlanguage{arabic}' not in source:
            if re.search(r'\\usepackage(?:\[[^\]]*\])?\{[^}]*(?:babel|polyglossia)[^}]*\}', source):
                raise ValueError('Ce document configure déjà ses langues. Utilisez le modèle arabe ou adaptez son préambule pour éviter un conflit.')
            source = re.sub(r'\\usepackage(?:\[[^\]]*\])?\{(?:inputenc|fontenc)\}\s*', '', source)
            preamble = '\\usepackage{fontspec}\n\\usepackage{polyglossia}\n\\setdefaultlanguage{arabic}\n\\setotherlanguage{french}\n\\newfontfamily\\arabicfont[Script=Arabic]{Arial}\n\\newfontfamily\\frenchfont{Arial}\n'
            source = source.replace('\\begin{document}', preamble + '\\begin{document}', 1)
            self.store.save_file(self.project, path, source)
            if doc:
                doc.reload()
        self.project['engine'] = 'xelatex'
        self.store.touch(self.project)
        self.open_project(self.project)
        self.status.set('Arabe activé · XeLaTeX · texte français dans un environnement french')

    def build_main_menus(self, parent):
        menus = {
            'File': [('Accueil des projets', self.show_home), ('Nouveau projet', self.new_project), ('Nouveau fichier', self.new_file), ('Ouvrir un fichier', self.open_existing_file), ('Enregistrer tout · Ctrl+S', self.save_all), ('Fermer l’onglet', self.close_tab), ('Exporter le fichier actif', self.export_active_source), ('Exporter le projet ZIP', self.export_zip), ('Exporter PDF', self.export_pdf)],
            'Edit': [('Annuler · Ctrl+Z', lambda: self.edit_action('edit_undo')), ('Rétablir', lambda: self.edit_action('edit_redo')), ('Couper', lambda: self.clip_action('<<Cut>>')), ('Copier', lambda: self.clip_action('<<Copy>>')), ('Coller', lambda: self.clip_action('<<Paste>>')), ('Tout sélectionner', self.select_all), ('Rechercher / remplacer', self.search_dialog), ('Commenter / décommenter', self.toggle_comment)],
            'Insert': [('Titre / section', self.heading_dialog), ('Équation', lambda: self.insert_latex('\\begin{equation}\n', '\n\\end{equation}\n')), ('Activer la langue arabe (XeLaTeX)', self.enable_arabic), ('Symboles mathématiques', self.symbols_dialog), ('Lien', self.insert_link), ('Image / figure', self.insert_image), ('Tableau', self.table_dialog), ('Liste à puces', lambda: self.insert_latex('\\begin{itemize}\n  \\item ', '\n\\end{itemize}\n')), ('Liste numérotée', lambda: self.insert_latex('\\begin{enumerate}\n  \\item ', '\n\\end{enumerate}\n')), ('Citation', lambda: self.insert_latex('\\cite{', '}')), ('Référence', lambda: self.insert_latex('\\ref{', '}')), ('Label', lambda: self.insert_latex('\\label{', '}')), ('Commentaire local', self.comments_dialog)],
            'View': [('Éditeur et PDF', lambda: self.set_layout('split')), ('Éditeur seul', lambda: self.set_layout('editor')), ('PDF seul', lambda: self.set_layout('pdf')), ('Afficher / masquer les fichiers', self.toggle_sidebar), ('Journal et erreurs', self.toggle_log), ('Code', lambda: self.set_edit_mode('Code')), ('Visual', lambda: self.set_edit_mode('Visual')), ('PDF clair / sombre', self.toggle_pdf_dark), ('Plein écran · F11', lambda: self.attributes('-fullscreen', not self.attributes('-fullscreen')))],
            'Format': [('Gras', lambda: self.format_text('bold')), ('Italique', lambda: self.format_text('italic')), ('Souligner', lambda: self.insert_latex('\\underline{', '}')), ('Titre / section', self.heading_dialog), ('Indenter', lambda: self.indent_lines(1)), ('Désindenter', lambda: self.indent_lines(-1)), ('Retour à la ligne', self.toggle_wrap), ('Taille du texte', self.preferences_dialog)],
            'Help': [('Guide & raccourcis', self.help_dialog), ('Assistant LaTeX local', self.assistant_dialog), ('À propos / version locale', self.upgrade_dialog)],
        }
        self.main_menus = menus
        for label, entries in menus.items():
            button = self.button(parent, label, lambda rows=entries: self.action_menu(rows))
            button.configure(style='Nav.TButton')
            button.pack(side='left', padx=1)

    def build_document_toolbar(self, parent):
        row = tk.Frame(parent, bg=PANEL, pady=3)
        row.pack(fill='x')
        actions = [('✦', self.assistant_dialog), ('↶', lambda: self.edit_action('edit_undo')), ('↷', lambda: self.edit_action('edit_redo')), ('T▾', self.heading_dialog), ('B', lambda: self.format_text('bold')), ('I', lambda: self.format_text('italic')), ('Ω', self.symbols_dialog), ('↗', self.insert_link), ('+', self.comments_dialog), ('⋯', lambda: self.action_menu(self.main_menus['Insert']))]
        action_buttons = []
        for label, action in actions:
            button = self.button(row, label, action, width=2)
            if action == self.comments_dialog:
                button.icon_name, button.tooltip = 'comments', 'Commentaires'
            button.configure(style='Mini.TButton')
            button.pack(side='left', padx=1)
            action_buttons.append(button)
        mode_row = tk.Frame(row, bg=PANEL)
        mode_row.pack(side='right')
        modes = {}
        for label in ('Code', 'Visual'):
            button = self.button(mode_row, label, lambda mode=label: self.set_edit_mode(mode))
            button.configure(style='Mini.TButton')
            button.selected = self.edit_mode.get() == label
            button.pack(side='left', padx=(4, 0))
            modes[label] = button
        button = self.button(mode_row, '✎', lambda: self.action_menu([('Editing — modifier le texte', lambda: self.set_readonly(False)), ('Viewing — lecture seule', lambda: self.set_readonly(True))]), width=2)
        button.configure(style='Mini.TButton')
        button.pack(side='right', padx=3)
        def responsive(event):
            available = event.width - mode_row.winfo_reqwidth() - 8
            count = max(3, min(len(action_buttons), available // 38))
            for index, item in enumerate(action_buttons):
                item.pack_forget()
                if index < count - 1 or index == len(action_buttons) - 1:
                    item.pack(side='left', padx=1)
        row.bind('<Configure>', responsive)
        return modes

    def build_activity_rail(self, parent, before):
        rail = tk.Frame(parent, bg=NAV, width=45, padx=2, pady=4)
        rail.pack(side='left', fill='y', before=before)
        rail.pack_propagate(False)
        for label, callback in [('▤', self.toggle_sidebar), ('⌕', self.search_dialog), ('▧', lambda: self.toggle_log(force=True)), ('▣', self.image_library), ('☷', self.comments_dialog), ('✦', self.assistant_dialog)]:
            button = self.button(rail, label, callback, width=2)
            button.configure(style='Nav.TButton')
            button.pack(fill='x', pady=2)
        for label, callback in [('?', self.help_dialog), ('⚙', self.preferences_dialog)]:
            button = self.button(rail, label, callback, width=2)
            button.configure(style='Nav.TButton')
            button.pack(side='bottom', fill='x', pady=3)

    def set_edit_mode(self, mode):
        doc = self.active_doc()
        for item in self.docs.values():
            if item.visual:
                item.visual.flush()
                item.visual.dispose()
                item.visual = None
        self.edit_mode.set(mode)
        if doc and mode == 'Visual':
            doc.visual = VisualView(doc.body, doc)
            doc.visual.place(relx=0, rely=0, relwidth=1, relheight=1)
        for item in self.docs.values():
            for name, button in item.mode_buttons.items():
                button.selected = name == mode
                button.draw()
        self.set_readonly(self.readonly)

    def flush_visual(self):
        for doc in self.docs.values():
            if doc.visual:
                doc.visual.flush()

    def editor_target(self):
        doc = self.active_doc()
        if not doc:
            return None
        if self.edit_mode.get() == 'Visual' and doc.visual:
            return doc.visual.active_text()
        return doc.text

    def set_readonly(self, value):
        if value and not self.readonly:
            self.flush_visual()
        self.readonly = value
        for doc in self.docs.values():
            doc.text.configure(state='disabled' if value else 'normal')
            if doc.visual:
                for field, _, _ in doc.visual.fields.values():
                    field.configure(state='disabled' if value else 'normal')
        if hasattr(self, 'status'):
            self.status.set('Viewing · lecture seule' if value else 'Editing · modification du texte')

    def clip_action(self, event):
        target = self.editor_target()
        if target and (not self.readonly or event == '<<Copy>>'):
            target.event_generate(event)

    def select_all(self):
        target = self.editor_target()
        if target:
            target.tag_add('sel', '1.0', 'end-1c')
            target.focus_set()

    def format_text(self, tag):
        if self.readonly:
            return
        doc = self.active_doc()
        if doc and self.edit_mode.get() == 'Visual' and doc.visual:
            doc.visual.format(tag)
        else:
            self.insert_latex('\\textbf{' if tag == 'bold' else '\\textit{', '}')

    def heading_dialog(self):
        self.action_menu([(label, lambda name=name: self.insert_latex('\\' + name + '{', '}\n')) for label, name in [('Chapitre', 'chapter'), ('Section', 'section'), ('Sous-section', 'subsection'), ('Sous-sous-section', 'subsubsection')]])

    def indent_lines(self, delta):
        self.set_edit_mode('Code')
        doc = self.active_doc()
        if not doc or self.readonly:
            return
        try:
            first, last = doc.text.index('sel.first linestart'), doc.text.index('sel.last lineend')
        except tk.TclError:
            first, last = doc.text.index('insert linestart'), doc.text.index('insert lineend')
        text = doc.text.get(first, last)
        result = '\n'.join('    ' + line if delta > 0 else re.sub(r'^( {1,4}|\t)', '', line) for line in text.split('\n'))
        doc.replace_range(first, last, result)

    def toggle_comment(self):
        self.set_edit_mode('Code')
        doc = self.active_doc()
        if not doc or self.readonly:
            return
        try:
            first, last = doc.text.index('sel.first linestart'), doc.text.index('sel.last lineend')
        except tk.TclError:
            first, last = doc.text.index('insert linestart'), doc.text.index('insert lineend')
        lines = doc.text.get(first, last).split('\n')
        uncomment = all(not line.strip() or line.lstrip().startswith('%') for line in lines)
        text = '\n'.join(re.sub(r'^(\s*)% ?', r'\1', line) if uncomment else '% ' + line for line in lines)
        doc.replace_range(first, last, text)

    def toggle_wrap(self):
        self.wrap.set(not self.wrap.get())
        self.update_wrap()

    def set_layout(self, mode):
        panes = self.horizontal_panes
        for frame in panes.panes():
            panes.forget(frame)
        if self.sidebar_visible:
            panes.add(self.file_sidebar, width=224, minsize=150)
        if mode != 'pdf':
            panes.add(self.middle_panes, width=550, minsize=300)
        if mode != 'editor':
            panes.add(self.pdf_panel, width=550, minsize=300)
        self.layout_mode = mode
        self.after_idle(self.render_pdf)

    def toggle_sidebar(self):
        self.sidebar_visible = not self.sidebar_visible
        self.set_layout(self.layout_mode)

    def layout_menu(self):
        self.action_menu([('Éditeur et PDF côte à côte', lambda: self.set_layout('split')), ('Éditeur uniquement', lambda: self.set_layout('editor')), ('PDF uniquement', lambda: self.set_layout('pdf')), ('Afficher / masquer les fichiers', self.toggle_sidebar), ('Afficher / masquer le journal', self.toggle_log)])

    def toggle_pdf_dark(self):
        self.pdf_dark = not self.pdf_dark
        self.render_pdf()

    def zoom_to(self, selection=None):
        if not self.pdf:
            return
        value = selection or self.pdf_zoom.get()
        page = self.pdf[self.page]
        width_scale = (max(300, self.canvas.winfo_width()) - 30) / page.rect.width
        if value == 'Largeur':
            self.zoom = 1
        elif value == 'Page entière':
            self.zoom = min(width_scale, max(100, self.canvas.winfo_height()-30) / page.rect.height) / width_scale
        else:
            percent = float(value.rstrip('%'))
            if not 25 <= percent <= 300:
                raise ValueError('Le zoom doit être compris entre 25 % et 300 %.')
            self.zoom = percent / 100 / width_scale
        self.render_pdf()

    def symbols_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title('Symboles mathématiques')
        dialog.configure(bg=PANEL)
        symbols = [('α', 'alpha'), ('β', 'beta'), ('γ', 'gamma'), ('δ', 'delta'), ('θ', 'theta'), ('λ', 'lambda'), ('μ', 'mu'), ('π', 'pi'), ('ρ', 'rho'), ('σ', 'sigma'), ('φ', 'phi'), ('ω', 'omega'), ('Σ', 'sum'), ('∫', 'int'), ('∞', 'infty'), ('≤', 'leq'), ('≥', 'geq'), ('≠', 'neq'), ('→', 'rightarrow'), ('×', 'times')]
        for index, (label, command) in enumerate(symbols):
            self.button(dialog, label, lambda name=command: (self.insert_latex('\\ensuremath{\\' + name, '}'), dialog.destroy()), width=3).grid(row=index//5, column=index%5, padx=5, pady=5)

    def ensure_package(self, name):
        from project_store import inside
        if not self.project or self.readonly:
            return
        path = inside(self.project['path'], self.project['main'])
        doc = self.docs.get(path)
        source = doc.content() if doc else path.read_text(encoding='utf-8-sig')
        if not re.search(r'\\usepackage(?:\[[^\]]*\])?\{[^}]*\b' + re.escape(name) + r'\b[^}]*\}', source):
            marker = '\\begin{document}'
            if marker in source:
                updated = source.replace(marker, '\\usepackage{' + name + '}\n' + marker, 1)
                if doc:
                    index = doc.text.search(marker, '1.0')
                    doc.text.edit_separator()
                    doc.text.insert(index, '\\usepackage{' + name + '}\n')
                    doc.text.edit_separator()
                else:
                    self.store.save_file(self.project, path, updated)

    def insert_link(self):
        if self.readonly:
            return
        url = simpledialog.askstring('Insérer un lien', 'Adresse URL :', parent=self)
        if url:
            if '{' in url or '}' in url:
                raise ValueError('L’adresse ne doit pas contenir de braces.')
            was_visual=self.prepare_source_edit()
            self.ensure_package('hyperref')
            self.insert_latex('\\href{' + url.replace('%', '\\%').replace('#', '\\#') + '}{', '}')
            if was_visual:self.return_to_visual()

    def table_dialog(self):
        if self.readonly or not self.project:
            return
        dialog = tk.Toplevel(self)
        dialog.title('Créer un tableau')
        dialog.geometry('750x520')
        settings = tk.Frame(dialog)
        settings.pack(fill='x', padx=12, pady=12)
        rows, columns = tk.IntVar(value=4), tk.IntVar(value=3)
        for label, variable, maximum in [('Lignes', rows, 30), ('Colonnes', columns, 8)]:
            ttk.Label(settings, text=label).pack(side='left', padx=5)
            ttk.Spinbox(settings, from_=1, to=maximum, textvariable=variable, width=5).pack(side='left')
        caption = tk.StringVar()
        ttk.Label(dialog, text='Titre du tableau (facultatif)').pack(anchor='w', padx=12)
        ttk.Entry(dialog, textvariable=caption).pack(fill='x', padx=12, pady=5)
        canvas = tk.Canvas(dialog, highlightthickness=0)
        canvas.pack(fill='both', expand=True, padx=12)
        scrollbar = ttk.Scrollbar(dialog, orient='vertical', command=canvas.yview)
        scrollbar.pack(side='right', fill='y')
        horizontal = ttk.Scrollbar(dialog, orient='horizontal', command=canvas.xview)
        horizontal.pack(fill='x', padx=12)
        canvas.configure(yscrollcommand=scrollbar.set, xscrollcommand=horizontal.set)
        grid = tk.Frame(canvas)
        canvas.create_window((0, 0), window=grid, anchor='nw')
        grid.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        cells = []
        def rebuild():
            nr, nc = rows.get(), columns.get()
            if not 1 <= nr <= 30 or not 1 <= nc <= 8:
                raise ValueError('Choisissez 1–30 lignes et 1–8 colonnes.')
            previous = [[entry.get() for entry in row] for row in cells]
            for child in grid.winfo_children():
                child.destroy()
            cells.clear()
            for r in range(nr):
                row = []
                for c in range(nc):
                    entry = ttk.Entry(grid, width=18)
                    entry.grid(row=r, column=c, padx=2, pady=3)
                    entry.insert(0, previous[r][c] if r < len(previous) and c < len(previous[r]) else (f'Colonne {c+1}' if r == 0 else ''))
                    row.append(entry)
                cells.append(row)
        self.button(settings, 'Actualiser la grille', rebuild).pack(side='left', padx=10)
        def insert():
            self.insert_latex(table_source([[e.get() for e in row] for row in cells], caption.get()), '')
            dialog.destroy()
        self.button(dialog, 'Insérer le tableau', insert, accent=True).pack(pady=12)
        rebuild()

    def insert_image(self):
        if self.readonly or not self.project:
            return
        raw = filedialog.askopenfilename(title='Insérer une image', filetypes=[('Images LaTeX', '*.png *.jpg *.jpeg *.pdf')])
        if not raw:
            return
        options = tk.Toplevel(self)
        options.title('Image — taille et légende')
        options.transient(self)
        width = tk.IntVar(value=80)
        caption = tk.StringVar()
        ttk.Label(options, text='Largeur (% de la ligne, 10–100)').pack(padx=20, pady=(15, 5))
        ttk.Spinbox(options, from_=10, to=100, textvariable=width, width=10).pack()
        ttk.Label(options, text='Légende (facultative)').pack(pady=(10, 5))
        ttk.Entry(options, textvariable=caption, width=45).pack(padx=20)
        accepted = []
        def accept():
            value = width.get()
            if not 10 <= value <= 100:
                raise ValueError('La largeur doit être entre 10 et 100 %.')
            accepted.append(value)
            options.destroy()
        self.button(options, 'Insérer', accept, accent=True).pack(pady=15)
        options.grab_set()
        self.wait_window(options)
        if not accepted:
            return
        import shutil
        source = Path(raw).resolve()
        folder = Path(self.project['path']) / 'images'
        folder.mkdir(exist_ok=True)
        safe_stem = re.sub(r'[^A-Za-z0-9_-]+', '-', source.stem).strip('-') or 'image'
        safe_name = safe_stem + source.suffix.lower()
        target = folder / safe_name
        if source != target:
            count = 2
            while target.exists():
                target = folder / (safe_stem + '-' + str(count) + source.suffix.lower())
                count += 1
            shutil.copy2(source, target)
        was_visual=self.prepare_source_edit()
        self.ensure_package('graphicx')
        relative = target.relative_to(Path(self.project['path'])).as_posix()
        figure = '\\begin{figure}[ht]\n\\centering\n\\includegraphics[width=' + str(accepted[0] / 100) + '\\linewidth]{' + relative + '}\n'
        if caption.get().strip():
            figure += '\\caption{' + escape_text(caption.get()) + '}\n'
        self.insert_latex(figure + '\\end{figure}\n', '')
        self.refresh_files()
        if was_visual:self.return_to_visual()

    def image_library(self):
        if not self.project:
            return
        from project_store import sources
        dialog = tk.Toplevel(self)
        dialog.title('Images et ressources')
        table = ttk.Treeview(dialog, show='tree', height=10)
        table.pack(fill='both', expand=True, padx=12, pady=12)
        items = {}
        for path in sources(self.project['path']):
            if path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.pdf'}:
                item = table.insert('', 'end', text=str(path.relative_to(Path(self.project['path']))))
                items[item] = path
        def show(event=None):
            selection = table.selection()
            if selection:
                self.set_layout('split')
                self.preview_resource(items[selection[0]])
        table.bind('<Double-1>', show)
        self.button(dialog, 'Insérer une nouvelle image', self.insert_image).pack(pady=12)

    def share_dialog(self):
        dialog = tk.Toplevel(self)
        dialog.title('Share — partage local')
        dialog.configure(bg=PANEL)
        tk.Label(dialog, text='Partager votre document', bg=PANEL, fg=FG, font=('Segoe UI', 18, 'bold')).pack(padx=28, pady=(24, 12))
        tk.Label(dialog, text='Exportez une copie à transmettre avec votre messagerie.\nAucun fichier n’est envoyé automatiquement.', bg=PANEL, fg='#728198', justify='left').pack(padx=28, pady=12)
        self.button(dialog, 'Exporter le projet ZIP', self.export_zip, accent=True).pack(fill='x', padx=28, pady=6)
        self.button(dialog, 'Exporter le PDF', self.export_pdf).pack(fill='x', padx=28, pady=(6, 24))

    def export_active_source(self):
        self.flush_visual()
        doc = self.active_doc()
        if doc:
            raw = filedialog.asksaveasfilename(initialfile=doc.path.name, defaultextension=doc.path.suffix, filetypes=[('Fichier source', '*' + doc.path.suffix)])
            if raw:
                Path(raw).write_text(doc.content(), encoding='utf-8')

    def assistant_dialog(self):
        doc = self.active_doc()
        text = doc.content() if doc else ''
        findings = []
        # Local checks, clearly separate from an online AI service.
        cleaned = re.sub(r'(?<!\\)%[^\n]*', '', text)
        if cleaned.count('{') != cleaned.count('}'):
            findings.append('Le nombre de braces ouvrantes et fermantes est différent.')
        stack = []
        for match in re.finditer(r'\\(begin|end)\{([^}]+)\}', cleaned):
            if match.group(1) == 'begin':
                stack.append(match.group(2))
            elif not stack or stack.pop() != match.group(2):
                findings.append('Environnement mal fermé : ' + match.group(2))
        if stack:
            findings.append('Environnements non fermés : ' + ', '.join(stack))
        messagebox.showinfo('Assistant LaTeX local', 'Vérification locale du fichier actif :\n\n' + ('\n'.join(findings) if findings else 'Aucun déséquilibre simple détecté. La compilation reste la vérification complète.') + '\n\nCet outil utilise des règles locales ; aucun service IA en ligne n’est connecté.', parent=self)

    def upgrade_dialog(self):
        messagebox.showinfo('À propos de LaTexTEx', 'LaTexTEx est une application locale sans abonnement.\n\nMenus, projets, compilation, PDF, commentaires locaux, historique et édition visuelle des textes et titres sont disponibles.\n\nVisual affiche les formules et permet de les modifier par double-clic. Les blocs non rendus restent accessibles en LaTeX. Le partage se fait par export ZIP/PDF ; les fonctions cloud d’Overleaf ne sont pas connectées.', parent=self)
