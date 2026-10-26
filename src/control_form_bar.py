"""A contextual save surface; never applies a different module implicitly."""
import tkinter as tk
from control_theme import T
from control_settings_search import SECTIONS
from i18n import tr
from control_fields import Select
from control_flow import install


class FormBar:
    def __init__(self,app):
        self.app=app;self.current=getattr(app,'settings_form_module',None);self.frame=tk.Frame(app.shell.main,bg=T.CARD);self.packed=False
        self.message=tk.StringVar(self.frame);label=app.label(self.frame,self.message,9,T.ACCENT);label.pack(fill='x',padx=10,pady=(4,0));label.bind('<Configure>',lambda e:label.configure(wraplength=max(100,e.width)))
        row=app.row(self.frame);install(row);self.choice=tk.StringVar(self.frame);self.selector=Select(row,textvariable=self.choice,values=[],width=22);self.selector.pack(side='left')
        self.selector.bind('<<ComboboxSelected>>',lambda _:self.select(self.choice.get(),True))
        self.save=app.button(row,'保存本模块',self.apply,True,140);self.reset=app.button(row,'撤销本次修改',self.discard,False,150)
        self.focus_token=app.root.bind('<FocusIn>',self.focus,add='+');self.key_token=app.root.bind('<Control-s>',self.key,add='+');self.frame.bind('<Destroy>',self.dispose,add='+');self.refresh()
    def panels(self):return {key:body for key,body in getattr(self.app,'form_panels',{}).items() if body.winfo_exists()}
    def refresh(self,module=None):
        panels=self.panels();changed={key:body.form_changed() for key,body in panels.items()}
        if self.current not in panels:self.current=next((key for key,n in changed.items() if n),next(iter(panels),None))
        if module and not self.current:self.current=module
        if any(changed.values()):
            if not self.packed:self.frame.pack(side='bottom',fill='x',before=self.app.shell.scroll.master,pady=(6,0));self.packed=True
        else:self.frame.pack_forget();self.packed=False
        count=changed.get(self.current,0);self.message.set(tr(SECTIONS.get(self.current,''))+' · '+tr('已修改 {count} 项').format(count=count))
        self.save.configure(state='normal' if count else 'disabled');self.reset.configure(state='normal' if count else 'disabled')
        others=sum(n>0 for key,n in changed.items() if key!=self.current)
        if others:self.message.set(self.message.get()+' · '+tr('另有 {count} 个模块未保存').format(count=others))
        labels={key:tr(SECTIONS.get(key,key))+' · '+str(changed[key]) for key in panels}
        self.selector.labels=labels;self.selector.configure(values=list(panels));self.choice.set(self.current or '')
    def select(self,module,reveal=False):
        if module not in self.panels():return
        self.current=module;self.app.settings_form_module=module;self.refresh()
        if reveal:
            body=self.panels()[module];self.app.root.update_idletasks();y=body.winfo_rooty()-self.app.content.winfo_rooty()-20
            self.app.scroll.yview_moveto(max(0,y)/max(1,self.app.content.winfo_height()))
    def focus(self,event):
        widget=event.widget;panels=self.panels()
        while widget is not None:
            found=next((key for key,body in panels.items() if widget is body),None)
            if found:self.select(found);return
            widget=getattr(widget,'master',None)
    def apply(self):
        body=self.panels().get(self.current)
        if body:body.form_save();self.refresh()
    def discard(self):
        body=self.panels().get(self.current)
        if body:body.form_reset();self.refresh()
    def key(self,_):
        if self.app.page==2:self.apply();return 'break'
    def dispose(self,event):
        if event.widget is self.frame:
            self.app.root.unbind('<FocusIn>',self.focus_token);self.app.root.unbind('<Control-s>',self.key_token)
            for variable in (self.message,self.choice):variable.__del__();variable._tk=None
    def destroy(self):self.frame.destroy()
    def winfo_exists(self):return self.frame.winfo_exists()
