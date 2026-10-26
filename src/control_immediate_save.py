"""Immediate preference edits with rollback, explicit failure and latest-draft retry."""
import tkinter as tk
from control_theme import T
from control_video_widgets import Action
from control_feedback import StatusFeedback
from control_widgets import px
from i18n import tr


class ImmediateSave:
    def __init__(self,app,parent,variables,persist,key):
        self.app=app;self.variables=variables;self.persist=persist;self.key=key;self.saved=self.snapshot();self.pending=None;self.notice=('修改后立即保存',{})
        self.context=getattr(app,'immediate_save_context',{});app.immediate_save_context=self.context
        old=self.context.get(key)
        if old:self.pending=dict(old['pending']);self.notice=old['notice']
        self.frame=tk.Frame(parent,bg=parent.cget('bg'));self.frame.pack(fill='x',pady=3)
        self.message=tk.StringVar(self.frame,value=tr(self.notice[0]).format(**self.notice[1]));self.frame.preference_variables=variables
        self.feedback=StatusFeedback(self.frame,self.message);self.feedback.pack(fill='x')
        self.retry_button=Action(self.frame,'重试保存',self.retry,120);self.retry_button.configure(height=px(self.frame,34))
        if self.pending is not None:self.retry_button.pack(anchor='w',pady=3);self.feedback.label.configure(fg=T.RED)
        self.frame.bind('<Destroy>',self.dispose,add='+');self.frame.retranslate=self.translate
    def snapshot(self):return {key:var.get() for key,var in self.variables.items()}
    def fill(self,values):
        for key,var in self.variables.items():var.set(values[key])
    def say(self,text,**values):
        self.notice=text,values;self.message.set(tr(text).format(**values));self.app.status.set(self.message.get())
    def submit(self):
        draft=self.snapshot();changes={key:value for key,value in draft.items() if value!=self.saved[key]}
        if not changes:
            if self.pending is not None:
                self.pending=None;self.context.pop(self.key,None);self.retry_button.pack_forget();self.feedback.label.configure(fg=T.MUTED);self.say('设置与已保存值一致')
            return True
        try:effective=self.persist(changes,draft) or draft
        except (OSError,ValueError) as error:
            self.pending=dict(changes);self.fill(self.saved);self.feedback.label.configure(fg=T.RED)
            self.say('设置未保存，已恢复原值：{error}',error=tr(str(error)) or type(error).__name__)
            self.context[self.key]=dict(pending=self.pending,notice=self.notice)
            self.retry_button.pack(anchor='w',pady=3);return False
        self.saved=dict(effective);self.fill(self.saved);self.pending=None;self.context.pop(self.key,None);self.retry_button.pack_forget();self.feedback.label.configure(fg=T.MUTED);self.say('设置已保存');return True
    def retry(self):
        if self.pending is None:return False
        self.fill(dict(self.saved,**self.pending));return self.submit()
    def reload(self,values):
        self.saved=dict(values);self.fill(values)
    def translate(self):
        self.message.set(tr(self.notice[0]).format(**self.notice[1]));b=self.retry_button;b.configure(width=max(px(b,120),b.font.measure(tr(b.label))+px(b,36)));b.paint()
    def dispose(self,event):
        if event.widget is self.frame:
            self.message.__del__();self.message._tk=None;self.persist=None
