"""Search field with a clear target and keyboard-first editing."""
import tkinter as tk
from i18n import tr
from control_fields import Field
from control_theme import T


class SearchField(Field):
    def __init__(self,parent,textvariable,command=None,placeholder='',**kwargs):
        self.variable=textvariable;self.command=command;self.pending=None;self.last=textvariable.get()
        self.placeholder=placeholder
        super().__init__(parent,textvariable=textvariable,**kwargs)
        self.placeholder_label=tk.Label(self.entry,text=tr(placeholder),anchor='w',bg=T.FIELD,fg=T.MUTED,font=self.entry.cget('font'),cursor='xterm',takefocus=False)
        self.placeholder_label.bind('<Button-1>',lambda _:(self.entry.focus_set(),self.entry.icursor(0)))
        self.clear_area=self.create_rectangle(0,0,1,1,outline='',tags='clear')
        self.clear_lines=[self.create_line(0,0,1,1,width=1.5,tags='clear') for _ in range(2)]
        self.tag_bind('clear','<Button-1>',lambda _:self.clear())
        self.tag_bind('clear','<Enter>',lambda _:self.configure(cursor='hand2'))
        self.tag_bind('clear','<Leave>',lambda _:self.configure(cursor=''))
        self.entry.bind('<Escape>',lambda _:self.clear())
        self.entry.bind('<Return>',lambda _:(self.flush(),'break')[1])
        self.trace=self.variable.trace_add('write',self.changed)
        self.bind('<Destroy>',self.dispose,add='+')
        self.paint()
    def changed(self,*_):
        self.paint()
        if self.command is None:return
        if self.pending:self.after_cancel(self.pending);self.pending=None
        if self.variable.get()!=self.last:self.pending=self.after(80,self.flush)
    def flush(self,force=False):
        if self.pending:self.after_cancel(self.pending);self.pending=None
        value=self.variable.get()
        if force or value!=self.last:
            self.last=value
            if self.command:self.command()
    def paint(self):
        super().paint()
        if not hasattr(self,'clear_area'):return
        s=self.s;w=self.winfo_width();h=self.winfo_height();visible=bool(self.variable.get())
        self.placeholder_label.configure(text=tr(self.placeholder),bg=T.FIELD,fg=T.MUTED)
        if not visible and self.placeholder:self.placeholder_label.place(x=0,y=0,relwidth=1,relheight=1)
        else:self.placeholder_label.place_forget()
        self.itemconfigure(self.item,width=max(1,w-(61 if visible else 28)*s))
        self.coords(self.clear_area,w-43*s,5*s,w-7*s,h-5*s)
        self.itemconfigure(self.clear_area,fill=T.FIELD,state='normal' if visible else 'hidden')
        x=w-25*s;y=h/2
        for line,sign in zip(self.clear_lines,(-1,1)):
            self.coords(line,x-4*s,y-4*s*sign,x+4*s,y+4*s*sign)
            self.itemconfigure(line,fill=T.MUTED,state='normal' if visible else 'hidden')
    def retranslate(self):self.paint()
    def clear(self):
        if self.variable.get():self.variable.set('');self.flush(True)
        self.entry.focus_set();return 'break'
    def dispose(self,event):
        if event.widget is self:
            if self.pending:self.after_cancel(self.pending);self.pending=None
            try:self.variable.trace_remove('write',self.trace)
            except tk.TclError:pass
