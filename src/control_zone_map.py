"""Measured trajectory and activation locations; no invented circuit outline."""
import tkinter as tk,math
from control_theme import T
from control_widgets import px
from i18n import tr

class ZoneMap(tk.Canvas):
    def __init__(self,parent,command):
        super().__init__(parent,bg=T.FIELD,height=px(parent,140),highlightthickness=0)
        self.command=command;self.geometry=[];self.zones=[];self.selected=None;self.features={};self.points=[]
        self.bind('<Configure>',self.draw);self.bind('<Button-1>',self.click)
    def set(self,geometry,zones,features=None):
        self.geometry=geometry;self.zones=zones;self.features=features or {};self.selected=None;self.draw()
    def select(self,zone):self.selected=zone;self.draw()
    def draw(self,_=None):
        self.delete('all');self.points=[];w=max(100,self.winfo_width());h=max(80,self.winfo_height())
        if not self.zones:return
        if len(self.geometry)<2 or max(p[1] for p in self.geometry)-min(p[1] for p in self.geometry)<1 and max(p[2] for p in self.geometry)-min(p[2] for p in self.geometry)<1:
            self.create_text(12,16,anchor='w',text=tr('距离分段视图：没有坐标，未绘制赛道形状'),fill=T.MUTED,font=(T.FONT,9))
            end=max(z['end'] for z in self.zones)
            for z in self.zones:
                a=20+(w-40)*z['start']/end;b=20+(w-40)*z['end']/end
                self.create_rectangle(a,50,b-2,115,fill=T.SELECT if z is self.selected else T.CARD,outline=T.ACCENT if z is self.selected else T.EDGE)
                self.create_text((a+b)/2,128,text=f"{z['start']:.0f} m",fill=T.MUTED,font=(T.FONT,8));self.points.append(((a+b)/2,80,(z['start']+z['end'])/2))
            return
        xs=[p[1] for p in self.geometry];ys=[p[2] for p in self.geometry];scale=min((w-40)/max(1,max(xs)-min(xs)),(h-58)/max(1,max(ys)-min(ys)))
        cx=(max(xs)+min(xs))/2;cy=(max(ys)+min(ys))/2
        for d,x,y in self.geometry:self.points.append((w/2+(x-cx)*scale,h/2+10-(y-cy)*scale,d))
        self.create_text(12,14,anchor='w',text=tr('实测轨迹 · 高亮为分析区间 · 黄 ABS / 蓝 TC（参考圈）'),fill=T.MUTED,font=(T.FONT,9))
        for a,b in zip(self.points,self.points[1:]):
            d=(a[2]+b[2])/2;color=T.MUTED
            if self.selected and self.selected['start']<=d<=self.selected['end']:color=T.ACCENT
            for key,c in (('abs',T.ACCENT),('tc',T.BLUE)):
                if any(lo<=d<=hi for lo,hi,_ in self.features.get('intervals',{}).get(key,[])):color=c
            self.create_line(a[0],a[1],b[0],b[1],fill=color,width=3 if color==T.ACCENT else 2)
    def click(self,event):
        if not self.points:return
        point=min(self.points,key=lambda p:(p[0]-event.x)**2+(p[1]-event.y)**2)
        z=next((z for z in self.zones if z['start']<=point[2]<z['end']),None)
        if z:self.command(z)
