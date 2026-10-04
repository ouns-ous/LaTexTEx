"""Embedded workspace tools and rounded surfaces for the desktop app."""
import tkinter as tk

SURFACE = '#ffffff'
BACKGROUND = '#f3f6fa'


def center_window(window, owner=None):
    window.update_idletasks()
    dimensions = window.wm_geometry().split('+')[0].split('x')
    requested_width, requested_height = map(int, dimensions)
    width = min(requested_width if requested_width > 1 else window.winfo_reqwidth(), window.winfo_screenwidth() - 40)
    height = min(requested_height if requested_height > 1 else window.winfo_reqheight(), window.winfo_screenheight() - 90)
    if owner and owner.winfo_viewable():
        x = owner.winfo_x() + (owner.winfo_width() - width) // 2
        y = owner.winfo_y() + (owner.winfo_height() - height) // 2
    else:
        x = (window.winfo_screenwidth() - width) // 2
        y = (window.winfo_screenheight() - height) // 2 - 20
    x = max(10, min(x, window.winfo_screenwidth() - width - 10))
    y = max(30, min(y, window.winfo_screenheight() - height - 50))
    window.geometry(f'{width}x{height}+{x}+{y}')


class SoftDialog(tk.Frame):
    """An embedded workspace panel, never an additional OS window."""
    def __init__(self, master, **kwargs):
        self.owner = master.winfo_toplevel()
        previous = getattr(self.owner, 'inline_panel', None)
        if previous and previous.winfo_exists():
            previous.destroy()
        kwargs.update(bg=SURFACE, highlightthickness=1, highlightbackground='#dbe6ef')
        super().__init__(self.owner, **kwargs)
        self.owner.inline_panel = self
        self.requested_size = None
        self.maximized = False
        self.pending = []
        self.return_action = None
        self.caption = tk.StringVar(value='Outils')
        header = tk.Frame(self, bg='#f5f8fb', padx=12, pady=5)
        header.pack(fill='x')
        tk.Label(header, textvariable=self.caption, bg='#f5f8fb', fg='#203149', font=('Segoe UI', 12, 'bold'), anchor='w').pack(side='left', fill='x', expand=True)
        self.owner.button(header, 'Fermer', self.destroy).pack(side='right', padx=(6, 0))
        self.expand_button = self.owner.button(header, 'Agrandir', self.toggle_maximize)
        self.expand_button.pack(side='right')
        self.resize_binding = self.owner.bind('<Configure>', self.on_resize, add='+')
        self.escape_binding = self.owner.bind('<Escape>', self.escape, add='+')
        self.return_binding = self.owner.bind('<Return>', self.on_return, add='+')
        super().bind('<Escape>', self.escape)
        self.pending.append(self.after_idle(self.reveal))

    def title(self, value=None):
        if value is not None:
            self.caption.set(value)
        return self.caption.get()

    def geometry(self, value):
        dimensions = value.split('+')[0].split('x')
        self.requested_size = tuple(map(int, dimensions))

    def transient(self, *args):
        pass

    def resizable(self, *args):
        pass

    def grab_set(self):
        # Background navigation remains usable; changing tools replaces the panel.
        pass

    def bind(self, sequence=None, func=None, add=None):
        if sequence == '<Return>':
            self.return_action = func
            return None
        return super().bind(sequence, func, add)

    def contains(self, widget):
        while widget:
            if widget == self:
                return True
            widget = getattr(widget, 'master', None)
        return False

    def on_return(self, event):
        if self.return_action and self.contains(event.widget) and not isinstance(event.widget, tk.Text):
            self.return_action(event)
            return 'break'

    def escape(self, event=None):
        self.destroy()
        return 'break'

    def toggle_maximize(self):
        self.maximized = not self.maximized
        self.expand_button.configure(text='Réduire' if self.maximized else 'Agrandir')
        self.position()

    def on_resize(self, event):
        if event.widget == self.owner:
            self.position()

    def position(self):
        if not self.winfo_exists():
            return
        editor = getattr(self.owner, 'editor_view', None)
        editing = bool(editor and editor.winfo_ismapped())
        top = 58 if editing else 18
        navigation_width = 45 if editing else 228
        available_width = max(300, self.owner.winfo_width() - navigation_width - 36)
        available_height = max(200, self.owner.winfo_height() - top - 18)
        if self.maximized:
            width, height = available_width, available_height
        else:
            width, height = self.requested_size or (560, self.winfo_reqheight())
            width = min(width, available_width)
            height = min(max(240, height), available_height)
        self.place(x=self.owner.winfo_width() - width - 18, y=top, width=width, height=height)
        self.lift()

    def destroy(self):
        for timer in self.pending:
            self.after_cancel(timer)
        self.pending.clear()
        for sequence, binding in [('<Configure>', self.resize_binding), ('<Escape>', self.escape_binding), ('<Return>', self.return_binding)]:
            self.owner.unbind(sequence, binding)
        if getattr(self.owner, 'inline_panel', None) == self:
            self.owner.inline_panel = None
        super().destroy()

    def reveal(self):
        if self.winfo_exists():
            self.position()


class SoftCard(tk.Frame):
    def __init__(self, master, **kwargs):
        kwargs.update(bg=BACKGROUND, highlightthickness=0, padx=12, pady=10)
        super().__init__(master, **kwargs)
        self.skin = tk.Canvas(self, bg=BACKGROUND, highlightthickness=0, borderwidth=0)
        self.skin.place(x=0, y=0, relwidth=1, relheight=1, bordermode='outside')
        tk.Misc.lower(self.skin)
        self.skin.bind('<Configure>', self.paint)

    def paint(self, event):
        width, height, radius = event.width, event.height, 16
        self.skin.delete('all')
        points = [radius, 2, width-radius, 2, width-2, 2, width-2, radius, width-2, height-radius, width-2, height-2, width-radius, height-2, radius, height-2, 2, height-2, 2, height-radius, 2, radius, 2, 2]
        self.skin.create_polygon(points, smooth=True, splinesteps=24, fill=SURFACE, outline='#e4ebf2')
