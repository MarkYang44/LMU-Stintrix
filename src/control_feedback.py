"""Small, lifecycle-bound feedback surfaces; data values never animate."""
import math,time,tkinter as tk
from control_theme import T
from control_motion import Motion,blend,motion_allowed,schedule_frame
from control_widgets import px
from i18n import tr,Label


class Activity(tk.Canvas):
    def __init__(self,parent):
        super().__init__(parent,width=px(parent,22),height=px(parent,22),bg=parent.cget('bg'),highlightthickness=0)
        self.active=False;self.job=None;self.deadline=time.perf_counter();self.symbol='';self.motion=Motion(self)
        self.arc=self.create_arc(3,3,px(self,19),px(self,19),style='arc',width=2,outline=T.ACCENT,state='hidden')
        self.mark=self.create_text(px(self,11),px(self,11),font=(T.FONT,11,'bold'),fill=T.GREEN,state='hidden')
        self.bind('<Map>',lambda _:self.resume());self.bind('<Unmap>',lambda _:self.stop());self.bind('<Destroy>',self.dispose,add='+')
    def resume(self):
        self.stop();self.deadline=time.perf_counter();self.tick()
    def stop(self):
        if self.job is not None:self.after_cancel(self.job);self.job=None
    def dispose(self,event):
        if event.widget is self:self.stop()
    def set(self,active):
        if active and self.active:return
        self.stop();self.deadline=time.perf_counter();self.ready_at=self.deadline+.15;self.active=active;self.symbol='';self.motion.cancel()
        self.itemconfigure(self.mark,state='hidden');self.itemconfigure(self.arc,state='hidden');self.tick()
    def tick(self):
        self.job=None
        if not self.active or not self.winfo_ismapped():return
        if not motion_allowed(self):
            self.itemconfigure(self.arc,state='hidden');self.itemconfigure(self.mark,text='…',fill=T.MUTED,state='normal');return
        if time.perf_counter()<getattr(self,'ready_at',0):
            self.job=self.after(max(1,round((self.ready_at-time.perf_counter())*1000)),self.tick);return
        self.itemconfigure(self.mark,state='hidden')
        self.itemconfigure(self.arc,state='normal',start=-(time.perf_counter()*240)%360,extent=240)
        self.deadline,self.job=schedule_frame(self,self.deadline,self.tick)
    def confirm(self):
        self.set(False);self.itemconfigure(self.mark,text='✓',state='normal')
        self.motion.animate('confirm',lambda t:self.itemconfigure(self.mark,fill=blend(T.ACCENT,T.GREEN,t)),150)


class StatusFeedback(tk.Frame):
    def __init__(self,parent,variable,font_size=9):
        super().__init__(parent,bg=parent.cget('bg'));self.variable=variable;self.tasks=set()
        self.icon=Activity(self);self.icon.pack(side='left',padx=(0,5));self.label=Label(self,textvariable=variable,bg=self.cget('bg'),fg=T.MUTED,font=(T.FONT,font_size),anchor='w',justify='left');self.label.pack(side='left',fill='x',expand=True)
        self.label.bind('<Configure>',lambda e:self.label.configure(wraplength=max(80,e.width)))
        self.trace=variable.trace_add('write',self.changed);self.bind('<Destroy>',self.dispose,add='+')
    def changed(self,*_):
        value=self.variable.get()
        prefixes=('设置已保存','已完成','已导出','已保存本机','参考圈已保存','对比已生成','新纪录')
        if not self.tasks and any(value.startswith(tr(p)) for p in prefixes):self.icon.confirm()
        elif not self.tasks:self.icon.set(False)
    def busy(self,key,active=True):
        if active:self.tasks.add(key)
        else:self.tasks.discard(key)
        self.icon.set(bool(self.tasks))
        if not self.tasks:self.changed()
    def success(self):
        if not self.tasks:self.icon.confirm()
    def dispose(self,event):
        if event.widget is self:
            try:self.variable.trace_remove('write',self.trace)
            except (tk.TclError,AttributeError):pass
            self.variable=None


class CountBadge(Label):
    def __init__(self,parent):
        super().__init__(parent,text='',bg=parent.cget('bg'),fg=T.MUTED,font=(T.FONT,9),anchor='w');self.motion=Motion(self);self.count=None
    def set(self,count):
        previous=self.count;self.count=count;self.configure(text=tr('筛选结果')+f' · {count}')
        if previous is not None and previous!=count:self.motion.animate('count',lambda t:self.configure(fg=blend(T.ACCENT,T.MUTED,t)),150)


class ImageSurface(tk.Canvas):
    """Fixed viewport, one thumbnail upload, position-only arrival; no image blending."""
    def __init__(self,parent,height=210):
        super().__init__(parent,bg=T.FIELD,highlightthickness=0,height=px(parent,height));self.motion=Motion(self);self.photo=None;self.image=None
        self.bitmap=self.create_image(0,0,state='hidden',tags='image')
        self.hint=self.create_text(0,0,text=tr('正在加载图片…'),fill=T.MUTED,font=(T.FONT,10))
        self.bind('<Configure>',self.layout);self.bind('<Destroy>',self.dispose,add='+')
    def pending(self,text=None):
        self.motion.cancel();self.image=None;self.photo=None;self.itemconfigure(self.bitmap,state='hidden',image='');self.itemconfigure(self.hint,text=text or tr('正在加载图片…'),state='normal');self.layout()
    def show(self,image):self.image=image;self.layout(arrive=True)
    def layout(self,event=None,arrive=False):
        width=max(1,self.winfo_width());height=max(1,self.winfo_height());self.coords(self.hint,width/2,height/2)
        if self.image is None:return
        from PIL import ImageOps,Image,ImageTk
        picture=ImageOps.contain(self.image,(max(1,width-12),max(1,height-12)),Image.Resampling.LANCZOS)
        self.photo=ImageTk.PhotoImage(picture,master=self);self.itemconfigure(self.bitmap,image=self.photo,state='normal');self.itemconfigure(self.hint,state='hidden')
        if arrive:
            self.motion.animate('image',lambda t:self.coords(self.bitmap,width/2,height/2+px(self,4)*(1-t)),150)
        else:self.motion.cancel('image');self.coords(self.bitmap,width/2,height/2)
    def dispose(self,event):
        if event.widget is self:self.photo=None;self.image=None


def record_improvements(entries,baseline):
    current={tuple(e['identity']):e['time_s'] for e in entries}
    improvements=[] if baseline is None else [e for e in entries if tuple(e['identity']) in baseline and e['time_s']<baseline[tuple(e['identity'])]-.0005]
    return current,improvements


class TabIndicator(tk.Canvas):
    """A single line tracks the committed tab; rapid changes start where it is."""
    def __init__(self,parent):
        super().__init__(parent,height=4,bg=parent.cget('bg'),highlightthickness=0)
        self.motion=Motion(self);self.line=self.create_line(0,2,0,2,fill=T.ACCENT,width=2);self.bounds=None;self.button=None
        self.bind('<Configure>',lambda _:self.select(self.button,False) if self.button else None)
    def select(self,button,animate=True):
        self.button=button;self.update_idletasks();target=(button.winfo_x(),button.winfo_x()+button.winfo_width())
        start=self.bounds or target
        def paint(t):
            self.bounds=tuple(a+(b-a)*t for a,b in zip(start,target));self.coords(self.line,self.bounds[0],2,self.bounds[1],2);self.itemconfigure(self.line,fill=T.ACCENT)
        self.motion.animate('tab',paint,160 if animate else 0)


class ConnectionFeedback(tk.Canvas):
    def __init__(self,parent):
        super().__init__(parent,width=18,height=18,bg=parent.cget('bg'),highlightthickness=0)
        self.dot=self.create_oval(5,5,13,13,fill=T.MUTED,outline='');self.mode=None;self.color=T.MUTED;self.motion=Motion(self)
    def set(self,mode):
        if self.mode==mode:return
        self.mode=mode;start=self.color;target={'waiting':T.MUTED,'connected':T.GREEN,'recording':T.ACCENT}[mode]
        def paint(t):self.color=blend(start,target,t);self.itemconfigure(self.dot,fill=self.color)
        self.motion.animate('connection',paint,160)


class VictoryBadge(tk.Canvas):
    def __init__(self,parent):
        super().__init__(parent,height=0,bg=parent.cget('bg'),highlightthickness=0)
        self.motion=Motion(self);self.item=self.create_text(46,24,anchor='w',text=tr('同组冠军'),fill=T.ACCENT,font=(T.FONT,12,'bold'))
        self.cup_points=(12,10,30,10,28,27,21,31,14,27,12,10,7,10,8,23,14,26,21,31,21,39,13,39,29,39,21,39,21,31,28,26,34,23,35,10,30,10)
        self.cup=self.create_line(*self.cup_points,fill=T.ACCENT,width=2)
    def celebrate(self):
        self.configure(height=48)
        def paint(t):
            scale=1+.06*math.sin(math.pi*t)
            self.coords(self.cup,*[21+(v-21)*scale if i%2==0 else 24+(v-24)*scale for i,v in enumerate(self.cup_points)])
            self.itemconfigure(self.cup,fill=blend(T.GREEN,T.ACCENT,t));self.itemconfigure(self.item,fill=blend(T.GREEN,T.ACCENT,t))
        self.motion.animate('victory',paint,320)


def new_champions(entries,baseline):
    current={str(e['folder']) for e in entries if e['place']==1}
    return current,[] if baseline is None else [e for e in entries if e['place']==1 and str(e['folder']) not in baseline]
