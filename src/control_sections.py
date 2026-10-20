"""Task navigation that preserves hidden forms and selections."""
import tkinter as tk
from control_theme import T


class TaskSections:
    def __init__(self,app,items,key):
        self.app=app;self.key=key;self.current=None;self.positions={}
        tabs=app.row(app.content);self.frames={name:tk.Frame(app.content,bg=T.BG) for name,_ in items};self.buttons={}
        for name,label in items:self.buttons[name]=app.button(tabs,label,lambda n=name:self.select(n),False,135)
    def select(self,name):
        if name not in self.frames:name=next(iter(self.frames))
        if self.current==name:return
        if self.current is not None:
            self.positions[self.current]=self.app.scroll.yview()[0];self.frames[self.current].pack_forget()
        self.current=name;setattr(self.app,self.key,name)
        self.frames[name].pack(fill='x')
        for key,button in self.buttons.items():button.configure(selected=key==name)
        self.app.root.update_idletasks();self.app.scroll.yview_moveto(self.positions.get(name,0))
