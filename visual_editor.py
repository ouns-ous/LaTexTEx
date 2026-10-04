"""Conservative visual LaTeX editing: untouched and advanced source is preserved."""
from dataclasses import dataclass
import re
import tkinter as tk
from tkinter import ttk


def escaped(text):
    mapping = {'\\': r'\textbackslash{}', '{': r'\{', '}': r'\}', '%': r'\%', '&': r'\&', '#': r'\#', '_': r'\_', '$': r'\$', '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    return ''.join(mapping.get(char, char) for char in text)


def inline(source):
    """Return display text and style spans; reject unknown syntax instead of losing it."""
    text, spans = [], []
    def walk(value, tags=()):
        index = 0
        while index < len(value):
            if value[index] == '\\':
                match = re.match(r'\\(textbf|textit|emph)\{', value[index:])
                if match:
                    start = index + match.end()
                    depth, end = 1, start
                    while end < len(value) and depth:
                        if value[end] == '\\':
                            end += 2
                            continue
                        if value[end] == '{': depth += 1
                        if value[end] == '}': depth -= 1
                        end += 1
                    if depth:
                        raise ValueError('Unbalanced command')
                    walk(value[start:end-1], tags + ('bold' if match.group(1) == 'textbf' else 'italic',))
                    index = end
                    continue
                if index + 1 < len(value) and value[index+1] in '%&#_${}':
                    char = value[index+1]
                    index += 2
                else:
                    raise ValueError('Unsupported inline command')
            else:
                char = value[index]
                if char in '{}$%~^':
                    raise ValueError('Advanced LaTeX')
                index += 1
            offset = len(text)
            text.append(char)
            for tag in tags:
                spans.append((tag, offset, offset + 1))
    walk(source)
    return ''.join(text), spans


def rich_inline(source):
    """Text/style runs and lossless opaque inline math/reference objects."""
    runs = []
    def argument(value, first):
        depth, cursor = 1, first
        while cursor < len(value) and depth:
            if value[cursor] == '\\':
                cursor += 2
                continue
            if value[cursor] == '{': depth += 1
            if value[cursor] == '}': depth -= 1
            cursor += 1
        if depth: raise ValueError('Commande non fermée')
        return cursor
    def walk(value, tags=()):
        cursor = 0
        while cursor < len(value):
            rest = value[cursor:]
            match = re.match(r'\\(textbf|textit|emph|underline)\{', rest)
            if match:
                first = cursor + match.end(); end = argument(value, first)
                tag = {'textbf':'bold','textit':'italic','emph':'italic','underline':'underline'}[match.group(1)]
                walk(value[first:end-1], tags+(tag,));cursor=end;continue
            marker = '\\)' if rest.startswith('\\(') else '$' if rest.startswith('$') and not rest.startswith('$$') else None
            if marker:
                start = cursor + (2 if marker == '\\)' else 1)
                end = start
                while end < len(value):
                    if value.startswith(marker,end): break
                    end += 2 if value[end] == '\\' and marker == '$' else 1
                if end >= len(value): raise ValueError('Mathématiques non fermées')
                last=end+len(marker);runs.append(('math',value[cursor:last],tags));cursor=last;continue
            math_command=re.match(r'\\ensuremath\{',rest)
            if math_command:
                first=cursor+math_command.end();end=argument(value,first)
                runs.append(('math',value[cursor:end],tags));cursor=end;continue
            match=re.match(r'\\(?:cite[a-zA-Z]*|ref|eqref|label)(?:\[[^\]]*\])*\{[^}]*\}',rest)
            if match:
                raw=match.group();runs.append(('reference',raw,tags));cursor+=len(raw);continue
            if value[cursor]=='\\':
                if cursor+1<len(value) and value[cursor+1] in '%&#_${}':
                    runs.append(('text',value[cursor+1],tags));cursor+=2;continue
                match=re.match(r'\\(textbackslash|textasciitilde|textasciicircum)\{\}',rest)
                if match:
                    runs.append(('text',{'textbackslash':'\\','textasciitilde':'~','textasciicircum':'^'}[match.group(1)],tags));cursor+=len(match.group());continue
                raise ValueError('Commande avancée')
            if value[cursor] in '{}%~^': raise ValueError('Syntaxe avancée')
            runs.append(('text',value[cursor],tags));cursor+=1
    walk(source)
    return runs


@dataclass
class Block:
    start: int
    end: int
    kind: str
    raw: str
    content: str = ''
    prefix: str = ''
    suffix: str = ''


class VisualModel:
    def __init__(self, source):
        self.source, self.blocks, self.patches = source, [], {}
        opening = re.search(r'\\begin\{document\}', source)
        closing = source.rfind('\\end{document}')
        start = opening.end() if opening else 0
        end = closing if opening and closing >= start else len(source)
        cursor = start
        while cursor < end:
            while cursor < end and source[cursor].isspace():
                cursor += 1
            if cursor >= end:
                break
            first = cursor
            heading = re.match(r'\\(chapter|section|subsection|subsubsection)(\*?)(\[[^\]]*\])?\{', source[cursor:end])
            kind, prefix, suffix = 'paragraph', '', ''
            if heading:
                content_start = cursor + heading.end()
                depth, last = 1, content_start
                while last < end and depth:
                    if source[last] == '\\':
                        last += 2
                        continue
                    if source[last] == '{': depth += 1
                    if source[last] == '}': depth -= 1
                    last += 1
                if depth:
                    last = end
                    kind, content = 'source', source[first:last]
                else:
                    kind, content = heading.group(1), source[content_start:last-1]
                    prefix, suffix = source[first:content_start], '}'
            else:
                environment = re.match(r'\\begin\{([^}]+)\}', source[cursor:end])
                if environment:
                    name = environment.group(1)
                    depth, last = 1, cursor + environment.end()
                    for token in re.finditer(r'\\(begin|end)\{' + re.escape(name) + r'\}', source[last:end]):
                        depth += 1 if token.group(1) == 'begin' else -1
                        if depth == 0:
                            last += token.end()
                            break
                    else:
                        last = end
                    kind, content = 'source', source[first:last]
                elif source.startswith('\\[', cursor) or source.startswith('$$', cursor):
                    marker = '\\]' if source.startswith('\\[', cursor) else '$$'
                    closing_math = source.find(marker, cursor + 2, end)
                    last = closing_math + len(marker) if closing_math >= 0 else end
                    kind, content = 'source', source[first:last]
                else:
                    boundary = re.search(r'\n[ \t]*\n|\\(?:chapter|section|subsection|subsubsection|begin)\b|\\\[|\$\$', source[cursor+1:end])
                    last = cursor + 1 + boundary.start() if boundary else end
                    content = source[first:last]
            raw = source[first:last]
            try:
                rich_inline(content)
            except ValueError:
                kind = 'source'
            self.blocks.append(Block(first, last, kind, raw, content, prefix, suffix))
            cursor = last

    def render_source(self):
        result, cursor = [], 0
        for index, block in enumerate(self.blocks):
            result.extend((self.source[cursor:block.start], self.patches.get(index, block.raw)))
            cursor = block.end
        result.append(self.source[cursor:])
        return ''.join(result)

    def offset(self, index):
        return self.blocks[index].start + sum(len(self.patches.get(i, b.raw)) - len(b.raw) for i, b in enumerate(self.blocks[:index]))


class VisualView(tk.Frame):
    """Continuous paper-like editing, with real local LaTeX previews."""
    def __init__(self, parent, doc):
        super().__init__(parent, bg='white')
        from visual_render import PreviewRenderer
        self.doc, self.app = doc, doc.app
        self.model = VisualModel(doc.content())
        self.fields, self.active, self.timer = {}, None, None
        self.objects, self.signatures, self.render_labels = {}, {}, {}
        self.photos, self.images = {}, {}
        self.resize_timer = None
        self.renderer = PreviewRenderer(self.app.project, doc.content())
        self.canvas = canvas = tk.Canvas(self, bg='white', highlightthickness=0)
        scroll = ttk.Scrollbar(self, command=canvas.yview)
        scroll.pack(side='right', fill='y')
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(fill='both', expand=True)
        body = self.body = tk.Frame(canvas, bg='white', pady=14)
        window = canvas.create_window(0, 0, window=body, anchor='nw')
        body.columnconfigure(1,weight=1)
        body.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: (canvas.itemconfigure(window,width=e.width),self.schedule_resize()))
        canvas.bind('<MouseWheel>',self.wheel)
        for index, block in enumerate(self.model.blocks):
            number = self.model.source.count('\n',0,block.start)+1
            tk.Label(body,text=str(number),bg='#f1f3f5',fg='#94999f',width=4,font=('Consolas',9),anchor='ne',pady=8).grid(row=index,column=0,sticky='ns')
            if block.kind == 'source':
                label = tk.Label(body,text='Rendu LaTeX…',bg='white',fg='#89929d',font=('Times New Roman',13),cursor='hand2',pady=8)
                label.grid(row=index,column=1,sticky='ew',padx=26,pady=8)
                label.bind('<Double-Button-1>',lambda e,i=index:self.edit_block(i))
                label.bind('<Button-1>',lambda e,i=index:setattr(self,'active',i))
                self.render_labels[('block',index)] = label
                self.renderer.request(('block',index),block.raw)
                label.bind('<MouseWheel>',self.wheel)
                continue
            size={'chapter':21,'section':18,'subsection':16,'subsubsection':14}.get(block.kind,14)
            field=tk.Text(body,wrap='word',undo=True,font=('Times New Roman',size,'bold' if block.kind!='paragraph' else 'normal'),bg='white',fg='#171a1d',borderwidth=0,highlightthickness=0,padx=0,pady=3,height=1,spacing1=2,spacing3=3,selectbackground='#c4e0f3',exportselection=False)
            field.grid(row=index,column=1,sticky='ew',padx=26,pady=(9 if block.kind!='paragraph' else 4,7))
            field.tag_configure('bold',font=('Times New Roman',size,'bold'))
            field.tag_configure('italic',font=('Times New Roman',size,'italic'))
            field.tag_configure('bolditalic',font=('Times New Roman',size,'bold italic'))
            field.tag_configure('underline',underline=True)
            field.tag_configure('center',justify='center')
            for kind,value,tags in rich_inline(block.content):
                if kind=='text':
                    field.insert('end-1c',value,tags)
                else:
                    token=(index,len(self.objects))
                    caption='…' if kind=='math' else '['+re.search(r'\{([^}]*)\}',value).group(1)+']'
                    label=tk.Label(field,text=caption,bg='white',fg='#556475',font=('Times New Roman',size),cursor='hand2',borderwidth=0)
                    field.window_create('end-1c',window=label,align='baseline',padx=2)
                    self.objects[str(label)]=(value,kind,index)
                    label.bind('<Double-Button-1>',lambda e,w=str(label):self.edit_inline(w))
                    label.bind('<Button-1>',lambda e,i=index:setattr(self,'active',i))
                    label.bind('<MouseWheel>',self.wheel)
                    if kind=='math':
                        self.render_labels[token]=label
                        self.renderer.request(token,value,True)
            self.apply_combined_styles(field)
            field.edit_reset();field.edit_modified(False)
            self.fields[index]=(field,field.get('1.0','end-1c'),[])
            self.signatures[index]=self.signature(field)
            field.bind('<FocusIn>',lambda e,i=index:self.focus_field(i))
            field.bind('<<Modified>>',lambda e,i=index:self.changed(i))
            field.bind('<Configure>',lambda e:self.schedule_resize())
            field.bind('<KeyRelease>',lambda e,i=index:self.field_key(i))
            field.bind('<MouseWheel>',self.wheel)
            field.bind('<Up>',lambda e,i=index:self.move_field(e,i,-1))
            field.bind('<Down>',lambda e,i=index:self.move_field(e,i,1))
        if not self.model.blocks:
            self.app.button(body,'Ajouter du texte',self.add_paragraph).grid(row=0,column=1,pady=20)
        self.poll_timer=self.after(75,self.poll_previews)
        self.schedule_resize()

    def wheel(self,event):
        self.canvas.yview_scroll(-1 if event.delta>0 else 1,'units')
        return 'break'

    def focus_field(self,index):
        self.active=index
        self.doc.text.mark_set('insert',f'1.0+{self.model.offset(index)}c')
        self.app.cursor.set(f'Ligne {self.model.source.count(chr(10),0,self.model.blocks[index].start)+1} · Visual')

    def field_key(self,index):
        self.active=index
        self.schedule_resize()

    def move_field(self,event,index,delta):
        field=self.fields[index][0]
        line=int(field.index('insert').split('.')[0])
        last=int(field.index('end-1c').split('.')[0])
        if (delta<0 and line==1) or (delta>0 and line==last):
            keys=list(self.fields);position=keys.index(index)+delta
            if 0<=position<len(keys):
                target=self.fields[keys[position]][0];target.focus_set();target.mark_set('insert','end-1c' if delta<0 else '1.0');return 'break'

    def schedule_resize(self):
        if self.resize_timer:self.after_cancel(self.resize_timer)
        self.resize_timer=self.after(40,self.resize_fields)

    def resize_fields(self):
        self.resize_timer=None
        for field,_,_ in self.fields.values():
            from tkinter import font as tkfont
            import math
            lines=field.count('1.0','end-1c','displaylines')
            line_height=tkfont.Font(font=field.cget('font')).metrics('linespace')
            image_height=max((label.winfo_reqheight() for label in field.winfo_children()),default=0)
            field.configure(height=max(1,(lines[0] if lines else 0)+1)+max(0,math.ceil(image_height/line_height)-1))
        for token,image in self.images.items():self.show_image(token,image)

    def show_image(self,token,image):
        from PIL import ImageTk,Image
        label=self.render_labels.get(token)
        if not label or not label.winfo_exists():return
        limit=max(180,self.canvas.winfo_width()-100)
        if token[0]!='block':limit=min(limit,300)
        ratio=min(1,limit/image.width)
        thumbnail=image.resize((max(1,int(image.width*ratio)),max(1,int(image.height*ratio))),Image.Resampling.LANCZOS)
        self.photos[token]=ImageTk.PhotoImage(thumbnail,master=self)
        label.configure(image=self.photos[token],text='')

    def poll_previews(self):
        import queue
        try:
            while True:
                token,image,error=self.renderer.results.get_nowait()
                if image:
                    self.images[token]=image;self.show_image(token,image)
                else:
                    label=self.render_labels[token]
                    raw=self.model.blocks[token[1]].raw if token[0]=='block' else ''
                    label.configure(text='Équation · double-clic pour modifier' if raw.startswith(('\\[','$$','\\begin{equation}','\\begin{align}')) else 'LaTeX · double-clic pour modifier',fg='#728198')
                    label.preview_error=error
                self.schedule_resize()
        except queue.Empty:pass
        self.poll_timer=self.after(75,self.poll_previews)

    def signature(self,field):
        items=tuple(field.dump('1.0','end-1c',text=True,window=True,tag=True))
        return items+tuple(('object-source',value,self.objects[value][0]) for kind,value,index in items if kind=='window' and value in self.objects)

    def active_text(self):
        return self.fields[self.active][0] if self.active in self.fields else None

    def apply_combined_styles(self,field):
        field.tag_remove('bolditalic','1.0','end')
        for kind,value,index in field.dump('1.0','end-1c',text=True):
            if kind!='text':continue
            for offset,char in enumerate(value):
                at=field.index(f'{index}+{offset}c')
                if {'bold','italic'}.issubset(field.tag_names(at)):field.tag_add('bolditalic',at,f'{at}+1c')
        field.tag_raise('bolditalic')

    def encode_field(self,field,with_positions=False):
        result=[];current=();positions={};length=0
        def styles(tags):
            nonlocal current,length
            if tags!=current:
                closing='}'*len(current);result.append(closing);length+=len(closing)
                opening=''.join({'bold':'\\textbf{','italic':'\\textit{','underline':'\\underline{'}[tag] for tag in tags)
                result.append(opening);length+=len(opening);current=tags
        for kind,value,index in field.dump('1.0','end-1c',text=True,window=True):
            if kind not in ('text','window'):continue
            parts=[(index,self.objects[value][0])] if kind=='window' and value in self.objects else [(field.index(f'{index}+{i}c'),escaped(char)) for i,char in enumerate(value)] if kind=='text' else []
            for at,raw in parts:
                tags=tuple(tag for tag in ('bold','italic','underline') if tag in field.tag_names(at));styles(tags)
                positions[at]=length;result.append(raw);length+=len(raw)
        positions[field.index('end-1c')]=length
        result.extend('}' for _ in current)
        source=''.join(result)
        return (source,positions) if with_positions else source

    def changed(self,index):
        field=self.fields[index][0]
        if not field.edit_modified():return
        field.edit_modified(False)
        if self.timer:self.after_cancel(self.timer)
        self.timer=self.after(400,self.flush)
        self.schedule_resize()

    def format(self,tag):
        field=self.active_text()
        if field:
            try:first,last=field.index('sel.first'),field.index('sel.last')
            except tk.TclError:return
            if tag in field.tag_names(first):field.tag_remove(tag,first,last)
            else:field.tag_add(tag,first,last)
            self.apply_combined_styles(field);self.flush()

    def flush(self):
        if getattr(self,'rebuilding',False):return
        if self.timer:self.after_cancel(self.timer);self.timer=None
        for index,(field,original,spans) in self.fields.items():
            if self.signature(field)==self.signatures[index]:self.model.patches.pop(index,None)
            else:
                block=self.model.blocks[index]
                self.model.patches[index]=block.prefix+self.encode_field(field)+block.suffix
        source=self.model.render_source()
        if source!=self.doc.content():self.doc.replace_range('1.0','end',source);self.doc.changed()

    def source_selection(self):
        """Map the actual Visual caret to source before inserting a LaTeX tool."""
        self.flush()
        field=self.active_text()
        if not field:
            self.flush()
            index=self.active if self.active is not None else next(iter(self.fields),None)
            offset=self.model.offset(index) if index is not None else len(self.doc.content())
            return offset,offset
        index=self.active;block=self.model.blocks[index]
        encoded,positions=self.encode_field(field,True)
        # Canonicalize only the paragraph being acted on; opaque objects stay exact.
        self.model.patches[index]=block.prefix+encoded+block.suffix
        self.signatures[index]=None
        source=self.model.render_source()
        if source!=self.doc.content():self.doc.replace_range('1.0','end',source)
        try:first,last=field.index('sel.first'),field.index('sel.last')
        except tk.TclError:first=last=field.index('insert')
        start=self.model.offset(index)+len(block.prefix)
        return start+positions.get(first,len(encoded)),start+positions.get(last,len(encoded))

    def focus_source_offset(self,offset):
        index=next((i for i,b in enumerate(self.model.blocks) if b.start<=offset<=b.end),None)
        if index is None:return
        self.active=index
        if index in self.fields:
            field=self.fields[index][0]
            encoded,positions=self.encode_field(field,True)
            relative=max(0,offset-self.model.blocks[index].start-len(self.model.blocks[index].prefix))
            at=min(positions,key=lambda at:abs(positions[at]-relative)) if positions else '1.0'
            field.focus_set();field.mark_set('insert',at)
            self.after_idle(lambda:self.canvas.yview_moveto(max(0,field.winfo_y()-30)/max(1,self.body.winfo_height())))

    def go_code(self,index):
        self.flush();offset=self.model.offset(index);self.app.set_edit_mode('Code');self.doc.text.mark_set('insert',f'1.0+{offset}c');self.doc.text.see('insert');self.doc.text.focus_set()

    def edit_source_dialog(self,title,raw,apply):
        if self.app.readonly:return
        dialog=tk.Toplevel(self.app);dialog.title(title);dialog.geometry('640x330');dialog.transient(self.app);dialog.grab_set()
        tk.Label(dialog,text='Modifiez le LaTeX ; le rendu se met à jour après validation.',anchor='w',padx=14,pady=12).pack(fill='x')
        text=tk.Text(dialog,undo=True,font=('Consolas',12),wrap='word',padx=12,pady=10);text.pack(fill='both',expand=True,padx=12);text.insert('1.0',raw)
        self.app.button(dialog,'Appliquer',lambda:(apply(text.get('1.0','end-1c')),dialog.destroy()),accent=True).pack(side='right',padx=12,pady=10)
        text.focus_set()

    def edit_block(self,index):
        self.active=index
        if self.model.blocks[index].raw.strip()=='\\maketitle':
            self.edit_title()
            return
        self.edit_source_dialog('Éditer le bloc LaTeX',self.model.patches.get(index,self.model.blocks[index].raw),lambda raw:self.replace_block(index,raw))

    def edit_title(self):
        if self.app.readonly:return
        source=self.doc.content()
        values={}
        for name in ('title','author','date'):
            match=re.search(r'\\'+name+r'\{',source)
            if match:
                first=match.end();last=first;depth=1
                while last<len(source) and depth:
                    if source[last]=='\\':last+=2;continue
                    if source[last]=='{':depth+=1
                    if source[last]=='}':depth-=1
                    last+=1
                if not depth:values[name]=(first,last-1,source[first:last-1])
        dialog=tk.Toplevel(self.app);dialog.title('Titre du document');dialog.transient(self.app);dialog.grab_set()
        variables={}
        for name,label in [('title','Titre'),('author','Auteur'),('date','Date (LaTeX accepté)')]:
            tk.Label(dialog,text=label,anchor='w').pack(fill='x',padx=18,pady=(10,3))
            variable=tk.StringVar(value=values.get(name,(0,0,'\\today' if name=='date' else ''))[2]);variables[name]=variable
            ttk.Entry(dialog,textvariable=variable,width=56).pack(fill='x',padx=18)
        def apply():
            self.flush();updated=self.doc.content()
            for name,(first,last,old) in sorted(values.items(),key=lambda item:item[1][0],reverse=True):
                updated=updated[:first]+variables[name].get()+updated[last:]
            for name in variables.keys()-values.keys():
                updated=updated.replace('\\begin{document}','\\'+name+'{'+variables[name].get()+'}\n\\begin{document}',1)
            self.doc.replace_range('1.0','end',updated);self.rebuilding=True;self.app.set_edit_mode('Visual');dialog.destroy()
        self.app.button(dialog,'Appliquer',apply,accent=True).pack(padx=18,pady=18,anchor='e')

    def replace_block(self,index,raw):
        self.flush();first=self.model.offset(index);old=self.model.patches.get(index,self.model.blocks[index].raw)
        self.doc.replace_range(f'1.0+{first}c',f'1.0+{first+len(old)}c',raw)
        self.rebuilding=True
        self.app.set_edit_mode('Visual')

    def edit_inline(self,key):
        raw,kind,index=self.objects[key]
        def apply(value):
            self.objects[key]=(value,kind,index);self.flush();self.app.set_edit_mode('Visual')
        self.edit_source_dialog('Éditer la formule' if kind=='math' else 'Éditer la référence',raw,apply)

    def add_paragraph(self):
        self.app.set_edit_mode('Code');index=self.doc.text.search('\\end{document}','1.0') or 'end-1c';self.doc.text.insert(index,'\nVotre texte ici.\n\n');self.app.set_edit_mode('Visual')

    def dispose(self):
        for timer in (self.timer,self.resize_timer,self.poll_timer):
            if timer:self.after_cancel(timer)
        self.renderer.close();self.destroy()
