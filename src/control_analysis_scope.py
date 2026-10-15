"""Compact advanced controls; default analysis stays within one session scope."""
import tkinter as tk
from control_theme import T
from control_widgets import Switch
from i18n import tr

def options(app,body,variables,changed=lambda:None):
    row=app.row(body)
    hint=app.label(row,'默认：同参赛方式、同阶段、已知条件',9);hint.pack(side='left',fill='x',expand=True)
    panel=tk.Frame(body,bg=T.CARD)
    for key,title in (('include_unknown','探索模式：纳入条件未知圈（不计入可靠提升结论）'),('cross_mode','探索：跨参赛方式比较（不计入可靠提升）'),('cross_phase','探索：跨阶段比较（不计入可靠提升）')):
        Switch(panel,title,variables[key],changed).pack(fill='x')
    def describe(*_):
        hint.configure(text=tr('探索选项已开启；混合样本不计入可靠提升') if any(v.get() for v in variables.values()) else tr('默认：同参赛方式、同阶段、已知条件'))
    for variable in variables.values():variable.trace_add('write',describe)
    def toggle():
        if panel.winfo_manager():panel.pack_forget()
        else:
            siblings=body.pack_slaves();i=siblings.index(row)
            panel.pack(fill='x',after=row)
    app.button(row,'分析范围',toggle,False,115);describe();return panel
