"""Classified, newest-first PB history with an interactive per-car progress line."""
import os,tkinter as tk
from i18n import tr
from control_theme import T
from control_widgets import px
from control_list import SessionList
from control_fields import Field,Select
from track_names import display,layout
from record_history import history
from history_view import filtered,series,SORTS
from control_history_chart import ProgressChart,lap_time
from json_store import load
from control_feedback import CountBadge
from race_mode import mode,LABELS


def show(app):
    generation=app.scan_generation;state={'entries':[],'selected':None};saved=getattr(app,'history_filters',dict(track='',car='',layout=None,sort=0));saved.setdefault('mode','');app.history_filters=saved
    body=app.card('纪录履历','同赛道布局、同车型分别统计刷新过程；默认最新记录优先')
    row=app.row(body);query=tk.StringVar(app.root);Field(row,textvariable=query).pack(side='left',fill='x',expand=True)
    from control_mode_filters import ModeControls
    from control_event_filters import replace_rows,edit_note
    from event_catalog import attach
    modes=ModeControls(body,app,lambda:populate(),'history_event_filters')
    modes.bind_query(query)
    count=CountBadge(body);count.pack(fill='x',pady=4)
    note=tk.StringVar(app.root);app.label(body,note,9).pack(fill='x',pady=4)
    table=SessionList(body,columns=('date','track','layout','class','mode','car','lap','time','gain'),height=5,selectmode='browse')
    for key,title,width in (('date','时间 (UTC)',180),('track','赛道',155),('layout','布局 / 长度',170),('class','组别',80),('mode','参赛方式',90),('car','车辆',225),('lap','圈',55),('time','最快圈',110),('gain','提升',120)):
        table.heading(key,text=title);table.column(key,width=px(table,width),minwidth=px(table,45),stretch=key in ('track','layout','car'))
    table.pack(fill='x',pady=8)
    preferred={'date':160,'track':140,'layout':150,'class':65,'mode':75,'car':190,'lap':40,'time':105,'gain':105}
    minimum={'date':135,'track':85,'layout':95,'class':50,'mode':65,'car':110,'lap':30,'time':90,'gain':95}
    def fit_columns(event):
        available=max(1,event.width-px(table,18));factor=min(1,available/sum(px(table,v) for v in preferred.values()))
        for key,width in preferred.items():table.column(key,width=max(px(table,minimum[key]),round(px(table,width)*factor)),minwidth=px(table,minimum[key]),stretch=key in ('track','layout','car'))
    table.bind('<Configure>',fit_columns,add='+')

    chart_body=app.card('成绩提升曲线','按时间展示同布局、同车型的纪录；圈速越低越快，点击数据点可定位赛事')
    chosen=tk.StringVar(app.root);label=app.label(chart_body,chosen,11,T.FG,True);label.pack(fill='x',pady=6)
    label.bind('<Configure>',lambda event:label.configure(wraplength=max(100,event.width)))
    summary=tk.StringVar(app.root);app.label(chart_body,summary,10,T.ACCENT).pack(fill='x',pady=6)
    def select_point(entry):
        for i,e in enumerate(state['entries']):
            if e is entry and table.exists(str(i)):
                table.selection_set((str(i),));table.yview('moveto',table.indices[str(i)]/max(1,len(table.order)));break
    chart=ProgressChart(chart_body,select_point);chart.pack(fill='x',pady=8)
    def alive():return not app.closing and generation==app.scan_generation and table.winfo_exists()
    def populate(*_):
        if not alive():return
        modes.describe()
        old=state['selected'];rows=[]
        for i,e in modes.pairs(state['entries'],query.get()):
            gain=e['improvement_s'];rows.append((str(i),(e['observed_utc'][:19].replace('T',' '),display(e['track']),layout(e['track'],e['layout'],e['length_m']),e['vehicle_class'],tr(LABELS[mode(e)]),e['session'].get('vehicle',''),e['lap']['number'],lap_time(e['time_s']),tr('首次记录') if gain is None else f'-{gain:.3f} s')))
        count.set(len(rows));replace_rows(table,rows,table.selection());state['selected']=None;chosen.set('');summary.set('');chart.set([])
        if rows:
            selected=next((str(i) for i,e in enumerate(state['entries']) if old and e['folder']==old.get('folder') and e['lap']['number']==old.get('lap',{}).get('number') and any(row[0]==str(i) for row in rows)),rows[0][0]);table.selection_set((selected,))
    query.trace_add('write',populate)
    def choose(_=None):
        ids=table.selection();e=state['entries'][int(ids[0])] if ids else None;state['selected']=e;modes.describe(e)
        if not e:return
        chosen.set(display(e['track'])+' · '+layout(e['track'],e['layout'],e['length_m'])+' · '+e['vehicle_class']+' · '+e['session'].get('vehicle',''))
        values=series([v for _,v in modes.pairs(state['entries'],query.get())],e);chart.set(values)
        gain=values[0]['time_s']-values[-1]['time_s'];summary.set(tr('累计提升')+f' {gain:.3f} s  /  '+tr('当前纪录')+' '+lap_time(values[-1]['time_s'])+'  /  '+str(len(values))+' '+tr('次纪录刷新')+( ' · '+tr('仅一条纪录，等待下一次突破') if len(values)==1 else ''))
    table.bind('<<TreeviewSelect>>',choose)
    def refresh():
        def done(value,error):
            if not alive():return
            if error:note.set(error);return
            state['entries']=value['entries'];note.set(tr('缺失日期排除')+' '+str(value['missing_dates'])+' / '+tr('冲突记录')+' '+str(value['conflicts']));modes.update_options(state['entries']);populate();app.status.set(str(len(value['entries']))+' '+tr('次纪录刷新'))
        def work():
            result=history(app.data_path,per_vehicle=True);result['entries']=attach(app.data_path,result['entries']);return result
        app.run_background(work,done)
    app.button(row,'刷新记录',refresh,False,112)
    tools=app.row(body);app.button(tools,'收藏与标签',lambda:edit_note(app,state['selected'],refresh),False,135)
    def curve():
        e=state['selected']
        if not e:return
        def work():
            from laps import write_compare
            from paths import ASSETS
            from uuid import uuid4
            folder=app.data_path/'PersonalRecords/History';folder.mkdir(parents=True,exist_ok=True);path=folder/(uuid4().hex+'.html')
            write_compare(path,ASSETS/'compare.html',[load(e['file'])]);return str(path)
        app.work(work,os.startfile)
    actions=app.row(chart_body);app.button(actions,'打开完整圈曲线',curve,True,170)
    app.button(actions,'打开赛事目录',lambda:os.startfile(state['selected']['folder']) if state['selected'] else None,False,150)
    def card():
        from control_achievement import show
        show(app,state['selected'])
    app.button(actions,'生成个人战绩卡',card,False,170)
    def comparable():
        from control_comparable import show
        show(app,state['selected'])
    app.button(actions,'同条件进步分析',comparable,False,180)
    refresh()
