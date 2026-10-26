"""Industrial surfaces and animated controls, using the lightweight Tk runtime."""
from i18n import tr
import ctypes
import tkinter as tk
from control_theme import T
from tkinter import font as tkfont
from control_motion import Motion,blend,keyboard_action



def scale(widget):return max(1,float(widget.winfo_fpixels('1i'))/96)
def px(widget,value):return round(value*scale(widget))


def rounded(canvas,x,y,w,h,r,**kwargs):
    """Clipped opposing corners, retained under its old name for UI compatibility."""
    return canvas.create_polygon(*polygon_points(x,y,w,h,r),**kwargs)


def polygon_points(x,y,w,h,r):
    r=min(r,w/3,h/3)
    return (x+r,y,x+w,y,x+w,y+h-r,x+w-r,y+h,x,y+h,x,y+r)


class Pill(tk.Canvas):
    def __init__(self,parent,text,command,width=140,primary=False):
        self.s=scale(parent);self.font=tkfont.Font(parent,family=T.FONT,size=10,weight='bold')
        width=max(width*self.s,self.font.measure(tr(text))+36*self.s)
        super().__init__(parent,width=round(width),height=px(parent,46),bg=parent.cget('bg'),highlightthickness=0,cursor='hand2',takefocus=True)
        self.primary=primary;self.command=command;self.label=text;self.amount=0;self.pressed=False;self.press_amount=0.;self.focused=False;self.motion=Motion(self)
        self.bind('<Configure>',lambda _:self.paint())
        self.bind('<Enter>',lambda _:self.hover(1));self.bind('<Leave>',lambda _:self.hover(0))
        self.bind('<ButtonPress-1>',self.press);self.bind('<ButtonRelease-1>',self.release)
        self.bind('<Return>',lambda _:keyboard_action(self,self.command));self.bind('<space>',lambda _:keyboard_action(self,self.command))
        self.bind('<FocusIn>',lambda _:self.focus(True));self.bind('<FocusOut>',lambda _:self.focus(False))
        self.bind('<Destroy>',self.dispose,add='+')
    def dispose(self,event):
        if event.widget is self:self.font.__del__();self.font.delete_font=False
    def focus(self,value):self.focused=value;self.paint()
    def hover(self,target):
        start=self.amount
        def paint(t):self.amount=start+(target-start)*t;self.paint()
        self.motion.animate('hover',paint,125,curve='hover')
    def press(self,_):
        self.pressed=True;self.focus_set();self.press_to(1,100);self.paint()
    def press_to(self,target,duration):
        start=self.press_amount
        def frame(t):self.press_amount=start+(target-start)*t;self.paint()
        self.motion.animate('press',frame,duration)
    def release(self,event):
        fire=self.pressed and 0<=event.x<self.winfo_width() and 0<=event.y<self.winfo_height()
        self.pressed=False;self.press_to(0,160);self.paint()
        if fire:self.command()
    def paint(self):
        s=self.s;w=self.winfo_width();h=self.winfo_height();shift=self.press_amount*s;inset=w*.015*self.press_amount
        base=T.BUTTON if self.primary else T.FIELD;over=T.BUTTON_HOVER if self.primary else T.HOVER;color=blend(base,over,self.amount)
        if not hasattr(self,'surface'):
            self.shadow=rounded(self,0,0,1,1,1,fill=T.BG,outline='')
            self.surface=rounded(self,0,0,1,1,1,fill=color,outline=T.EDGE)
            self.accent=self.create_line(0,0,1,0,fill=T.ACCENT)
            self.caption=self.create_text(0,0,font=self.font)
        self.coords(self.shadow,*polygon_points(2*s,4*s,w-4*s,h-7*s,7*s));self.itemconfigure(self.shadow,fill=T.BG)
        self.coords(self.surface,*polygon_points(2*s+inset,2*s+shift,w-4*s-2*inset,h-7*s,7*s))
        self.itemconfigure(self.surface,fill=color,outline=T.ACCENT if self.focused or self.primary else T.EDGE)
        self.coords(self.accent,10*s+inset,3*s+shift,30*s+24*s*self.amount+inset,3*s+shift)
        self.itemconfigure(self.accent,fill=T.ACCENT,width=2*s,state='hidden' if self.primary else 'normal')
        self.coords(self.caption,w/2,h/2-s+shift);self.itemconfigure(self.caption,text=tr(self.label),fill=T.INK if self.primary else T.FG,font=self.font)



class GlassCard(tk.Canvas):
    def __init__(self,parent,compact=False):
        self.s=scale(parent);self.margin=round((14 if compact else 22)*self.s);self.vertical=26 if compact else 42
        super().__init__(parent,bg=parent.cget('bg'),highlightthickness=0,height=100)
        self.body=tk.Frame(self,bg=T.CARD);self.item=self.create_window(self.margin,round((12 if compact else 20)*self.s),anchor='nw',window=self.body)
        self.bind('<Configure>',self.layout);self.body.bind('<Configure>',self.resize)
    def resize(self,_):
        h=self.body.winfo_reqheight()+round(self.vertical*self.s)
        if int(self.cget('height'))!=h:self.configure(height=h)
    def layout(self,_):
        s=self.s;w=self.winfo_width();h=self.winfo_height();self.itemconfigure(self.item,width=max(30,w-2*self.margin))
        self.delete('glass')
        rounded(self,1,1,w-3,h-7*s,12*s,fill=T.CARD,outline=T.EDGE,width=1,tags='glass')
        self.create_line(17*s,1,69*s,1,fill=T.ACCENT,width=2*s,tags='glass')
        for i in range(3):
            self.create_line(w-(22+i*6)*s,h-13*s,w-(18+i*6)*s,h-17*s,fill=T.EDGE,tags='glass')
        self.tag_lower('glass')


class Switch(tk.Canvas):
    """Pointer feedback, velocity-preserving thumb travel, and retained artwork."""
    def __init__(self,parent,text,variable,command,compact=False):
        self.s=scale(parent);self.variable=variable;self.command=command;self.text=text;self.enabled=True
        self.value=float(variable.get());self.press_amount=0.;self.amount=0.;self.pressed=False;self.motion=None
        options={}
        if compact:
            from tkinter import font as tkfont
            measure=tkfont.Font(parent,font=(T.FONT,10));options['width']=measure.measure(tr(text))+px(parent,80);measure.__del__();measure.delete_font=False
        super().__init__(parent,height=px(parent,38 if compact else 48),bg=parent.cget('bg'),highlightthickness=0,takefocus=True,cursor='hand2',**options)
        self.motion=Motion(self);self.bind('<Configure>',lambda _:self.paint())
        self.bind('<ButtonPress-1>',self.press);self.bind('<ButtonRelease-1>',self.release)
        self.bind('<Return>',lambda _:keyboard_action(self,self.toggle));self.bind('<space>',lambda _:keyboard_action(self,self.toggle))
        self.bind('<Enter>',lambda _:self.hover(1));self.bind('<Leave>',lambda _:self.hover(0))
        self.bind('<FocusIn>',lambda _:self.paint());self.bind('<FocusOut>',lambda _:self.paint())
        self.trace=variable.trace_add('write',self.changed);self.bind('<Destroy>',self.cleanup,add='+')
    def cleanup(self,event):
        if event.widget is self:
            try:self.variable.trace_remove('write',self.trace)
            except (tk.TclError,AttributeError):pass
            self.variable=None;self.command=None
    def hover(self,target):
        if not self.enabled:return
        start=self.amount
        def frame(t):self.amount=start+(target-start)*t;self.paint()
        self.motion.animate('hover',frame,125,curve='hover')
    def pressure(self,target):
        start=self.press_amount
        def frame(t):self.press_amount=start+(target-start)*t;self.paint()
        self.motion.animate('press',frame,100 if target else 160)
    def press(self,_):
        if not self.enabled:return 'break'
        self.winfo_toplevel()._motion_keyboard_until=0
        self.pressed=True;self.focus_set();self.pressure(1);self.paint()
    def release(self,event):
        commit=self.enabled and self.pressed and 0<=event.x<self.winfo_width() and 0<=event.y<self.winfo_height()
        self.pressed=False;self.pressure(0)
        if commit:self.toggle()
    def toggle(self):
        if self.enabled:self.focus_set();self.variable.set(not self.variable.get());self.command()
    def configure(self,cnf=None,**kwargs):
        if isinstance(cnf,dict):kwargs={**cnf,**kwargs};cnf=None
        if 'state' in kwargs:
            self.enabled=kwargs.pop('state')!='disabled';self.pressed=False
            kwargs.update(takefocus=self.enabled,cursor='hand2' if self.enabled else 'arrow')
        result=super().configure(cnf,**kwargs)
        if hasattr(self,'motion') and self.motion is not None:self.paint()
        return result
    config=configure
    def cget(self,key):
        if key=='state':return 'normal' if self.enabled else 'disabled'
        return super().cget(key)
    def changed(self,*_):
        def paint(value):self.value=value;self.paint()
        self.motion.spring('toggle',paint,self.value,float(self.variable.get()),response=.28)
    def paint(self):
        s=self.s;w=self.winfo_width();h=self.winfo_height();x=w-56*s;y=(h-28*s)/2
        if not hasattr(self,'track'):
            self.caption=self.create_text(0,0,anchor='w',font=(T.FONT,10))
            self.track=rounded(self,0,0,1,1,1,outline=T.EDGE)
            self.thumb=rounded(self,0,0,1,1,1,outline='')
        self.coords(self.caption,0,h/2);self.itemconfigure(self.caption,text=tr(self.text),fill=T.FG if self.enabled else T.MUTED)
        self.coords(self.track,*polygon_points(x,y,52*s,28*s,5*s))
        rail=blend(T.FIELD,T.SELECT,self.value)
        self.itemconfigure(self.track,fill=blend(rail,T.HOVER,self.amount*.18),outline=T.ACCENT if self.focus_get() is self else blend(T.EDGE,T.MUTED,self.amount*.35))
        cx=x+(14+24*self.value)*s;half=(9+1.5*self.press_amount)*s
        self.coords(self.thumb,*polygon_points(cx-half,y+4*s,half*2,20*s,3*s))
        self.itemconfigure(self.thumb,fill=blend(T.MUTED,T.ACCENT,self.value) if self.enabled else T.EDGE)


class CardGrid(tk.Frame):
    """Two balanced columns on wide displays; stack before forms become cramped."""
    def __init__(self,parent):
        super().__init__(parent,bg=T.BG);self.cards=[];self.wide=None;self.bind('<Configure>',self.layout)
        self.columnconfigure(0,weight=1,uniform='cards');self.columnconfigure(1,weight=1,uniform='cards')
    def add(self,card):self.cards.append(card);self.layout()
    def layout(self,_=None):
        wide=self.winfo_width()>=px(self,900)
        if self.wide==wide and all(c.winfo_manager() for c in self.cards):return
        self.wide=wide
        for i,card in enumerate(self.cards):
            card.grid(row=0 if wide else i,column=i if wide else 0,columnspan=1 if wide else 2,
                sticky='new',padx=(0,px(self,9)) if wide and i==0 else ((px(self,9),0) if wide else 0),pady=(0,px(self,18)))


class LaunchArtwork(tk.Canvas):
    """Static racing-line motif, so decoration adds no idle rendering load."""
    def __init__(self,parent):
        super().__init__(parent,bg=T.CARD,height=px(parent,78),highlightthickness=0);self.bind('<Configure>',self.paint)
    def paint(self,_=None):
        self.delete('all');s=scale(self);w=self.winfo_width()
        self.create_text(0,20*s,text='LE MANS ULTIMATE',anchor='w',fill=T.FG,font=('Segoe UI',15,'bold'))
        self.create_text(1*s,48*s,text='DRIVE  /  RECORD  /  REFLECT',anchor='w',fill=T.ACCENT,font=('Segoe UI',8,'bold'))
        if w>=px(self,500):
            from lmu_mark import draw
            draw(self,285*s,20*s,80*s,'#FFFFFF' if T.mode=='dark' else '#FF1D43')
        if w<px(self,610):return
        x=w-270*s
        for offset,color in ((0,T.EDGE),(7,T.MUTED),(14,T.ACCENT)):
            points=(x,56*s+offset,x+42*s,56*s+offset,x+77*s,12*s+offset,x+134*s,12*s+offset,x+166*s,46*s+offset,x+239*s,46*s+offset)
            self.create_line(*points,fill=color,width=2*s)
        self.create_rectangle(x+173*s,47*s,x+181*s,55*s,fill=T.ACCENT,outline='')


def backdrop(root):
    """Opaque readable content, with native dark chrome and rounded corners."""
    root.attributes('-alpha',1.0)
    if not hasattr(ctypes,'WinDLL'):return
    try:
        root.update_idletasks();user=ctypes.WinDLL('user32');user.GetParent.argtypes=[ctypes.c_void_p];user.GetParent.restype=ctypes.c_void_p
        hwnd=user.GetParent(root.winfo_id()) or root.winfo_id();dwm=ctypes.WinDLL('dwmapi')
        dwm.DwmSetWindowAttribute.argtypes=[ctypes.c_void_p,ctypes.c_uint,ctypes.c_void_p,ctypes.c_uint]
        for key,value in ((20,1 if T.mode=='dark' else 0),(33,2)):
            data=ctypes.c_int(value);dwm.DwmSetWindowAttribute(hwnd,key,ctypes.byref(data),ctypes.sizeof(data))
    except (OSError,AttributeError):pass
