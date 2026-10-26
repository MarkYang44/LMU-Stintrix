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
from track_names import display,layout_label
from control_video_widgets import Action
from laps import finished_metadata
from lap_identity import same_layout
from control_search import SearchField
from track_names import search_text


def show(app,root,initial=()):
    root=Path(root).resolve()
    existing=getattr(app,'lap_pair_window',None)
    if existing is not None and existing.winfo_exists():
        existing.lift();existing.focus_force()
        if initial:existing.pair_controls['select_initial'](initial)
        return existing
    window=panel(app,'Stintrix · 圈 A / 圈 B',1000,710);window.minsize(860,680);app.lap_pair_window=window
    state={'events':{},'laps':{'A':{},'B':{}},'rows':{'A':{},'B':{}},'headers':{},'generation':{'A':0,'B':0},'loading':set(),'busy':False,'reason':False,'result':None,'message':'正在读取赛事…','initial':tuple(initial),'inventory_ready':False}
    quick={}
    status=tk.StringVar(window,value=tr('正在读取赛事…'));events={};numbers={};lap_boxes={};event_boxes={}
    footer=tk.Frame(window,bg=T.BG);footer.pack(side='bottom',fill='x',padx=20,pady=(4,14))
    def say(message):state['message']=str(message);status.set(tr(str(message)))
    intro=Label(window,text='先选择赛道，再选择圈 A 和圈 B 的赛事及有效圈；支持跨车型，同布局。',bg=T.BG,fg=T.FG,wraplength=940,justify='left');intro.pack(fill='x',padx=20,pady=16)
    intro.bind('<Configure>',lambda e:intro.configure(wraplength=max(100,e.width)))
    query=tk.StringVar(window);matches=tk.StringVar(window);track=tk.StringVar(window)
    search_row=tk.Frame(window,bg=T.BG);search_row.pack(fill='x',padx=20)
    Label(search_row,text='赛道',bg=T.BG,fg=T.MUTED).pack(side='left',padx=(0,10))
    track_box=Select(search_row,textvariable=track,values=[],state='disabled',width=29);track_box.pack(side='left',padx=(0,10))
    search=SearchField(search_row,query,placeholder='在当前赛道搜索日期、车型或赛事');search.pack(side='left',fill='x',expand=True)
    Label(window,textvariable=matches,bg=T.BG,fg=T.MUTED,anchor='w').pack(fill='x',padx=20,pady=(4,0))
    def filter_events(*_):
        words=query.get().strip().casefold().split()
        scoped=[(label,event) for label,event in state['events'].items() if circuit_key(event)==track.get() and track.get()]
        values=[label for label,event in scoped if all(word in (label+' '+search_text(event.get('track',''))+' '+search_text(event.get('track_layout',''))).casefold() for word in words)]
        for box in event_boxes.values():box.configure(values=values)
        matches.set(tr('匹配 {shown}/{total} 场 · 筛选不改变已选赛事').format(shown=len(values),total=len(scoped)) if track.get() else tr('先选择赛道；仅在选择赛事后读取有效圈'))
    def circuit_key(event):return str(event.get('track','')).strip().casefold()
    def event_labels(values):
        result={}
        for event in values:
            if event['status'] in ('recording','write_error'):continue
            layout=event.get('track_layout') or event['track'];length=event.get('track_length_m')
            circuit=display(event['track'])+(' / '+layout_label(event['track'],layout) if layout!=event['track'] else '')+(f' / {length:.0f} m' if isinstance(length,(int,float)) else '')
            result[f"{event['date'][:19]} · {event['session_type']} · {circuit} · {event['vehicle']} · {event['key']}"]=event
        return result
    def track_choices():
        labels={};counts={}
        for event in state['events'].values():
            key=circuit_key(event)
            if key:labels.setdefault(key,event['track']);counts[key]=counts.get(key,0)+1
        shown={key:display(value) for key,value in labels.items()}
        track_box.labels={'':'请选择赛道',**{key:(name+(' / '+labels[key] if list(shown.values()).count(name)>1 else '')+f' · {counts[key]}') for key,name in shown.items()}}
        track_box.configure(values=['',*sorted(labels,key=lambda k:shown[k].casefold())]);track_box.paint()
    def choose_track(_=None):
        if state['busy']:return
        for key in ('A','B'):
            state['generation'][key]+=1;state['loading'].discard(key);state['laps'][key]={};state['rows'][key]={};state['headers'].pop(key,None)
            events[key].set('');numbers[key].set('');lap_boxes[key].configure(values=[])
        filter_events();say('请选择圈 A 和圈 B 的赛事；仅扫描所选记录' if track.get() else '先选择赛道；仅在选择赛事后读取有效圈');refresh()
    track_box.bind('<<ComboboxSelected>>',choose_track)
    def lap_labels(rows):
        return {f"{tr('第 ')}{v['number']}{tr(' 圈')} · {int(v['time_s']//60)}:{v['time_s']%60:06.3f}":v['number'] for v in rows}
    query_trace=query.trace_add('write',filter_events)
    window.bind('<Control-f>',lambda _:(search.entry.focus_set(),'break')[1])
    def refresh():
        ready=state['inventory_ready'] and not state['busy'] and not state['loading'] and all(numbers[k].get() in state['laps'][k] for k in ('A','B'))
        reason=''
        if ready:
            keys=[(events[k].get(),state['laps'][k][numbers[k].get()]) for k in ('A','B')]
            if keys[0]==keys[1]:reason='圈 A 和圈 B 必须选择不同圈'
            elif not same_layout(*[dict(session=state['headers'][k],lap=state['rows'][k][keys[i][1]]) for i,k in enumerate(('A','B'))]):reason='请选择同一赛道、同一布局的两圈；缺少可靠长度时无法确认布局'
        if reason:say(reason)
        elif state['reason']:say('两圈身份兼容，可以生成对比')
        state['reason']=bool(reason);ready=ready and not reason
        button.configure(state='normal' if ready else 'disabled')
        reopen.configure(state='normal' if state['result'] and not state['busy'] else 'disabled')
        for key in ('A','B'):
            event_boxes[key].configure(state='disabled' if state['busy'] or not state['inventory_ready'] or not track.get() else 'readonly')
            lap_boxes[key].configure(state='disabled' if state['busy'] or key in state['loading'] or not state['laps'][key] else 'readonly')
        for key,action in quick.items():action.configure(state='normal' if state['inventory_ready'] and not state['busy'] and not state['loading'] and (all(events[k].get() for k in ('A','B')) if key=='swap' else state['laps'][key]) else 'disabled')
        track_box.configure(state='disabled' if state['busy'] or not state['inventory_ready'] else 'readonly')
        feedback.busy('scan',bool(state['loading']) or state['busy'])
    def scan(key):
        if state['busy']:return
        label=events[key].get();event=state['events'].get(label)
        if event is None or circuit_key(event)!=track.get():return
        state['generation'][key]+=1;generation=state['generation'][key]
        state['laps'][key]={};state['rows'][key]={};numbers[key].set('');lap_boxes[key].configure(state='disabled')
        state['loading'].add(key);say('后台扫描有效完整圈…');refresh()
        def done(result,error):
            if app.closing or not window.winfo_exists() or generation!=state['generation'][key]:return
            state['loading'].discard(key)
            if error:say(error)
            else:
                state['headers'][key]=result['session'];state['rows'][key]={v['number']:v for v in result['laps']}
                values=lap_labels(result['laps'])
                state['laps'][key]=values;lap_boxes[key].configure(values=list(values),state='readonly')
                if values:numbers[key].set(next(iter(values)))
                say('仅显示已验证的有效完整圈；排除无效圈、进站圈与未验证旧圈。')
                if not values:say('这场赛事没有已验证的有效完整圈')
                a=state['events'].get(events['A'].get())
                if key=='B' and a and a['folder']==event['folder'] and len(values)>1:numbers['B'].set(list(values)[1])
            refresh()
        app.run_background(lambda:dict(laps=valid_laps(event['folder']),session=finished_metadata(event['folder'])),done)
    for key in ('A','B'):
        area=tk.Frame(window,bg=T.CARD);area.pack(fill='x',padx=20,pady=7)
        Label(area,text='圈 '+key,bg=T.CARD,fg=T.ACCENT,font=(T.FONT,13,'bold')).pack(anchor='w',padx=12,pady=6)
        events[key]=tk.StringVar(window);numbers[key]=tk.StringVar(window)
        event_boxes[key]=Select(area,textvariable=events[key],values=[],state='disabled')
        event_boxes[key].pack(fill='x',padx=12,pady=5)
        event_boxes[key].bind('<<ComboboxSelected>>',lambda _,k=key:scan(k))
        lap_boxes[key]=Select(area,textvariable=numbers[key],values=[],state='disabled')
        lap_boxes[key].pack(fill='x',padx=12,pady=(5,12));lap_boxes[key].bind('<<ComboboxSelected>>',lambda _:refresh())
    actions=tk.Frame(window,bg=T.BG);actions.pack(fill='x',padx=20,pady=6)
    def fastest(key):
        if state['busy'] or state['loading'] or not state['rows'][key]:return
        number=min(state['rows'][key].values(),key=lambda v:v['time_s'])['number'];numbers[key].set(next(label for label,n in state['laps'][key].items() if n==number));refresh()
    def swap():
        if state['busy'] or state['loading']:return
        a,b=events['A'].get(),events['B'].get();na,nb=numbers['A'].get(),numbers['B'].get()
        events['A'].set(b);events['B'].set(a);numbers['A'].set(nb);numbers['B'].set(na)
        for name in ('laps','rows','headers'):state[name]['A'],state[name]['B']=state[name].get('B',{}),state[name].get('A',{})
        for key in ('A','B'):lap_boxes[key].configure(values=list(state['laps'][key]))
        refresh()
    for key,label,command in [('A','A：最快有效圈',lambda:fastest('A')),('B','B：最快有效圈',lambda:fastest('B')),('swap','交换 A / B',swap)]:
        quick[key]=Action(actions,label,command,180);quick[key].pack(side='left',padx=(0,8))
    from control_flow import install
    install(actions)
    def compare():
        refresh()
        if not button.enabled:return
        selections=[(state['events'][events[k].get()]['folder'],state['laps'][k][numbers[k].get()]) for k in ('A','B')]
        state['busy']=True;refresh();say('后台生成所选两圈对比；完成前锁定赛事与圈号。')
        def done(result,error):
            if app.closing or not window.winfo_exists():return
            state['busy']=False
            say(error or '对比已生成，原始记录保留')
            if not error:
                state['result']=str(result['comparison']);open_last()
            refresh()
        app.run_background(lambda:export_pair(root,selections,ASSETS/'compare.html'),done)
    def open_last():
        path=state['result']
        if not path:return
        if not Path(path).is_file():say('上次对比文件已移动或删除，请重新生成。');return
        try:os.startfile(path)
        except OSError as error:say(error)
    bottom_actions=tk.Frame(footer,bg=T.BG);bottom_actions.pack(fill='x')
    button=Action(bottom_actions,'提取两圈并对比',compare,200,True);button.configure(state='disabled');button.pack(side='left')
    reopen=Action(bottom_actions,'打开上次对比',open_last,160);reopen.configure(state='disabled');reopen.pack(side='left')
    install(bottom_actions)
    feedback=StatusFeedback(footer,status);feedback.pack(fill='x',pady=(6,0));feedback.busy('inventory')
    def select_initial(paths):
        if state['busy']:say('当前对比正在生成，请完成后再切换赛事。');return False
        state['initial']=tuple(Path(path).resolve() for path in paths[:2])
        if not state['inventory_ready']:return True
        if any(not any(Path(event['folder']).resolve()==path for event in state['events'].values()) for path in state['initial']):
            state['inventory_ready']=False;feedback.busy('inventory');say('正在更新赛事清单…');refresh()
            app.run_background(lambda:inventory(root),loaded);return True
        first=next((event for event in state['events'].values() if state['initial'] and Path(event['folder']).resolve()==state['initial'][0]),None)
        if first is not None and track.get()!=circuit_key(first):track.set(circuit_key(first));choose_track()
        changed=False
        for index,key in enumerate(('A','B')):
            if index>=len(state['initial']):break
            label=next((label for label,event in state['events'].items() if Path(event['folder']).resolve()==state['initial'][index]),None)
            if label is None:continue
            if circuit_key(state['events'][label])!=track.get():say('已按圈 A 的赛道筛选，请重新选择圈 B 的赛事');continue
            if events[key].get()!=label:events[key].set(label);scan(key);changed=True
        filter_events();refresh()
        return changed
    def loaded(result,error):
        if app.closing or not window.winfo_exists():return
        feedback.busy('inventory',False)
        if error:state['inventory_ready']=bool(state['events']);say(error);refresh();return
        values=event_labels(result)
        state['events']=values;state['inventory_ready']=True
        track_choices()
        if track.get() and track.get() not in track_box.values:track.set('');choose_track()
        filter_events()
        available=tuple(path for path in state['initial'] if any(Path(event['folder']).resolve()==Path(path).resolve() for event in values.values()))
        missing=len(available)!=len(state['initial'])
        if available:select_initial(available)
        elif not track.get():say('先选择赛道；仅在选择赛事后读取有效圈')
        if not values:say('尚无已完成的赛事记录')
        elif missing:say('所选赛事当前不可用，已保留其他选择。')
        refresh()
    app.run_background(lambda:inventory(root),loaded)
    def dispose(event):
        if event.widget is window:
            query.trace_remove('write',query_trace)
            for variable in (query,matches,status,track,*events.values(),*numbers.values()):variable.__del__();variable._tk=None
    window.bind('<Destroy>',dispose,add='+')
    def translate():
        selected={key:state['events'].get(events[key].get(),{}).get('folder') for key in ('A','B')}
        state['events']=event_labels(list(state['events'].values()))
        for key,folder in selected.items():events[key].set(next((label for label,value in state['events'].items() if value['folder']==folder),''))
        track_choices()
        filter_events()
        status.set(tr(state['message']))
        for key in ('A','B'):
            chosen=state['laps'][key].get(numbers[key].get());values=lap_labels(state['rows'][key].values());state['laps'][key]=values
            lap_boxes[key].configure(values=list(values));numbers[key].set(next((label for label,number in values.items() if number==chosen),''))
        from control_widgets import px
        for action in [button,reopen,*quick.values()]:action.configure(width=max(px(action,160),action.font.measure(tr(action.label))+px(action,36)));action.paint()
        for row in (actions,bottom_actions):row.event_generate('<Configure>',width=row.winfo_width())
        refresh()
    window.retranslate=translate
    window.pair_controls=dict(events=events,numbers=numbers,state=state,quick=quick,refresh=refresh,scan=scan,compare=button,status=status,query=query,search=search,matches=matches,event_boxes=event_boxes,lap_boxes=lap_boxes,select_initial=select_initial,reopen=reopen,footer=footer,track=track,track_box=track_box,choose_track=choose_track)
    return window
