"""Interruptible native motion with shared curves, frame deadlines and accessibility."""
import time,math,os,ctypes
import tkinter as tk

FRAME_MS=16
CURVES={'out':(.23,1,.32,1),'inout':(.77,0,.175,1),'hover':(.25,.1,.25,1)}
_policy=(0.,True)


def ease(value,curve='out'):
    value=min(1,max(0,value))
    if value in (0,1):return value
    x1,y1,x2,y2=CURVES[curve];lo,hi=0.,1.
    def component(t,a,b):return 3*(1-t)**2*t*a+3*(1-t)*t*t*b+t**3
    for _ in range(18):
        t=(lo+hi)/2
        if component(t,x1,x2)<value:lo=t
        else:hi=t
    return component((lo+hi)/2,y1,y2)


def system_motion():
    global _policy
    if os.environ.get('LMU_STINTRIX_REDUCED_MOTION')=='1':return False
    now=time.perf_counter()
    if now-_policy[0]<1:return _policy[1]
    allowed=True
    if os.name=='nt':
        value=ctypes.c_int(1)
        try:
            if ctypes.windll.user32.SystemParametersInfoW(0x1042,0,ctypes.byref(value),0):allowed=bool(value.value)
        except (OSError,AttributeError):pass
    _policy=(now,allowed);return allowed


def motion_allowed(widget):
    try:keyboard=time.perf_counter()<getattr(widget.winfo_toplevel(),'_motion_keyboard_until',0)
    except (tk.TclError,AttributeError):keyboard=False
    return system_motion() and not keyboard


def input_policy(widget):
    root=widget.winfo_toplevel()
    if getattr(root,'_native_motion_policy',False):return
    root._native_motion_policy=True
    def key(_):root._motion_keyboard_until=time.perf_counter()+.2
    def pointer(_):root._motion_keyboard_until=0
    root.bind('<KeyPress>',key,add='+');root.bind('<ButtonPress>',pointer,add='+')


def keyboard_action(widget,action):
    widget.winfo_toplevel()._motion_keyboard_until=time.perf_counter()+.2
    return action()


def blend(first,second,fraction):
    a=[int(first[i:i+2],16) for i in (1,3,5)];b=[int(second[i:i+2],16) for i in (1,3,5)]
    return '#'+''.join(f'{round(x+(y-x)*fraction):02x}' for x,y in zip(a,b))


def schedule_frame(widget,deadline,callback):
    interval=FRAME_MS/1000;deadline+=interval;now=time.perf_counter()
    if deadline<=now:deadline+=(math.floor((now-deadline)/interval)+1)*interval
    return deadline,widget.after(max(1,round((deadline-now)*1000)),callback)


class Motion:
    def __init__(self,widget):
        self.widget=widget;self.jobs={};self.tokens={};self.springs={};input_policy(widget);widget.bind('<Destroy>',self.destroy,add='+')
    def destroy(self,event):
        if event.widget is self.widget:self.cancel();self.widget=None
    def cancel(self,key=None):
        for name in set(self.jobs)|set(self.tokens) if key is None else [key]:
            self.tokens.pop(name,None);self.springs.pop(name,None)
            job=self.jobs.pop(name,None)
            if job:
                try:self.widget.after_cancel(job)
                except tk.TclError:pass
    def animate(self,key,paint,duration=180,curve='out'):
        self.cancel(key)
        if self.widget is None:return
        if duration<=0 or not motion_allowed(self.widget):paint(1.);return
        token=object();self.tokens[key]=token
        started=time.perf_counter();deadline=[started]
        def frame():
            self.jobs.pop(key,None)
            if self.widget is None or not self.widget.winfo_exists():return
            now=time.perf_counter();t=min(1,(now-started)*1000/duration);paint(ease(t,curve))
            # Painting may destroy or retarget this animation (a page switch).
            if self.widget is None or not self.widget.winfo_exists() or self.tokens.get(key) is not token:return
            if t<1:
                deadline[0],self.jobs[key]=schedule_frame(self.widget,deadline[0],frame)
            else:self.tokens.pop(key,None)
        frame()

    def spring(self,key,paint,current,target,response=.28):
        previous=self.springs.get(key);velocity=previous['velocity'] if previous else 0.
        self.cancel(key)
        if self.widget is None:return
        if not motion_allowed(self.widget):paint(target);return
        token=object();self.tokens[key]=token
        state=dict(value=current,velocity=velocity,last=time.perf_counter(),deadline=time.perf_counter());self.springs[key]=state
        def frame():
            self.jobs.pop(key,None)
            if self.widget is None or not self.widget.winfo_exists() or self.tokens.get(key) is not token:return
            now=time.perf_counter();dt=max(0,now-state['last']);state['last']=now
            value,speed=spring_step(state['value'],state['velocity'],target,dt,response)
            state.update(value=max(0,min(1,value)),velocity=speed if 0<=value<=1 else 0.)
            finished=abs(state['value']-target)<.001 and abs(state['velocity'])<.02
            paint(target if finished else state['value'])
            if self.widget is None or self.tokens.get(key) is not token:return
            if finished:self.tokens.pop(key,None);self.springs.pop(key,None)
            else:state['deadline'],self.jobs[key]=schedule_frame(self.widget,state['deadline'],frame)
        frame()


def spring_step(current,velocity,target,dt,response=.4):
    """Exact critically damped solution; stable across missed frames, no bounce."""
    omega=2*math.pi/response;offset=current-target;b=velocity+omega*offset;decay=math.exp(-omega*dt)
    return target+(offset+b*dt)*decay,(velocity-omega*b*dt)*decay


class SmoothScroll:
    def __init__(self,widget,position,limit,paint):
        self.widget=widget;self.position=position;self.limit=limit;self.paint=paint
        self.target=0.;self.job=None;self.last=0.;self.velocity=0.;self.value=None
        widget.bind('<Destroy>',self.destroy,add='+')
    def destroy(self,event):
        if event.widget is self.widget:
            self.cancel();self.widget=None;self.position=None;self.limit=None;self.paint=None
    def cancel(self):
        if self.job is not None:
            try:self.widget.after_cancel(self.job)
            except tk.TclError:pass
        self.job=None;self.velocity=0.;self.value=None
        try:self.target=self.position()
        except (tk.TclError,TypeError):self.target=0.
    def move(self,value):
        self.cancel();self.target=max(0,min(self.limit(),value));self.paint(self.target)
    def add(self,delta):
        if not motion_allowed(self.widget):self.move(self.position()+delta);return
        if self.job is None:self.target=self.position();self.value=self.target;self.velocity=0.
        self.target=max(0,min(self.limit(),self.target+delta))
        if self.job is None:
            self.last=time.perf_counter();self.deadline=self.last;self.deadline,self.job=schedule_frame(self.widget,self.deadline,self.frame)
    def frame(self):
        self.job=None
        if self.widget is None or not self.widget.winfo_exists():return
        maximum=max(0,self.limit());self.target=max(0,min(maximum,self.target))
        if not motion_allowed(self.widget):self.paint(self.target);self.velocity=0.;self.value=None;return
        now=time.perf_counter();dt=max(0,now-self.last);self.last=now
        current=max(0,min(maximum,self.value if self.value is not None else self.position()))
        value,self.velocity=spring_step(current,self.velocity,self.target,dt,response=.36)
        self.value=max(0,min(maximum,value))
        if self.value!=value:self.velocity=0.
        if abs(self.target-self.value)<.3 and abs(self.velocity)<5:
            self.paint(self.target);self.velocity=0.;self.value=None;return
        self.paint(self.value);self.deadline,self.job=schedule_frame(self.widget,self.deadline,self.frame)


def reveal_window(window):
    """Occasional tool windows fade as a single native surface, never resize."""
    parent=getattr(window,'master',None)
    if parent is not None and not motion_allowed(parent):
        window._motion_keyboard_until=time.perf_counter()+.2
    driver=Motion(window)
    try:window.attributes('-alpha',0.)
    except tk.TclError:return
    driver.animate('surface',lambda t:window.attributes('-alpha',t),200)
    def close():
        current=float(window.attributes('-alpha'))
        def frame(t):
            if t==1:window.destroy()
            else:window.attributes('-alpha',current*(1-t))
        driver.animate('surface',frame,150)
    window.protocol('WM_DELETE_WINDOW',close)
