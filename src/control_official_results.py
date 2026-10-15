"""Native official career browser; source XML and existing reports remain untouched."""
import os,tkinter as tk
from pathlib import Path
from i18n import tr
from control_theme import T
from control_fields import Field,Select
from control_list import SessionList
from control_metrics import Metrics
from track_names import display,search_text,layout
from official_results import load,refresh
from race_mode import mode,LABELS
from control_mode_filters import ModeControls
from control_event_filters import replace_rows,edit_note
from event_catalog import attach
from control_history_chart import lap_time

def place(total,group):
    return ('P'+str(total) if total else '—')+' / '+tr('同组')+' '+('P'+str(group) if group else tr('未知'))

def show(app):
    generation=app.scan_generation;state=dict(entries={},selected=None,busy=False)
    body=app.card('官方战绩','只读导入游戏结果 XML；没有遥测的赛事只展示成绩与官方圈计时')
    row=app.row(body);query=tk.StringVar(app.root);Field(row,textvariable=query).pack(side='left',fill='x',expand=True)
    driver_row=app.row(body);app.label(driver_row,'多人赛事车手姓名',9).pack(side='left',padx=(0,12));driver_name=tk.StringVar(app.root);Field(driver_row,textvariable=driver_name,width=22).pack(side='left')
    from race_model import read_json
    driver_name.set(read_json(app.data_path/'OfficialResults/preferences.json',{}).get('player_name',''))
    note=tk.StringVar(app.root);app.label(body,note,9).pack(fill='x',pady=6)
    modes=ModeControls(body,app,lambda:populate(),'official_mode_filters')
    modes.bind_query(query)
    table=SessionList(body,columns=('date','phase','mode','track','car','finish','best','link'),height=7)
    for key,label,width in (('date','时间 (UTC)',180),('phase','阶段',75),('mode','参赛方式',85),('track','赛道 / 布局',180),('car','车辆',215),('finish','完赛 / 同组',155),('best','最快圈',110),('link','关联',120)):
        table.heading(key,text=label);table.column(key,width=width,minwidth=70,stretch=key in ('track','car'))
    table.pack(fill='x',pady=8)
    info=app.card('官方成绩详情','成绩来自游戏 XML；燃油、油刹曲线和赛道条件只在存在关联遥测时可查看')
    metrics=Metrics(info,[('driver','车手姓名'),('mode','参赛方式'),('date','比赛时间 (UTC)'),('track','赛道'),('layout','赛道布局 / 长度'),('phase','阶段'),('vehicle','使用车型'),('team','车型所在车队'),('class','车辆类别'),('grid','发车 / 同组'),('finish','完赛 / 同组'),('best','个人最快圈'),('finish_time','官方 FinishTime / 秒'),('laps','完成圈数'),('status','完赛状态'),('source','数据来源')]);metrics.pack(fill='x',pady=8)
    app.label(info,'官方圈计时：XML 未提供完整有效圈验证，不计入遥测圈速纪录。',9).pack(fill='x',pady=6)
    lap_table=SessionList(info,columns=('lap','time','s1','s2','s3'),height=5)
    for key,title in (('lap','圈'),('time','圈速'),('s1','S1 / s'),('s2','S2 / s'),('s3','S3 / s')):
        lap_table.heading(key,text=title);lap_table.column(key,width=140,minwidth=60,stretch=True)
    lap_table.pack(fill='x',pady=6)
    text=tk.StringVar(app.root);label=app.label(info,text,10);label.pack(fill='x',pady=8);label.bind('<Configure>',lambda e:label.configure(wraplength=max(150,e.width)))
    app.label(info,'成绩冲突对照（只展示，不自动覆盖）',12,T.FG,True).pack(anchor='w',pady=8)
    conflicts=SessionList(info,columns=('field','telemetry','official','decision'),height=3)
    for key,title in (('field','冲突字段'),('telemetry','遥测观测值'),('official','官方 XML 值'),('decision','处理建议')):
        conflicts.heading(key,text=title);conflicts.column(key,width=190,minwidth=90,stretch=True)
    conflicts.pack(fill='x',pady=5)
    def alive():return not app.closing and generation==app.scan_generation and table.winfo_exists()
    labels=dict(matched='已关联',unmatched='无关联遥测',ambiguous='待确认',conflict='成绩冲突')
    def populate(*_):
        if not alive():return
        modes.describe()
        rows=[];term=query.get().casefold()
        for _,e in modes.pairs(list(state['entries'].values()),query.get()):
            key=e['id']
            rows.append((key,(e['started_utc'][:19].replace('T',' '),tr(e['phase']),tr(LABELS[mode(e)]),display(e['layout']),e['vehicle'],place(e['finish_place'],e['finish_class_place']),lap_time(e['best_lap_s']) if e['best_lap_s'] else '—',tr(labels.get(e.get('link_status'),'无关联遥测')))))
        old=state['selected'];chosen=old['id'] if old else None
        replace_rows(table,rows,(chosen,) if chosen else ());state['selected']=None;metrics.set();text.set('');lap_table.replace([],());conflicts.replace([],())
        if rows:table.selection_set((chosen,) if chosen and table.exists(chosen) else (rows[0][0],))
    def selected(_=None):
        ids=table.selection();e=state['entries'].get(ids[0]) if ids else None;state['selected']=e;modes.describe(e)
        if not e:return
        metrics.set(dict(driver=e['driver'],mode=tr(LABELS[mode(e)]),date=e['started_utc'][:19].replace('T',' ')+' UTC',track=display(e['track']),layout=layout(e['track'],e['layout'],e['length_m']),phase=tr(e['phase']),vehicle=e['vehicle'],team=e['team'] or tr('未知'),**{'class':e['vehicle_class'] or tr('未知')},grid=place(e['grid_place'],e['grid_class_place']),finish=place(e['finish_place'],e['finish_class_place']),best=lap_time(e['best_lap_s']) if e['best_lap_s'] else tr('未知'),finish_time=f"{e['finish_time_s']:.3f}" if e['finish_time_s'] else tr('未知'),laps=str(e['completed_laps']) if e['completed_laps'] is not None else tr('未知'),status=e['finish_status'] or tr('未知'),source='LMU result XML'))
        lap_table.replace([(str(i),(l['number'],lap_time(l['time_s']),*[f'{v:.3f}' if v is not None else '—' for v in l['sectors']])) for i,l in enumerate(e['laps'])],())
        from result_conflicts import rows,provenance
        conflicts.replace(rows(e),())
        text.set(tr('FinishTime 为官方完赛计时，起跑基准未确认，不能直接当作比赛用时。')+'\n'+tr(labels.get(e.get('link_status'),'无关联遥测'))+'\n'+provenance(e))
    table.bind('<<TreeviewSelect>>',selected);query.trace_add('write',populate)
    def accept(result):
        state['entries']={e['id']:e for e in result['entries']};modes.update_options(list(state['entries'].values()));note.set(tr('赛事')+f" {len(state['entries'])} / "+tr('未读取记录')+f" {len(result['errors'])} / "+tr('冲突记录')+f" {len(result['conflicts'])}");populate()
    def sync(source=None):
        if state['busy']:return
        if source is None:
            from paths import discover_game
            game=discover_game()
            if not game:app.status.set(tr('未找到 LMU 安装目录'));return
            source=game/'UserData/Log/Results'
        state['busy']=True;note.set(tr('正在读取官方赛事结果…'));app.shell.status_feedback.busy('official-results')
        def done(value,error):
            state['busy']=False;app.shell.status_feedback.busy('official-results',False)
            if not alive():return
            if error:note.set(error);return
            accept(value);app.status.set(tr('已完成')+' · '+tr('官方成绩同步'))
        chosen=driver_name.get().strip() or None
        def work():
            result=refresh(app.data_path,source,chosen);result['entries']=attach(app.data_path,result['entries']);return result
        app.run_background(work,done)
    def folder():
        from tkinter import filedialog
        path=filedialog.askdirectory(parent=app.root,title=tr('选择结果 XML 文件夹'))
        if path:sync(path)
    tools=app.row(body);app.button(tools,'同步游戏成绩',sync,True,155);app.button(tools,'导入结果文件夹',folder,False,170)
    actions=app.row(info)
    def open_xml():
        e=state['selected'];path=Path(e['source_xml']) if e else None
        if path and path.is_file():os.startfile(str(path))
        else:app.status.set(tr('原 XML 已移动；已导入成绩仍保留'))
    def open_review():
        e=state['selected'];folder=Path(e['linked_folder']) if e and e.get('linked_folder') else None
        if folder and e.get('link_status')=='matched' and (folder/'review.html').is_file():os.startfile(str(folder/'review.html'))
        else:app.status.set(tr('没有可打开的关联遥测复盘；不会补造曲线'))
    app.button(actions,'查看原始 XML',open_xml,False,155);app.button(actions,'打开关联复盘',open_review,True,155)
    app.button(app.row(info),'收藏与标签',lambda:edit_note(app,state['selected'],lambda:initial()),False,135)
    def initial():
        def work():
            result=load(app.data_path);result['entries']=attach(app.data_path,result['entries']);return result
        app.run_background(work,lambda value,error:note.set(error) if error else accept(value) if alive() else None)
    initial()
