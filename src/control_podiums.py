"""Championship, runner-up and third-place race browser with readable details."""
import os,math,tkinter as tk
from datetime import datetime,timezone
from pathlib import Path
from i18n import tr
from control_theme import T
from control_feedback import VictoryBadge,new_champions
from control_fields import Field
from control_list import SessionList
from control_metrics import Metrics
from podium_records import index,detail,rank
from record_presentation import number,tire
from race_model import lap_time,elapsed
from track_names import display,search_text,layout
from control_record_art import RecordHeader

from race_mode import mode,LABELS as MODE_LABELS
from control_mode_filters import ModeControls
from control_event_filters import replace_rows,edit_note
from event_catalog import attach

LABELS={1:'冠军',2:'亚军',3:'季军'}

def date(value):
    try:
        d=datetime.fromisoformat(value.replace('Z','+00:00'))
        return (d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d).astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    except (ValueError,AttributeError,TypeError):return tr('未知')

def place(value):return 'P'+str(value) if rank(value) else tr('未知')

def span(a,b,key,unit='',digits=1):
    x=number(a.get(key),unit,digits);y=number(b.get(key),unit,digits)
    return x if x==y else x+' → '+y

def show(app):
    generation=app.scan_generation;state=dict(entries=[],selected=None,request=0,category=0,data=None)
    body=app.card('领奖台记录','仅收录已确认同组完赛前三的正赛；排位、退赛、取消资格与演示不计入')
    filters=app.row(body);buttons={}
    victory=VictoryBadge(body);victory.pack(fill='x')
    query=tk.StringVar(app.root);note=tk.StringVar(app.root,value=tr('正在读取领奖台赛事…'))
    row=app.row(body);Field(row,textvariable=query).pack(side='left',fill='x',expand=True)
    modes=ModeControls(body,app,lambda:populate(),'podium_mode_filters')
    modes.bind_query(query)
    table=SessionList(body,columns=('award','date','track','class','mode','car','start','finish','lap'),height=7,selectmode='browse')
    for key,title,width in [('award','成绩',85),('date','比赛时间 (UTC)',175),('track','赛道',180),('class','组别',75),('mode','参赛方式',90),('car','车辆',225),('start','同组发车',95),('finish','同组完赛',95),('lap','最快圈',100)]:
        table.heading(key,text=title);table.column(key,width=width,minwidth=70,stretch=key in ('track','car'))
    table.pack(fill='x',pady=8);app.label(body,note,9,T.MUTED).pack(fill='x',pady=4)
    info=app.card('赛事详情','成绩、比赛进程、赛道条件与车辆条件分区展示')
    header=RecordHeader(info,app);header.pack(fill='x',pady=(6,8))
    hero=app.label(header.text,'尚无选择',20,T.ACCENT,True);hero.pack(fill='x',pady=6)
    hero.bind('<Configure>',lambda e:hero.configure(wraplength=max(100,e.width)))
    message=tk.StringVar(app.root);app.label(header.text,message,9,T.MUTED).pack(fill='x',pady=5)
    app.label(info,'赛事成绩',12,T.FG,True).pack(anchor='w',pady=(12,8))
    results=Metrics(info,[('date','比赛时间 (UTC)'),('race_time','比赛用时'),('recorded','已记录时长'),('grid','总发车名次'),('finish','总完赛名次'),('class_grid','同组发车名次'),('class_finish','同组完赛名次'),('count','同组参赛车数'),('best','个人最快圈'),('laps','已记录完整圈')]);results.pack(fill='x')
    app.label(info,'车辆身份',12,T.FG,True).pack(anchor='w',pady=(12,8))
    identity=Metrics(info,[('vehicle','使用车型'),('team','车型所在车队'),('class','车辆类别')]);identity.pack(fill='x')
    app.label(info,'赛道条件 · 记录起点 → 终点',12,T.FG,True).pack(anchor='w',pady=(12,8))
    track=Metrics(info,[('layout','赛道布局 / 长度'),('track_temp','赛道温度'),('air','气温'),('wet','路面湿度'),('rain','降雨强度'),('grip','赛道抓地状态编号')]);track.pack(fill='x')
    app.label(info,'车辆条件 · 记录起点 → 终点',12,T.FG,True).pack(anchor='w',pady=(12,8))
    car=Metrics(info,[('fuel','油量'),('front','前轮胎种'),('rear','后轮胎种'),('wear','最低轮胎余量'),('tc','牵引力控制'),('abs','ABS'),('energy','虚拟能量'),('battery','电池电量')]);car.pack(fill='x')
    app.label(info,'比赛时长与圈速曲线',12,T.FG,True).pack(anchor='w',pady=(12,8))
    app.label(info,'横轴为记录进程；绿色为有效圈，灰色为无效、进站或部分圈。',9,T.MUTED).pack(fill='x')
    pace=tk.Canvas(info,bg=T.FIELD,height=285,highlightthickness=0);pace.pack(fill='x',pady=8)
    app.label(info,'全场油门 / 刹车曲线',12,T.FG,True).pack(anchor='w',pady=(12,8))
    inputs=tk.Canvas(info,bg=T.FIELD,height=220,highlightthickness=0);inputs.pack(fill='x',pady=8)
    hover=tk.StringVar(app.root);app.label(info,hover,9,T.MUTED).pack(fill='x')
    def alive():return not app.closing and generation==app.scan_generation and table.winfo_exists()
    def draw(_=None):
        pace.delete('all');inputs.delete('all');data=state['data']
        if not data:return
        duration=data['recorded_s'] or max((p['time_s'] for p in data['pace']),default=1);points=data['pace'];left=78;right=max(left+50,pace.winfo_width()-25)
        times=[p['lap_s'] for p in points];lo=max(0,min(times)-2) if times else 0;hi=max(times)+2 if times else 1
        for i in range(4):
            y=22+i/3*207;v=hi-i/3*(hi-lo)
            pace.create_line(left,y,right,y,fill=T.EDGE);pace.create_text(left-8,y,text=lap_time(v),anchor='e',fill=T.MUTED)
        previous=None;state['dots']=[]
        for p in points:
            x=left+max(0,min(1,p['time_s']/duration))*(right-left);y=22+(hi-p['lap_s'])/(hi-lo)*207
            if previous:pace.create_line(*previous,x,y,fill=T.MUTED,width=1)
            color=T.ACCENT if p['best'] else T.GREEN if p['eligible'] else T.MUTED
            pace.create_oval(x-4,y-4,x+4,y+4,fill=color,outline='');previous=(x,y);state['dots'].append((x,y,p))
        if not points:pace.create_text((left+right)/2,120,text=tr('没有可用的完整圈时长数据'),fill=T.MUTED)
        for i in range(5):pace.create_text(left+i/4*(right-left),259,text=elapsed(duration*i/4),fill=T.MUTED,anchor='w' if i==0 else 'e' if i==4 else 'center')
        width=max(130,inputs.winfo_width());right=width-25
        for lane,(label,color) in enumerate(((tr('油门'),T.GREEN),(tr('刹车'),T.RED))):
            top=20+lane*90;inputs.create_text(12,top,text=label,anchor='w',fill=color);inputs.create_line(left,top+65,right,top+65,fill=T.EDGE)
            coords=[]
            for i,low,high in data['inputs']:
                x=left+i/599*(right-left);coords.extend((x,top+65*(1-low[lane]),x,top+65*(1-high[lane])))
            if len(coords)>3:inputs.create_line(*coords,fill=color,width=1.5)
        if data.get('xml_only'):inputs.create_text(width/2,110,text=tr('仅官方圈计时，未记录油门 / 刹车曲线'),fill=T.MUTED)
        for i in range(5):inputs.create_text(left+i/4*(right-left),207,text=elapsed(duration*i/4),fill=T.MUTED,anchor='w' if i==0 else 'e' if i==4 else 'center')
    pace.bind('<Configure>',draw);inputs.bind('<Configure>',draw)
    def inspect(event):
        dots=state.get('dots',[])
        if dots:
            _,_,p=min(dots,key=lambda v:abs(event.x-v[0]));hover.set(tr('第 ')+str(p['lap'])+tr(' 圈')+' · '+lap_time(p['lap_s'])+' · '+tr('记录进程')+' '+elapsed(p['time_s']))
    pace.bind('<Motion>',inspect)
    def selected(_=None):
        ids=table.selection()
        if not ids:return
        entry=state['entries'][int(ids[0])];modes.describe(entry);state['selected']=entry;state['request']+=1;request=state['request'];state['data']=None
        s=entry['summary'];hero.configure(text=tr(LABELS[entry['place']])+' · '+display(entry['track'])+' · '+tr(MODE_LABELS[mode(entry)]))
        header.show_vehicle(entry['session'].get('vehicle',''))
        results.set(dict(date=date(entry['started_utc']),grid=place(s.get('grid_place')),finish=place(s.get('finish_place')),class_grid=place(s.get('grid_class_place')),class_finish=place(entry['place']),count=str(s['class_size']) if rank(s.get('class_size')) else tr('未知'),best=lap_time(entry.get('fastest_s'))))
        identity.set(dict(vehicle=entry['session'].get('vehicle') or tr('未知'),team=entry['team'] or tr('未知'),**{'class':entry['vehicle_class']}))
        track.set();car.set();draw();message.set(tr('正在读取完整比赛曲线与条件…'));hover.set('')
        def done(data,error):
            if not alive() or request!=state['request']:return
            if error:message.set(error);return
            state['data']=data;a,b=data['start'],data['end']
            values={k:label.cget('text') for k,label in results.values.items()}
            values.update(race_time=elapsed(data['race_s']) if data['race_s'] is not None else tr('未知'),recorded=elapsed(data['recorded_s']) if data['recorded_s'] is not None else tr('未知'),best=lap_time(data['fastest_s']),laps=str(data['completed_laps']) if data['completed_laps'] is not None else tr('未知'));results.set(values)
            length=entry['length_m'];track.set(dict(layout=layout(entry['track'],entry['layout'],length) if length else display(entry['layout']),track_temp=span(a,b,'track_temp_c',' °C'),air=span(a,b,'ambient_temp_c',' °C'),wet=span({k:(v*100 if k=='wetness' else v) for k,v in a.items()},{k:(v*100 if k=='wetness' else v) for k,v in b.items()},'wetness',' %'),rain=span({k:(v*100 if k=='rain' else v) for k,v in a.items()},{k:(v*100 if k=='rain' else v) for k,v in b.items()},'rain',' %'),grip=span(a,b,'track_grip',digits=0)))
            def compound(axle):
                x,y=tire(a,axle),tire(b,axle);return x if x==y else x+' → '+y
            car.set(dict(fuel=span(a,b,'fuel_l',' L'),front=compound('front'),rear=compound('rear'),wear=span(a,b,'remaining',' %'),tc=span(a,b,'tc_level',digits=0),abs=span(a,b,'abs_level',digits=0),energy=span(a,b,'virtual_energy_pct',' %'),battery=span(a,b,'battery_soc_pct',' %')))
            if data.get('xml_only'):
                message.set(tr('仅官方成绩与圈计时；没有油刹、燃油或赛道条件遥测，灰色圈不代表处罚。'));draw();header.arrive();return
            message.set(tr('中途开始记录：曲线仅覆盖已记录区间，缺失数据不补造。') if data['partial'] else tr('条件显示记录起点至终点；缺失值显示未知。'));draw();header.arrive()
        app.run_background(lambda:detail(entry),done)
    table.bind('<<TreeviewSelect>>',selected)
    def populate():
        if not alive():return
        modes.describe()
        term=query.get().strip().casefold();rows=[]
        for i,e in modes.pairs(state['entries'],query.get()):
            if state['category'] and state['category']!=e['place']:continue
            rows.append((str(i),(tr(LABELS[e['place']]),date(e['started_utc']).replace(' UTC',''),display(e['track']),e['vehicle_class'],tr(MODE_LABELS[mode(e)]),e['session'].get('vehicle',''),place(e['summary'].get('grid_class_place')),place(e['place']),lap_time(e.get('fastest_s')))))
        old_folder=(state['selected'] or {}).get('folder');old_id=next((str(i) for i,e in enumerate(state['entries']) if e['folder']==old_folder),None)
        replace_rows(table,rows,(old_id,) if old_id else ());state['selected']=None;state['request']+=1;state['data']=None;hero.configure(text='尚无选择');message.set('');hover.set('')
        header.show_vehicle()
        for grid in (results,identity,track,car):grid.set()
        draw()
        if rows:table.selection_set((old_id,) if old_id and table.exists(old_id) else (rows[0][0],))
    def choose(category):
        state['category']=category
        for p,button in buttons.items():button.primary=p==category;button.paint()
        populate()
    for p,label in ((0,'全部'),(1,'冠军'),(2,'亚军'),(3,'季军')):buttons[p]=app.button(filters,label,lambda p=p:choose(p),p==0,110)
    query.trace_add('write',lambda *_:populate())
    def refresh():
        def done(result,error):
            if not alive():return
            if error:note.set(error);return
            baseline,new=new_champions(result['entries'],getattr(app,'champion_baseline',None));app.champion_baseline=baseline
            if new and not getattr(app,'champion_celebrated',False):
                app.champion_celebrated=True;victory.celebrate()
            state['entries']=result['entries'];modes.update_options(state['entries'])
            for p,button in buttons.items():button.label=tr(LABELS[p] if p else '全部')+' · '+str(result['counts'][p] if p else len(result['entries']));button.paint()
            note.set(tr('没有同组结果的旧记录无法自动认定领奖台')+' · '+str(result['missing_class_results'])+' / '+tr('冲突记录')+' '+str(result['conflicts']))
            populate();app.status.set(str(len(result['entries']))+' '+tr('场同组领奖台赛事'))
        def work():
            result=index(app.data_path);result['entries']=attach(app.data_path,result['entries']);return result
        app.run_background(work,done)
    app.button(row,'刷新记录',refresh,False,112)
    actions=app.row(info)
    app.button(actions,'打开赛事复盘',lambda:os.startfile(str(Path(state['selected']['folder'])/'review.html')) if state['selected'] and (Path(state['selected']['folder'])/'review.html').is_file() else None,True,160)
    app.button(actions,'打开赛事目录',lambda:os.startfile(state['selected']['folder']) if state['selected'] else None,False,150)
    def open_report(name):
        entry=state['selected']
        if not entry:app.status.set(tr('请选择 1 场赛事记录'));return
        if entry.get('xml_only'):
            app.status.set(tr('仅有官方 XML 成绩；请在官方战绩查看圈计时和原文件'));return
        folder=Path(entry['folder']);path=folder/name
        if path.is_file():os.startfile(str(path));return
        def build():
            from race_report import generate
            generate(folder)
            if not path.is_file():raise ValueError('这场记录没有完成圈，未生成圈速单；可以查看比赛日志')
            return str(path)
        app.work(build,os.startfile)
    app.button(actions,'查看圈速单',lambda:open_report('圈速单.png'),False,140)
    app.button(actions,'查看比赛日志',lambda:open_report('比赛日志.png'),False,150)
    def card():
        from control_achievement import show
        show(app,state['selected'])
    app.button(actions,'生成个人战绩卡',card,False,170)
    notes_row=app.row(info);app.button(notes_row,'收藏与标签',lambda:edit_note(app,state['selected'],refresh),False,135)
    refresh()
