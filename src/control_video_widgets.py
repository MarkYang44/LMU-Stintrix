"""Video task surfaces using the application's existing native motion tokens."""
import tkinter as tk
from control_theme import T
from control_widgets import Pill,px
from control_motion import Motion,blend,SmoothScroll,keyboard_action
from control_feedback import TabIndicator
from i18n import tr


class Action(Pill):
    """Shared press feedback with real disabled and selected states."""
    def __init__(self,parent,text,command,width=135,primary=False):
        self.enabled=True;self.selected=False;self.action=command
        super().__init__(parent,text,self.invoke,width,primary)
    def invoke(self):
        if self.enabled and self.action:return self.action()
    def configure(self,cnf=None,**kwargs):
        if isinstance(cnf,dict):kwargs={**cnf,**kwargs};cnf=None
        if not kwargs:return super().configure(cnf)
        if 'state' in kwargs:
            self.enabled=kwargs.pop('state')!='disabled'
            self.pressed=False;self.press_amount=0
            if hasattr(self,'motion'):self.motion.cancel()
            kwargs.update(cursor='hand2' if self.enabled else 'arrow',takefocus=self.enabled)
        if 'text' in kwargs:self.label=kwargs.pop('text')
        if 'selected' in kwargs:self.selected=kwargs.pop('selected')
        if kwargs:tk.Canvas.configure(self,**kwargs)
        if hasattr(self,'motion'):self.paint()
    config=configure
    def cget(self,key):
        if key=='state':return 'normal' if self.enabled else 'disabled'
        if key=='text':return tr(self.label)
        return super().cget(key)
    def hover(self,target):
        if self.enabled:super().hover(target)
    def press(self,event):
        if self.enabled:super().press(event)
    def paint(self):
        super().paint()
        if not self.enabled:
            self.itemconfigure(self.caption,fill=T.MUTED)
            self.itemconfigure(self.surface,fill=blend(T.FIELD,T.BG,.35),outline=T.EDGE)
            self.itemconfigure(self.accent,state='hidden')
        elif self.selected and not self.primary:
            self.itemconfigure(self.surface,fill=blend(T.SELECT,T.HOVER,self.amount*.25),outline=T.ACCENT)
            self.itemconfigure(self.caption,fill=T.ACCENT)


class ChoiceStrip(tk.Frame):
    def __init__(self,parent,variable,choices,command):
        super().__init__(parent,bg=parent.cget('bg'));self.variable=variable;self.choices=choices;self.command=command;self.buttons={}
        row=tk.Frame(self,bg=self.cget('bg'));row.pack(fill='x')
        for title,value in choices:
            button=Action(row,title,lambda v=value:self.choose(v),width=100)
            button.pack(side='left',fill='x',expand=True,padx=(0,px(self,5)));self.buttons[value]=button
        self.indicator=TabIndicator(self);self.indicator.pack(fill='x')
        self.trace=variable.trace_add('write',lambda *_:self.refresh());self.bind('<Destroy>',self.dispose,add='+')
        self.refresh(False)
        for i,button in enumerate(self.buttons.values()):
            for key,delta in (('<Left>',-1),('<Right>',1)):
                button.bind(key,lambda _,index=i,d=delta:keyboard_action(self,lambda:self.arrow(index+d)))
    def arrow(self,index):
        current=next(i for i,(_,value) in enumerate(self.choices) if value==self.variable.get())
        direction=1 if index>current else -1
        while 0<=index<len(self.choices):
            value=self.choices[index][1]
            if self.buttons[value].enabled:self.choose(value);self.buttons[value].focus_set();break
            index+=direction
        return 'break'
    def choose(self,value):
        if not self.buttons[value].enabled or self.variable.get()==value:return
        self.variable.set(value);self.command()
    def refresh(self,animate=True):
        for value,button in self.buttons.items():button.configure(selected=value==self.variable.get())
        button=self.buttons.get(self.variable.get())
        if button:self.indicator.select(button,animate)
    def dispose(self,event):
        if event.widget is self:
            self.variable.trace_remove('write',self.trace);self.command=None


class Steps(tk.Frame):
    """Persistent pages, interruptible marker, no snapshot/crossfade of large images."""
    def __init__(self,parent):
        super().__init__(parent,bg=T.BG);self.pages=[];self.buttons=[];self.current=None;self.offset=0.
        self.header=tk.Frame(self,bg=T.BG);self.header.pack(fill='x',pady=(0,px(self,6)))
        self.indicator=TabIndicator(self);self.indicator.pack(fill='x',pady=(0,px(self,12)))
        self.viewport=tk.Frame(self,bg=T.BG,width=1,height=1);self.viewport.pack(fill='both',expand=True)
        self.motion=Motion(self.viewport);self.viewport.bind('<Configure>',self.resized)
    def add(self,page,text):
        index=len(self.pages);self.pages.append(page)
        button=Action(self.header,text,lambda:self.select(page),width=180)
        button.pack(side='left',fill='x',expand=True,padx=(0,px(self,7)));self.buttons.append(button)
        button.bind('<Left>',lambda _:keyboard_action(self,lambda:self.arrow(index-1)))
        button.bind('<Right>',lambda _:keyboard_action(self,lambda:self.arrow(index+1)))
        if self.current is None:self.select(page,False)
    def arrow(self,index):
        index=max(0,min(len(self.pages)-1,index));self.select(self.pages[index]);self.buttons[index].focus_set();return 'break'
    def resized(self,_):
        self.motion.cancel('page');self.offset=0
        if self.current is not None:self.place_page(self.current,0)
    def place_page(self,index,offset):
        self.offset=offset
        self.pages[index].place(in_=self.viewport,x=0,y=round(offset),relwidth=1,relheight=1)
    def select(self,page=None,animate=True):
        if page is None:return str(self.pages[self.current]) if self.current is not None else ''
        index=page if isinstance(page,int) else next(i for i,p in enumerate(self.pages) if p==page or str(p)==str(page))
        if index==self.current:return str(self.pages[index])
        self.motion.cancel('page')
        for p in self.pages:p.place_forget()
        self.current=index
        for i,button in enumerate(self.buttons):button.configure(selected=i==index)
        self.indicator.select(self.buttons[index],animate)
        # These pages are visited repeatedly. Keep fields and calibration fixed;
        # the interruptible tab marker alone communicates the pointer action.
        self.place_page(index,0)
        self.event_generate('<<NotebookTabChanged>>',when='tail')
        return str(self.pages[index])


class TaskProgress(tk.Canvas):
    def __init__(self,parent):
        super().__init__(parent,bg=parent.cget('bg'),height=px(parent,8),highlightthickness=0)
        self.motion=Motion(self);self.value=0.;self.target=0.;self.complete=False
        self.rail=self.create_rectangle(0,0,1,1,outline='',fill=T.FIELD)
        self.fill=self.create_rectangle(0,0,1,1,outline='',fill=T.ACCENT)
        self.bind('<Configure>',lambda _:self.paint())
    def __setitem__(self,key,value):
        if key!='value':return super().__setitem__(key,value)
        target=max(0,min(100,float(value)))
        if target==self.target:return
        self.target=target;start=self.value
        self.motion.animate('progress',lambda t:self.present(start+(target-start)*t),120 if target>=start else 0)
    def __getitem__(self,key):return self.target if key=='value' else super().__getitem__(key)
    def present(self,value):self.value=value;self.paint()
    def paint(self):
        w=self.winfo_width();h=self.winfo_height()
        self.coords(self.rail,0,0,w,h);self.itemconfigure(self.rail,fill=T.FIELD)
        self.coords(self.fill,0,0,w*self.value/100,h);self.itemconfigure(self.fill,fill=T.GREEN if self.complete else T.ACCENT)


class ScrollPage(tk.Frame):
    def __init__(self,parent):
        from tkinter import ttk
        super().__init__(parent,bg=T.BG)
        self.canvas=tk.Canvas(self,bg=T.BG,highlightthickness=0,width=1,height=1)
        bar=ttk.Scrollbar(self,orient='vertical',command=self.scroll_to,style='Lab.Vertical.TScrollbar')
        self.canvas.configure(yscrollcommand=bar.set);bar.pack(side='right',fill='y');self.canvas.pack(fill='both',expand=True)
        self.body=tk.Frame(self.canvas,bg=T.BG);self.item=self.canvas.create_window(px(self,2),0,window=self.body,anchor='nw')
        self.canvas.bind('<Configure>',self.resize);self.body.bind('<Configure>',self.content_changed)
        self.scroller=SmoothScroll(self.canvas,self.position,self.limit,self.paint)
        self.bind('<Unmap>',lambda _:self.scroller.cancel())
    def position(self):return self.canvas.canvasy(0)
    def limit(self):return max(0,self.body.winfo_reqheight()-self.canvas.winfo_height())
    def paint(self,value):self.canvas.yview_moveto(value/max(1,self.body.winfo_reqheight()))
    def scroll_to(self,*args):self.scroller.cancel();self.canvas.yview(*args)
    def wheel(self,delta):self.scroller.add(-delta/120*px(self,68))
    def resize(self,event):
        self.scroller.cancel();self.canvas.itemconfigure(self.item,width=max(1,event.width-px(self,4)))
    def content_changed(self,_):self.canvas.configure(scrollregion=self.canvas.bbox('all'))
