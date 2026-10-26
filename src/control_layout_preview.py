"""Draft-only monitor canvas. No window placement or recorder calls happen here."""
import ctypes
import tkinter as tk
from tkinter import font as tkfont
from control_theme import T
from control_widgets import px
from hud_layouts import SIZES
from i18n import tr


def monitors(root):
    """Physical desktop rectangles, including monitors at negative coordinates."""
    if hasattr(ctypes, 'WinDLL'):
        from ctypes import wintypes
        result=[]
        callback=ctypes.WINFUNCTYPE(wintypes.BOOL,ctypes.c_void_p,ctypes.c_void_p,ctypes.POINTER(wintypes.RECT),ctypes.c_ssize_t)
        def collect(_monitor,_dc,rect,_data):
            r=rect.contents;result.append((r.left,r.top,r.right-r.left,r.bottom-r.top));return True
        fn=callback(collect)
        if ctypes.WinDLL('user32').EnumDisplayMonitors(None,None,fn,0) and result:return result
    from hud_presentation import bounds
    return [bounds(root)]


def move_panel(panel,x,y,screens,snap=False):
    """Clamp to the nearest real screen, rather than the bounding-box gaps."""
    if snap:x=round(x/10)*10;y=round(y/10)*10
    screen=min(screens,key=lambda r:max(r[0]-x,0,x-r[0]-r[2])**2+max(r[1]-y,0,y-r[1]-r[3])**2)
    sx,sy,sw,sh=screen
    return round(max(sx,min(x,sx+max(0,sw-panel['width'])))),round(max(sy,min(y,sy+max(0,sh-panel['height']))))


class LayoutPreview(tk.Canvas):
    def __init__(self,parent,snapshot,selected,select,change,snap,titles):
        super().__init__(parent,height=px(parent,205),bg=T.BG,highlightthickness=1,highlightbackground=T.EDGE,takefocus=True)
        self.snapshot=snapshot;self.selected=selected;self.select=select;self.change=change;self.snap=snap;self.titles=titles
        self.screens=monitors(self);self.drag=None;self.boxes={};self.ratio=1.;self.origin=(0,0);self.zoom=1.;self.pan=[0.,0.];self.focus_rect=None;self.pan_drag=None
        self.caption_font=tkfont.Font(self,font=(T.FONT,8));self.bind('<Destroy>',self.dispose,add='+')
        self.bind('<Configure>',lambda _:self.paint())
        self.bind('<Button-1>',self.press);self.bind('<B1-Motion>',self.motion);self.bind('<ButtonRelease-1>',lambda _:self.end_drag())
        self.bind('<MouseWheel>',self.wheel);self.bind('<Button-2>',self.start_pan);self.bind('<B2-Motion>',self.move_pan);self.bind('<ButtonRelease-2>',lambda _:self.end_drag())
        for key in ('Left','Right','Up','Down'):self.bind('<'+key+'>',self.nudge)
        self.bind('<FocusIn>',lambda _:self.configure(highlightbackground=T.ACCENT));self.bind('<FocusOut>',lambda _:self.configure(highlightbackground=T.EDGE))
    def paint(self):
        self.delete('all');self.boxes={}
        data=self.snapshot()
        if data is None:return
        left=min(r[0] for r in self.screens);top=min(r[1] for r in self.screens)
        right=max(r[0]+r[2] for r in self.screens);bottom=max(r[1]+r[3] for r in self.screens)
        if self.focus_rect is not None:left,top,right,bottom=self.focus_rect
        w=max(1,self.winfo_width());h=max(1,self.winfo_height());pad=px(self,18)
        self.ratio=max(.001,min((w-2*pad)/max(1,right-left),(h-2*pad)/max(1,bottom-top)))*self.zoom
        self.origin=((w-(right-left)*self.ratio)/2-left*self.ratio+self.pan[0],(h-(bottom-top)*self.ratio)/2-top*self.ratio+self.pan[1])
        ox,oy=self.origin;r=self.ratio
        for i,(x,y,sw,sh) in enumerate(self.screens):
            self.create_rectangle(ox+x*r,oy+y*r,ox+(x+sw)*r,oy+(y+sh)*r,fill=T.FIELD,outline=T.EDGE)
            self.create_text(ox+(x+sw/2)*r,oy+(y+sh)*r-10,text=f'{tr("显示器")} {i+1} · {sw}×{sh}',fill=T.MUTED,font=(T.FONT,8))
        keys=[k for k in data['panels'] if k!=self.selected()]+[self.selected()]
        for key in keys:
            p=data['panels'][key];x=ox+p['x']*r;y=oy+p['y']*r;pw=max(12,p['width']*r);ph=max(10,p['height']*r)
            self.boxes[key]=(x,y,x+pw,y+ph);active=key==self.selected()
            self.create_rectangle(x,y,x+pw,y+ph,fill=T.SELECT if active else T.CARD,outline=T.ACCENT if active else T.MUTED,width=2 if active else 1,dash=() if p['visible'] else (3,3))
            title=tr(self.titles[key]);available=max(1,pw-8)
            if self.caption_font.measure(title)>available:
                while title and self.caption_font.measure(title+'…')>available:title=title[:-1]
                title+='…'
            self.create_text(x+4,y+min(ph/2,12),text=title,anchor='w',font=self.caption_font,fill=T.FG)
            if active:self.create_rectangle(x+pw-6,y+ph-6,x+pw,y+ph,fill=T.ACCENT,outline='')
    def press(self,event):
        self.focus_set()
        key=next((key for key,box in reversed(list(self.boxes.items())) if box[0]<=event.x<=box[2] and box[1]<=event.y<=box[3]),None)
        if key is None:return self.start_pan(event)
        if not self.select(key):return 'break'
        data=self.snapshot()
        if data is None:return 'break'
        p=dict(data['panels'][key]);box=self.boxes[key]
        self.drag=(key,event.x,event.y,p,event.x>=box[2]-9 and event.y>=box[3]-9)
        self.paint();return 'break'
    def motion(self,event):
        if self.pan_drag:return self.move_pan(event)
        if not self.drag:return 'break'
        key,x,y,p,resize=self.drag;dx=(event.x-x)/self.ratio;dy=(event.y-y)/self.ratio
        if resize:
            mode=self.snapshot()['mode'];minimum={'normal':(440,160),'curves':(240,60),'controls':(320,80)}[mode] if key=='main' else SIZES[key]
            width=round(p['width']+dx);height=round(p['height']+dy)
            if self.snap():width=round(width/10)*10;height=round(height/10)*10
            values=dict(width=max(minimum[0],min(8192,width)),height=max(minimum[1],min(8192,height)))
        else:
            nx,ny=move_panel(p,p['x']+dx,p['y']+dy,self.screens,self.snap());values=dict(x=nx,y=ny)
        self.change(key,values);self.paint();return 'break'
    def nudge(self,event):
        data=self.snapshot()
        if data is None:return 'break'
        key=self.selected();p=data['panels'][key];step=10 if event.state&1 else 1
        dx,dy={'Left':(-step,0),'Right':(step,0),'Up':(0,-step),'Down':(0,step)}[event.keysym]
        x,y=move_panel(p,p['x']+dx,p['y']+dy,self.screens,False);self.change(key,dict(x=x,y=y));self.paint();return 'break'
    def dispose(self,event):
        if event.widget is self:self.caption_font.__del__();self.caption_font.delete_font=False
    def end_drag(self):self.drag=None;self.pan_drag=None;self.configure(cursor='')
    def start_pan(self,event):
        self.focus_set();self.drag=None;self.pan_drag=(event.x,event.y,tuple(self.pan));self.configure(cursor='fleur');return 'break'
    def move_pan(self,event):
        if self.pan_drag:
            x,y,pan=self.pan_drag;self.pan=[pan[0]+event.x-x,pan[1]+event.y-y];self.paint()
        return 'break'
    def zoom_at(self,factor,x=None,y=None):
        if self.snapshot() is None:return
        x=self.winfo_width()/2 if x is None else x;y=self.winfo_height()/2 if y is None else y
        old=self.ratio;ox,oy=self.origin;point=((x-ox)/old,(y-oy)/old)
        self.zoom=max(.25,min(16.,self.zoom*factor));self.paint();ox,oy=self.origin
        self.pan[0]+=x-(ox+point[0]*self.ratio);self.pan[1]+=y-(oy+point[1]*self.ratio);self.paint()
    def wheel(self,event):
        self.zoom_at(1.2**max(-3,min(3,event.delta/120)),event.x,event.y);return 'break'
    def fit_all(self):
        self.screens=monitors(self);self.focus_rect=None;self.zoom=1.;self.pan=[0.,0.];self.paint()
    def fit_selected(self):
        data=self.snapshot()
        if data is None:return
        p=data['panels'][self.selected()];dx=max(40,p['width']*.2);dy=max(40,p['height']*.4)
        self.focus_rect=(p['x']-dx,p['y']-dy,p['x']+p['width']+dx,p['y']+p['height']+dy);self.zoom=1.;self.pan=[0.,0.];self.paint()
