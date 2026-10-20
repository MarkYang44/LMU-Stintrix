"""Recent video results: accessible without selecting or decoding a video."""
import os
from pathlib import Path
from datetime import datetime
from track_names import display
from control_maintenance import shell
from control_video_widgets import Action
from control_fields import Field
from control_theme import T
import tkinter as tk
from video_results import inventory,file_in
from i18n import tr


def show(app,root):
    old=getattr(app,'video_results_window',None)
    if old is not None and old.winfo_exists():old.lift();return old
    window,footer,table,status=shell(app,'最近提取结果',[
        ('date','提取时间 / UTC',180),('video','视频文件',300),('track','赛道',180),('hz','实际原始 / Hz',110),('kind','可用报告',150)])
    app.video_results_window=window;state={'items':{},'generation':0,'selected':None,'shown':0};buttons={}
    search=tk.StringVar(window)
    row=tk.Frame(table.master,bg=T.CARD);row.pack(fill='x',before=table)
    field=Field(row,textvariable=search);field.pack(side='left',fill='x',expand=True)
    Action(row,'清空搜索',lambda:search.set(''),120).pack(side='right',padx=(8,0))
    app.label(row,'搜索文件名或赛道',9,T.MUTED).pack(side='right',padx=8)
    def selected():
        ids=table.selection();return state['items'].get(ids[0]) if ids else None
    def choose(_=None):
        item=selected()
        for key,button in buttons.items():button.configure(state='normal' if item and (key=='folder' or key in item['reports']) else 'disabled')
        if item:
            state['selected']=item['folder']
            q=item.get('quality',{});actual=q.get('actual_sample_hz');target=q.get('requested_sample_hz')
            status.set(tr('目标 / 实际原始频率')+': '+(f'{target:g} / {actual:.2f} Hz' if isinstance(target,(int,float)) and isinstance(actual,(int,float)) else tr('旧结果未记录频率'))+' · '+tr('120 Hz 为插值估算，不增加原始精度')+f" · {state['shown']} / {len(state['items'])}")
    def open_result(kind):
        item=selected()
        if item is None:return
        folder=Path(item['folder'])
        file=file_in(folder,'curve.json' if kind=='folder' else 'report.html' if kind=='raw' else 'report_120hz.html',root)
        if file is None:status.set(tr('结果文件不存在或已移动'));return
        try:os.startfile(str(folder if kind=='folder' else file))
        except OSError as error:status.set(str(error))
    for kind,label in [('raw','打开原始报告'),('smooth','打开 120 Hz 报告'),('folder','打开结果目录')]:
        button=Action(footer,label,lambda k=kind:open_result(k),170);button.pack(side='left',padx=(0,8));button.configure(state='disabled');buttons[kind]=button
    def render(*_):
        from track_names import search_text
        query=search.get().strip().casefold();previous=state['selected'];offset=table.offset
        rows=[]
        for key,item in state['items'].items():
            track=item['identity'].get('track','')
            if query and query not in (item['video_file']+' '+search_text(track)).casefold():continue
            actual=item.get('quality',{}).get('actual_sample_hz');stamp=item.get('created_utc','')
            try:stamp=datetime.strptime(stamp,'%Y%m%dT%H%M%SZ').strftime('%Y-%m-%d %H:%M:%S')
            except (ValueError,TypeError):stamp=str(stamp)
            rows.append((key,(stamp,item['video_file'],display(track),f'{actual:.2f}' if isinstance(actual,(int,float)) else '—',tr('原始 + 120 Hz 插值') if 'smooth' in item['reports'] else tr('原始样本'))))
        ids={key for key,_ in rows};chosen=(previous,) if previous in ids else (rows[0][0],) if rows else ()
        state['shown']=len(rows);table.replace(rows,chosen);table.scroller.move(offset);choose()
        if not rows:status.set(tr('没有匹配的结果') if state['items'] else tr('暂无提取结果；完成提取后会自动出现在这里。'))
    def refresh():
        state['generation']+=1;generation=state['generation'];status.set(tr('正在读取最近结果…'))
        def done(items,error):
            if app.closing or not window.winfo_exists() or generation!=state['generation']:return
            if error:status.set(error);return
            state['items']={item['folder']:item for item in items};render()
        app.run_background(lambda:inventory(root),done)
    search.trace_add('write',render)
    def clear_search(_):search.set('');return 'break'
    field.entry.bind('<Escape>',clear_search);window.bind('<Control-f>',lambda _:field.entry.focus_set())
    table.bind('<<TreeviewSelect>>',choose);table.bind('<Double-1>',lambda _:open_result('raw'));table.bind('<Return>',lambda _:open_result('raw'))
    Action(footer,'刷新结果',refresh,135).pack(side='right');window.bind('<Escape>',lambda _:window.destroy())
    def retranslate():
        for key,label in [('date','提取时间 / UTC'),('video','视频文件'),('track','赛道'),('hz','实际原始 / Hz'),('kind','可用报告')]:table.heading(key,text=label)
        for widget in footer.winfo_children():
            if hasattr(widget,'paint'):widget.paint()
        render()
    window.retranslate=retranslate
    window.results_search=search;window.refresh_results=refresh;window.results_state=state;window.results_table=table;window.results_buttons=buttons
    refresh();return window
