"""Responsive label/value tiles for native record detail sections."""
import tkinter as tk
from i18n import tr,Label
from control_theme import T
from control_widgets import px


class Metrics(tk.Frame):
    def __init__(self,parent,fields):
        super().__init__(parent,bg=T.CARD)
        self.tiles=[];self.values={};self.columns=0
        for key,caption in fields:
            tile=tk.Frame(self,bg=T.FIELD);tile.columnconfigure(0,weight=1)
            Label(tile,text=caption,bg=T.FIELD,fg=T.MUTED,font=(T.FONT,9),anchor='w').grid(row=0,column=0,sticky='ew',padx=12,pady=(9,3))
            value=Label(tile,text='—',bg=T.FIELD,fg=T.FG,font=(T.FONT,12,'bold'),anchor='w',justify='left')
            value.grid(row=1,column=0,sticky='ew',padx=12,pady=(0,10))
            tile.bind('<Configure>',lambda e,v=value:v.configure(wraplength=max(80,e.width-24)))
            self.tiles.append(tile);self.values[key]=value
        self.bind('<Configure>',self.layout)
    def layout(self,event):
        columns=max(1,min(3,int(event.width/max(1,px(self,220)))))
        if columns==self.columns:return
        self.columns=columns
        for i in range(3):self.columnconfigure(i,weight=1 if i<columns else 0,uniform='metrics' if i<columns else '')
        for i,tile in enumerate(self.tiles):tile.grid(row=i//columns,column=i%columns,sticky='nsew',padx=(0,px(self,8)) if i%columns<columns-1 else 0,pady=(0,px(self,8)))
    def set(self,values=None):
        for key,label in self.values.items():
            value=(values or {}).get(key,'—')
            label.configure(text=value,fg=T.MUTED if value in ('—',tr('未知')) else T.FG)
