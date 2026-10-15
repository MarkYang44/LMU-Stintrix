"""Time-based progress line for one circuit/layout/class/car history."""
import tkinter as tk
import bisect
from record_history import dated
from control_widgets import px
from control_theme import T
from i18n import tr
from control_motion import Motion,blend


def lap_time(value):return f'{int(value//60)}:{value%60:06.3f}'


class ProgressChart(tk.Canvas):
    def __init__(self,parent,command,height=240):
        super().__init__(parent,bg=T.FIELD,height=px(parent,height),highlightthickness=0)
        self.entries=[];self.points=[];self.command=command;self.hover=None;self.motion=Motion(self);self.cursor=None;self.tooltip=None;self.ring=None
        self.bind('<Configure>',self.draw);self.bind('<Motion>',self.inspect);self.bind('<Leave>',self.leave);self.bind('<Button-1>',self.select)
    def set(self,entries):self.entries=entries;self.hover=None;self.draw()
    def draw(self,_=None):
        self.motion.cancel();self.delete('all');self.points=[];self.cursor=None;self.tooltip=None;self.ring=None;w=self.winfo_width();h=self.winfo_height();left=px(self,85);right=w-px(self,25);top=px(self,25);bottom=h-px(self,40)
        if not self.entries:
            self.create_text(w/2,h/2,text=tr('选择纪录查看该赛道与车辆的提升曲线'),fill=T.MUTED,font=(T.FONT,10));return
        times=[dated(e['observed_utc']).timestamp() for e in self.entries];laps=[e['time_s'] for e in self.entries]
        low,high=min(laps),max(laps);padding=max(.05,(high-low)*.12);low-=padding;high+=padding
        for i in range(4):
            y=top+(bottom-top)*i/3;value=high-(high-low)*i/3
            self.create_line(left,y,right,y,fill=T.EDGE);self.create_text(left-px(self,10),y,text=lap_time(value),fill=T.MUTED,anchor='e',font=(T.FONT,9))
        coordinates=[]
        for e,t,v in zip(self.entries,times,laps):
            x=(left+right)/2 if times[-1]==times[0] else left+(t-times[0])/(times[-1]-times[0])*(right-left)
            y=bottom-(v-low)/(high-low)*(bottom-top);self.points.append((x,y,e));coordinates.extend((x,y))
        if len(coordinates)>2:self.create_line(*coordinates,fill=T.ACCENT,width=px(self,2))
        radius=px(self,4)
        for x,y,e in self.points:self.create_oval(x-radius,y-radius,x+radius,y+radius,fill=T.ACCENT,outline=T.FIELD)
        self.create_text(left,bottom+px(self,20),text=self.entries[0]['observed_utc'][:16].replace('T',' ') if self.entries[0]['observed_utc'][:10]==self.entries[-1]['observed_utc'][:10] else self.entries[0]['observed_utc'][:10],fill=T.MUTED,anchor='w',font=(T.FONT,9))
        if len(self.entries)>1:self.create_text(right,bottom+px(self,20),text=self.entries[-1]['observed_utc'][:16].replace('T',' ') if self.entries[0]['observed_utc'][:10]==self.entries[-1]['observed_utc'][:10] else self.entries[-1]['observed_utc'][:10],fill=T.MUTED,anchor='e',font=(T.FONT,9))
        self.xs=[p[0] for p in self.points]
        self.bounds=(left,right,top,bottom)
        self.cursor=self.create_line(0,0,0,0,fill=T.MUTED,dash=(3,4),state='hidden')
        self.tooltip=self.create_text(0,0,text='',fill=T.FG,font=(T.FONT,10,'bold'),state='hidden')
        self.ring=self.create_oval(0,0,0,0,outline=T.ACCENT,width=2,state='hidden')
        self.update_hover()
    def update_hover(self):
        if self.cursor is None:return
        visible=self.hover is not None and self.hover<len(self.points)
        for item in (self.cursor,self.tooltip):self.itemconfigure(item,state='normal' if visible else 'hidden')
        if not visible:return
        x,y,e=self.points[self.hover];left,right,top,bottom=self.bounds
        self.coords(self.cursor,x,top,x,bottom)
        label=e['observed_utc'][:19].replace('T',' ')+' UTC  ·  '+lap_time(e['time_s'])
        self.coords(self.tooltip,min(right-px(self,160),max(left+px(self,160),x)),top+px(self,10));self.itemconfigure(self.tooltip,text=label)
    def nearest(self,x):
        i=bisect.bisect_left(self.xs,x)
        candidates=[j for j in (i-1,i) if 0<=j<len(self.points)]
        return min(candidates,key=lambda j:abs(x-self.points[j][0]))
    def inspect(self,event):
        if not self.points:return
        nearest=self.nearest(event.x)
        if nearest!=self.hover:self.hover=nearest;self.update_hover()
    def leave(self,_):self.hover=None;self.update_hover()
    def select(self,event):
        if self.points:
            _,_,entry=self.points[self.nearest(event.x)];self.command(entry)
            point=next((p for p in self.points if p[2] is entry),None)
            if point and self.ring is not None:
                x,y,_=point;ring=self.ring
                def frame(t):
                    r=px(self,6+4*t);self.coords(ring,x-r,y-r,x+r,y+r);self.itemconfigure(ring,state='hidden' if t==1 else 'normal',outline=blend(T.ACCENT,T.FIELD,t))
                self.motion.animate('point',frame,150)
