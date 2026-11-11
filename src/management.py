"""Focused Tk windows, shared by the existing HUD. Local operations only."""
from platform_runtime import open_path
from i18n import tr,Label
import json
from json_store import load as load_json
import os
from pathlib import Path
import tkinter as tk
from control_fields import Select,Field
from control_theme import T
from tkinter import ttk,messagebox,filedialog
from library import inventory,save_note
from reference import ReferenceLap,DistanceAligner
from storage import atomic_json,recover_session,compress_session
from sessionlab import analyze_session
from laps import write_compare,complete_laps,export_selected_laps,finished_metadata
from paths import ASSETS
from track_names import display as track_name,search_text as track_search
from control_motion import fade_in


def panel(app,title,width,height):
    from control_window import fit
    window=tk.Toplevel(app.root);fade_in(window);window.title(tr(title))
    window.configure(bg=T.BG);window.attributes('-topmost',True);fit(window,width,height,owner=app.root)
    style=ttk.Style(window);style.theme_use('clam')
    style.configure('Scope.Treeview',background=T.CARD,foreground=T.FG,fieldbackground=T.CARD,rowheight=29)
    style.configure('Scope.Treeview.Heading',background=T.FIELD,foreground=T.MUTED)
    style.map('Scope.Treeview',background=[('selected',T.SELECT)])
    return window


def show_diagnostics(app,root):
    from control_window import window as sheet,fit,Facts,card,note
    from control_widgets import px
    window=sheet(app.root,'Stintrix · 性能诊断','采样、绘制与写盘的实时节奏，每 0.5 秒刷新；只读，不影响记录。',topmost=True,transient=False)
    body=window.body;gap=px(window,10)
    tiles=tk.Frame(body,bg=T.BG);tiles.pack(fill='x');rates={}
    for column,(key,label) in enumerate((('poll','实际轮询'),('fresh','共享内存新帧'),('draw','实际绘制'))):
        outer,inner=card(tiles,14);outer.grid(row=0,column=column,sticky='nsew',padx=(0 if column==0 else gap,0));tiles.columnconfigure(column,weight=1,uniform='rate')
        Label(inner,text=label,bg=T.CARD,fg=T.MUTED,font=(T.FONT,9),anchor='w').pack(fill='x')
        value=tk.Label(inner,text='—',bg=T.CARD,fg=T.FG,font=(T.MONO,17,'bold'),anchor='w');value.pack(fill='x',pady=(px(window,3),0))
        detail=tk.Label(inner,text='',bg=T.CARD,fg=T.MUTED,font=(T.FONT,9),anchor='w');detail.pack(fill='x');rates[key]=(value,detail)
    outer,table=card(body,16);outer.pack(fill='x',pady=(gap,0))
    for column,text in enumerate(('最近 5 秒','P50 ms','P95 ms','P99 ms')):
        Label(table,text=text,bg=T.CARD,fg=T.MUTED,font=(T.FONT,9),anchor='w' if column==0 else 'e').grid(row=0,column=column,sticky='ew',pady=(0,px(window,4)))
        table.columnconfigure(column,weight=3 if column==0 else 1,uniform='latency' if column else None)
    latency={}
    for row,(key,name) in enumerate([('read','共享内存读取'),('draw','绘制回调至 idle'),('interval','绘制间隔'),('latency','读入→首次绘制')],1):
        Label(table,text=name,bg=T.CARD,fg=T.FG,font=(T.FONT,10),anchor='w').grid(row=row,column=0,sticky='ew',pady=px(window,3))
        latency[key]=[tk.Label(table,text='—',bg=T.CARD,fg=T.FG,font=(T.MONO,10),anchor='e') for _ in range(3)]
        for column,cell in enumerate(latency[key],1):cell.grid(row=row,column=column,sticky='ew',pady=px(window,3))
    outer,inner=card(body,16);outer.pack(fill='x',pady=(gap,0))
    facts=Facts(inner,[('stutters','累计长帧'),('missed','绘制错过周期'),('writer','写盘队列 / 峰值'),('alignment','参考对齐 / 可信度'),('unknown','参考条件未知')]);facts.pack(fill='x')
    for text in ('延迟仅测插件读入至 Tk idle，不含方向盘、游戏或屏幕扫描。','读取耗时只包含真实共享内存；DEMO 的该项为空。','GPU 渲染尚未替换：先用实赛基准识别瓶颈。'):
        note(body,text).pack(fill='x',pady=(px(window,8) if text.startswith('延迟') else 0,0))
    snapshot={}
    def collect():
        nonlocal snapshot
        poll,fresh=app.engine.actual_rates();snapshot=app.engine.diagnostics.snapshot()
        batch=app.engine.recorder.batch
        snapshot.update(poll_hz=poll,fresh_hz=fresh,draw_hz=app.actual_draw_rate(),sampling_target=app.engine.target_hz,
            drawing_target=app.drawing_target(),missed_poll_cycles=app.engine.missed_cycles,
            missed_draw_cycles=app.render_clock.missed_cycles,writer_queue=batch.queue.qsize() if batch else 0,
            writer_peak=batch.peak if batch else 0,alignment=app.engine.reference_state,recording_error=getattr(app.engine,'recording_failure',None))
        return snapshot
    def display():
        if not window.winfo_exists() or app.closing:return
        s=collect();fmt=lambda v:'—' if v is None else f'{v:.3f}'
        rates['poll'][0].configure(text=f"{s['poll_hz']:.1f} Hz");rates['poll'][1].configure(text=tr('目标')+f" {s['sampling_target']} Hz")
        rates['fresh'][0].configure(text=f"{s['fresh_hz']:.1f} Hz");rates['fresh'][1].configure(text=tr('占轮询')+f" {s['fresh_hz']/s['poll_hz']:.0%}" if s['poll_hz'] else '—')
        rates['draw'][0].configure(text=f"{s['draw_hz']:.1f} Hz");rates['draw'][1].configure(text=tr('目标')+f" {s['drawing_target']} Hz")
        for key,cells in latency.items():
            d=s[key]
            for cell,name in zip(cells,('p50_ms','p95_ms','p99_ms')):cell.configure(text=fmt(d[name]))
        a=s['alignment']
        facts.set('stutters',str(s['stutters']),translate=False);facts.set('missed',str(s['missed_draw_cycles']),translate=False)
        facts.set('writer',f"{s['writer_queue']} / {s['writer_peak']} "+tr('行'),translate=False)
        facts.set('alignment',f"{tr(a.get('mode','关闭'))} / {a.get('confidence',0):.0%}",translate=False)
        facts.set('unknown',' / '.join(tr({'fuel_l':'燃油','tyre_compound':'胎种','track_temp_c':'赛道温度','wetness':'湿度','tc_level':'TC','abs_level':'ABS'}[k]) for k in a.get('conditions',{}).get('unknown',[])) or '—',translate=False)
        window.after(500,display)
    def export():
        path=Path(root)/'Diagnostics'/'latest.json';path.parent.mkdir(exist_ok=True)
        atomic_json(path,collect());window.status.set(tr('诊断已导出：')+str(path));folder_button.configure(state='normal')
    window.add_action('导出诊断 JSON',export,True,150)
    folder_button=window.add_action('打开所在目录',lambda:open_path(str(Path(root)/'Diagnostics')),False,130);folder_button.configure(state='disabled')
    window.add_action('关闭',window.destroy,False,90)
    display();fit(window,700);return window


def show_library(app,root,render_review,make_report,initial=()):
    from control_library import show
    return show(app,root,render_review,make_report,initial)


def show_lap_selection(app,root,folder):
    root=Path(root).resolve();folder=Path(folder).resolve()
    if not folder.is_relative_to(root):raise ValueError('只能选择本插件目录中的比赛记录')
    dialogs=getattr(app,'lap_selection_windows',None)
    if dialogs is None:dialogs=app.lap_selection_windows={}
    existing=dialogs.get(str(folder))
    if existing is not None and existing.winfo_exists():existing.lift();existing.focus_force();return existing
    from control_window import window as sheet,fit,card,note
    from control_widgets import px
    from control_video_widgets import Action
    window=sheet(app.root,'Stintrix · 同场完整圈对比','正在读取这场赛事的完整圈…',topmost=True,transient=False,feedback=True);dialogs[str(folder)]=window
    status=window.status;status.set(tr('后台扫描完整圈…'));state={'busy':False,'laps':{},'output':None}
    vars={};boxes={};buttons={}
    outer,inner=card(window.body,16);outer.pack(fill='x');inner.columnconfigure(1,weight=1)
    for row,key in enumerate(('A','B')):
        Label(inner,text='圈 '+key,bg=T.CARD,fg=T.ACCENT,font=(T.FONT,11,'bold'),anchor='w').grid(row=row,column=0,sticky='w',padx=(0,px(window,14)),pady=px(window,5))
        vars[key]=tk.StringVar(window)
        boxes[key]=Select(inner,textvariable=vars[key],state='disabled',height=12,placeholder='等待读取完整圈')
        boxes[key].grid(row=row,column=1,sticky='ew',pady=px(window,5))
        buttons[key]=Action(inner,'提取此圈',lambda k=key:export([k]),104);buttons[key].grid(row=row,column=2,sticky='e',padx=(px(window,10),0),pady=px(window,5))
    note(window.body,'仅列出起终点、采样和距离完整的圈。无效 / 进站标记会保留；此类圈可查看数据，但不生成驾驶改进建议，也不能用作 HUD 参考。').pack(fill='x',pady=(px(window,12),0))
    note(window.body,tr('记录目录：')+folder.name,8).pack(fill='x',pady=(px(window,6),0))
    def enable(*_):
        ready=not state['busy'] and bool(state['laps'])
        for k in ('A','B'):
            boxes[k].configure(state='readonly' if ready else 'disabled')
            buttons[k].configure(state='normal' if ready and vars[k].get() in state['laps'] else 'disabled')
        pair=ready and all(vars[k].get() in state['laps'] for k in ('A','B')) and vars['A'].get()!=vars['B'].get()
        buttons['compare'].configure(state='normal' if pair else 'disabled')
        buttons['folder'].configure(state='normal' if state['output'] else 'disabled')
    def background(work,done):
        if state['busy']:return
        state['busy']=True;status.set(tr('后台处理中…'));window.footer.feedback.busy('work');enable()
        def finish(result,error):
            if app.closing or not window.winfo_exists():return
            state['busy']=False;window.footer.feedback.busy('work',False)
            if error:status.set(error)
            else:
                try:done(result)
                except OSError as e:status.set(tr('文件已生成，打开失败：') + str(e))
            enable()
        app.run_background(work,finish)
    def selected(keys):
        try:return [state['laps'][vars[k].get()]['number'] for k in keys]
        except KeyError:raise ValueError('请先选择完整圈') from None
    def export(keys,compare=False):
        try:numbers=selected(keys)
        except ValueError as e:status.set(tr(str(e)));return
        if len(set(numbers))!=len(numbers):status.set(tr('圈 A 和圈 B 必须选择不同圈'));return
        def done(result):
            state['output']=result['folder'];status.set(tr('已提取第 ') + ' / '.join(map(str, numbers)) + tr(' 圈；JSON 与完整 CSV 保存到：\n') + result['folder'])
            if result['comparison']:open_path(result['comparison'])
        background(lambda:export_selected_laps(folder,numbers,ASSETS/'compare.html' if compare else None),done)
    buttons['compare']=window.add_action('提取两圈并对比',lambda:export(['A','B'],True),True,150)
    buttons['folder']=window.add_action('打开提取目录',lambda:open_path(state['output']),False,130)
    for button in buttons.values():button.configure(state='disabled')
    for box in boxes.values():box.bind('<<ComboboxSelected>>',enable)
    def loaded(result):
        metadata,scan=result;window.header.set(subtitle=' · '.join(v for v in (track_name(metadata.get('track','')),metadata.get('vehicle','')) if v))
        labels=[]
        for v in scan['laps']:
            minutes=int(v['time_s']//60);seconds=v['time_s']-minutes*60
            flags=[]
            if v.get('lap_invalidated'):flags.append(tr('无效标记'))
            if v.get('in_pits'):flags.append(tr('进站标记'))
            if not flags:flags.append(tr('有效性已记录' if v['validity']=='verified' else '有效性未验证'))
            label=f"{tr('第 ')}{v['number']}{tr(' 圈  ·  ')}{minutes}:{seconds:06.3f}  ·  "+' / '.join(flags)
            state['laps'][label]=v;labels.append(label)
        for box in boxes.values():box['values']=labels;box.placeholder='选择完整圈' if labels else '没有完整圈'
        if labels:vars['A'].set(labels[0])
        if len(labels)>1:vars['B'].set(labels[1])
        status.set(f"{tr('找到 ')}{len(labels)}{tr(' 个完整圈，排除 ')}{len(scan['candidates']) - len(labels)}{tr(' 个不完整或圈号不明确的记录。')}" + (tr('请选择圈 A／圈 B，再提取或对比。') if len(labels) > 1 else tr('两圈对比需要至少两个完整圈。')) + (' ' + scan['error'] if scan['error'] else ''))
    window.lap_controls=dict(vars=vars,boxes=boxes,buttons=buttons,state=state)
    background(lambda:(finished_metadata(folder),complete_laps(folder)),loaded);fit(window,700);return window
