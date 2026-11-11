"""A live sketch of the next HUD, drawn the way the HUD draws itself.

The display mode decides whether the metric header and the pedal and wheel
panel appear; the waveform window decides how many swings fit the trace.
Changing either reshapes the sketch in 180 ms (at once for keyboard input
and reduced motion), so each choice shows what it does before a session.
"""
import math
import tkinter as tk
from control_theme import T
from control_widgets import rounded,scale
from control_motion import Motion
from i18n import tr

# (metric header, pedal and wheel panel) per stored display mode.
LAYOUT={'normal':(1.,1.),'curves':(0.,0.),'controls':(0.,1.)}
CYCLES={'5':1.,'10':2.,'20':4.}


class HudPreview(tk.Canvas):
    def __init__(self,parent,mode_label,window,modes,command=None):
        self.s=scale(parent);self.mode_label=mode_label;self.window=window;self.modes=modes;self.command=command;self.hovered=False
        super().__init__(parent,bg=parent.cget('bg'),highlightthickness=0,height=round(128*self.s),cursor='hand2' if command else '')
        if command:
            from control_tooltip import Tooltip
            self.tip=Tooltip(self)
            self.bind('<Enter>',self.enter);self.bind('<Leave>',self.leave);self.bind('<Button-1>',lambda _:(self.tip.hide(),self.command()))
        self.header,self.panel=LAYOUT[modes.get(mode_label.get(),'normal')];self.cycles=CYCLES.get(window.get(),2.)
        self.motion=Motion(self);self.traces=[(v,v.trace_add('write',self.changed)) for v in (mode_label,window)]
        self.bind('<Configure>',lambda _:self.paint());self.bind('<Destroy>',self.dispose,add='+')
    def enter(self,event):
        self.hovered=True;self.paint();text=tr('打开 HUD 布局，调整位置、尺寸与透明度')
        self.tip.request('layout',text,self.winfo_rootx()+event.x,self.winfo_rooty()+self.winfo_height())
    def leave(self,_):self.hovered=False;self.tip.hide();self.paint()
    def dispose(self,event):
        if event.widget is not self:return
        if self.command:self.tip.hide()
        for variable,token in self.traces:
            try:variable.trace_remove('write',token)
            except tk.TclError:pass
    def changed(self,*_):
        target=(*LAYOUT[self.modes.get(self.mode_label.get(),'normal')],CYCLES.get(self.window.get(),2.))
        start=(self.header,self.panel,self.cycles)
        def frame(t):
            self.header,self.panel,self.cycles=(a+(b-a)*t for a,b in zip(start,target));self.paint()
        self.motion.animate('layout',frame,180)
    def retranslate(self):self.paint()
    def paint(self):
        s=self.s;w=self.winfo_width();h=self.winfo_height()
        if w<=1 or h<=1:return
        self.delete('all');pad=10*s;line=max(1,1.6*s)
        rounded(self,0,0,w-1,h-1,8*s,fill=T.FIELD,outline=T.ACCENT if self.hovered else T.EDGE)
        self.create_text(pad,pad,text=tr('画面预览')+' · '+tr(self.mode_label.get()),anchor='nw',fill=T.FG if self.hovered else T.MUTED,font=(T.FONT,8))
        self.create_text(w-pad,pad,text=(tr('HUD 布局')+' ▸   ' if self.hovered else '')+f'{self.window.get()} s',anchor='ne',fill=T.ACCENT if self.hovered else T.MUTED,font=(T.MONO,8))
        left=pad;right=w-pad;top=pad+18*s;bottom=h-pad
        if bottom-top<24*s:return
        header=self.header*min(30*s,(bottom-top)*.3)
        if header>2*s:
            gap=6*s;cell=(right-left-2*gap)/3
            for i,(name,color,value) in enumerate((('THROTTLE',T.GREEN,'0%'),('BRAKE',T.RED,'51%'),('STEERING',T.BLUE,'+65%'))):
                x=left+i*(cell+gap);rounded(self,x,top,cell,max(1,header-4*s),4*s,fill=T.CARD,outline=T.EDGE)
                if header>20*s and cell>70*s:
                    middle=top+(header-4*s)/2
                    self.create_oval(x+6*s,middle-2*s,x+10*s,middle+2*s,fill=color,outline='')
                    self.create_text(x+14*s,middle,text=name,anchor='w',fill=T.MUTED,font=(T.MONO,7))
                    self.create_text(x+cell-6*s,middle,text=value,anchor='e',fill=color,font=(T.MONO,9,'bold'))
            top+=header
        panel=self.panel*min(120*s,(right-left)*.3)
        trace_right=right-(panel+6*s*self.panel)
        rounded(self,left,top,trace_right-left,bottom-top,4*s,fill=T.CARD,outline=T.EDGE)
        # Three swings like the live traces; a longer window packs more of them.
        inner=(left+6*s,top+6*s,trace_right-6*s,bottom-6*s);span=inner[2]-inner[0];height=inner[3]-inner[1]
        if span>10*s and height>8*s:
            for color,phase,amplitude in ((T.GREEN,0.,.42),(T.RED,math.pi,.42),(T.BLUE,math.pi/2,.32)):
                points=[]
                for k in range(61):
                    value=.5+amplitude*math.sin(2*math.pi*self.cycles*k/60+phase)
                    points+=[inner[0]+span*k/60,inner[3]-height*value]
                self.create_line(*points,fill=color,width=line,smooth=True)
        if panel>12*s:
            x0=trace_right+6*s*self.panel;width=right-x0
            rounded(self,x0,top,width,bottom-top,4*s,fill=T.CARD,outline=T.EDGE)
            if width>40*s and bottom-top>40*s:
                bar=8*s;base=bottom-8*s;room=bottom-top-16*s
                for i,(color,amount) in enumerate(((T.RED,.51),(T.GREEN,.06))):
                    x=x0+8*s+i*(bar+4*s)
                    self.create_rectangle(x,base-room,x+bar,base,fill=T.FIELD,outline='')
                    self.create_rectangle(x,base-room*amount,x+bar,base,fill=color,outline='')
                cx=x0+8*s+2*(bar+4*s)+(width-16*s-2*(bar+4*s))/2;cy=top+(bottom-top)/2;r=max(4*s,min((width-16*s-2*(bar+4*s))/2,(bottom-top)/2-8*s))
                if r>8*s:
                    self.create_oval(cx-r,cy-r,cx+r,cy+r,outline=T.MUTED,width=line)
                    angle=math.radians(-90+65*.9)
                    self.create_line(cx,cy,cx+r*math.cos(angle),cy+r*math.sin(angle),fill=T.BLUE,width=line)
