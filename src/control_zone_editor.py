"""Staged distance-zone edits: direct save, recoverable reset and explicit drafts."""
import copy,tkinter as tk
from functools import partial
from i18n import tr,Label
from control_theme import T
from control_fields import Field
from control_list import SessionList
from control_video_widgets import Action,ScrollPage
from control_flow import install
from control_feedback import StatusFeedback
from control_validation import Feedback
from control_widgets import px,backdrop
from training_zones import validate,save,path

FIELDS=(('name','名称'),('start','起点 / m'),('apex','弯心 / m'),('end','终点 / m'))


def persist(root,entry,zones,automatic):
    if automatic:path(root,entry).unlink(missing_ok=True)
    else:save(root,entry,zones)


def show(app,entry,definitions,on_save):
    if app.closing:return
    windows=getattr(app,'zone_windows',{});app.zone_windows=windows;identity=str(path(app.data_path,entry).resolve())
    previous=windows.get(identity)
    if previous is not None and previous.winfo_exists():
        if on_save not in previous.zone_editor.callbacks:previous.zone_editor.callbacks.append(on_save)
        previous.deiconify();previous.lift();previous.focus_force();return previous
    panel=ZoneEditor(app,identity,entry,definitions,on_save);windows[identity]=panel.window;backdrop(panel.window);return panel.window


class ZoneEditor:
    def __init__(self,app,identity,entry,definitions,on_save):
        self.app=app;self.identity=identity;self.entry=copy.deepcopy(entry);self.callbacks=[on_save];self.items=[(str(i),copy.deepcopy(z)) for i,z in enumerate(definitions)];self.serial=len(self.items);self.selected=None;self.loading=False;self.automatic=False;self.busy=False;self.undo_state=None;self.after_close=None;self.notice=('',{})
        self.original=copy.deepcopy(self.items)
        w=tk.Toplevel(app.root);self.window=w;w.zone_editor=self;w.configure(bg=T.BG);w.transient(app.root);w.geometry('940x760');w.minsize(680,540)
        footer=tk.Frame(w,bg=T.CARD);footer.pack(side='bottom',fill='x',padx=18,pady=(0,14));self.status=tk.StringVar(w);self.feedback=StatusFeedback(footer,self.status);self.feedback.pack(fill='x',padx=10,pady=6)
        row=tk.Frame(footer,bg=T.CARD);row.pack(fill='x',padx=10,pady=(0,8));self.actions=row;install(row);self.buttons={}
        for key,title,command in (('save','保存并重新分析',self.commit),('undo','撤销上一步',self.undo),('automatic','恢复自动区间',self.reset)):
            b=Action(row,title,command,160,key=='save');b.pack(side='left');self.buttons[key]=b
        self.scroll=ScrollPage(w);self.scroll.pack(fill='both',expand=True,padx=18,pady=(14,8));self.scroll.canvas.configure(bg=T.CARD);body=self.scroll.body;body.configure(bg=T.CARD)
        def label(text,size=10):
            l=Label(body,text=text,bg=T.CARD,fg=T.FG if size>10 else T.MUTED,font=(T.FONT,size),anchor='w',justify='left');l.pack(fill='x',padx=12,pady=6);l.bind('<Configure>',lambda e:l.configure(wraplength=max(80,e.width)));return l
        label('编辑分析区间',18);label('距离单位 m；自定义名称不等于官方弯号。允许留空区间，禁止重叠。');label('直接编辑后保存即可；切换区间会先保留有效输入，原始圈数据不变。')
        self.context=label('',10);self.table=SessionList(body,columns=tuple(k for k,_ in FIELDS),height=4,selectmode='browse');self.table.pack(fill='x',padx=12,pady=8)
        self.table.bind('<<TreeviewSelect>>',self.choose);self.table.viewport.bind('<MouseWheel>',self.table_wheel)
        self.forms=tk.Frame(body,bg=T.CARD);self.forms.pack(fill='x',padx=8,pady=4);self.tiles=[];self.variables={};self.fields={};self.validation=Feedback()
        for key,title in FIELDS:
            tile=tk.Frame(self.forms,bg=T.CARD);self.tiles.append(tile);Label(tile,text=title,bg=T.CARD,fg=T.MUTED,font=(T.FONT,9)).pack(anchor='w');v=tk.StringVar(w);self.variables[key]=v
            field=Field(tile,textvariable=v,width=12);field.pack(fill='x',pady=(3,4));self.fields[key]=field
            hint=Label(tile,text='',bg=T.CARD,fg=T.RED,font=(T.FONT,9),anchor='w',justify='left');self.validation.add(key,field,title,hint)
            v.trace_add('write',self.changed)
        self.forms.bind('<Configure>',self.layout)
        edits=tk.Frame(body,bg=T.CARD);edits.pack(fill='x',padx=12,pady=8);self.edits=edits;install(edits)
        for key,title,command in (('new','新建区间',self.new),('remove','移除选中区间',self.remove)):
            b=Action(edits,title,command,150);b.pack(side='left');self.buttons[key]=b
        w.protocol('WM_DELETE_WINDOW',self.close);w.bind('<Escape>',lambda _:(self.close(),'break')[1]);w.bind('<Control-s>',lambda _:(self.commit(),'break')[1]);w.bind('<MouseWheel>',self.wheel);w.bind('<Destroy>',self.dispose,add='+');w.retranslate=self.translate
        from control_confirm import register
        register(app,w,self.close);self.populate(self.items[0][0] if self.items else None);self.say('选择区间编辑，或新建区间');self.translate()
    def alive(self):return not self.app.closing and bool(self.window.winfo_exists())
    def say(self,text,**values):self.notice=(text,values);self.status.set(tr(text).format(**values))
    def raw(self):return {k:v.get() for k,v in self.variables.items()}
    def form_dirty(self):return self.raw()!=self.form_initial
    def dirty(self):return self.automatic or self.items!=self.original or self.form_dirty()
    def snapshot(self):return copy.deepcopy((self.items,self.selected,self.raw(),self.form_initial,self.automatic))
    def sync(self):
        for key,b in self.buttons.items():b.configure(state='normal' if not self.busy and (key!='remove' or self.selected is not None and not self.automatic) and (key!='undo' or self.undo_state is not None) and (key!='automatic' or not self.automatic) else 'disabled')
        for f in self.fields.values():f.entry.configure(state='disabled' if self.busy or self.automatic else 'normal')
    def changed(self,*_):
        if self.loading:return
        self.validation.clear();self.say('修改尚未保存；直接保存会包含当前输入');self.sync()
    def form(self,values):
        self.loading=True
        for k,v in self.variables.items():v.set(str(values.get(k,'')))
        self.form_initial=self.raw();self.loading=False;self.validation.clear()
    def populate(self,selected,raw=None,initial=None):
        self.loading=True;self.table.replace([(i,(z['name'],*(f'{z[k]:.3f}' for k in ('start','apex','end')))) for i,z in self.items],(selected,) if selected is not None else ());self.selected=selected;self.loading=False
        self.form(dict(self.items).get(selected,{}) if raw is None else raw)
        if initial is not None:self.form_initial=initial
        self.sync()
    def error(self,message,fields):
        e=ValueError(tr(message));e.fields=fields;raise e
    def apply_form(self):
        if self.automatic or not self.form_dirty():return
        values=self.raw()
        if not values['name'].strip() or len(values['name'].strip())>60:self.error('区间名称须为 1–60 个字符',('name',))
        for k in ('start','apex','end'):
            try:values[k]=float(values[k])
            except ValueError:self.error('请输入有效数值',(k,))
        try:zone=validate([values],self.entry['length_m'])[0]
        except ValueError as error:error.fields=('start','apex','end');raise
        selected=self.selected
        if selected is None:selected=str(self.serial);self.serial+=1
        items=[(i,z) for i,z in self.items if i!=selected]+[(selected,zone)]
        try:validate([z for _,z in items],self.entry['length_m'])
        except ValueError as error:error.fields=('start','end');raise
        self.items=sorted(items,key=lambda item:item[1]['start']);self.populate(selected)
    def attempt(self,command):
        try:command();return True
        except (ValueError,KeyError,TypeError) as error:self.validation.show(error);self.say('区间未保存：{error}',error=error);return False
    def choose(self,_=None):
        if self.loading:return
        selected=next(iter(self.table.selection()),None)
        if self.busy or self.automatic:
            self.loading=True;self.table.selection_set((self.selected,) if self.selected is not None else ());self.loading=False;return
        if selected==self.selected:return
        before=self.snapshot()
        if not self.attempt(self.apply_form):
            self.loading=True;self.table.selection_set((self.selected,) if self.selected else ());self.loading=False;return
        if before[2]!=before[3]:self.undo_state=before
        self.populate(selected);self.say('选择区间编辑，或新建区间')
    def new(self):
        if self.busy:return
        before=self.snapshot()
        if not self.attempt(self.apply_form):return
        self.undo_state=before;self.automatic=False;self.populate(None);self.say('填写新区间后直接保存即可');self.fields['name'].focus_set()
    def remove(self):
        if self.busy or self.selected is None or self.automatic:return
        self.undo_state=self.snapshot();index=next(i for i,(key,_) in enumerate(self.items) if key==self.selected);self.items.pop(index);self.populate(self.items[min(index,len(self.items)-1)][0] if self.items else None);self.say('区间已移除，保存后生效；可撤销')
    def reset(self):
        if self.busy or self.automatic:return
        self.undo_state=self.snapshot();self.automatic=True;self.say('已暂选自动区间；保存后生效，可撤销');self.sync()
    def undo(self):
        if self.busy or self.undo_state is None:return
        current=self.snapshot();self.items,selected,raw,initial,self.automatic=copy.deepcopy(self.undo_state);self.undo_state=current;self.populate(selected,raw,initial);self.say('已撤销；保存后生效')
    def commit(self,after=None):
        if self.busy:return
        if not self.attempt(self.apply_form):return
        if not self.automatic and not self.attempt(lambda:validate([z for _,z in self.items],self.entry['length_m'])):return
        self.busy=True;self.after_close=after;self.feedback.busy('save');self.say('正在保存分析区间…');self.sync()
        def done(value,error):
            if not self.alive():return
            self.busy=False;self.feedback.busy('save',False)
            if error:self.after_close=None;self.say('区间未保存：{error}',error=error);self.sync();return
            for callback in self.callbacks:
                try:callback()
                except Exception as failure:self.app.status.set(tr('区间已保存，重新分析未能启动：{error}').format(error=failure))
            after=self.after_close;self.window.destroy()
            if after:after()
        self.app.run_background(partial(persist,self.app.data_path,self.entry,copy.deepcopy([z for _,z in self.items]),self.automatic),done)
    def close(self,done=None,exiting=False):
        if self.busy:self.after_close=done;return
        if self.dirty():
            from control_confirm import ask
            answer=ask(self.window,'有未保存修改','保存包含当前输入；恢复自动区间也仅在保存后生效。',[('save','保存并重新分析'),('discard','放弃修改并关闭'),('cancel','继续编辑')])
            if answer=='save':self.commit(done);return
            if answer!='discard':return
        self.window.destroy()
        if done:done()
    def layout(self,event):
        columns=max(1,min(4,event.width//210))
        for i,tile in enumerate(self.tiles):tile.grid(row=i//columns,column=i%columns,sticky='new',padx=4,pady=4)
        for i in range(4):self.forms.columnconfigure(i,weight=1 if i<columns else 0,minsize=0)
    def translate(self):
        self.window.title(tr('编辑分析区间'));self.context.configure(text=tr('赛道长度')+f" {self.entry['length_m']:g} m")
        for key,title in FIELDS:self.table.heading(key,text=tr(title));self.table.column(key,width=210 if key=='name' else 120,minwidth=90,stretch=True)
        for b in self.buttons.values():b.configure(width=max(px(b,120),b.font.measure(tr(b.label))+px(b,36)))
        for row in (self.actions,self.edits):row.event_generate('<Configure>',width=row.winfo_width())
        self.say(self.notice[0],**self.notice[1])
    def table_wheel(self,event):
        t=self.table
        if not event.state&1 and (t.limit()<=0 or event.delta>0 and t.offset<=0 or event.delta<0 and t.offset>=t.limit()):self.scroll.wheel(event.delta);return 'break'
        return t.wheel(event)
    def wheel(self,event):
        widget=event.widget
        while widget is not None and widget is not self.window:
            if widget is self.table:return
            if widget is self.scroll:self.scroll.wheel(event.delta);return 'break'
            widget=getattr(widget,'master',None)
    def dispose(self,event):
        if event.widget is not self.window:return
        self.app.zone_windows.pop(self.identity,None);self.callbacks.clear()
        for v in (*self.variables.values(),self.status):v.__del__();v._tk=None
