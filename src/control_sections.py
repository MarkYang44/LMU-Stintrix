"""Task navigation that preserves hidden forms and selections."""
import tkinter as tk
from control_theme import T


class TaskSections:
    def __init__(self,app,items,key):
        self.app=app;self.key=key;self.current=None;self.positions={};self.on_select=None
        from control_video_widgets import TabBar,Tab
        from control_widgets import px
        bar=TabBar(app.content);bar.pack(anchor='w',pady=(0,px(app.content,12)));self.bar=bar
        self.frames={name:tk.Frame(app.content,bg=T.BG) for name,_ in items};self.buttons={}
        for name,label in items:self.buttons[name]=Tab(bar,label,lambda n=name:self.select(n),120)
    def select(self,name):
        if name not in self.frames:name=next(iter(self.frames))
        if self.current==name:return
        token=self.app.shell.cover_page() if self.app.pages.building is None and not self.app.shell.covering else None
        if self.current is not None:
            self.positions[self.current]=self.app.scroll.yview()[0];self.frames[self.current].pack_forget()
        self.current=name;setattr(self.app,self.key,name)
        self.frames[name].pack(fill='x')
        for key,button in self.buttons.items():button.configure(selected=key==name)
        if self.on_select:self.on_select(name)
        self.app.root.update_idletasks();self.app.scroll.yview_moveto(self.positions.get(name,0))
        if token is not None:self.app.shell.reveal_page(token)


class ScrollSpy:
    """Section tabs that follow the reading position of one long page.

    The tab whose section has crossed the upper reading line is selected;
    reaching the end of the page selects the last tab, because short final
    sections can never scroll up to that line.
    """
    LINE=.2
    def __init__(self,app,tabs,indicator,owner):
        self.app=app;self.tabs=tabs;self.indicator=indicator;self.current=None
        app.shell.scroll_listeners.append(self.update)
        owner.bind('<Destroy>',lambda e:self.dispose() if e.widget is owner else None,add='+')
        owner.after_idle(self.update)
    def dispose(self):
        listeners=getattr(self.app.shell,'scroll_listeners',[])
        if self.update in listeners:listeners.remove(self.update)
    def section(self):
        scroll=self.app.scroll;first,last=scroll.yview()
        if last>=.999 and first>.001:return self.tabs[-1][1]
        line=scroll.winfo_rooty()+scroll.winfo_height()*self.LINE;current=self.tabs[0][1]
        for _,body in self.tabs:
            if body.winfo_exists() and body.winfo_ismapped() and body.winfo_rooty()<=line:current=body
        return current
    def update(self):
        if not self.tabs or not self.indicator.winfo_exists():return
        body=self.section()
        if body is not self.current:self.show(body)
    def show(self,body):
        self.current=body
        for button,target in self.tabs:
            if button.winfo_exists():button.configure(selected=target is body)
        chosen=next((button for button,target in self.tabs if target is body),None)
        if chosen is not None and chosen.winfo_exists():self.indicator.select(chosen)


class Disclosure(tk.Frame):
    """Low-frequency details retain their open state without consuming the first screen."""
    def __init__(self,parent,app,key,title,header=None):
        from control_video_widgets import Action
        from control_widgets import px
        super().__init__(parent,bg=parent.cget('bg'));self.app=app;self.key=key;self.title=title
        self.states=getattr(app,'disclosure_states',{});app.disclosure_states=self.states
        self.button=Action(header if header is not None else self,title,self.toggle,130);self.button.configure(height=px(self,34));self.button.pack(side='left' if header is not None else 'top',anchor='w',padx=(8,0) if header is not None else 0)
        self.body=tk.Frame(self,bg=self.cget('bg'));self.pack(fill='x',pady=0 if header is not None else 3);self.retranslate=self.translate;self.set_open(bool(self.states.get(key)))
    def set_open(self,value,animate=False):
        self.states[self.key]=value
        if value:
            from control_motion import expand
            show=lambda:self.body.pack(fill='x',pady=5)
            if animate:expand(self.body,show)
            else:show()
        else:self.body.pack_forget()
        self.translate()
    def toggle(self):self.set_open(not bool(self.body.winfo_manager()),True)
    def translate(self):
        from i18n import tr
        from control_widgets import px
        b=self.button;b.configure(text=tr(self.title)+(' ▾' if self.states.get(self.key) else ' ▸'));b.configure(width=max(px(b,130),b.font.measure(b.label)+px(b,36)));b.paint()
