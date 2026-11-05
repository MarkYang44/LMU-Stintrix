"""Delayed, non-focusing text hints owned by a single widget."""
import time
import tkinter as tk
from control_theme import T

DELAY_MS=450
# Once a hint has been read, neighbouring hints open at once: the first delay
# prevents accidental pop-ups, later ones would only make scanning feel slow.
# A perceptually instant 60 ms still coalesces fast sweeps across table cells.
WARM_S=.6;WARM_DELAY_MS=60
_warm_until=0.


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
        warm=time.perf_counter()<_warm_until
        def show():
            self.pending=None
            if not self.widget.winfo_exists() or not self.widget.winfo_ismapped():return
            window=tk.Toplevel(self.widget.winfo_toplevel());self.window=window;window.overrideredirect(True);window.title('Stintrix Tooltip')
            # The first hint fades in briefly; neighbouring hints answer at once.
            from control_motion import motion_allowed,Motion
            fade=not warm and motion_allowed(self.widget)
            if fade:window.attributes('-alpha',0.)
            from control_widgets import px
            # Same hairline edge as the selector and action-menu popovers.
            tk.Label(window,text=str(text)[:2000],wraplength=px(window,480),justify='left',anchor='w',bg=T.FIELD,fg=T.FG,relief='flat',borderwidth=0,
                highlightthickness=1,highlightbackground=T.EDGE,highlightcolor=T.EDGE,font=(T.FONT,9),padx=px(window,10),pady=px(window,7)).pack()
            window.update_idletasks()
            from control_layout_preview import monitors
            screens=monitors(self.widget);sx,sy,sw,sh=next((r for r in screens if r[0]<=x<r[0]+r[2] and r[1]<=y<r[1]+r[3]),screens[0])
            width=window.winfo_reqwidth();height=window.winfo_reqheight();left=max(sx,min(x+14,sx+sw-width));top=max(sy,min(y+18,sy+sh-height))
            if self.window is window and window.winfo_exists():
                position(window,left,top)
                if fade:Motion(window).animate('arrive',lambda t:window.attributes('-alpha',t),120)
        self.pending=self.widget.after(WARM_DELAY_MS if warm else DELAY_MS,show)
    def hide(self):
        global _warm_until
        if self.window is not None:_warm_until=time.perf_counter()+WARM_S
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
