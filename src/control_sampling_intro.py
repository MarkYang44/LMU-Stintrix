"""Compact recording policy and a saved-value summary; diagnostics open on demand."""
import tkinter as tk
import sampling,recording_policy
from control_theme import T
from control_widgets import Switch,px
from control_sections import Disclosure
from control_immediate_save import ImmediateSave
from i18n import tr


def refresh(app):
    label=getattr(app,'sampling_summary',None)
    if label is None or not label.winfo_exists():return
    value=sampling.load_settings(app.data_path/'settings.json')
    rate=tr('固定频率')+' '+str(value['fixed_hz'])+' Hz' if value['mode']=='fixed' else tr('动态频率')+' '+str(value['min_hz'])+'–'+str(value['max_hz'])+' Hz'
    draw=tr('跟随采样') if value['draw_mode']=='sync' else tr('手动刷新')+' '+str(value['draw_hz'])+' Hz'
    label.configure(text=tr('当前已保存采样')+' · '+rate+' · '+draw)


def build(app):
    body=app.card('',compact=True);row=app.row(body);row.pack_configure(pady=0)
    app.practice_recording=tk.BooleanVar(app.root,value=recording_policy.load(app.data_path))
    def save(changes,draft):
        recording_policy.save(app.data_path,draft['practice'])
        if app.active():app.hud.engine.practice_enabled=draft['practice']
        return dict(practice=recording_policy.load(app.data_path))
    app.practice_save=ImmediateSave(app,row,dict(practice=app.practice_recording),save,'practice')
    app.practice_save.frame.pack_forget()
    switch=Switch(row,'记录练习赛',app.practice_recording,app.practice_save.submit,compact=True);switch.pack(side='left',padx=(0,8))
    from control_interface import show
    button=app.button(row,'检查数据接口',lambda:show(app),False,140);button.configure(height=px(button,34))
    app.practice_save.frame.pack(side='left',fill='x',expand=True,padx=6)
    app.sampling_summary=app.label(body,'',10,T.ACCENT);app.sampling_summary.pack(fill='x',pady=4)
    app.sampling_summary.bind('<Configure>',lambda e:app.sampling_summary.configure(wraplength=max(100,e.width)))
    details=Disclosure(body,app,'sampling-intro','记录与采样说明')
    for text in ('开启后保存完整采样、车辆遥测、圈速与报告；Warmup 保持实时显示','检查官方 SDK、通道可用性和数据陈旧状态；诊断只保存本机'):
        label=app.label(details.body,text,9,T.MUTED);label.pack(fill='x',pady=3);label.bind('<Configure>',lambda e:e.widget.configure(wraplength=max(100,e.width)))
    body.reveal_anchor=lambda:details.set_open(True);app.sampling_details=details
    def resume():app.practice_save.reload(dict(practice=recording_policy.load(app.data_path)));refresh(app)
    app.pages.on_resume(resume);refresh(app);return body,switch
