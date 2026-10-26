"""Task navigation that preserves hidden forms and selections."""
import tkinter as tk
from control_theme import T


class TaskSections:
    def __init__(self,app,items,key):
        self.app=app;self.key=key;self.current=None;self.positions={};self.on_select=None
        tabs=app.row(app.content);self.frames={name:tk.Frame(app.content,bg=T.BG) for name,_ in items};self.buttons={}
        from control_flow import install
        install(tabs)
        for name,label in items:self.buttons[name]=app.button(tabs,label,lambda n=name:self.select(n),False,135)
    def select(self,name):
        if name not in self.frames:name=next(iter(self.frames))
        if self.current==name:return
        token=self.app.shell.cover_page() if self.app.pages.building is None and not self.app.shell.covering else None
        if self.current is not None:
            self.positions[self.current]=self.app.scroll.yview()[0];self.frames[self.current].pack_forget()
        self.current=name;setattr(self.app,self.key,name)
        self.frames[name].pack(fill='x')
        for key,button in self.buttons.items():button.configure(selected=key==name)
        if self.on_select:self.on_select(name)
        self.app.root.update_idletasks();self.app.scroll.yview_moveto(self.positions.get(name,0))
        if token is not None:self.app.shell.reveal_page(token)


class Disclosure(tk.Frame):
    """Low-frequency details retain their open state without consuming the first screen."""
    def __init__(self,parent,app,key,title,header=None):
        from control_video_widgets import Action
        from control_widgets import px
        super().__init__(parent,bg=parent.cget('bg'));self.app=app;self.key=key;self.title=title
        self.states=getattr(app,'disclosure_states',{});app.disclosure_states=self.states
        self.button=Action(header if header is not None else self,title,self.toggle,130);self.button.configure(height=px(self,34));self.button.pack(side='left' if header is not None else 'top',anchor='w',padx=(8,0) if header is not None else 0)
        self.body=tk.Frame(self,bg=self.cget('bg'));self.pack(fill='x',pady=0 if header is not None else 3);self.retranslate=self.translate;self.set_open(bool(self.states.get(key)))
    def set_open(self,value):
        self.states[self.key]=value
        if value:self.body.pack(fill='x',pady=5)
        else:self.body.pack_forget()
        self.translate()
    def toggle(self):self.set_open(not bool(self.body.winfo_manager()))
    def translate(self):
        from i18n import tr
        from control_widgets import px
        b=self.button;b.configure(text=tr(self.title)+(' ▾' if self.states.get(self.key) else ' ▸'));b.configure(width=max(px(b,130),b.font.measure(b.label)+px(b,36)));b.paint()
