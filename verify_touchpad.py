from pathlib import Path
from types import SimpleNamespace
import tempfile,time,json
from project_studio import App,ROOT
with tempfile.TemporaryDirectory(prefix='touchpad-',dir=ROOT) as folder:
    app=App(data_dir=Path(folder)/'data',legacy=Path(folder)/'absent')
    app.show_pdf(ROOT/'documents'/'Bienvenue.pdf');app.update();app.zoom_to('100%')
    def pump():
        end=time.monotonic()+.12
        while time.monotonic()<end:app.update();time.sleep(.01)
    app.canvas.event_generate('<MouseWheel>',delta=120,state=4,x=150,y=200);pump()
    assert 109<=int(app.pdf_zoom.get().rstrip('%'))<=111
    app.canvas.event_generate('<MouseWheel>',delta=-120,state=4,x=150,y=200);pump()
    assert 99<=int(app.pdf_zoom.get().rstrip('%'))<=101
    before=app.photo.width()
    for i in range(8):app.canvas.event_generate('<MouseWheel>',delta=15,state=4,x=150,y=200)
    pump();assert app.photo.width()>before
    before=app.photo.width();app.pdf_wheel(SimpleNamespace(delta=-15,state=0,x=150,y=200));pump();assert app.photo.width()==before
    app.touchpad_zoom.set(True);app.pdf_wheel(SimpleNamespace(delta=120,state=0,x=150,y=200));pump();assert app.photo.width()>before
    app.zoom_to('25%');app.pdf_wheel(SimpleNamespace(delta=-120,state=4,x=150,y=200));pump();assert int(app.pdf_zoom.get().rstrip('%'))==25
    app.pdf_wheel(SimpleNamespace(delta=120,state=4,x=150,y=200));app.clear_pdf();pump();assert app.wheel_zoom_timer is None and app.wheel_zoom_target is None
    app.preferences_dialog();app.update()
    dialog=next(w for w in app.winfo_children() if w.winfo_class()=='Toplevel')
    next(w for w in dialog.winfo_children() if getattr(w,'label','')=='Appliquer et enregistrer').invoke()
    assert json.loads(app.preferences_path.read_text())['touchpad_zoom'] is True
    app.on_close()
    restarted=App(data_dir=Path(folder)/'data',legacy=Path(folder)/'absent');restarted.withdraw();assert restarted.touchpad_zoom.get();restarted.on_close()
print('PASS: Ctrl+touchpad zoom, high-resolution deltas, ordinary scrolling, optional zoom without Ctrl, limits, cancellation and persistent preference')
