"""EVO record layout: compact facts and balanced, lazy photos without blanks."""
import tkinter as tk
from control_theme import T
from control_widgets import px
from control_metrics import Metrics
from guide_cards import Picture
from i18n import Label
from evo_record_presentation import FIELDS


class Header(tk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent,bg=T.CARD);self.app=app
        self.text=tk.Frame(self,bg=T.CARD);self.text.pack(fill='x')
        Label(self.text,text='ASSETTO CORSA EVO  /  PERSONAL BEST',bg=T.CARD,fg=T.ACCENT,font=('Consolas',9,'bold'),anchor='w').pack(fill='x',pady=(0,4))
        self.facts_host=tk.Frame(self,bg=T.CARD)
        self.art=tk.Frame(self,bg=T.CARD);self.images=[];self.picture=None;self.track_picture=None;self.columns=None
        self.art.bind('<Configure>',self.layout)

    def arrive(self):pass

    def layout(self,event=None):
        if not self.images:return
        width=self.art.winfo_width();columns=2 if len(self.images)>1 and width>=px(self,560) else 1
        if columns==self.columns:return
        self.columns=columns
        for i in range(2):self.art.columnconfigure(i,weight=1 if i<columns else 0,uniform='evo-photos' if i<columns else '')
        gap=px(self,12)
        for i,host in enumerate(self.images):
            col=i%columns;pad=(round(gap*col/columns),round(gap*(columns-1-col)/columns))
            host.grid(row=i//columns,column=col,sticky='nsew',padx=pad,pady=(0,px(self,8)))

    def show_vehicle(self,vehicle=''):
        for host in self.images:host.destroy()
        self.images=[];self.picture=None;self.track_picture=None;self.columns=None;self.art.pack_forget()
        if not isinstance(vehicle,tuple):return
        from evo_art import item
        model,track,layout=vehicle
        for kind,name,variant,title in (('cars',model,'','车辆照片'),('tracks',track,layout,'赛道照片')):
            entry=item(kind,name,variant,root=self.app.data_path)
            if not entry:continue
            host=tk.Frame(self.art,bg=T.FIELD);self.images.append(host)
            Label(host,text=title,bg=T.FIELD,fg=T.MUTED,font=(T.FONT,9),anchor='w').pack(fill='x',padx=10,pady=(7,3))
            picture=Picture(host,self.app,entry);picture.configure(width=1);picture.pack_configure(pady=0)
            if kind=='cars':self.picture=picture
            else:self.track_picture=picture
        if self.images:self.art.pack(fill='x',pady=(10,0));self.layout()


class Facts(Metrics):
    def __init__(self,parent):
        self.visible=();self.grid_key=None;super().__init__(parent,FIELDS)

    def layout(self,event=None):
        width=event.width if event is not None else self.winfo_width()
        columns=max(1,min(3,len(self.visible),int(width/max(1,px(self,220)))))
        wrap=max(80,(width-px(self,8)*(columns-1))//columns-px(self,24))
        if self.wrap!=(columns,wrap):
            self.wrap=(columns,wrap)
            for label in (*self.captions,*self.values.values()):label.configure(wraplength=wrap)
        key=(columns,self.visible)
        if self.grid_key==key:return
        self.grid_key=key
        self.columns=columns
        for i in range(3):self.columnconfigure(i,weight=1 if i<columns else 0,uniform='metrics' if i<columns else '')
        for tile in self.tiles:tile.grid_forget()
        lookup=dict(zip(self.values,self.tiles))
        gap=px(self,8)
        for i,key in enumerate(self.visible):
            col=i%columns;pad=(round(gap*col/columns),round(gap*(columns-1-col)/columns))
            lookup[key].grid(row=i//columns,column=col,sticky='nsew',padx=pad,pady=(0,gap))

    def set(self,values=None):
        values=values or {};self.visible=tuple(key for key in self.values if key in values)
        for key in self.visible:self.values[key].configure(text=values[key],fg=T.FG)
        if self.visible:
            if not self.master.winfo_manager():self.master.pack(fill='x',pady=(8,0),after=self.master.master.text)
            if not self.winfo_manager():self.pack(fill='x')
            self.layout()
        else:self.pack_forget();self.master.pack_forget()
