"""Viewport-sized image tiles; zoom/pan never upload a whole enlarged report."""
import tkinter as tk
from tkinter import ttk
from control_theme import T
from control_widgets import px


class ImageViewport(tk.Frame):
    def __init__(self,parent,changed=lambda:None):
        super().__init__(parent,bg=T.BG);self.changed=changed;self.image=None;self.photo=None;self.scale=1.;self.offset=[0.,0.];self.mode='width';self.drag=None;self.job=None;self.refine=None
        self.columnconfigure(0,weight=1);self.rowconfigure(0,weight=1)
        self.canvas=tk.Canvas(self,bg=T.FIELD,highlightthickness=0,takefocus=True,cursor='hand2');self.canvas.grid(row=0,column=0,sticky='nsew')
        self.vbar=ttk.Scrollbar(self,orient='vertical',command=lambda *args:self.scrollbar(1,*args),style='Lab.Vertical.TScrollbar');self.vbar.grid(row=0,column=1,sticky='ns')
        self.hbar=ttk.Scrollbar(self,orient='horizontal',command=lambda *args:self.scrollbar(0,*args),style='Lab.Horizontal.TScrollbar');self.hbar.grid(row=1,column=0,sticky='ew')
        self.bitmap=self.canvas.create_image(0,0,anchor='nw');self.canvas.bind('<Configure>',self.resize)
        self.canvas.bind('<MouseWheel>',self.wheel);self.canvas.bind('<Button-1>',self.press);self.canvas.bind('<B1-Motion>',self.motion);self.canvas.bind('<ButtonRelease-1>',self.release)
        self.bind('<Destroy>',self.dispose,add='+')
    def snapshot(self):return dict(scale=self.scale,offset=list(self.offset),mode=self.mode)
    def show(self,image,view=None):
        self.image=image;self.canvas.configure(cursor='fleur');self.mode=(view or {}).get('mode','width')
        if view and self.mode=='manual':self.scale=view['scale'];self.offset=list(view['offset']);self.queue()
        else:self.fit(self.mode)
    def clear(self):self.image=None;self.photo=None;self.canvas.itemconfigure(self.bitmap,image='');self.queue()
    def resize(self,_):
        if self.image and self.mode!='manual':self.fit(self.mode)
        else:self.queue(True)
    def fit(self,mode='width'):
        if self.image is None:return
        self.mode=mode;w=max(1,self.canvas.winfo_width()-px(self,32));h=max(1,self.canvas.winfo_height()-px(self,32))
        self.scale=max(.03,min(8.,w/self.image.width if mode=='width' else min(w/self.image.width,h/self.image.height) if mode=='all' else 1.))
        self.offset=[px(self,16),px(self,16)];self.queue()
    def bounds(self):
        if self.image is None:self.hbar.set(0,1);self.vbar.set(0,1);return
        for axis,(length,viewport) in enumerate(zip((self.image.width,self.image.height),(self.canvas.winfo_width(),self.canvas.winfo_height()))):
            total=length*self.scale;pad=px(self,16)
            self.offset[axis]=(viewport-total)/2 if total+2*pad<=viewport else max(viewport-total-pad,min(pad,self.offset[axis]))
            full=max(1,total+2*pad);first=0. if full<=viewport else max(0,(pad-self.offset[axis])/full)
            (self.hbar if axis==0 else self.vbar).set(first,min(1.,first+viewport/full))
    def queue(self,fast=False):
        self.fast=fast;self.bounds();self.changed()
        if self.job is None:self.job=self.after(16 if fast else 0,self.paint)
        if self.refine is not None:self.after_cancel(self.refine);self.refine=None
        if fast:self.refine=self.after(130,self.finish)
    def finish(self):self.refine=None;self.fast=False;self.paint()
    def paint(self):
        if self.job is not None:self.after_cancel(self.job);self.job=None
        if self.image is None:return
        from PIL import Image,ImageTk
        self.bounds();w=max(1,self.canvas.winfo_width());h=max(1,self.canvas.winfo_height());s=self.scale;x,y=self.offset
        left=max(0,int(-x/s));top=max(0,int(-y/s));right=min(self.image.width,int((w-x)/s)+1);bottom=min(self.image.height,int((h-y)/s)+1)
        if right<=left or bottom<=top:return
        tile=self.image if (left,top,right,bottom)==(0,0,*self.image.size) else self.image.crop((left,top,right,bottom));size=(max(1,round((right-left)*s)),max(1,round((bottom-top)*s)))
        if tile.mode in ('1','P'):tile=tile.convert('RGBA')
        if tile.size!=size:tile=tile.resize(size,Image.Resampling.BILINEAR if getattr(self,'fast',False) else Image.Resampling.LANCZOS)
        self.photo=ImageTk.PhotoImage(tile,master=self.canvas);self.canvas.itemconfigure(self.bitmap,image=self.photo);self.canvas.coords(self.bitmap,round(x+left*s),round(y+top*s))
    def zoom(self,factor,x=None,y=None):
        if self.image is None:return
        x=self.canvas.winfo_width()/2 if x is None else x;y=self.canvas.winfo_height()/2 if y is None else y
        old=self.scale;self.scale=max(.03,min(8.,old*factor));self.mode='manual';self.offset=[x-(x-self.offset[0])*self.scale/old,y-(y-self.offset[1])*self.scale/old];self.queue(True)
    def pan(self,dx=0,dy=0):
        self.mode='manual';self.offset[0]+=dx;self.offset[1]+=dy;self.queue(True)
    def wheel(self,event):
        steps=max(-5,min(5,event.delta/120))
        if event.state&4:self.zoom(1.2**steps,event.x,event.y)
        elif event.state&1:self.pan(dx=steps*px(self,90))
        else:self.pan(dy=steps*px(self,90))
        return 'break'
    def press(self,event):self.canvas.focus_set();self.drag=(event.x,event.y,tuple(self.offset))
    def motion(self,event):
        if self.drag:
            x,y,offset=self.drag;self.mode='manual';self.offset=[offset[0]+event.x-x,offset[1]+event.y-y];self.queue(True)
    def release(self,_=None):self.drag=None;self.queue()
    def scrollbar(self,axis,command,value,units=None):
        if self.image is None:return
        self.mode='manual';length=(self.image.width,self.image.height)[axis]*self.scale+px(self,32);view=(self.canvas.winfo_width(),self.canvas.winfo_height())[axis]
        if command=='moveto':self.offset[axis]=px(self,16)-float(value)*length
        else:self.offset[axis]-=float(value)*(view*.85 if units=='pages' else px(self,80))
        self.queue(True)
    def edge(self,bottom=False):
        if self.image is not None:self.offset[1]=-self.image.height*self.scale if bottom else px(self,16);self.mode='manual';self.queue()
    def dispose(self,event):
        if event.widget is self:
            for job in (self.job,self.refine):
                if job is not None:self.after_cancel(job)
            self.job=self.refine=None;self.photo=None;self.image=None
