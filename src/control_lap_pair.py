"""Independent event and verified-lap selectors; scan only chosen sessions."""
import os
import tkinter as tk
from pathlib import Path
from i18n import tr,Label
from control_fields import Select
from control_theme import T
from library import inventory
from lap_comparison import valid_laps,export_pair
from management import panel
from paths import ASSETS
from control_feedback import StatusFeedback
from track_names import display


def show(app,root,initial=()):
    root=Path(root).resolve()
    existing=getattr(app,'lap_pair_window',None)
    if existing is not None and existing.winfo_exists():
        existing.lift();existing.focus_force();return existing
    window=panel(app,'Stintrix · 圈 A / 圈 B',1000,530);app.lap_pair_window=window
    state={'events':{},'laps':{'A':{},'B':{}},'generation':{'A':0,'B':0},'loading':set(),'busy':False}
    status=tk.StringVar(window,value=tr('正在读取赛事…'));events={};numbers={};lap_boxes={};event_boxes={}
    Label(window,text='分别选择圈 A 和圈 B 的赛事及有效圈；支持跨车型，同赛道同布局。',bg=T.BG,fg=T.FG,
          wraplength=940,justify='left').pack(fill='x',padx=20,pady=16)
    def refresh():
        ready=not state['busy'] and not state['loading'] and all(numbers[k].get() in state['laps'][k] for k in ('A','B'))
        button.configure(state='normal' if ready else 'disabled')
        feedback.busy('scan',bool(state['loading']) or state['busy'])
    def scan(key):
        label=events[key].get();event=state['events'].get(label)
        if event is None:return
        state['generation'][key]+=1;generation=state['generation'][key]
        state['laps'][key]={};numbers[key].set('');lap_boxes[key].configure(state='disabled')
        state['loading'].add(key);status.set(tr('后台扫描有效完整圈…'));refresh()
        def done(result,error):
            if app.closing or not window.winfo_exists() or generation!=state['generation'][key]:return
            state['loading'].discard(key)
            if error:status.set(error)
            else:
                values={f"{tr('第 ')}{v['number']}{tr(' 圈')} · {int(v['time_s']//60)}:{v['time_s']%60:06.3f}":v['number'] for v in result}
                state['laps'][key]=values;lap_boxes[key].configure(values=list(values),state='readonly')
                if values:numbers[key].set(next(iter(values)))
                status.set(tr('仅显示已验证的有效完整圈；排除无效圈、进站圈与未验证旧圈。'))
                if not values:status.set(tr('这场赛事没有已验证的有效完整圈'))
                if key=='B' and events['A'].get()==label and len(values)>1:numbers['B'].set(list(values)[1])
            refresh()
        app.run_background(lambda:valid_laps(event['folder']),done)
    for key in ('A','B'):
        area=tk.Frame(window,bg=T.CARD);area.pack(fill='x',padx=20,pady=7)
        Label(area,text='圈 '+key,bg=T.CARD,fg=T.ACCENT,font=(T.FONT,13,'bold')).pack(anchor='w',padx=12,pady=6)
        events[key]=tk.StringVar(window);numbers[key]=tk.StringVar(window)
        event_boxes[key]=Select(area,textvariable=events[key],values=[],state='disabled')
        event_boxes[key].pack(fill='x',padx=12,pady=5)
        event_boxes[key].bind('<<ComboboxSelected>>',lambda _,k=key:scan(k))
        lap_boxes[key]=Select(area,textvariable=numbers[key],values=[],state='disabled')
        lap_boxes[key].pack(fill='x',padx=12,pady=(5,12));lap_boxes[key].bind('<<ComboboxSelected>>',lambda _:refresh())
    def compare():
        selections=[(state['events'][events[k].get()]['folder'],state['laps'][k][numbers[k].get()]) for k in ('A','B')]
        state['busy']=True;refresh();status.set(tr('后台处理中…'))
        for box in event_boxes.values():box.configure(state='disabled')
        def done(result,error):
            if app.closing or not window.winfo_exists():return
            state['busy']=False
            for box in event_boxes.values():box.configure(state='readonly')
            status.set(error or tr('对比已生成，原始记录保留'))
            if not error:
                try:os.startfile(result['comparison'])
                except OSError as e:status.set(str(e))
            refresh()
        app.run_background(lambda:export_pair(root,selections,ASSETS/'compare.html'),done)
    button=tk.Button(window,text=tr('提取两圈并对比'),command=compare,state='disabled',bg=T.ACCENT,fg=T.BG)
    button.pack(anchor='w',padx=20,pady=12)
    feedback=StatusFeedback(window,status);feedback.pack(fill='x',padx=20);feedback.busy('inventory')
    def loaded(result,error):
        if app.closing or not window.winfo_exists():return
        feedback.busy('inventory',False)
        if error:status.set(error);return
        values={}
        for event in result:
            if event['status'] in ('recording','write_error'):continue
            layout=event.get('track_layout') or event['track'];length=event.get('track_length_m')
            circuit=display(event['track'])+(' / '+display(layout) if layout!=event['track'] else '')+(f' / {length:.0f} m' if isinstance(length,(int,float)) else '')
            label=f"{event['date'][:19]} · {event['session_type']} · {circuit} · {event['vehicle']} · {event['key']}"
            values[label]=event
        state['events']=values
        for index,key in enumerate(('A','B')):
            event_boxes[key].configure(values=list(values),state='readonly')
            chosen=next((label for label,event in values.items() if index<len(initial) and Path(event['folder'])==initial[index]),next(iter(values),''))
            events[key].set(chosen)
            if chosen:scan(key)
        if not values:status.set(tr('尚无已完成的赛事记录'))
    app.run_background(lambda:inventory(root),loaded)
    return window
