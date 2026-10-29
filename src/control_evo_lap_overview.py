"""Native lap inventory: no raw samples loaded for filtering or selection."""
import tkinter as tk
from pathlib import Path
from control_fields import Select
from control_flow import install
from control_maintenance import shell,offline_ready
from control_theme import T
from control_search import SearchField
from control_widgets import backdrop,px
from race_model import lap_status,lap_time
from evo_comparison import available
from i18n import tr


def show(app,folder):
    if app.closing:return
    if not offline_ready(app):app.status.set(tr('请先停止 HUD 并等待后台任务完成，再查看圈速总览。'));return
    root=Path(app.data_path).resolve();folder=Path(folder).resolve()
    from simulators import root_identity
    if root_identity(root)!='ac_evo' or not folder.is_relative_to(root):raise ValueError('只能选择当前 AC EVO 目录中的赛事')
    windows=getattr(app,'evo_lap_windows',{});app.evo_lap_windows=windows;identity=(root,folder)
    old=windows.get(identity)
    if old is not None and old.winfo_exists():old.deiconify();old.lift();old.lap_overview['refresh']();return old
    columns=[('lap','圈',65),('time','圈速',120),('delta','距最快',100),('status','状态',240),('samples','采样数',90)]
    window,footer,table,status=shell(app,'AC EVO · 圈速总览',columns)
    windows[identity]=window;window.minsize(800,600)
    body=table.master
    heading=app.label(body,'',11,T.ACCENT,True);heading.pack(fill='x',before=table,pady=4)
    facts=tk.StringVar(window);fact_label=app.label(body,facts,11,T.FG);fact_label.pack(fill='x',before=table,pady=8)
    fact_label.bind('<Configure>',lambda e:fact_label.configure(wraplength=max(80,e.width)))
    heading.bind('<Configure>',lambda e:heading.configure(wraplength=max(80,e.width)))
    row=app.row(body);row.pack(before=table,fill='x')
    query=tk.StringVar(window);kind=tk.StringVar(window,value='all')
    state=dict(result=None,loading=False,generation=0,rows={},runs={},usable_count=0,selection_key=None,selection_summary=None,message='正在读取圈速…')
    search=SearchField(row,query,command=lambda:populate(),placeholder='搜索圈号或状态');search.pack(side='left',fill='x',expand=True,padx=(0,10))
    kinds={'all':'全部圈','valid':'完整有效圈','other':'需要检查的圈'}
    selector=Select(row,textvariable=kind,values=list(kinds),labels={k:tr(v) for k,v in kinds.items()},width=19);selector.pack(side='left');selector.bind('<<ComboboxSelected>>',lambda _:populate())
    note=app.label(body,'双击有效圈或按 Enter 查看曲线；多选按 Enter 对比。仅统计完整有效圈；波动为标准差，未作条件校正。',9,T.MUTED);note.pack(fill='x',before=table,pady=4)
    note.bind('<Configure>',lambda e:note.configure(wraplength=max(80,e.width)))
    selection_text=tk.StringVar(window);selection_row=app.row(footer)
    selection_label=app.label(selection_row,selection_text,10,T.MUTED);selection_label.pack(side='left',fill='x',expand=True,pady=(8,4))
    selection_label.bind('<Configure>',lambda e:selection_label.configure(wraplength=max(80,e.width)))
    actions=app.row(footer);install(actions)
    buttons={}
    from control_evo_rhythm import Rhythm
    rhythm=Rhythm(app,body,row,table,lambda:not state['loading'])
    def say(message):state['message']=str(message);status.set(tr(str(message)))
    def selected():return [state['rows'][key] for key in table.selection() if key in state['rows']]
    def sync(*_):
        keys=[key for key in table.selection() if key in state['rows']];rows=[state['rows'][key] for key in keys]
        usable=bool(rows) and all(row['usable'] for row in rows) and not state['loading']
        key=tuple((key,state['rows'][key]['usable'],state['rows'][key]['lap']['time']) for key in keys)
        if key!=state['selection_key']:
            from evo_lap_overview import selection_summary
            state['selection_key']=key;state['selection_summary']=selection_summary(rows)
        s=state['selection_summary']
        if not s['total']:text=tr('选择圈记录，即时查看有效圈统计；未作条件校正。')
        elif not s['valid']:text=tr('已选 {total} 圈 · 可用 {valid} 圈；其余不计入统计。').format(**s)
        else:text=tr('已选 {total} / 可用 {valid} 圈 · 平均 {mean} · 最快 {fastest} · 最慢 {slowest} · 波动 {std}；未作条件校正。').format(**{**s,**{k:lap_time(s[k]) for k in ('mean','fastest','slowest')},'std':f"{s['std']:.3f} s" if s['std'] is not None else '—'})
        if selection_text.get()!=text:selection_text.set(text)
        selection_label.configure(fg=T.ACCENT if s['valid'] else T.MUTED)
        mixed=0<s['valid']<s['total']
        buttons['keep-usable'].configure(state='normal' if mixed and not state['loading'] else 'disabled')
        if mixed:
            if not buttons['keep-usable'].winfo_manager():buttons['keep-usable'].pack(side='right',before=selection_label,padx=(10,0))
        else:buttons['keep-usable'].pack_forget()
        buttons['csv'].configure(state='normal' if usable and len(rows)<=6 else 'disabled')
        buttons['timing'].configure(state='normal' if state['rows'] and not state['loading'] else 'disabled')
        buttons['compare'].configure(state='normal' if usable and 2<=len(rows)<=6 else 'disabled')
        buttons['curve'].configure(state='normal' if usable and len(rows)==1 else 'disabled')
        buttons['best-two'].configure(state='normal' if not state['loading'] and state['usable_count']>=2 else 'disabled')
        buttons['best-many'].configure(state='normal' if not state['loading'] and state['usable_count']>=3 else 'disabled')
        buttons['run'].configure(state='normal' if not state['loading'] and state['runs'] else 'disabled')
        buttons['refresh'].configure(state='disabled' if state['loading'] else 'normal')
        rhythm.button.configure(state='disabled' if state['loading'] else 'normal')
    def identities(limit=2):
        if not offline_ready(app):say('请先停止 HUD 并等待后台任务完成，再查看圈速总览。');return []
        rows=selected()
        return [(folder,row['lap']['num']) for row in rows] if 1<=len(rows)<=limit and all(row['usable'] for row in rows) else []
    def csv():
        values=identities(6)
        if values:
            from control_evo_exports import selected_csv
            selected_csv(app,root,values)
    def timing():
        if state['loading'] or not state['rows']:return
        if not offline_ready(app):say('请先停止 HUD 并等待后台任务完成，再导出圈速清单。');return
        from tkinter import filedialog
        snapshot=state['result'];indices=tuple(int(key) for key in table.order)
        destination=filedialog.askdirectory(parent=window,title=tr('导出圈速清单 · 当前筛选 {count} 圈').format(count=len(indices)))
        if not destination or app.closing or not window.winfo_exists():return
        if not offline_ready(app):say('请先停止 HUD 并等待后台任务完成，再导出圈速清单。');return
        from evo_lap_overview import timing_csv
        state['loading']=True;app.lap_curve_jobs=getattr(app,'lap_curve_jobs',0)+1;settled=False
        say(tr('正在导出当前筛选中的 {count} 圈清单…').format(count=len(indices)));sync()
        def done(result,error):
            nonlocal settled
            if settled:return
            settled=True;app.lap_curve_jobs=max(0,getattr(app,'lap_curve_jobs',0)-1)
            if app.closing or not window.winfo_exists():return
            state['loading']=False
            if error:say(error)
            else:say(tr('圈速清单已导出 {count} 行，不含整圈遥测：{path}').format(count=result['rows'],path=result['path']))
            sync()
        try:app.run_background(lambda:timing_csv(root,folder,destination,snapshot,indices),done)
        except Exception as error:done(None,error)
    def compare():
        values=identities(6)
        if len(values)==2:
            from control_lap_pair import show as pair
            pair(app,root,selected=values)
        elif 3<=len(values)<=6:prepare_view(values)
    def curve():
        values=identities(1)
        if len(values)!=1:return
        prepare_view(values)
    def activate(_=None):
        if state['loading']:return 'break'
        rows=selected()
        if len(rows)==1:curve()
        elif 2<=len(rows)<=6:compare()
        return 'break'
    def double(event):
        if state['loading']:return 'break'
        key=table.at(event)
        if key is not None:
            table.selection_set((key,));curve()
        return 'break'
    def prepare_view(values):
        source,number=values[0];single=len(values)==1;state['loading']=True;app.lap_curve_jobs=getattr(app,'lap_curve_jobs',0)+1
        say(tr('正在准备第 {number} 圈完整曲线…').format(number=number) if single else tr('正在准备 {count} 圈完整对比…').format(count=len(values)));sync()
        from evo_comparison import export_single,export_many
        settled=False
        def done(result,error):
            nonlocal settled
            if settled:return
            settled=True
            app.lap_curve_jobs=max(0,getattr(app,'lap_curve_jobs',0)-1)
            if app.closing or not window.winfo_exists():return
            state['loading']=False
            if error:say(error)
            else:
                import os
                try:
                    if len(values)>2:
                        from control_evo_compare import remember_multi
                        remember_multi(app,root,result['comparison'],len(values))
                    os.startfile(result['comparison'])
                    say(tr('第 {number} 圈完整曲线已打开；原始记录保留。').format(number=number) if single else tr('{count} 圈对比已打开；原始记录保留。').format(count=len(values)))
                except (OSError,ValueError) as issue:say(issue)
            sync()
        try:app.run_background(lambda:export_single(root,source,number) if single else export_many(root,values),done)
        except Exception as error:done(None,error)
    def best_two(count=2):
        choices=sorted((key for key,row in state['rows'].items() if row['usable']),key=lambda key:(state['rows'][key]['lap']['time'],int(key)))[:count]
        if len(choices)<2:return
        table.selection_set(choices);table.scroller.move(table.order.index(choices[0])*table.rowheight);table.viewport.focus_set();sync()
        say(tr('已选择当前筛选中最快的 {count} 圈').format(count=len(choices)))
    def select_run(count):
        if state['loading'] or app.closing:return
        run=state['runs'].get(count)
        if run is None:return
        if rhythm.visible:rhythm.set_view(False)
        table.selection_set(run['keys']);table.scroller.move(table.order.index(run['keys'][0])*table.rowheight);table.viewport.focus_set();sync()
        say(tr('已选择连续第 {first}–{last} 圈 · 平均 {mean}；未作条件校正。').format(**run,mean=lap_time(run['mean_s'])))
    def keep_usable():
        if state['loading'] or app.closing:return
        before=table.selection();keys=[key for key in before if key in state['rows'] and state['rows'][key]['usable']]
        if not keys or len(keys)==len(before):return
        table.selection_set(keys);sync()
        if not rhythm.visible:table.viewport.focus_set()
        say(tr('保留已选的 {kept} 圈，取消选中 {removed} 圈；原记录未修改。').format(kept=len(keys),removed=len(before)-len(keys)))
    buttons['keep-usable']=app.button(selection_row,'保留所选可用圈',keep_usable,False,155)
    buttons['keep-usable'].pack_forget()
    buttons['curve']=app.button(actions,'打开所选圈曲线',curve,True,190)
    buttons['csv']=app.button(actions,'导出所选圈 CSV',csv,False,175)
    buttons['timing']=app.button(actions,'导出圈速清单',timing,False,155)
    buttons['compare']=app.button(actions,'对比所选圈',compare,True,175)
    buttons['best-two']=app.button(actions,'选择最快两圈',best_two,False,155)
    buttons['best-many']=app.button(actions,'选择最快多圈',lambda:best_two(6),False,155)
    from control_action_menu import ActionMenu,MenuAction
    def open_runs():
        for action in run_menu.actions:
            run=state['runs'].get(int(action.key))
            action.hint=tr('第 {first}–{last} 圈 · 平均 {mean}').format(**run,mean=lap_time(run['mean_s'])) if run else tr('没有满足条件的连续完整有效圈')
        result=run_menu.toggle()
        if run_menu.popup:
            action=next((a for a in run_menu.actions if a.key==run_menu.active),None)
            if action:run_menu.footer.configure(text=action.hint)
        return result
    buttons['run']=app.button(actions,'连续圈段 ▾',open_runs,False,155)
    run_menu=ActionMenu(buttons['run'],[
        MenuAction(str(n),'选择最快连续 3 圈' if n==3 else '选择最快连续 5 圈',lambda n=n:select_run(n),
            enabled=lambda n=n:not state['loading'] and n in state['runs']) for n in (3,5)
    ],title='连续圈段',context=lambda:tr('当前筛选 · 未作条件校正'))
    buttons['refresh']=app.button(actions,'刷新圈速',lambda:refresh(),False,130)
    def action_widths():
        for button in buttons.values():button.configure(width=max(px(button,115),button.font.measure(tr(button.label))+px(button,36)))
        actions.event_generate('<Configure>',width=max(1,actions.winfo_width()))
    table.bind('<<TreeviewSelect>>',sync,add='+');table.copy_feedback=say
    table.viewport.bind('<Return>',activate);table.viewport.bind('<Double-1>',double)
    table.set_empty('没有符合筛选的圈记录')
    def sort_rows(key=None,reverse=None):
        if key is None:
            if table.sort_state is None:return
            key,reverse=table.sort_state
        elif reverse is None:reverse=table.sort_state==(key,False)
        def value(iid):
            row=state['rows'][iid];lap=row['lap']
            if key=='status':return table.rows[iid][3].casefold()
            if key=='delta':return lap['time']-state['result']['summary']['fastest'] if row['usable'] else None
            return lap[{'lap':'num','time':'time','samples':'samples'}[key]]
        known=[iid for iid in table.order if value(iid) is not None];unknown=[iid for iid in table.order if value(iid) is None]
        table.order=sorted(known,key=lambda iid:(value(iid),int(iid)),reverse=reverse)+unknown
        table.sort_state=(key,reverse);table.header_key=None;table.schedule()
    table.sort_command=lambda key:(sort_rows(key),table.scroller.move(0))
    def populate(selected_ids=None):
        if state['result'] is None:return
        run_menu.close(False)
        before=table.selection() if selected_ids is None else selected_ids;offset=table.offset;state['rows']={};state['usable_count']=0;rows=[]
        value=state['result']['index'];valid=available(value);words=query.get().strip().casefold().split();best=state['result']['summary']['fastest']
        for i,lap in enumerate(value['laps']):
            usable=valid.get(lap['num']) is lap;label=' / '.join(tr(v) for v in lap_status(lap).split(' / '))
            if not usable and lap['complete'] and not lap['partial'] and lap['valid'] is True and not lap['in_pits']:label+=' / '+tr('未满足导出条件')
            if kind.get()=='valid' and not usable or kind.get()=='other' and usable:continue
            if not all(word in (str(lap['num'])+' '+label).casefold() for word in words):continue
            delta=f"+{lap['time']-best:.3f} s" if usable and best is not None else '—'
            key=str(i);state['rows'][key]=dict(lap=lap,usable=usable)
            state['usable_count']+=bool(usable)
            rows.append((key,(lap['num'],lap_time(lap['time']),delta,label,lap['samples'])))
        table.replace(rows,selected=[key for key in before if key in state['rows']]);sort_rows();table.scroller.move(offset)
        from evo_lap_overview import fastest_runs
        state['runs']=fastest_runs(state['rows'])
        rhythm.set(state['rows'])
        say(tr('显示 {shown}/{total} 圈；单圈看曲线，2 圈进入 A/B，3–6 圈叠加；CSV 可一次导出 1–6 圈。').format(shown=len(state['rows']),total=len(value['laps'])));sync()
    def refresh():
        if state['loading'] or not offline_ready(app):return
        run_menu.close(False);state['loading']=True;state['generation']+=1;generation=state['generation'];say('正在读取圈速…');sync()
        from evo_lap_overview import load
        def done(result,error):
            if app.closing or not window.winfo_exists() or generation!=state['generation']:return
            state['loading']=False
            if error:
                # A failed refresh must not leave old lap actions usable.
                state['result']=None;state['rows']={};state['runs']={};state['usable_count']=0;rhythm.set({});facts.set('');table.delete(*table.get_children());say(error);sync();return
            def identity(lap):return tuple(lap.get(k) for k in ('num','first_index','end_index'))
            wanted={identity(row['lap']) for row in selected()}
            keep=[str(i) for i,lap in enumerate(result['index']['laps']) if identity(lap) in wanted]
            state['result']=result;meta=result['session'];s=result['summary']
            heading.configure(text=' · '.join(str(meta[k]) for k in ('track','track_layout','vehicle') if meta.get(k)))
            facts.set(tr('本场有效圈 {valid}/{total} · 最快 {fastest} · 中位数 {median} · 波动 {std}').format(**{**s,'fastest':lap_time(s['fastest']),'median':lap_time(s['median']),'std':f"{s['std']:.3f} s" if s['std'] is not None else '—'}));populate(selected_ids=keep)
        app.run_background(lambda:load(root,folder),done)
    def translate():
        run_menu.close(False)
        window.title(tr('AC EVO · 圈速总览'))
        action_widths();rhythm.sync_button()
        for key,label,_ in columns:table.heading(key,text=label)
        table.set_empty('没有符合筛选的圈记录')
        selector.labels={k:tr(v) for k,v in kinds.items()};selector.paint()
        if state['result']:
            s=state['result']['summary'];facts.set(tr('本场有效圈 {valid}/{total} · 最快 {fastest} · 中位数 {median} · 波动 {std}').format(**{**s,'fastest':lap_time(s['fastest']),'median':lap_time(s['median']),'std':f"{s['std']:.3f} s" if s['std'] is not None else '—'}));populate()
        else:
            if rhythm.visible:rhythm.render()
            status.set(tr(state['message']))
    def close():window.destroy()
    def dispose(event):
        if event.widget is window:windows.pop(identity,None);state['generation']+=1
    window.bind('<Destroy>',dispose,add='+');window.bind('<Escape>',lambda _:(close(),'break')[1]);window.protocol('WM_DELETE_WINDOW',close)
    window.bind('<Control-f>',lambda _:(search.focus_set(),'break')[1]);window.bind('<F5>',lambda _:(refresh(),'break')[1]);window.retranslate=translate
    window.lap_overview=dict(root=root,folder=folder,state=state,table=table,buttons=buttons,query=query,kind=kind,populate=populate,refresh=refresh,status=status,facts=facts,sort=sort_rows,activate=activate,double=double,rhythm=rhythm,run_menu=run_menu,select_run=select_run,selection_text=selection_text)
    action_widths();backdrop(window);refresh();return window
