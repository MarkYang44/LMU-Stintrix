"""Model-matched, viewport-driven vehicle photo for podium detail headers."""
import tkinter as tk
from guidebook import catalog
from guide_cards import Picture
from race_art import normalized
from control_theme import T
from control_widgets import px
from control_motion import Motion


def vehicle_picture(vehicle):
    wanted=normalized(vehicle)
    if not wanted:return None
    exact=next((car for car in catalog()['cars'].values() if normalized(car['name'])==wanted),None)
    if exact:return exact
    from race_art import image_model
    model=image_model(vehicle);base=normalized(model) if model else None
    return next(({**car,'reference_model':car['name']} for car in catalog()['cars'].values() if base and normalized(car['name'])==base),None)


class RecordHeader(tk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent,bg=T.CARD)
        self.app=app;self.surface=tk.Canvas(self,bg=T.CARD,highlightthickness=0,height=4);self.surface.grid(row=0,column=0,sticky='nsew')
        self.text=tk.Frame(self.surface,bg=T.CARD);self.text_item=self.surface.create_window(0,0,anchor='nw',window=self.text);self.motion=Motion(self.surface)
        self.text.bind('<Configure>',lambda _:self.surface.configure(height=self.text.winfo_reqheight()+4))
        self.surface.bind('<Configure>',lambda e:self.surface.itemconfigure(self.text_item,width=max(1,e.width)))
        self.art=tk.Frame(self,bg=T.CARD);self.picture=None;self.track_picture=None;self.reference_note=None;self.columnconfigure(0,weight=1)
        self.bind('<Configure>',self.layout)

    def layout(self,_=None):
        if not self.picture:return
        wide=self.winfo_width()>=px(self,680);width=px(self,340)
        self.columnconfigure(1,minsize=width if wide else 0)
        self.art.grid(row=0 if wide else 1,column=1 if wide else 0,sticky='ne' if wide else 'nw',padx=(px(self,20),0) if wide else 0)
        self.art.configure(width=width)
        self.art.pack_propagate(False)
        self.art.configure(height=round(width*9/16)*(2 if self.track_picture else 1)+(px(self,22) if self.reference_note else 0))

    def arrive(self):
        start=self.surface.coords(self.text_item)[1]
        if not self.motion.jobs:start=3
        self.motion.animate('detail',lambda t:self.surface.coords(self.text_item,0,start*(1-t)),140)

    def show_vehicle(self,vehicle=''):
        if self.picture:self.picture.destroy();self.picture=None
        if self.track_picture:self.track_picture.destroy();self.track_picture=None
        if self.reference_note:self.reference_note.destroy();self.reference_note=None
        self.art.grid_forget();self.columnconfigure(1,minsize=0)
        track_item=None
        if isinstance(vehicle,tuple):
            from evo_art import item as official_item
            vehicle,track,layout=vehicle
            item=official_item('cars',vehicle,root=self.app.data_path)
            track_item=official_item('tracks',track,layout,root=self.app.data_path)
        else:item=vehicle_picture(vehicle)
        if item:
            self.picture=Picture(self.art,self.app,item)
            self.picture.pack_configure(pady=0)
            if item.get('reference_model'):
                from i18n import Label
                self.reference_note=Label(self.art,text='同车系参考图',bg=T.CARD,fg=T.MUTED,font=(T.FONT,8));self.reference_note.pack(anchor='w')
            self.layout()
        if track_item:
            self.track_picture=Picture(self.art,self.app,track_item);self.track_picture.pack_configure(pady=0)
            if not self.picture:self.picture=self.track_picture;self.track_picture=None
            self.layout()
