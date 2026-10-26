"""Training priorities: reusable, coalesced and exportable only for current scope."""
import tkinter as tk
from functools import partial
from control_theme import T
from control_list import SessionList
from record_presentation import number
from i18n import tr


def show(app,entry):
    from control_analysis_window import existing,AnalysisWindow
    window,identity=existing(app,'training',entry)
    if identity is None:return window
    p=AnalysisWindow(app,identity,'训练优先级报告',entry);entry=p.entry;root=app.data_path;body=p.body
    from race_model import read_json
    saved=read_json(root/'PersonalRecords/training_settings.json',{})
    if not isinstance(saved,dict):saved={}
    policies={key:p.variable(bool(saved.get(key,False)),True) for key in ('include_unknown','cross_mode','cross_phase')}
    from control_analysis_scope import options
    advanced=options(app,body,policies,p.schedule);p.editors.extend(advanced.switches)
    for var in policies.values():var.trace_add('write',p.changed)
    from condition_match import settings
    p.draft=lambda:{k:v.get() for k,v in policies.items()};p.policy=lambda:settings(p.draft());p.preference=root/'PersonalRecords/training_settings.json'
    p.loading='正在分析同布局、同车型的有效圈…'
    from training_report import report
    p.scanner=partial(report,root,entry)
    from training_presentation import save
    p.exporter=partial(save,root)
    table=SessionList(body,columns=('zone','distance','loss','std','count'),height=5,selectmode='browse')
    columns=(('zone','分析区间',130),('distance','距离',180),('loss','典型时间差',150),('std','波动',150),('count','样本圈数',120))
    for key,title,width in columns:
        table.heading(key,text=title);table.column(key,width=width,minwidth=75,stretch=True)
    table.pack(fill='x',padx=10,pady=8);detail=p.variable();label=app.label(body,detail,11,T.FG);label.pack(fill='x',padx=12,pady=6);label.bind('<Configure>',lambda e:label.configure(wraplength=max(100,e.width)))
    from control_zone_map import ZoneMap
    def map_choose(zone):
        for i,z in enumerate((p.result or {}).get('priorities',[])):
            if z is zone:table.selection_set((str(i),));table.yview('moveto',max(0,int(i)-1)/max(1,len(table.order)));break
    map_view=ZoneMap(body,map_choose);map_view.pack(fill='x',padx=10,pady=6)
    p.heading('正的距离差表示更晚制动或更晚恢复全油门；正的速度差表示速度更高。',9)
    p.heading('区间来自制动输入，不代表官方弯号；训练排序不保证提升秒数。',9)
    state=dict(selected=None,created=set())
    def zone_key(z):return z.get('name'),z['start'],z['end']
    def choose(_=None):
        ids=table.selection();zone=(p.result or {}).get('priorities',[]);z=zone[int(ids[0])] if ids and int(ids[0])<len(zone) else None;state['selected']=z
        if z:
            d=z['differences'];map_view.select(z);parts=[tr('制动点差')+': '+number(d['brake_m'],' m'),tr('最低速度差')+': '+number(d['minimum_kmh'],' km/h'),tr('全油门恢复差')+': '+number(d['full_m'],' m')]
            for key,title in (('coast_s','滑行时间差'),('abs_s','ABS 触发时间差'),('tc_s','TC 触发时间差')):parts.append(tr(title)+': '+number(d.get(key),' s',3))
            detail.set('  /  '.join(parts))
        else:detail.set('')
        p.sync()
    table.bind('<<TreeviewSelect>>',choose)
    def render(value):
        if state.get('created_version')!=p.version:state['created'].clear();state['created_version']=p.version
        old=zone_key(state['selected']) if state['selected'] else None;r=value['reference']
        p.say('实际参考圈 {lap} · 可用圈数 {count} · 条件未知字段 {unknown}',lap=f"{int(r['time_s']//60)}:{r['time_s']%60:06.3f}",count=value['count'],unknown=len(value['unknown']))
        map_view.set(value.get('geometry',[]),value['priorities'],value.get('reference_features'));rows=[]
        for i,z in enumerate(value['priorities']):rows.append((str(i),(z['name'] if z.get('source')=='user_distance' else tr(z['name'].split()[0])+' '+z['name'].split()[-1],f"{z['start']:.0f}–{z['end']:.0f} m",number(z['median_loss_s'],' s',3),number(z['std_s'],' s',3),z['count'])))
        selected=next((str(i) for i,z in enumerate(value['priorities']) if zone_key(z)==old),rows[0][0] if rows else None);position=table.yview()[0];table.replace(rows,())
        if selected is not None:table.selection_set((selected,))
        else:choose()
        table.yview('moveto',position)
    p.render=render;p.on_translate=lambda:([table.heading(key,text=title) for key,title,_ in columns],render(p.result) if p.result else None)
    p.button('scan','重新分析',p.apply,lambda:not p.exporting and not p.writing)
    p.button('export','导出完整训练报告',p.export,p.ready,True)
    def edit_zones():
        if not p.ready():return
        from control_zone_editor import show as editor
        value=p.result;editor(app,entry,value.get('zone_definitions',value['priorities']),lambda:p.apply() if p.alive() else None)
    p.button('zones','编辑分析区间',edit_zones,p.ready)
    def set_goal():
        if not p.ready() or state['selected'] is None or zone_key(state['selected']) in state['created']:return
        from training_goals import create
        value=p.result;zone=state['selected'];identity=zone_key(zone);p.writing=True;p.feedback.busy('goal');p.say('正在建立训练目标…');p.sync()
        def done(goal,error):
            if not p.alive():return
            p.writing=False;p.feedback.busy('goal',False)
            if error:p.say('训练目标未建立：{error}',error=error)
            else:state['created'].add(identity);p.say('训练目标已建立：{zone}',zone=zone['name'])
            p.sync()
        app.run_background(partial(create,root,value,zone),done)
    p.button('goal','设为本次训练目标',set_goal,lambda:p.ready() and state['selected'] is not None and zone_key(state['selected']) not in state['created'])
    from control_training_goals import show as goals
    p.button('goals','查看训练目标',lambda:goals(app))
    p.table=table;p.policies=policies;p.zone_state=state;p.map=map_view;p.finish();return p.window
