"""Model-matched, viewport-driven vehicle photo for podium detail headers."""
import tkinter as tk
from guidebook import catalog
from guide_cards import Picture
from race_art import normalized
from control_theme import T
from control_widgets import px


def vehicle_picture(vehicle):
    wanted=normalized(vehicle)
    if not wanted:return None
    return next((car for car in catalog()['cars'].values() if normalized(car['name'])==wanted),None)


class RecordHeader(tk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent,bg=T.CARD)
        self.app=app;self.text=tk.Frame(self,bg=T.CARD);self.text.grid(row=0,column=0,sticky='nsew')
        self.art=tk.Frame(self,bg=T.CARD);self.picture=None;self.columnconfigure(0,weight=1)
        self.bind('<Configure>',self.layout)

    def layout(self,_=None):
        if not self.picture:return
        wide=self.winfo_width()>=px(self,680);width=px(self,340)
        self.columnconfigure(1,minsize=width if wide else 0)
        self.art.grid(row=0 if wide else 1,column=1 if wide else 0,sticky='ne' if wide else 'nw',padx=(px(self,20),0) if wide else 0)
        self.art.configure(width=width)
        self.art.pack_propagate(False)
        self.art.configure(height=round(width*9/16))

    def show_vehicle(self,vehicle=''):
        if self.picture:self.picture.destroy();self.picture=None
        self.art.grid_forget();self.columnconfigure(1,minsize=0)
        item=vehicle_picture(vehicle)
        if item:
            self.picture=Picture(self.art,self.app,item)
            self.picture.pack_configure(pady=0)
            self.layout()
