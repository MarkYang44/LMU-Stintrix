"""Shared maintenance lists: stable identities, bounded UI work and explicit state."""
import tkinter as tk
from tkinter import ttk
from control_theme import T
from control_maintenance import shell
from control_fields import Select
from control_search import SearchField
from control_video_widgets import Action
from control_flow import install as flow
from control_motion import keyboard_action
from control_widgets import px
from i18n import tr


def existing(app,name):
    window=getattr(app,name,None)
    if window is not None and window.winfo_exists():window.deiconify();window.lift();return window


class WorkList:
    def __init__(self,app,title,columns,key,row,filters=None,accept=lambda item,view:True,detail=lambda item:'',hint='',searchable=lambda item:'',include=lambda item:False):
        self.app=app;self.key=key;self.row=row;self.accept=accept;self.detail=detail;self.searchable=searchable;self.title=title;self.columns=columns;self.include=include;self.on_loaded=None
        self.items={};self.remembered=();self.loading=False;self.error=False;self.generation=0;self.buttons={};self.conditions={};self.widths={};self.notice=('',{});self.detail_text=None
        self.window,self.footer,self.table,self.status=shell(app,title,columns,feedback=True);self.window.worklist=self
        self.window.geometry('1050x720');self.window.minsize(800,620)
        self.query=tk.StringVar(self.window);self.view=tk.StringVar(self.window,value=next(iter(filters or {'all':''})));self.count=tk.StringVar(self.window)
        parent=self.table.master;tools=tk.Frame(parent,bg=T.CARD);tools.pack(fill='x',before=self.table,pady=(0,5))
        if filters:
            self.filter=Select(tools,textvariable=self.view,values=list(filters),labels=filters,width=24);self.filter.pack(side='left',padx=(0,8))
            self.filter.bind('<<ComboboxSelected>>',lambda _:self.render())
        self.search=SearchField(tools,self.query,self.render);self.search.pack(side='left',fill='x',expand=True)
        self.count_label=app.label(parent,self.count,9,T.MUTED);self.count_label.pack(fill='x',before=self.table)
        self.hint=app.label(parent,hint,9,T.MUTED);self.hint.pack(fill='x',before=self.table,pady=(3,0));self.hint.bind('<Configure>',lambda e:self.hint.configure(wraplength=max(100,e.width)))
        holder=tk.Frame(parent,bg=T.FIELD);holder.pack(side='bottom',fill='x',before=self.table)
        self.details=tk.Text(holder,height=3,bg=T.FIELD,fg=T.FG,insertbackground=T.FG,relief='flat',wrap='word',font=(T.FONT,9),padx=8,pady=6,state='disabled')
        scrollbar=ttk.Scrollbar(holder,command=self.details.yview,orient='vertical',style='Lab.Vertical.TScrollbar');scrollbar.pack(side='right',fill='y');self.details.configure(yscrollcommand=scrollbar.set);self.details.pack(fill='both',expand=True)
        self.table.bind('<<TreeviewSelect>>',self.selected);self.table.copy_feedback=lambda text:self.say(text)
        self.window.bind('<Control-f>',lambda _:(self.search.entry.focus_set(),'break')[1]);self.window.bind('<Escape>',lambda _:self.window.destroy())
        self.window.bind('<Destroy>',self.dispose,add='+');self.window.retranslate=self.translate;flow(self.footer)
    def alive(self):return not self.app.closing and self.window.winfo_exists()
    def say(self,text,**values):
        self.notice=(text,values);self.status.set(tr(text).format(**values) if values else tr(text))
    def selected_items(self):return [self.items[i] for i in self.table.selection() if i in self.items]
    def selected(self,event=None):
        if event is not None:self.remembered=self.table.selection()
        self.count.set(tr('显示 {shown}/{total} 项 · 已选 {selected} 项').format(shown=len(self.table.get_children()),total=len(self.items),selected=len(self.table.selection())))
        chosen=self.selected_items();text=self.detail(chosen[0]) if len(chosen)==1 else tr('已选择 {count} 项').format(count=len(chosen)) if chosen else tr('选择一项查看详情')
        if text!=self.detail_text:
            self.details.configure(state='normal');self.details.delete('1.0','end');self.details.insert('1.0',text);self.details.configure(state='disabled');self.detail_text=text
        self.sync()
    def render(self):
        if not self.alive():return
        words=self.query.get().casefold().split();rows=[]
        for key,item in self.items.items():
            values=self.row(item)
            text=(' '.join(map(str,values))+' '+self.searchable(item)).casefold()
            if self.include(item) or self.accept(item,self.view.get()) and all(word in text for word in words):rows.append((key,values))
        keyboard_action(self.table,lambda:self.table.replace(rows,self.remembered))
        self.table.set_empty('正在读取列表…' if self.loading else '读取失败，请刷新重试' if self.error else '没有匹配的项目' if self.items else '暂无项目')
        self.count.set(tr('显示 {shown}/{total} 项 · 已选 {selected} 项').format(shown=len(rows),total=len(self.items),selected=len(self.table.selection())))
        self.selected()
    def sync(self):
        if not self.alive():return
        for key,button in self.buttons.items():
            enabled=not self.loading and bool(self.conditions[key]())
            if button.enabled!=enabled:button.configure(state='normal' if enabled else 'disabled')
    def action(self,key,title,command,width=150,primary=False,enabled=lambda:True):
        def invoke():
            if not self.alive():return
            self.sync()
            if self.buttons[key].enabled:return command()
        button=Action(self.footer,title,invoke,width,primary);button.pack(side='left',padx=(0,8));self.buttons[key]=button;self.conditions[key]=enabled;self.widths[key]=width;self.sync();return button
    def load(self,work,notice,**values):
        self.generation+=1;generation=self.generation;self.loading=True;self.error=False;self.say('正在读取列表…');self.window.work_feedback.busy('load');self.render();self.sync()
        def done(value,error):
            if not self.alive() or generation!=self.generation:return
            self.loading=False;self.window.work_feedback.busy('load',False)
            if error is not None:self.error=True;self.render();self.say(str(error));self.sync()
            else:self.items={self.key(item):item for item in value};self.render();self.say(notice,**values)
            if self.on_loaded:self.on_loaded()
        self.app.run_background(work,done)
    def translate(self):
        for key,label,_ in self.columns:self.table.heading(key,label)
        self.window.title(tr(self.title));self.render()
        text,values=self.notice;self.say(text,**values)
        for key,button in self.buttons.items():button.configure(width=max(px(button,self.widths[key]),button.font.measure(tr(button.label))+px(button,36)))
        if self.footer.winfo_width()>1:self.footer.event_generate('<Configure>',width=self.footer.winfo_width(),height=self.footer.winfo_height())
    def dispose(self,event):
        if event.widget is self.window:
            for variable in (self.query,self.view,self.count,self.status):variable.__del__();variable._tk=None
