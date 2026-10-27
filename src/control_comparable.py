"""Comparable conditions: explicit drafts, stable result selection and safe export."""
from functools import partial
import tkinter as tk
from control_theme import T
from control_fields import Select
from control_list import SessionList
from control_history_chart import ProgressChart,lap_time
from condition_match import settings,DEFAULTS
from record_presentation import number
from i18n import tr


def show(app,entry):
    from control_analysis_window import existing,AnalysisWindow
    window,identity=existing(app,'comparable',entry)
    if identity is None:return window
    p=AnalysisWindow(app,identity,'同条件进步分析',entry,(1120,820));entry=p.entry;root=app.data_path;body=p.body
    from race_model import read_json
    p.preference=root/'PersonalRecords/comparable_settings.json';saved=read_json(p.preference,{})
    try:policy=settings(saved)
    except (ValueError,TypeError):policy=dict(DEFAULTS)
    from control_analysis_policy import PolicyForm
    form=PolicyForm(p,app,policy)
    flags={key:p.variable(policy[key],True) for key in ('include_unknown','cross_mode','cross_phase')}
    form.flags=flags
    from control_analysis_scope import options
    advanced=options(app,body,flags,p.changed);p.editors.extend(advanced.editors);p.scope=advanced
    for var in flags.values():var.trace_add('write',p.changed)
    p.draft=lambda:{**{k:v.get() for k,v in form.inputs.items()},**{k:v.get() for k,v in flags.items()}};p.policy=lambda:form.read({k:v.get() for k,v in flags.items()});p.loading='正在按条件筛选有效圈…'
    from comparable_progress import analyse
    p.scanner=partial(analyse,root,entry)
    from comparable_presentation import save
    p.exporter=partial(save,root);summary=p.variable();label=app.label(body,summary,10,T.ACCENT);label.pack(fill='x',padx=12,pady=6);label.bind('<Configure>',lambda e:label.configure(wraplength=max(100,e.width)))
    table=SessionList(body,columns=('date','count','median','best','std','quality'),height=5,selectmode='browse')
    columns=(('date','时间 (UTC)',180),('count','有效圈数',95),('median','典型圈速（中位数）',170),('best','最快圈',110),('std','波动 / 秒',110),('quality','样本与条件',200))
    for key,title,width in columns:
        table.heading(key,text=title);table.column(key,width=width,minwidth=70,stretch=True)
    table.pack(fill='x',padx=10,pady=6)
    def identity(value):return str(value.get('folder','')),value['observed_utc']
    def point(e):
        for i,s in enumerate((p.result or {}).get('sessions',[])):
            if identity(s)==identity(e):table.selection_set((str(i),));table.yview('moveto',max(0,int(i)-1)/max(1,len(table.order)));break
    chart=ProgressChart(body,point,height=190);chart.pack(fill='x',padx=10,pady=6);detail=p.variable();label=app.label(body,detail,9);label.pack(fill='x',padx=12,pady=6);label.bind('<Configure>',lambda e:label.configure(wraplength=max(100,e.width)))
    metric=p.variable('median_s');choices=Select(p.actions,textvariable=metric,values=['median_s','best_s'],labels={'median_s':'典型圈速','best_s':'最快圈'},width=14);choices.pack(side='left');state=dict(selected=None)
    def draw(*_):
        if p.result:chart.set([dict(s,time_s=s[metric.get()]) for s in p.result['sessions']])
    choices.bind('<<ComboboxSelected>>',draw)
    def choose(_=None):
        ids=table.selection();sessions=(p.result or {}).get('sessions',[]);e=sessions[int(ids[0])] if ids else None;state['selected']=e
        if e:
            from analysis_scope import phase
            from race_mode import mode,LABELS
            detail.set(tr(LABELS[mode(e)])+' / '+tr(phase(e))+' / '+tr('圈起点油量区间')+': '+str(e['fuel_range_l'])+' L / '+tr('条件未知字段')+': '+(', '.join(e['unknown']) or tr('无'))+'\n'+tr('统计为实测结果，未按油量修正圈速，不能归因于驾驶提升。'))
        else:detail.set('')
    table.bind('<<TreeviewSelect>>',choose)
    def render(value):
        old=identity(state['selected']) if state['selected'] else None;exc=value['excluded'];p.say('可比赛事 {count} · 条件未知排除 {unknown} · 条件不同排除 {different}',count=len(value['sessions']),unknown=exc['unknown'],different=exc['different'])
        gain=value['summary'];summary.set(tr('典型圈速提升')+': '+number(gain['pace_gain_s'],' s',3)+' / '+tr('波动减少')+': '+number(gain['consistency_gain_s'],' s',3) if gain else tr('至少需要两场条件已知、各有足够有效圈的赛事，才能描述长期变化'))
        rows=[]
        for i,s in enumerate(value['sessions']):
            quality='探索性：条件未知' if s['unknown'] else '样本不足' if not s['qualified'] else '可比样本';rows.append((str(i),(s['observed_utc'][:19].replace('T',' '),s['count'],lap_time(s['median_s']),lap_time(s['best_s']),number(s['std_s'],'',3),tr(quality))))
        selected=next((str(i) for i,s in enumerate(value['sessions']) if identity(s)==old),rows[-1][0] if rows else None);position=table.yview()[0];table.replace(rows,());draw()
        if selected is not None:table.selection_set((selected,))
        else:choose()
        table.yview('moveto',position)
    def translate():
        from control_widgets import px
        tk.Canvas.configure(choices,width=max(choices.font.measure(tr(label)) for label in choices.labels.values())+px(choices,80));form.describe()
        for key,title,_ in columns:table.heading(key,text=title)
        if p.result:render(p.result)
    p.render=render;p.on_translate=translate
    p.button('scan','应用条件并分析',p.apply,lambda:not p.exporting and not p.writing,True);p.button('export','导出同条件报告',p.export,p.ready)
    p.form=form;p.flags=flags;p.table=table;p.metric=metric;p.metric_choice=choices;p.chart=chart;p.selection_state=state;p.finish();return p.window
