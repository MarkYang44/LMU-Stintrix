"""Shared history/time and evidence-only session/lap charts."""
import tkinter as tk
import bisect,math
from record_history import dated
from control_widgets import px
from control_theme import T
from i18n import tr
from control_motion import Motion,blend


def lap_time(value):return f'{int(value//60)}:{value%60:06.3f}'


class ProgressChart(tk.Canvas):
    def __init__(self,parent,command,height=240,*,axis='time'):
        if axis not in ('time','lap'):raise ValueError('Unknown chart axis')
        self.axis=axis
        super().__init__(parent,bg=T.FIELD,height=px(parent,height),highlightthickness=0)
        self.entries=[];self.points=[];self.command=command;self.hover=None;self.motion=Motion(self);self.cursor=None;self.tooltip=None;self.ring=None;self.target=None;self.keyboard_cursor=False
        self.bind('<Configure>',self.draw);self.bind('<Motion>',self.inspect);self.bind('<Leave>',self.leave);self.bind('<Button-1>',self.select)
        self.configure(takefocus=True)
        for sequence,key in (('<Left>','left'),('<Right>','right'),('<Home>','home'),('<End>','end'),('<Return>','enter')):
            self.bind(sequence,lambda _,key=key:self.key(key))
        self.bind('<FocusOut>',self.blur)
    def set(self,entries,*,target=None):
        self.target=target if self.axis=='lap' and type(target) in (int,float) and math.isfinite(target) and target>0 else None
        self.entries=entries;self.hover=None;self.keyboard_cursor=False;self.draw()
    def draw(self,_=None):
        self.motion.cancel();self.delete('all');self.points=[];self.cursor=None;self.tooltip=None;self.ring=None;w=self.winfo_width();h=self.winfo_height();left=px(self,85);right=w-px(self,25);top=px(self,25);bottom=h-px(self,40)
        if not self.entries:
            self.create_text(w/2,h/2,text=tr(getattr(self,'empty_text','选择纪录查看该赛道与车辆的提升曲线')),fill=T.MUTED,font=(T.FONT,10));return
        times=[e['number'] for e in self.entries] if self.axis=='lap' else [dated(e['observed_utc']).timestamp() for e in self.entries];laps=[e['time_s'] for e in self.entries]
        low,high=min(laps),max(laps)
        if self.target is not None:low=min(low,self.target);high=max(high,self.target)
        padding=max(.05,(high-low)*.12);low-=padding;high+=padding
        if self.target is not None:low=max(0.,low)
        for i in range(4):
            y=top+(bottom-top)*i/3;value=high-(high-low)*i/3
            if self.target is not None:value=max(low,value)
            self.create_line(left,y,right,y,fill=T.EDGE);self.create_text(left-px(self,10),y,text=lap_time(value),fill=T.MUTED,anchor='e',font=(T.FONT,9))
        if self.target is not None:
            y=bottom-(self.target-low)/(high-low)*(bottom-top)
            self.create_line(left,y,right,y,fill=T.MUTED,dash=(5,4),tags='target')
            self.create_text(left+px(self,8),y-px(self,4),text=tr('目标')+' '+lap_time(self.target),fill=T.MUTED,anchor='sw',font=(T.FONT,9),tags='target')
        coordinates=[];previous=None
        for e,t,v in zip(self.entries,times,laps):
            x=(left+right)/2 if times[-1]==times[0] else left+(t-times[0])/(times[-1]-times[0])*(right-left)
            if self.axis=='lap' and previous is not None and t!=previous+1:
                if len(coordinates)>2:self.create_line(*coordinates,fill=T.ACCENT,width=px(self,2),tags='series')
                coordinates=[]
            y=bottom-(v-low)/(high-low)*(bottom-top);self.points.append((x,y,e));coordinates.extend((x,y));previous=t
        if len(coordinates)>2:self.create_line(*coordinates,fill=T.ACCENT,width=px(self,2),tags='series')
        radius=px(self,4)
        for x,y,e in self.points:self.create_oval(x-radius,y-radius,x+radius,y+radius,fill=T.ACCENT,outline=T.FIELD)
        if self.axis=='lap':first=tr('第 ')+str(self.entries[0]['number'])+tr(' 圈');last=tr('第 ')+str(self.entries[-1]['number'])+tr(' 圈')
        else:
            same=self.entries[0]['observed_utc'][:10]==self.entries[-1]['observed_utc'][:10]
            first=self.entries[0]['observed_utc'][:16].replace('T',' ') if same else self.entries[0]['observed_utc'][:10]
            last=self.entries[-1]['observed_utc'][:16].replace('T',' ') if same else self.entries[-1]['observed_utc'][:10]
        self.create_text(left,bottom+px(self,20),text=first,fill=T.MUTED,anchor='w',font=(T.FONT,9))
        if len(self.entries)>1:self.create_text(right,bottom+px(self,20),text=last,fill=T.MUTED,anchor='e',font=(T.FONT,9))
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
        label=(tr('第 ')+str(e['number'])+tr(' 圈') if self.axis=='lap' else e['observed_utc'][:19].replace('T',' ')+' UTC')+'  ·  '+lap_time(e['time_s'])
        if self.target is not None:label+='\n'+tr('距目标 {delta}').format(delta=f"{e['time_s']-self.target:+.3f} s")
        self.coords(self.tooltip,min(right-px(self,160),max(left+px(self,160),x)),top+px(self,10));self.itemconfigure(self.tooltip,text=label)
    def nearest(self,x):
        i=bisect.bisect_left(self.xs,x)
        candidates=[j for j in (i-1,i) if 0<=j<len(self.points)]
        return min(candidates,key=lambda j:abs(x-self.points[j][0]))
    def inspect(self,event):
        if not self.points:return
        self.keyboard_cursor=False
        nearest=self.nearest(event.x)
        if nearest!=self.hover:self.hover=nearest;self.update_hover()
    def leave(self,_):
        if not self.keyboard_cursor:self.hover=None;self.update_hover()
    def blur(self,_):self.keyboard_cursor=False;self.hover=None;self.update_hover()
    def select(self,event):
        if self.points:
            self.focus_set();self.activate(self.nearest(event.x))
    def key(self,key):
        if not self.points:return 'break'
        self.keyboard_cursor=True
        last=len(self.points)-1
        if key=='enter':self.activate(self.hover if self.hover is not None else 0);return 'break'
        if key=='home':index=0
        elif key=='end':index=last
        elif self.hover is None:index=last if key=='left' else 0
        else:index=max(0,min(last,self.hover+(-1 if key=='left' else 1)))
        if index!=self.hover:self.hover=index;self.update_hover()
        return 'break'
    def activate(self,index):
        if self.points:
            _,_,entry=self.points[index];self.command(entry)
            point=next((p for p in self.points if p[2] is entry),None)
            if point and self.ring is not None:
                x,y,_=point;ring=self.ring
                def frame(t):
                    r=px(self,6+4*t);self.coords(ring,x-r,y-r,x+r,y+r);self.itemconfigure(ring,state='hidden' if t==1 else 'normal',outline=blend(T.ACCENT,T.FIELD,t))
                self.motion.animate('point',frame,150)
