"""Opaque, versioned native page handoff; no moving child windows or global locks."""
import ctypes
import tkinter as tk
from i18n import tr,Label
from control_theme import T
from control_widgets import px


def redraw(widget):
    if not widget.winfo_exists() or not widget.winfo_ismapped():return
    if hasattr(ctypes,'WinDLL'):
        try:
            user=ctypes.WinDLL('user32',use_last_error=True)
            user.RedrawWindow.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint]
            user.RedrawWindow.restype=ctypes.c_bool
            user.RedrawWindow(widget.winfo_id(),None,None,0x185)
        except (OSError,AttributeError):pass


class Surface:
    def __init__(self,host):
        self.host=host;self.covering=False;self.generation=0;self.job=None
        self.cover=tk.Frame(host,bg=T.BG,takefocus=False)
        self.hint=Label(self.cover,text='正在准备页面…',bg=T.BG,fg=T.MUTED,font=(T.FONT,11),anchor='w')
        self.cover.bind('<Destroy>',self.dispose,add='+')
    def cancel_hint(self):
        if self.job is not None:self.cover.after_cancel(self.job);self.job=None
    def begin(self):
        already=self.covering
        if not self.covering:
            self.focus=self.host.focus_get()
            if self.focus is not None and str(self.focus).startswith(str(self.host)):self.cover.focus_set()
        self.generation+=1;token=self.generation;self.cancel_hint();self.hint.pack_forget()
        self.covering=True;self.cover.place(x=0,y=0,relwidth=1,relheight=1);self.cover.lift()
        # Map an opaque native sibling BEFORE retiring old controls. Canvas
        # item visibility alone cannot guarantee cleared Windows child pixels.
        if not already:self.host.update_idletasks();redraw(self.cover)
        def hint():
            self.job=None
            if self.covering and token==self.generation:
                self.hint.configure(text=tr('正在准备页面…'));self.hint.pack(fill='x',padx=px(self.cover,24),pady=px(self.cover,28))
        self.job=self.cover.after(150,hint);return token
    def reveal(self,token=None):
        if token is not None and token!=self.generation:return False
        self.host.update_idletasks()
        if token is not None and token!=self.generation:return False
        self.cancel_hint();self.cover.place_forget();self.covering=False
        self.host.update_idletasks();redraw(self.host)
        if self.host.focus_get() is self.cover:
            previous=getattr(self,'focus',None)
            if previous is not None and previous.winfo_exists() and previous.winfo_ismapped():previous.focus_set()
            else:self.host.winfo_toplevel().focus_set()
        self.focus=None;return True
    def dispose(self,event):
        if event.widget is self.cover:self.cancel_hint();self.generation+=1;self.covering=False
