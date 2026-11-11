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
    # A titled section like every other: the policy switch spans its row
    # (caption left, control right), its save state reads under it, and the
    # saved sampling summary shares a line with the interface check.
    body=app.card('记录与数据接口','练习赛记录策略与游戏数据接口；开关修改后立即保存')
    app.practice_recording=tk.BooleanVar(app.root,value=recording_policy.load(app.data_path))
    def save(changes,draft):
        recording_policy.save(app.data_path,draft['practice'])
        if app.active():app.hud.engine.practice_enabled=draft['practice']
        return dict(practice=recording_policy.load(app.data_path))
    switch=Switch(body,'记录练习赛',app.practice_recording,lambda:app.practice_save.submit());switch.pack(fill='x')
    app.practice_save=ImmediateSave(app,body,dict(practice=app.practice_recording),save,'practice')
    row=app.row(body);row.pack_configure(pady=(px(body,6),0))
    from control_interface import show
    button=app.button(row,'检查数据接口',lambda:show(app),False,140,compact=True);button.pack_configure(side='right',padx=0,pady=0)
    details=Disclosure(body,app,'sampling-intro','记录与采样说明',header=row);details.button.configure(height=px(row,38));details.button.pack_configure(side='right',padx=(0,px(row,8)))
    app.sampling_summary=app.label(row,'',10,T.FG);app.sampling_summary.pack(side='left',fill='x',expand=True)
    app.sampling_summary.bind('<Configure>',lambda e:app.sampling_summary.configure(wraplength=max(100,e.width)))
    for text in ('开启后保存完整采样、车辆遥测、圈速与报告；Warmup 保持实时显示','检查官方 SDK、通道可用性和数据陈旧状态；诊断只保存本机'):
        label=app.label(details.body,text,9,T.MUTED);label.pack(fill='x',pady=3);label.bind('<Configure>',lambda e:e.widget.configure(wraplength=max(100,e.width)))
    body.reveal_anchor=lambda:details.set_open(True);app.sampling_details=details
    def resume():app.practice_save.reload(dict(practice=recording_policy.load(app.data_path)));refresh(app)
    app.pages.on_resume(resume);refresh(app);return body,switch
