"""Delayed, non-focusing text hints owned by a single widget."""
import tkinter as tk
from control_theme import T


def position(window,x,y):
    """Tk negative geometry denotes a screen-edge offset; Win32 accepts absolute coordinates."""
    import ctypes
    if hasattr(ctypes,'WinDLL'):
        user=ctypes.WinDLL('user32');user.GetParent.argtypes=[ctypes.c_void_p];user.GetParent.restype=ctypes.c_void_p
        user.SetWindowPos.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_uint]
        handle=user.GetParent(window.winfo_id()) or window.winfo_id();user.SetWindowPos(handle,None,round(x),round(y),0,0,0x15)
    else:window.geometry(f'{round(x):+d}{round(y):+d}')


class Tooltip:
    def __init__(self,widget):self.widget=widget;self.pending=None;self.window=None;self.key=None;self.bindings=[]
    def request(self,key,text,x,y):
        if key==self.key:return
        self.hide();self.key=key;owner=self.widget.winfo_toplevel()
        for sequence in ('<Configure>','<FocusOut>'):
            token=owner.bind(sequence,lambda e,w=owner:self.hide() if e.widget is w else None,add='+');self.bindings.append((owner,sequence,token))
        def show():
            self.pending=None
            if not self.widget.winfo_exists() or not self.widget.winfo_ismapped():return
            window=tk.Toplevel(self.widget.winfo_toplevel());self.window=window;window.overrideredirect(True);window.title('Stintrix Tooltip')
            tk.Label(window,text=str(text)[:2000],wraplength=480,justify='left',anchor='w',bg=T.FIELD,fg=T.FG,relief='solid',borderwidth=1,font=(T.FONT,9),padx=10,pady=7).pack()
            window.update_idletasks()
            from control_layout_preview import monitors
            screens=monitors(self.widget);sx,sy,sw,sh=next((r for r in screens if r[0]<=x<r[0]+r[2] and r[1]<=y<r[1]+r[3]),screens[0])
            width=window.winfo_reqwidth();height=window.winfo_reqheight();left=max(sx,min(x+14,sx+sw-width));top=max(sy,min(y+18,sy+sh-height))
            if self.window is window and window.winfo_exists():position(window,left,top)
        self.pending=self.widget.after(450,show)
    def hide(self):
        for owner,sequence,token in self.bindings:
            if owner.winfo_exists():owner.unbind(sequence,token)
        self.bindings=[]
        if self.pending is not None:
            try:self.widget.after_cancel(self.pending)
            except tk.TclError:pass
        self.pending=None;self.key=None
        if self.window is not None:
            if self.window.winfo_exists():self.window.destroy()
            self.window=None
