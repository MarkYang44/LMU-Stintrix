"""Compact, removable guide choices with bounded captions and full-text hints."""
import tkinter as tk
from control_theme import T
from control_widgets import px
from control_video_widgets import Action
from control_tooltip import Tooltip


class Chips(tk.Frame):
    def __init__(self,parent,remove,fallback):
        super().__init__(parent,bg=T.CARD,height=1)
        self.remove=remove;self.fallback=fallback;self.values=None;self.buttons={}
        self.pack(fill='x');self.pack_propagate(False);self.bind('<Configure>',self.layout)

    def set(self,values):
        values=tuple(values)
        if values==self.values:return
        focused=self.focus_get();keys=list(self.buttons);index=next((i for i,key in enumerate(keys) if self.buttons[key] is focused),None)
        for button in self.buttons.values():button.destroy()
        self.values=values;self.buttons={}
        for key,text in values:
            button=Action(self,text+' ×',lambda k=key:self.remove(k),105);button.full_text=text;button.configure(height=px(button,34));self.buttons[key]=button
            tip=Tooltip(button)
            def hint(event=None,b=button,t=tip):t.request(b.full_text,b.full_text,b.winfo_rootx(),b.winfo_rooty()+b.winfo_height())
            button.bind('<Enter>',hint,add='+');button.bind('<FocusIn>',hint,add='+')
            button.bind('<Leave>',lambda _,t=tip:t.hide(),add='+');button.bind('<FocusOut>',lambda _,t=tip:t.hide(),add='+');button.bind('<Destroy>',lambda _,t=tip:t.hide(),add='+')
        self.layout()
        if index is not None:
            if self.buttons:list(self.buttons.values())[min(index,len(self.buttons)-1)].focus_set()
            else:self.fallback()

    def layout(self,_=None):
        width=max(1,self.winfo_width());gap=px(self,6);x=y=line=0
        for button in self.buttons.values():
            maximum=max(1,min(width,px(self,380)));text=button.full_text;available=max(0,maximum-px(button,36))
            if button.font.measure(text+' ×')>available:
                while text and button.font.measure(text+'… ×')>available:text=text[:-1]
                text+='…'
            text+=' ×';size=min(maximum,max(px(button,105),button.font.measure(text)+px(button,36)));height=px(button,34)
            if x and x+size>width:y+=line+gap;x=line=0
            button.configure(text=text,width=size);button.place(x=x,y=y,width=size,height=height);x+=size+gap;line=max(line,height)
        self.configure(height=y+line if self.buttons else 1)
