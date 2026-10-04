"""Shared centered dialogs and rounded surfaces for the desktop workspace."""
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


class SoftDialog(tk.Toplevel):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.withdraw()
        self.configure(bg=SURFACE)
        self.owner = master.winfo_toplevel()
        self.transient(self.owner)
        self.bind('<Escape>', lambda event: self.destroy())
        self.pending = [self.after_idle(self.reveal)]

    def destroy(self):
        for timer in self.pending:
            self.after_cancel(timer)
        self.pending.clear()
        super().destroy()

    def reveal(self):
        if not self.winfo_exists():
            return
        center_window(self, self.owner)
        try:
            self.attributes('-alpha', 0.0)
        except tk.TclError:
            pass
        self.deiconify()
        self.lift()
        # Keep the normal Windows frame, resizing and keyboard behavior.
        try:
            self.fade_in(0)
        except tk.TclError:
            pass

    def fade_in(self, step):
        if self.winfo_exists():
            self.attributes('-alpha', min(1.0, step / 6))
            if step < 6:
                self.pending.append(self.after(18, lambda: self.fade_in(step + 1)))


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
