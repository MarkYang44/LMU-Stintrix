"""Compact advanced controls; default analysis stays within one session scope."""
import tkinter as tk
from control_theme import T
from control_widgets import Switch
from i18n import tr

def options(app,body,variables,changed=lambda:None):
    row=app.row(body)
    hint=app.label(row,'默认：同参赛方式、同阶段、已知条件',9);hint.pack(side='left',fill='x',expand=True);hint.bind('<Configure>',lambda e:hint.configure(wraplength=max(80,e.width)))
    panel=tk.Frame(body,bg=T.CARD);panel.switches=[]
    note=app.label(panel,'以下选项仅用于探索，混合样本不计入可靠提升结论。',9);note.pack(fill='x',padx=8,pady=4);note.bind('<Configure>',lambda e:note.configure(wraplength=max(80,e.width)))
    for key,title in (('include_unknown','纳入条件未知圈'),('cross_mode','跨参赛方式比较'),('cross_phase','跨阶段比较')):
        switch=Switch(panel,title,variables[key],changed);switch.pack(fill='x',padx=8);panel.switches.append(switch)
    def describe(*_):
        hint.configure(text=tr('探索选项已开启；混合样本不计入可靠提升') if any(v.get() for v in variables.values()) else tr('默认：同参赛方式、同阶段、已知条件'))
    for variable in variables.values():variable.trace_add('write',describe)
    def toggle():
        if panel.winfo_manager():panel.pack_forget()
        else:
            siblings=body.pack_slaves();i=siblings.index(row)
            panel.pack(fill='x',after=row)
        button.configure(selected=bool(panel.winfo_manager()))
    button=app.button(row,'分析范围',toggle,False,115);describe();return panel
