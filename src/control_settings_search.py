"""Search the rendered preference controls; values and page context stay intact."""
import tkinter as tk
from control_search import SearchField
from control_theme import T
from i18n import tr

SECTIONS={'sampling':'输入采样','vehicle':'车辆策略','endurance':'耐力与天气'}


from control_video_widgets import Action
class Result(Action):
    """Keep long translated result names inside their column; full text stays reachable."""
    def __init__(self,parent,text,command):
        self.full_text=text;super().__init__(parent,text,command,140)
        from control_tooltip import Tooltip
        self.tip=Tooltip(self)
        self.bind('<Enter>',self.hint,add='+');self.bind('<FocusIn>',self.hint,add='+')
        self.bind('<Leave>',lambda _:self.tip.hide(),add='+');self.bind('<FocusOut>',lambda _:self.tip.hide(),add='+')
        self.bind('<Destroy>',lambda e:self.tip.hide() if e.widget is self else None,add='+')
    def paint(self):
        super().paint();text=self.full_text;maximum=max(1,self.winfo_width()-28*self.s)
        if self.font.measure(text)>maximum:
            while text and self.font.measure(text+'…')>maximum:text=text[:-1]
            text+='…'
        self.itemconfigure(self.caption,text=text)
    def hint(self,_=None):
        if self.font.measure(self.full_text)>self.winfo_width()-28*self.s:self.tip.request(self.full_text,self.full_text,self.winfo_rootx(),self.winfo_rooty()+self.winfo_height())


def register(app,key,label,widget,module,action=None):
    if not hasattr(app,'settings_index'):app.settings_index=[]
    app.settings_index.append(dict(key=key,label=label,widget=widget,section=SECTIONS.get(module,module),action=action))


def matches(entries,query):
    words=query.casefold().split()
    return [entry for entry in entries if all(word in (' '.join([entry['key'],entry['label'],tr(entry['label']),entry['section'],tr(entry['section'])])).casefold() for word in words)] if words else []


def register_routes(app,anchor):
    def route(page,attribute,section=None):
        app.show_page(page)
        if section:app.data_tasks.select(section)
        app.root.update_idletasks();variable=getattr(app,attribute,None)
        def walk(parent):
            for widget in parent.winfo_children():
                if getattr(widget,'variable',None) is variable and variable is not None and widget.winfo_ismapped():return widget
                found=walk(widget)
                if found:return found
        widget=walk(app.content)
        if widget:
            y=widget.winfo_rooty()-app.content.winfo_rooty();app.scroll.yview_moveto(max(0,y-36)/max(1,app.content.winfo_height()));widget.focus_set()
    for key,label,page,attribute,section in [('silent_recording','静默记录 · 隐藏全部 HUD',0,'silent_mode',None),('storage_auto','赛后自动压缩',3,'storage_auto','storage'),('storage_columnar','新赛事使用分块列式存储',3,'storage_columnar','storage'),('cache_limit_mb','可重建缓存上限 / MiB',3,'cache_limit','storage'),('renderer_mode','生成方式',3,'renderer_mode','renderer')]:
        register(app,key,label,anchor,'运行与数据',lambda p=page,a=attribute,s=section:route(p,a,s))
    def shortcuts():
        from control_shortcuts import show
        show(app)
    register(app,'global_shortcuts','全局快捷键',anchor,'显示与操作',shortcuts)


class Search:
    def __init__(self,app,parent):
        self.app=app;self.pending=None;self.buttons=[];self.entries=[];self.variable=tk.StringVar(parent,value=getattr(app,'settings_query',''))
        self.row=tk.Frame(parent,bg=T.BG);self.row.pack(fill='x',pady=(0,4));app.label(self.row,'搜索设置',10,T.MUTED).pack(side='left',padx=(0,12));self.field=SearchField(self.row,self.variable,self.request);self.field.pack(side='left',fill='x',expand=True)
        self.results=tk.Frame(parent,bg=T.BG)
        self.field.entry.bind('<Return>',lambda _:self.open_first())
        self.field.entry.bind('<Down>',lambda _:self.first_button())
        self.row.bind('<Destroy>',self.dispose,add='+')
        if self.variable.get().strip():self.pending=self.row.after_idle(self.update)
    def request(self):
        self.app.settings_query=self.variable.get()
        self.app.settings_results_open=bool(self.variable.get().strip())
        if self.pending:self.row.after_cancel(self.pending)
        self.pending=self.row.after(140,self.update)
    def update(self):
        self.pending=None
        for widget in self.results.winfo_children():widget.destroy()
        self.buttons=[];self.entries=matches(getattr(self.app,'settings_index',[]),self.variable.get())
        if not self.variable.get().strip() or not getattr(self.app,'settings_results_open',True):self.results.pack_forget();return
        self.results.pack(fill='x',pady=3)
        self.app.label(self.results,tr('匹配')+' · '+self.variable.get(),9,T.ACCENT).grid(row=0,column=0,columnspan=2,sticky='w')
        for index,entry in enumerate(self.entries[:6]):
            row=tk.Frame(self.results,bg=T.BG);row.grid(row=1+index//2,column=index%2,sticky='ew',padx=(0,6),pady=2)
            text=tr(entry['section'])+' · '+tr(entry['label'])
            from control_widgets import px
            button=Result(row,text,lambda value=entry:self.jump(value));button.configure(height=px(button,34));button.pack(fill='x');self.buttons.append(button)
        for column in (0,1):self.results.columnconfigure(column,weight=1,uniform='results')
        if not self.entries:self.app.label(self.results,'没有匹配设置，可尝试“采样”“胎压”或“天气”。',9,T.MUTED).grid(row=1,column=0,columnspan=2,sticky='w',pady=5)
        elif len(self.entries)>6:self.app.label(self.results,'结果较多，请输入更具体的关键词。',9,T.MUTED).grid(row=4,column=0,columnspan=2,sticky='w')
    def jump(self,entry):
        widget=entry['widget']
        if not widget.winfo_exists():return
        self.app.settings_results_open=False;self.results.pack_forget();self.app.root.update_idletasks()
        if entry.get('action'):entry['action']();return
        y=widget.winfo_rooty()-self.app.content.winfo_rooty()
        self.app.scroll.yview_moveto(max(0,y-45)/max(1,self.app.content.winfo_height()));widget.focus_set()
    def open_first(self):
        self.field.flush();self.app.settings_results_open=True
        if self.pending:self.row.after_cancel(self.pending);self.pending=None
        self.update()
        if self.entries:self.jump(self.entries[0])
        return 'break'
    def first_button(self):
        self.field.flush();self.app.settings_results_open=True
        if self.pending:self.row.after_cancel(self.pending);self.pending=None
        self.update()
        if self.buttons:self.buttons[0].focus_set()
        return 'break'
    def focus(self):
        self.app.settings_results_open=True
        if self.pending:self.row.after_cancel(self.pending);self.pending=None
        self.update();self.field.focus_set();self.field.entry.selection_range(0,'end');return 'break'
    def dispose(self,event):
        if event.widget is self.row:
            self.app.settings_query=self.variable.get()
            if self.field.last!=self.variable.get():self.app.settings_results_open=bool(self.variable.get().strip())
            if self.pending:self.row.after_cancel(self.pending)
            self.variable.__del__();self.variable._tk=None
