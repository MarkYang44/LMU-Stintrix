"""Training priorities window: background aggregation, readable native list."""
import os,tkinter as tk
from i18n import tr
from control_theme import T
from control_motion import reveal_window
from control_feedback import StatusFeedback
from control_list import SessionList
from record_presentation import number
from track_names import display


def show(app,entry):
    if not entry:app.status.set(tr('请选择一条纪录'));return
    window=tk.Toplevel(app.root);window.title(tr('训练优先级报告'));window.configure(bg=T.BG);window.geometry(f'1100x{min(920,window.winfo_screenheight()-90)}');window.minsize(850,680)
    footer=tk.Frame(window,bg=T.CARD);footer.pack(side='bottom',fill='x',padx=18,pady=(0,18))
    body=tk.Frame(window,bg=T.CARD);body.pack(fill='both',expand=True,padx=18,pady=18)
    app.label(body,'训练优先级报告',20,T.FG,True).pack(anchor='w',pady=12)
    app.label(body,display(entry['track'])+' · '+entry['session'].get('vehicle',''),12,T.ACCENT).pack(anchor='w')
    message=tk.StringVar(window,value=tr('正在分析同布局、同车型的有效圈…'));feedback=StatusFeedback(body,message,10);feedback.pack(fill='x',pady=12);feedback.busy('scan')
    from control_widgets import Switch
    from condition_match import settings
    from race_model import read_json
    saved=read_json(app.data_path/'PersonalRecords/training_settings.json',{})
    policies={key:tk.BooleanVar(window,value=bool(saved.get(key,False))) for key in ('include_unknown','cross_mode','cross_phase')}
    from control_analysis_scope import options
    options(app,body,policies,lambda:rescan())
    details=tk.Frame(body,bg=T.CARD);details.pack(side='bottom',fill='x')
    table=SessionList(body,columns=('zone','distance','loss','std','count'),height=5,selectmode='browse')
    for key,title,width in (('zone','分析区间',130),('distance','距离',180),('loss','典型时间差',150),('std','波动',150),('count','样本圈数',120)):
        table.heading(key,text=title);table.column(key,width=width,minwidth=75,stretch=True)
    table.pack(fill='both',expand=True)
    detail=tk.StringVar(window,value='');label=app.label(details,detail,11,T.FG);label.pack(fill='x',pady=8)
    label.bind('<Configure>',lambda event:label.configure(wraplength=max(100,event.width)))
    app.label(details,'正的距离差表示更晚制动或更晚恢复全油门；正的速度差表示速度更高。',9).pack(anchor='w')
    app.label(details,'区间来自制动输入，不代表官方弯号；训练排序不保证提升秒数。',9).pack(anchor='w',pady=6)
    from control_zone_map import ZoneMap
    def map_choose(zone):
        for i,z in enumerate(state.get('report',{}).get('priorities',[])):
            if z is zone:table.selection_set((str(i),));break
    map_view=ZoneMap(body,map_choose);map_view.pack(fill='x',before=table,pady=6)
    state=dict(request=0)

    def choose(_=None):
        ids=table.selection()
        if not ids or 'report' not in state:return
        z=state['report']['priorities'][int(ids[0])];d=z['differences']
        map_view.select(z)
        parts=[tr('制动点差')+': '+number(d['brake_m'],' m'),tr('最低速度差')+': '+number(d['minimum_kmh'],' km/h'),tr('全油门恢复差')+': '+number(d['full_m'],' m')]
        for key,title in (('coast_s','滑行时间差'),('abs_s','ABS 触发时间差'),('tc_s','TC 触发时间差')):
            parts.append(tr(title)+': '+number(d.get(key),' s',3))
        detail.set('  /  '.join(parts))
    table.bind('<<TreeviewSelect>>',choose)
    def done(result,error):
        if not window.winfo_exists():return
        feedback.busy('scan',False)
        if error:message.set(error);return
        state['report']=result;r=result['reference'];map_view.set(result.get('geometry',[]),result['priorities'],result.get('reference_features'))
        message.set(tr('实际参考圈')+f" {int(r['time_s']//60)}:{r['time_s']%60:06.3f} · "+tr('可用圈数')+' '+str(result['count'])+' · '+tr('条件未知字段')+' '+str(len(result['unknown'])))
        rows=[]
        for i,z in enumerate(result['priorities']):
            rows.append((str(i),(z['name'] if z.get('source')=='user_distance' else tr(z['name'].split()[0])+' '+z['name'].split()[-1],f"{z['start']:.0f}–{z['end']:.0f} m",number(z['median_loss_s'],' s',3),number(z['std_s'],' s',3),z['count'])))
        table.replace(rows,())
        if rows:table.selection_set((rows[0][0],))
    from training_report import report
    def rescan():
        state['request']+=1;request=state['request'];feedback.busy('scan');message.set(tr('正在分析同布局、同车型的有效圈…'))
        def completed(value,error):
            if window.winfo_exists() and request==state['request']:done(value,error)
        policy=settings({k:v.get() for k,v in policies.items()})
        from storage import atomic_json
        target=app.data_path/'PersonalRecords/training_settings.json';target.parent.mkdir(parents=True,exist_ok=True);atomic_json(target,policy)
        app.run_background(lambda:report(app.data_path,entry,policy),completed)
    rescan()
    def export():
        if 'report' in state:
            from training_presentation import save
            app.work(lambda:save(app.data_path,state['report']),os.startfile)
    actions=app.row(footer);app.button(actions,'导出完整训练报告',export,True,190)
    def edit_zones():
        if 'report' in state:
            from control_zone_editor import show as editor
            value=state['report'];editor(app,entry,value.get('zone_definitions',value['priorities']),rescan)
    app.button(actions,'编辑分析区间',edit_zones,False,160)
    def set_goal():
        ids=table.selection()
        if not ids or 'report' not in state:return
        value=state['report'];zone=value['priorities'][int(ids[0])]
        from training_goals import create
        def done(goal,error):
            if window.winfo_exists():message.set(error or tr('训练目标已建立；下一场结束后可查看跟进'))
        app.run_background(lambda:create(app.data_path,value,zone),done)
    goals_row=app.row(footer)
    app.button(goals_row,'设为本次训练目标',set_goal,False,175)
    from control_training_goals import show as goals
    app.button(goals_row,'查看训练目标',lambda:goals(app),False,150)
    reveal_window(window)
