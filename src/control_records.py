"""Native personal-best browser with conditions and a bounded curve canvas."""
import os
import tkinter as tk
from i18n import tr
from control_theme import T
from control_fields import Field
from control_list import SessionList
from personal_records import records,detail,entries,select_records
from race_mode import mode,LABELS
from control_mode_filters import ModeControls
from control_event_filters import replace_rows,edit_note
from event_catalog import attach
from record_presentation import present
from track_names import display,search_text,layout
from control_metrics import Metrics
from control_record_art import RecordHeader
from control_feedback import CountBadge,record_improvements,TabIndicator
from control_motion import Motion,blend


def show(app):
    """Sibling views share the existing personal-records navigation entry."""
    outer=app.content;row=app.row(outer);indicator=TabIndicator(outer);indicator.pack(fill='x');view=tk.Frame(outer,bg=T.BG);view.pack(fill='x')
    buttons=[];selected=getattr(app,'personal_record_view','best')
    def mount(kind):
        if getattr(view,'mounted',None)==kind:return
        view.mounted=kind
        app.personal_record_view=kind;app.scan_generation+=1
        for widget in view.winfo_children():widget.destroy()
        for key,button in buttons:
            button.primary=key==kind;button.paint()
            if key==kind:indicator.select(button)
        app.content=view
        try:
            if kind=='podium':
                from control_podiums import show as show_podiums
                show_podiums(app)
            elif kind=='official':
                from control_official_results import show as show_official
                show_official(app)
            elif kind=='history':
                from control_history import show as show_history
                show_history(app)
            else:show_best(app)
        finally:app.content=outer
        app.scroll.yview_moveto(0)
    for kind,label in (('best','赛道最快圈'),('podium','同组领奖台'),('history','纪录履历'),('official','官方战绩')):
        buttons.append((kind,app.button(row,label,lambda k=kind:mount(k),kind==selected,155)))
    mount(selected)


def show_best(app):
    root=app.data_path
    generation=app.scan_generation;state={'entries':[],'curve':[],'selected':None,'request':0}
    body=app.card('个人赛道纪录','每个赛道布局、车辆组别各保留最快有效圈；不包含演示或未验证旧圈')
    row=app.row(body);query=tk.StringVar(app.root);Field(row,textvariable=query).pack(side='left',fill='x',expand=True)
    modes=ModeControls(body,app,lambda:populate(),'best_mode_filters')
    modes.bind_query(query)
    table=SessionList(body,columns=('track','layout','class','mode','car','time'),height=6,selectmode='browse')
    for key,title,width in [('track','赛道',190),('layout','布局 / 长度',160),('class','组别',90),('mode','参赛方式',90),('car','车辆',230),('time','最快圈',100)]:
        table.heading(key,text=title);table.column(key,width=width,minwidth=65,stretch=key in ('track','layout','car'))
    table.pack(fill='x',pady=8)
    count=CountBadge(body);count.pack(fill='x',pady=4)
    info=app.card('纪录详情','选择一条纪录查看完整圈曲线与赛道、车辆条件')
    header=RecordHeader(info,app);header.pack(fill='x',pady=(6,8))
    caption=tk.StringVar(app.root,value=tr('尚无选择'))
    label=app.label(header.text,caption,10);label.pack(fill='x',pady=6)
    label.bind('<Configure>',lambda e:label.configure(wraplength=max(200,e.width)))
    badge=app.label(header.text,'',10,T.ACCENT,True);badge.pack(anchor='w');badge_motion=Motion(badge)
    track_title=app.label(header.text,'—',17,T.FG,True);track_title.pack(fill='x',pady=(2,8))
    track_title.bind('<Configure>',lambda e:track_title.configure(wraplength=max(100,e.width)))
    hero=app.row(header.text);time_label=app.label(hero,'—',32,T.ACCENT,True);time_label.pack(side='left',padx=(0,24))
    context=tk.Frame(hero,bg=T.CARD);context.pack(side='left',fill='x',expand=True)
    car_label=app.label(context,'—',11,T.FG,True);car_label.pack(fill='x',pady=4)
    car_label.bind('<Configure>',lambda e:car_label.configure(wraplength=max(100,e.width)))
    date_label=app.label(context,'—',9,T.MUTED);date_label.pack(fill='x',pady=4)
    date_label.bind('<Configure>',lambda e:date_label.configure(wraplength=max(100,e.width)))
    app.label(info,'赛道条件',12,T.FG,True).pack(anchor='w',pady=(16,8))
    track_metrics=Metrics(info,[('layout','布局 / 长度'),('track_temp','赛道温度'),('air_temp','气温'),('wetness','路面湿度'),('rain','降雨强度')]);track_metrics.pack(fill='x')
    app.label(info,'车辆与轮胎',12,T.FG,True).pack(anchor='w',pady=(12,8))
    car_metrics=Metrics(info,[('fuel','圈起点油量'),('front','前轮胎种'),('rear','后轮胎种'),('remaining','最低轮胎余量'),('assists','驾驶辅助')]);car_metrics.pack(fill='x')
    canvas=tk.Canvas(info,bg=T.FIELD,highlightthickness=0,height=250);canvas.pack(fill='x',pady=8)
    def alive():return not app.closing and generation==app.scan_generation and table.winfo_exists()
    def draw(_=None):
        canvas.delete('all');w=max(100,canvas.winfo_width());left=52;right=w-18
        for i,(name,color) in enumerate(((tr('油门'),T.GREEN),(tr('刹车'),T.RED))):
            top=24+i*105;canvas.create_text(8,top,text=name,fill=color,anchor='w')
            canvas.create_line(left,top+75,right,top+75,fill=T.EDGE)
            points=[]
            for index,low,high in state['curve']:
                x=left+index/599*(right-left)
                points.extend((x,top+75*(1-low[i]),x,top+75*(1-high[i])))
            if len(points)>=4:canvas.create_line(*points,fill=color,width=1.5)
        if state['selected']:
            length=state['selected']['length_m']
            for i in range(5):canvas.create_text(left+i/4*(right-left),242,text=f'{length*i/4:.0f} m',fill=T.MUTED)
    canvas.bind('<Configure>',draw)
    def clear():
        header.show_vehicle()
        for widget in (track_title,time_label,car_label,date_label):widget.configure(text='—')
        track_metrics.set();car_metrics.set()
    def selected(_=None):
        ids=table.selection()
        if not ids:return
        entry=state['entries'][int(ids[0])];modes.describe(entry);state['selected']=entry;state['request']+=1;request=state['request']
        state['curve']=[];draw();clear();caption.set(tr('正在读取纪录详情…'))
        header.show_vehicle(entry['session'].get('vehicle',''))
        def done(result,error):
            if not alive() or request!=state['request']:return
            if error:caption.set(error);return
            presentation=present(entry,result)
            track_title.configure(text=presentation['track']);time_label.configure(text=presentation['time'])
            car_label.configure(text=presentation['car']);date_label.configure(text=presentation['context']+' · '+tr(LABELS[mode(entry)]))
            track_metrics.set(presentation['track_metrics']);car_metrics.set(presentation['car_metrics'])
            caption.set('');state['curve']=result['curve'];draw();header.arrive()
        app.run_background(lambda:detail(entry),done)
    table.bind('<<TreeviewSelect>>',selected)
    def populate():
        if not alive():return
        modes.describe()
        search=query.get().strip().casefold();rows=[]
        candidates=[e for _,e in modes.pairs(state.get('all_entries',[]),query.get())]
        state['entries']=select_records(candidates)
        for i,e in modes.pairs(state['entries']):
            layout_name=layout(e['track'],e['layout'],e['length_m'])
            t=e['time_s'];rows.append((str(i),(display(e['track']),layout_name,e['vehicle_class'],tr(LABELS[mode(e)]),e['session'].get('vehicle',''),f'{int(t//60)}:{t%60:06.3f}')))
        old_folder=(state['selected'] or {}).get('folder');old_id=next((str(i) for i,e in enumerate(state['entries']) if e['folder']==old_folder),None)
        count.set(len(rows));replace_rows(table,rows,(old_id,) if old_id else ())
        state['selected']=None;state['request']+=1;state['curve']=[];caption.set(tr('尚无选择'));clear();draw()
        if rows:table.selection_set((old_id,) if old_id and table.exists(old_id) else (rows[0][0],))
    query.trace_add('write',lambda *_:populate())
    def refresh():
        def done(result,error):
            if not alive():return
            if error:app.status.set(error);return
            winners=select_records(result)
            baseline,improved=record_improvements(winners,getattr(app,'record_best_baseline',None));app.record_best_baseline=baseline
            state['all_entries']=result;modes.update_options(result);populate();app.status.set(f"{len(state['entries'])} {tr('条个人赛道纪录')}")
            if improved:
                badge.configure(text=tr('新纪录')+' · '+display(improved[0]['track']));badge_motion.animate('record',lambda t:badge.configure(fg=blend(T.GREEN,T.ACCENT,t)),180)
                app.status.set(tr('新纪录')+' · '+display(improved[0]['track']))
            else:badge.configure(text='')
        app.run_background(lambda:attach(root,entries(root)),done)
    app.button(row,'刷新记录',refresh,False,112)
    def open_record():
        entry=state['selected']
        if entry:
            from laps import write_compare
            from json_store import load
            from paths import ASSETS
            def work():
                from pathlib import Path
                output=root/'PersonalRecords';output.mkdir(exist_ok=True);path=output/'record.html'
                write_compare(path,ASSETS/'compare.html',[load(entry['file'])]);return str(path)
            app.work(work,os.startfile)
    row=app.row(info);app.button(row,'打开完整圈曲线',open_record,True,170)
    app.button(row,'收藏与标签',lambda:edit_note(app,state['selected'],refresh),False,135)
    app.button(row,'打开赛事目录',lambda:os.startfile(state['selected']['folder']) if state['selected'] else None,False,150)
    def training():
        from control_training import show
        show(app,state['selected'])
    def card():
        from control_achievement import show
        show(app,state['selected'])
    analysis_row=app.row(info)
    app.button(analysis_row,'训练优先级报告',training,False,170)
    app.button(analysis_row,'生成个人战绩卡',card,False,170)
    def comparable():
        from control_comparable import show
        show(app,state['selected'])
    app.button(analysis_row,'同条件进步分析',comparable,False,180)
    from control_training_goals import show as show_goals
    app.button(app.row(info),'训练目标跟进',lambda:show_goals(app),False,170)
    refresh()
