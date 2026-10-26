"""Theme-aware action flyout; no input grab, idle polling or native menu styling."""
from dataclasses import dataclass
import tkinter as tk
from tkinter import font as tkfont
from control_motion import Motion,keyboard_action
from control_theme import T
from control_widgets import px,rounded
from i18n import tr


@dataclass
class MenuAction:
    key:str
    label:str
    command:object
    group:str=''
    enabled:object=lambda:True
    hint:str=''
    danger:bool=False
    visible:object=lambda:True


class ActionMenu:
    def __init__(self,trigger,actions,title='更多操作',context=lambda:''):
        self.trigger=trigger;self.owner=trigger.winfo_toplevel();self.actions=list(actions)
        self.title=title;self.context=context;self.popup=None;self.bindings=[];self.active=None
        trigger.bind('<Destroy>',self.dispose,add='+')
    def dispose(self,event):
        if event.widget is self.trigger:self.close(False)
    def invoke(self,key):
        action=next(a for a in self.actions if a.key==key)
        if not action.visible() or not action.enabled():return
        self.close();return action.command()
    def toggle(self):
        if self.popup:return self.close()
        return self.open()
    def open(self,position=None,return_focus=None):
        if self.popup:self.close(False)
        self.return_focus=return_focus or self.trigger
        previous=getattr(self.owner,'_stintrix_active_select',None)
        if previous is not None and previous is not self:previous.close(False)
        self.owner._stintrix_active_select=self
        actions=[a for a in self.actions if a.visible()]
        if not actions:return self.close(False)
        self.popup=panel=tk.Frame(self.owner,bg=T.CARD,highlightthickness=1,highlightbackground=T.EDGE,takefocus=True)
        self.font=tkfont.Font(panel,family=T.FONT,size=10);self.small=tkfont.Font(panel,family=T.FONT,size=9)
        margin=px(panel,12);self.row_h=px(panel,38);self.group_h=px(panel,27)
        width=min(self.owner.winfo_width()-margin*2,max(px(panel,290),max(self.font.measure(tr(a.label)) for a in actions)+px(panel,64)))
        head=tk.Frame(panel,bg=T.CARD);head.pack(fill='x',padx=margin,pady=(margin,px(panel,8)))
        tk.Label(head,text=tr(self.title),font=(T.FONT,10,'bold'),bg=T.CARD,fg=T.FG,anchor='w').pack(fill='x')
        tk.Label(head,text=self.context() or tr('选择操作'),font=self.small,bg=T.CARD,fg=T.MUTED,anchor='w').pack(fill='x',pady=(3,0))
        self.footer=tk.Label(panel,text=tr('↑ ↓ 选择 · Enter 执行 · Esc 关闭'),font=self.small,bg=T.CARD,fg=T.MUTED,anchor='nw',height=2,justify='left',wraplength=width-margin*2)
        self.footer.pack(side='bottom',fill='x',padx=margin,pady=(px(panel,7),margin))
        body=tk.Frame(panel,bg=T.CARD);body.pack(fill='both',expand=True)
        self.canvas=tk.Canvas(body,bg=T.CARD,highlightthickness=0,takefocus=False)
        self.canvas.pack(side='left',fill='both',expand=True)
        self.rows=[];self.positions={};y=0;group=None
        for action in actions:
            if action.group!=group:
                group=action.group
                if group:self.rows.append((y,None,group));y+=self.group_h
            self.rows.append((y,action,''));self.positions[action.key]=(y,y+self.row_h);y+=self.row_h
        self.full_height=y+px(panel,5);self.canvas.configure(scrollregion=(0,0,width,self.full_height))
        panel.update_idletasks();chrome=head.winfo_reqheight()+self.footer.winfo_reqheight()+px(panel,45)
        height=min(chrome+self.full_height,px(panel,560),self.owner.winfo_height()-margin*2)
        if height<chrome+self.full_height:
            from tkinter import ttk
            bar=ttk.Scrollbar(body,orient='vertical',style='Lab.Vertical.TScrollbar',command=self.canvas.yview)
            bar.pack(side='right',fill='y');self.canvas.configure(yscrollcommand=bar.set)
        originx=self.trigger.winfo_rootx()-self.owner.winfo_rootx()
        originy=self.trigger.winfo_rooty()-self.owner.winfo_rooty()+self.trigger.winfo_height()+px(panel,4)
        if position:originx,originy=position
        x=max(margin,min(self.owner.winfo_width()-width-margin,originx))
        y=max(margin,min(self.owner.winfo_height()-height-margin,originy))
        self.active=next((a.key for a in actions if a.enabled()),None)
        self.canvas.bind('<Configure>',lambda _:self.paint());self.canvas.bind('<Motion>',self.pointer)
        self.canvas.bind('<Leave>',lambda _:self.hover(None));self.canvas.bind('<ButtonRelease-1>',self.click)
        self.canvas.bind('<MouseWheel>',self.wheel);panel.bind('<MouseWheel>',self.wheel)
        panel.bind('<KeyPress>',lambda e:keyboard_action(panel,lambda:self.key(e)))
        panel.bind('<FocusOut>',self.focus_lost)
        for sequence,callback in (('<ButtonPress-1>',self.outside),('<Configure>',self.moved),('<FocusOut>',self.owner_focus_lost)):
            self.bindings.append((sequence,self.owner.bind(sequence,callback,add='+')))
        self.trigger.configure(selected=True);self.motion=Motion(panel)
        def frame(t):
            panel.place(x=x,y=round(y-px(panel,4)*(1-t)),width=width,height=height);panel.lift()
        self.motion.animate('reveal',frame,140);panel.focus_set();self.paint()
        return 'break'
    def paint(self):
        if not self.popup:return
        c=self.canvas;c.delete('all');w=c.winfo_width();s=px(c,1)
        for y,action,group in self.rows:
            if action is None:
                if y:c.create_line(12*s,y,w-12*s,y,fill=T.EDGE)
                c.create_text(16*s,y+self.group_h*.58,text=tr(group),anchor='w',font=self.small,fill=T.MUTED)
                continue
            enabled=action.enabled();selected=self.active==action.key
            if selected:rounded(c,6*s,y+2*s,w-12*s,self.row_h-4*s,5*s,fill=T.SELECT if enabled else T.FIELD,outline='')
            color=T.RED if action.danger else T.FG
            c.create_text(18*s,y+self.row_h/2,text=tr(action.label),anchor='w',font=self.font,fill=color if enabled else T.MUTED)
            if not enabled:c.create_text(w-18*s,y+self.row_h/2,text='—',anchor='e',font=self.small,fill=T.MUTED)
    def at(self,event):
        y=self.canvas.canvasy(event.y)
        return next((a.key for start,a,_ in self.rows if a and start<=y<start+self.row_h),None)
    def hover(self,key):
        if self.active==key:return
        self.active=key;self.paint()
        action=next((a for a in self.actions if a.key==key),None)
        self.footer.configure(text=tr(action.hint) if action and action.hint else tr('↑ ↓ 选择 · Enter 执行 · Esc 关闭'))
    def pointer(self,event):self.hover(self.at(event))
    def click(self,event):
        key=self.at(event)
        if key:self.invoke(key)
        return 'break'
    def wheel(self,event):
        self.canvas.yview_scroll(-1 if event.delta>0 else 1,'units');return 'break'
    def reveal_active(self):
        if self.active is None:return
        top,bottom=self.positions[self.active];offset=self.canvas.canvasy(0);h=self.canvas.winfo_height()
        if top<offset:self.canvas.yview_moveto(top/self.full_height)
        elif bottom>offset+h:self.canvas.yview_moveto((bottom-h)/self.full_height)
    def key(self,event):
        key=event.keysym
        if key=='Escape':return self.close()
        if key in ('Tab','ISO_Left_Tab'):
            anchor=getattr(self,'return_focus',None) or self.trigger;self.close();target=anchor.tk_focusPrev() if event.state&1 or key=='ISO_Left_Tab' else anchor.tk_focusNext()
            if target:target.focus_set()
            return 'break'
        enabled=[a.key for a in self.actions if a.key in self.positions and a.visible() and a.enabled()]
        if key in ('Down','Up','Home','End'):
            if not enabled:return 'break'
            index=enabled.index(self.active) if self.active in enabled else (-1 if key=='Down' else 0)
            index=0 if key=='Home' else len(enabled)-1 if key=='End' else (index+(1 if key=='Down' else -1))%len(enabled)
            self.hover(enabled[index]);self.reveal_active();return 'break'
        if key in ('Return','space') and self.active:self.invoke(self.active);return 'break'
    def outside(self,event):
        if self.popup and event.widget is not self.trigger and event.widget is not self.popup and not str(event.widget).startswith(str(self.popup)+'.'):self.close(False)
    def moved(self,event):
        if event.widget is self.owner:self.close(False)
    def owner_focus_lost(self,event):
        if event.widget is self.owner and self.owner.focus_get() is None:self.close(False)
    def focus_lost(self,event):
        if self.popup and event.widget is self.popup:
            focus=self.owner.focus_get()
            if focus is None or (focus is not self.popup and not str(focus).startswith(str(self.popup)+'.')):self.close(False)
    def close(self,restore=True):
        popup=self.popup;self.popup=None;focus=getattr(self,'return_focus',None) or self.trigger;self.return_focus=None
        for sequence,binding in self.bindings:
            try:self.owner.unbind(sequence,binding)
            except tk.TclError:pass
        self.bindings=[]
        if getattr(self.owner,'_stintrix_active_select',None) is self:self.owner._stintrix_active_select=None
        if popup:
            popup.destroy()
            for font in (self.font,self.small):font.__del__();font.delete_font=False
        try:
            if self.trigger.winfo_exists():
                self.trigger.configure(selected=False)
                if restore and focus.winfo_exists():focus.focus_set()
        except tk.TclError:pass
        return 'break'
