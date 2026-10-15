"""Comparable progress window: measured medians, sample sizes and explicit unknowns."""
import os,json,tkinter as tk
from pathlib import Path
from i18n import tr
from control_theme import T
from control_fields import Field,Select
from control_widgets import Switch,px
from control_feedback import StatusFeedback
from control_list import SessionList
from control_history_chart import ProgressChart,lap_time
from control_motion import reveal_window
from condition_match import settings,DEFAULTS
from comparable_progress import analyse
from record_presentation import number
from track_names import display

def show(app,entry):
    if not entry:app.status.set(tr('请选择一条纪录'));return
    window=tk.Toplevel(app.root);window.title(tr('同条件进步分析'));window.configure(bg=T.BG);window.geometry(f"1120x{min(850,window.winfo_screenheight()-90)}");window.minsize(850,590)
    footer=tk.Frame(window,bg=T.CARD);footer.pack(side='bottom',fill='x',padx=18,pady=(0,18))
    body=tk.Frame(window,bg=T.CARD);body.pack(fill='both',expand=True,padx=18,pady=18)
    app.label(body,'同条件进步分析',18,T.FG,True).pack(anchor='w',pady=8);app.label(body,display(entry['track'])+' · '+entry['session'].get('vehicle',''),10,T.ACCENT).pack(anchor='w')
    from race_model import read_json
    preference=app.data_path/'PersonalRecords/comparable_settings.json'
    try:policy=settings(read_json(preference,{}))
    except (ValueError,TypeError):policy=dict(DEFAULTS)
    inputs={};form=tk.Frame(body,bg=T.CARD);form.pack(fill='x',pady=8)
    for i,(key,title) in enumerate((('fuel_l','油量容差 / L'),('track_temp_c','赛道温度容差 / °C'),('ambient_temp_c','气温容差 / °C'),('wetness','湿度容差 / 0–1'),('rain','雨强容差 / 0–1'),('min_laps','稳定性最低圈数'))):
        tile=tk.Frame(form,bg=T.CARD);tile.grid(row=0,column=i,sticky='ew',padx=4);form.columnconfigure(i,weight=1);heading=app.label(tile,title,9);heading.pack(fill='x');heading.bind('<Configure>',lambda e,w=heading:w.configure(wraplength=max(80,e.width)));var=tk.StringVar(window,value=str(policy[key]));inputs[key]=var;Field(tile,textvariable=var,width=10).pack(fill='x')
    unknown=tk.BooleanVar(window,value=policy['include_unknown'])
    cross_mode=tk.BooleanVar(window,value=policy['cross_mode']);cross_phase=tk.BooleanVar(window,value=policy['cross_phase'])
    from control_analysis_scope import options
    options(app,body,dict(include_unknown=unknown,cross_mode=cross_mode,cross_phase=cross_phase))
    message=tk.StringVar(window);feedback=StatusFeedback(body,message);feedback.pack(fill='x',pady=8)
    summary=tk.StringVar(window);app.label(body,summary,10,T.ACCENT).pack(fill='x',pady=4)
    state=dict(request=0,selected=None,result=None)
    detail_frame=tk.Frame(body,bg=T.CARD);detail_frame.pack(side='bottom',fill='x')
    def point(e):
        if table.exists(e['observed_utc']):table.selection_set((e['observed_utc'],))
    chart=ProgressChart(body,point,height=190);chart.pack(fill='x',pady=6)
    table=SessionList(body,columns=('date','count','median','best','std','quality'),height=4)
    for k,label,width in (('date','时间 (UTC)',180),('count','有效圈数',95),('median','典型圈速（中位数）',170),('best','最快圈',110),('std','波动 / 秒',110),('quality','样本与条件',200)):
        table.heading(k,text=label);table.column(k,width=width,minwidth=70,stretch=True)
    table.pack(fill='both',expand=True,pady=6)
    detail=tk.StringVar(window);label=app.label(detail_frame,detail,9);label.pack(fill='x',pady=4);label.bind('<Configure>',lambda e:label.configure(wraplength=max(150,e.width)))
    metric=tk.StringVar(window,value=tr('典型圈速'));choices=Select(footer,textvariable=metric,values=[tr('典型圈速'),tr('最快圈')],width=14);choices.pack(side='right',padx=8,pady=4)
    def draw(*_):
        if not state['result']:return
        key='median_s' if metric.get()==tr('典型圈速') else 'best_s'
        chart.set([dict(s,time_s=s[key]) for s in state['result']['sessions']])
    choices.bind('<<ComboboxSelected>>',draw)
    def choose(_=None):
        ids=table.selection();e=next((s for s in (state.get('result') or {}).get('sessions',[]) if ids and s['observed_utc']==ids[0]),None);state['selected']=e
        if e:
            from analysis_scope import phase
            from race_mode import mode,LABELS
            detail.set(tr(LABELS[mode(e)])+' / '+tr(phase(e))+' / '+tr('圈起点油量区间')+': '+str(e['fuel_range_l'])+' L / '+tr('条件未知字段')+': '+(', '.join(e['unknown']) or tr('无'))+'\n'+tr('统计为实测结果，未按油量修正圈速，不能归因于驾驶提升。'))
    table.bind('<<TreeviewSelect>>',choose)
    def scan():
        try:p=settings({**{k:v.get() for k,v in inputs.items()},'include_unknown':unknown.get(),'cross_mode':cross_mode.get(),'cross_phase':cross_phase.get()})
        except (ValueError,TypeError) as e:message.set(str(e));return
        state['request']+=1;request=state['request'];feedback.busy('scan');message.set(tr('正在按条件筛选有效圈…'))
        from storage import atomic_json
        preference.parent.mkdir(parents=True,exist_ok=True);atomic_json(preference,p)
        def done(value,error):
            if not window.winfo_exists() or request!=state['request']:return
            feedback.busy('scan',False)
            if error:message.set(error);return
            state['result']=value;exc=value['excluded'];message.set(tr('可比赛事')+f" {len(value['sessions'])} / "+tr('条件未知排除')+f" {exc['unknown']} / "+tr('条件不同排除')+f" {exc['different']}")
            gain=value['summary']
            summary.set(tr('典型圈速提升')+': '+number(gain['pace_gain_s'],' s',3)+' / '+tr('波动减少')+': '+number(gain['consistency_gain_s'],' s',3) if gain else tr('至少需要两场条件已知、各有足够有效圈的赛事，才能描述长期变化'))
            rows=[]
            for s in value['sessions']:
                quality='探索性：条件未知' if s['unknown'] else '样本不足' if not s['qualified'] else '可比样本'
                rows.append((s['observed_utc'],(s['observed_utc'][:19].replace('T',' '),s['count'],lap_time(s['median_s']),lap_time(s['best_s']),number(s['std_s'],'',3),tr(quality))))
            table.replace(rows,());draw()
            if rows:table.selection_set((rows[-1][0],))
        app.run_background(lambda:analyse(app.data_path,entry,p),done)
    def export():
        if not state['result']:return
        from comparable_presentation import save
        app.work(lambda:save(app.data_path,state['result']),os.startfile)
    row=app.row(footer);app.button(row,'应用条件并分析',scan,True,175);app.button(row,'导出同条件报告',export,False,170)
    scan();reveal_window(window)
