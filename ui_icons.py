"""Crisp, shared 24-unit outline icons rendered directly on Tk canvases."""
import math
import json
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageTk

ASSET_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent)) / "assets" / "fontawesome"
FONT_PATH = ASSET_ROOT / "fa-solid-900.ttf"
GLYPHS = json.loads((ASSET_ROOT / "selected-icons.json").read_text(encoding="utf-8"))
FONT_CACHE = {}

ICONS = {'↶':'undo', '↷':'redo', '⌕':'search', '‹':'left', '›':'right', '−':'minus', '+':'plus', '▾':'down', '✎':'edit', '↗':'link', '⋯':'more', '✦':'sparkles', '▤':'file', '▧':'code', '▣':'image', '☷':'comments', '?':'help', '⚙':'settings', '▣':'image', '↑':'upload', '↓':'download', '◐':'contrast', '×':'close', 'B':'bold', 'I':'italic', 'T▾':'type', 'Ω':'omega'}
TIPS = {'undo':'Annuler · Ctrl+Z','redo':'Rétablir','search':'Rechercher','left':'Précédent','right':'Suivant','minus':'Réduire le zoom','plus':'Ajouter','down':'Options','edit':'Editing / Viewing','link':'Insérer un lien','more':'Autres outils','sparkles':'Assistant LaTeX local','file':'Fichiers','code':'Journal de compilation','image':'Images et ressources','comments':'Commentaires','help':'Aide','settings':'Préférences','upload':'Importer','download':'Télécharger le PDF','contrast':'PDF clair / sombre','close':'Fermer','bold':'Gras','italic':'Italique','type':'Titres et sections','omega':'Symboles mathématiques','folder':'Nouveau dossier','file-plus':'Nouveau fichier'}

def draw_icon(canvas, name, x, y, color, size=18):
    if name in GLYPHS:
        key = (name, color, size)
        if not hasattr(canvas, '_icon_images'):
            canvas._icon_images = {}
        if key not in canvas._icon_images:
            resolution = size * 4
            if resolution not in FONT_CACHE:
                FONT_CACHE[resolution] = ImageFont.truetype(str(FONT_PATH), resolution)
            font = FONT_CACHE[resolution]
            glyph = chr(int(GLYPHS[name], 16))
            bounds = font.getbbox(glyph)
            tile = Image.new('RGBA', (resolution + 8, resolution + 8))
            painter = ImageDraw.Draw(tile)
            painter.text(((tile.width-(bounds[2]-bounds[0]))/2-bounds[0], (tile.height-(bounds[3]-bounds[1]))/2-bounds[1]), glyph, font=font, fill=color)
            tile = tile.resize((size+2,size+2), Image.Resampling.LANCZOS)
            canvas._icon_images[key] = ImageTk.PhotoImage(tile, master=canvas)
        canvas.create_image(x, y, image=canvas._icon_images[key])
        return
    scale = size/24
    def points(coords): return [((x-size/2)+v*scale if i%2==0 else (y-size/2)+v*scale) for i,v in enumerate(coords)]
    def line(*coords): canvas.create_line(*points(coords),fill=color,width=1.7,capstyle='round',joinstyle='round')
    def oval(a,b,c,d,fill=''): canvas.create_oval(*points((a,b,c,d)),outline=color,width=1.7,fill=fill)
    def rect(a,b,c,d): canvas.create_rectangle(*points((a,b,c,d)),outline=color,width=1.7)
    if name in ('left','right','down'):
        line(*( (15,5,8,12,15,19) if name=='left' else (9,5,16,12,9,19) if name=='right' else (6,9,12,15,18,9)))
    elif name in ('plus','minus','close'):
        if name=='close': line(6,6,18,18); line(18,6,6,18)
        else:
            line(5,12,19,12)
            if name=='plus': line(12,5,12,19)
    elif name=='search': oval(3,3,16,16); line(15,15,21,21)
    elif name in ('undo','redo'):
        transform = lambda a: 24-a if name=='redo' else a
        coords = (4,10,8,6,13,6,18,8,20,12,19,17,15,20)
        line(*[transform(v) if i%2==0 else v for i,v in enumerate(coords)])
        line(transform(4),4,transform(4),10,transform(10),10)
    elif name in ('file','file-plus','code'):
        line(6,2,14,2,19,7,19,22,6,22,6,2); line(14,2,14,7,19,7)
        if name=='file-plus': line(9,14,16,14);line(12.5,10.5,12.5,17.5)
        elif name=='code':line(10,11,8,14,10,17);line(15,11,17,14,15,17)
        else:line(9,12,16,12);line(9,16,16,16)
    elif name=='folder': line(2,7,2,20,22,20,22,7,11,7,9,4,2,4,2,7);line(12,11,12,17);line(9,14,15,14)
    elif name in ('upload','download'):
        line(4,17,4,21,20,21,20,17)
        if name=='upload':line(12,17,12,3);line(7,8,12,3,17,8)
        else:line(12,3,12,16);line(7,11,12,16,17,11)
    elif name=='image':rect(3,3,21,21);oval(7,6,11,10);line(4,19,10,13,14,17,17,12,21,17)
    elif name=='comments':line(3,4,21,4,21,17,10,17,5,21,5,17,3,17,3,4);line(7,9,17,9);line(7,13,14,13)
    elif name=='link':
        line(10,15,7,18,4,18,2,16,2,13,7,8,10,8);line(14,9,17,6,20,6,22,8,22,11,17,16,14,16);line(8,16,16,8)
    elif name=='edit':line(4,17,16,5,20,9,8,21,3,22,4,17);line(14,7,18,11)
    elif name=='more':
        for a in (5,12,19):oval(a-1,a*0+11,a+1,13,color)
    elif name=='help':
        oval(2,2,22,22);line(9,8,10,6,14,6,16,8,16,10,12,13,12,15);oval(11.5,18,12.5,19,color)
    elif name=='contrast':
        oval(3,3,21,21); canvas.create_arc(*points((3,3,21,21)),start=90,extent=180,fill=color,outline=color);line(12,3,12,21)
    elif name=='settings':
        oval(8,8,16,16)
        outline=[]
        for i in range(32):
            angle=i*math.pi/16; radius=10 if i%4 in (1,2) else 8
            outline.extend((12+radius*math.cos(angle),12+radius*math.sin(angle)))
        line(*(outline+outline[:2]))
    elif name=='sparkles':line(12,2,15,9,22,12,15,15,12,22,9,15,2,12,9,9,12,2)
    elif name=='bold':line(7,3,7,21,14,21,18,19,18,15,14,12,7,12,14,12,17,9,17,5,14,3,7,3)
    elif name=='italic':line(10,3,20,3);line(4,21,14,21);line(15,3,9,21)
    elif name=='type':line(4,5,18,5);line(11,5,11,21);line(7,21,15,21);line(20,13,22,15,24,13)
    elif name=='history':
        oval(4,4,21,21);line(12,7,12,13,16,15);line(2,5,2,11,7,11)
    elif name=='layout':
        rect(3,3,21,21);line(10,3,10,21);line(3,8,10,8)
    elif name=='share':
        oval(4,3,12,11);line(2,21,2,18,5,14,11,14,14,18,14,21);line(18,5,18,13);line(14,9,22,9)
    elif name=='refresh':
        line(20,9,18,5,13,3,7,5,4,9);line(4,15,6,19,11,21,17,19,20,15);line(20,3,20,9,14,9);line(4,21,4,15,10,15)
    elif name=='omega':line(3,21,9,21,9,18,5,14,4,9,6,5,10,3,14,3,18,5,20,9,19,14,15,18,15,21,21,21)

CAPTIONS = {'History':('history','History'), 'Layout':('layout','Layout'), 'Share':('share','Share'), '↻ Actualiser':('refresh','Actualiser'), '+ Nouveau projet':('plus','Nouveau projet'), '＋ Fichier':('file-plus','Fichier')}
