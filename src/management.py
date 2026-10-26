"""Focused Tk windows, shared by the existing HUD. Local operations only."""
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


def panel(app,title,width,height):
    window=tk.Toplevel(app.root);window.title(tr(title));window.geometry(f'{width}x{height}')
    window.configure(bg=T.BG);window.attributes('-topmost',True)
    style=ttk.Style(window);style.theme_use('clam')
    style.configure('Scope.Treeview',background=T.CARD,foreground=T.FG,fieldbackground=T.CARD,rowheight=29)
    style.configure('Scope.Treeview.Heading',background=T.FIELD,foreground=T.MUTED)
    style.map('Scope.Treeview',background=[('selected',T.SELECT)])
    return window


def show_diagnostics(app,root):
    window=panel(app,'Stintrix · 性能诊断',680,465)
    label=Label(window,bg=T.BG,fg=T.FG,justify='left',anchor='nw',font=('Consolas',11));label.pack(fill='both',expand=True,padx=20,pady=18)
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
        rows=[f"轮询目标 {s['sampling_target']} / 绘制目标 {s['drawing_target']} Hz",
              f"实际轮询 {s['poll_hz']:.1f} / 新数据 {s['fresh_hz']:.1f} / 绘制 {s['draw_hz']:.1f} Hz",'',
              '最近 5 秒                 P50 ms    P95 ms    P99 ms']
        for key,name in [('read','共享内存读取'),('draw','绘制回调至 idle'),('interval','绘制间隔'),('latency','读入→首次绘制')]:
            d=s[key];rows.append(f"{name:<15} {fmt(d['p50_ms']):>9} {fmt(d['p95_ms']):>9} {fmt(d['p99_ms']):>9}")
        a=s['alignment'];rows.extend(['',f"累计长帧 {s['stutters']} / 绘制错过周期 {s['missed_draw_cycles']}",
            f"写盘队列 {s['writer_queue']} / 峰值 {s['writer_peak']} 行",
            f"参考对齐 {a.get('mode','关闭')} / 可信度 {a.get('confidence',0):.0%}",
            '参考条件未知：'+(' / '.join({'fuel_l':'燃油','tyre_compound':'胎种','track_temp_c':'赛道温度','wetness':'湿度','tc_level':'TC','abs_level':'ABS'}[k] for k in a.get('conditions',{}).get('unknown',[])) or '—'),
            '','延迟仅测插件读入至 Tk idle，不含方向盘、游戏或屏幕扫描。',
            '读取耗时只包含真实共享内存；DEMO 的该项为空。','GPU 渲染尚未替换：先用实赛基准识别瓶颈。'])
        label.config(text='\n'.join(rows));window.after(500,display)
    def export():
        path=Path(root)/'Diagnostics'/'latest.json';path.parent.mkdir(exist_ok=True)
        atomic_json(path,collect());messagebox.showinfo(tr('诊断已导出'),str(path),parent=window)
    tk.Button(window,text=tr('导出当前诊断 JSON'),command=export).pack(pady=10);display();return window


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
    window=panel(app,'Stintrix · 同场完整圈对比',720,395);dialogs[str(folder)]=window
    title=Label(window,text=folder.name,bg=T.BG,fg='#dce9fb',font=('Segoe UI',11),wraplength=670,justify='left',anchor='w')
    title.pack(fill='x',padx=18,pady=(15,10))
    status=tk.StringVar(window,value=tr('后台扫描完整圈…'));state={'busy':False,'laps':{},'output':None}
    vars={};boxes={}
    for key in ('A','B'):
        row=tk.Frame(window,bg=T.BG);row.pack(fill='x',padx=18,pady=6)
        Label(row,text='圈 '+key,bg=T.BG,fg='#c6def5',font=('Segoe UI',11),width=6,anchor='w').pack(side='left')
        vars[key]=tk.StringVar(window)
        boxes[key]=Select(row,textvariable=vars[key],state='disabled',font=('Segoe UI',11),height=12)
        boxes[key].pack(side='left',fill='x',expand=True)
    Label(window,text='仅列出起终点、采样和距离完整的圈。无效 / 进站标记会保留；\n此类圈可查看数据，但不生成驾驶改进建议，也不能用作 HUD 参考。',
        bg=T.BG,fg='#91abc8',justify='left',anchor='w',wraplength=670).pack(fill='x',padx=18,pady=12)
    actions=tk.Frame(window,bg=T.BG);actions.pack(fill='x',padx=18,pady=6);buttons={}
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
        state['busy']=True;status.set(tr('后台处理中…'));enable()
        def finish(result,error):
            if app.closing or not window.winfo_exists():return
            state['busy']=False
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
        except ValueError as e:status.set(str(e));return
        if len(set(numbers))!=len(numbers):status.set(tr('圈 A 和圈 B 必须选择不同圈'));return
        def done(result):
            state['output']=result['folder'];status.set(tr('已提取第 ') + ' / '.join(map(str, numbers)) + tr(' 圈；JSON 与完整 CSV 保存到：\n') + result['folder'])
            if result['comparison']:os.startfile(result['comparison'])
        background(lambda:export_selected_laps(folder,numbers,ASSETS/'compare.html' if compare else None),done)
    for key,text,command in [('A','提取圈 A',lambda:export(['A'])),('B','提取圈 B',lambda:export(['B'])),
            ('compare','提取两圈并对比',lambda:export(['A','B'],True)),('folder','打开提取目录',lambda:os.startfile(state['output']))]:
        buttons[key]=tk.Button(actions,text=tr(text),command=command,state='disabled');buttons[key].pack(side='left',padx=(0,9),pady=5)
    Label(window,textvariable=status,bg=T.BG,fg='#9dc7e9',anchor='nw',justify='left',wraplength=670).pack(fill='both',expand=True,padx=18,pady=12)
    for box in boxes.values():box.bind('<<ComboboxSelected>>',enable)
    def loaded(result):
        metadata,scan=result;title.config(text=track_name(metadata.get('track', '')) + ' · ' + metadata.get('vehicle', '') + '\n' + folder.name)
        labels=[]
        for v in scan['laps']:
            minutes=int(v['time_s']//60);seconds=v['time_s']-minutes*60
            flags=[]
            if v.get('lap_invalidated'):flags.append(tr('无效标记'))
            if v.get('in_pits'):flags.append(tr('进站标记'))
            if not flags:flags.append(tr('有效性已记录' if v['validity']=='verified' else '有效性未验证'))
            label=f"{tr('第 ')}{v['number']}{tr(' 圈  ·  ')}{minutes}:{seconds:06.3f}  ·  "+' / '.join(flags)
            state['laps'][label]=v;labels.append(label)
        for box in boxes.values():box['values']=labels
        if labels:vars['A'].set(labels[0])
        if len(labels)>1:vars['B'].set(labels[1])
        status.set(f"{tr('找到 ')}{len(labels)}{tr(' 个完整圈，排除 ')}{len(scan['candidates']) - len(labels)}{tr(' 个不完整或圈号不明确的记录。')}" + (tr('请选择圈 A／圈 B，再提取或对比。') if len(labels) > 1 else tr('两圈对比需要至少两个完整圈。')) + (' ' + scan['error'] if scan['error'] else ''))
    background(lambda:(finished_metadata(folder),complete_laps(folder)),loaded);return window
