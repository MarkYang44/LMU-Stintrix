"""Responsive, bounded label/value tiles for native record details."""
import tkinter as tk
from i18n import tr,Label
from control_theme import T
from control_widgets import px


class Metrics(tk.Frame):
    def __init__(self,parent,fields):
        super().__init__(parent,bg=T.CARD)
        self.tiles=[];self.values={};self.captions=[];self.columns=0;self.wrap=None
        for key,caption in fields:
            tile=tk.Frame(self,bg=T.FIELD);tile.columnconfigure(0,weight=1)
            title=Label(tile,text=caption,bg=T.FIELD,fg=T.MUTED,font=(T.FONT,9),anchor='w',justify='left')
            title.grid(row=0,column=0,sticky='ew',padx=12,pady=(9,3));self.captions.append(title)
            value=Label(tile,text='—',bg=T.FIELD,fg=T.FG,font=(T.FONT,12,'bold'),anchor='w',justify='left')
            value.grid(row=1,column=0,sticky='ew',padx=12,pady=(0,10))
            self.tiles.append(tile);self.values[key]=value
        self.bind('<Configure>',self.layout)
    def layout(self,event):
        columns=max(1,min(3,int(event.width/max(1,px(self,220)))))
        # Use the frame's available width. A label's requested width must never
        # feed back through its tile and continually resize the whole grid.
        wrap=max(80,(event.width-px(self,8)*(columns-1))//columns-px(self,24))
        if self.wrap!=(columns,wrap):
            self.wrap=(columns,wrap)
            for label in (*self.captions,*self.values.values()):label.configure(wraplength=wrap)
        if columns==self.columns:return
        self.columns=columns
        for i in range(3):self.columnconfigure(i,weight=1 if i<columns else 0,uniform='metrics' if i<columns else '')
        for i,tile in enumerate(self.tiles):tile.grid(row=i//columns,column=i%columns,sticky='nsew',padx=(0,px(self,8)) if i%columns<columns-1 else 0,pady=(0,px(self,8)))
    def set(self,values=None):
        for key,label in self.values.items():
            value=(values or {}).get(key,'—')
            label.configure(text=value,fg=T.MUTED if value in ('—',tr('未知')) else T.FG)
