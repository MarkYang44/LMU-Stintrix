"""Recent video results: accessible without selecting or decoding a video."""
import os
from pathlib import Path
from datetime import datetime
from track_names import display
from control_maintenance import shell
from control_video_widgets import Action
from control_search import SearchField
from control_theme import T
from control_motion import keyboard_action
import tkinter as tk
from video_results import inventory,file_in
from i18n import tr


def show(app,root):
    old=getattr(app,'video_results_window',None)
    if old is not None and old.winfo_exists():old.deiconify();old.lift();old.refresh_results();return old
    window,footer,table,status=shell(app,'最近提取结果',[
        ('date','提取时间 / UTC',180),('video','视频文件',300),('track','赛道',180),('hz','实际原始 / Hz',110),('kind','可用报告',150)])
    window.minsize(760,500)
    app.video_results_window=window;state={'items':{},'generation':0,'selected':None,'remembered':(),'shown':0,'loading':False,'pending':False,'initialized':False,'error':None};buttons={}
    search=tk.StringVar(window);count=tk.StringVar(window)
    row=tk.Frame(table.master,bg=T.CARD);row.pack(fill='x',before=table)
    app.label(row,'搜索文件名或赛道',9,T.MUTED).pack(side='left',padx=(0,8))
    field=SearchField(row,textvariable=search,command=lambda:render());field.pack(side='left',fill='x',expand=True)
    app.label(table.master,count,9,T.MUTED).pack(fill='x',before=table,pady=(4,0))
    def selected():
        ids=table.selection();return state['items'].get(ids[0]) if len(ids)==1 else None
    def choose(_=None):
        if _ is not None:state['remembered']=table.selection()
        count.set(tr('显示 {shown}/{total} 项 · 已选 {selected} 项').format(shown=state['shown'],total=len(state['items']),selected=len(table.selection())))
        item=selected()
        for key,button in buttons.items():button.configure(state='normal' if item and (key in ('folder','history') or key in item['reports']) else 'disabled')
        if state['loading']:status.set(tr('正在读取最近结果…'));return
        if state['error'] is not None:status.set(tr('读取结果失败：{error}').format(error=state['error']));return
        if item:
            state['selected']=item['folder']
            q=item.get('quality',{});actual=q.get('actual_sample_hz');target=q.get('requested_sample_hz')
            reports=' / '.join(tr(label) for key,label in [('raw','原始报告'),('smooth','120 Hz 插值报告')] if key in item['reports'])
            text=tr('可用报告：{reports}').format(reports=reports)+' · '+tr('目标 / 实际原始频率')+': '+(f'{target:g} / {actual:.2f} Hz' if isinstance(target,(int,float)) and isinstance(actual,(int,float)) else tr('旧结果未记录频率'))
            if 'smooth' in item['reports']:text+='\n'+tr('120 Hz 为插值估算，不增加原始精度')
            status.set(text)
        elif table.selection():status.set(tr('已选择多项；打开报告、目录或历史对比时，请只选择一项。'))
        else:status.set(tr('请选择一个结果后打开报告'))
    def open_result(kind):
        item=selected()
        if item is None:return
        if kind=='auto':kind='raw' if 'raw' in item['reports'] else 'smooth'
        if kind not in ('folder','history') and kind not in item['reports']:return
        folder=Path(item['folder'])
        if kind=='history':
            file=file_in(folder,'curve.json',root)
            if file is None:status.set(tr('结果文件不存在或已移动'));return
            from control_video_history import show as history
            history(app,root,file);return
        file=file_in(folder,'curve.json' if kind=='folder' else 'report.html' if kind=='raw' else 'report_120hz.html',root)
        if file is None:status.set(tr('结果文件不存在或已移动'));return
        try:os.startfile(str(folder if kind=='folder' else file))
        except OSError as error:status.set(str(error))
    for kind,label in [('raw','打开原始报告'),('smooth','打开 120 Hz 报告'),('folder','打开结果目录'),('history','与历史圈对比')]:
        button=Action(footer,label,lambda k=kind:open_result(k),170,kind=='raw');button.pack(side='left',padx=(0,8));button.configure(state='disabled');buttons[kind]=button
    def render(*_):
        from track_names import search_text
        query=search.get().strip().casefold();offset=table.offset
        rows=[]
        for key,item in state['items'].items():
            track=item['identity'].get('track','')
            if query and query not in (item['video_file']+' '+search_text(track)).casefold():continue
            actual=item.get('quality',{}).get('actual_sample_hz');stamp=item.get('created_utc','')
            try:stamp=datetime.strptime(stamp,'%Y%m%dT%H%M%SZ').strftime('%Y-%m-%d %H:%M:%S')
            except (ValueError,TypeError):stamp=str(stamp)
            kind='原始 + 120 Hz 插值' if len(item['reports'])==2 else '120 Hz 插值报告' if 'smooth' in item['reports'] else '原始样本'
            rows.append((key,(stamp,item['video_file'],display(track),f'{actual:.2f}' if isinstance(actual,(int,float)) else '—',tr(kind))))
        ids={key for key,_ in rows};chosen=tuple(key for key in state['remembered'] if key in ids)
        if not state['initialized'] and rows:chosen=(rows[0][0],);state['remembered']=chosen
        state['shown']=len(rows);keyboard_action(table,lambda:table.replace(rows,chosen));table.scroller.move(offset);choose()
        if state['loading']:table.set_empty('正在读取最近结果…')
        elif state['error'] is not None:table.set_empty('读取失败，请刷新重试','刷新结果',refresh)
        elif not state['items']:table.set_empty('暂无提取结果；完成提取后会自动出现在这里。')
        elif search.get():table.set_empty('没有匹配的结果','清空搜索',field.clear)
        else:table.set_empty('没有匹配的结果')
        if not rows and not state['loading'] and state['error'] is None:status.set(tr('没有匹配的结果') if state['items'] else tr('暂无提取结果；完成提取后会自动出现在这里。'))
    def refresh():
        if state['loading']:state['pending']=True;return
        state['generation']+=1;generation=state['generation'];state['loading']=True;state['error']=None;status.set(tr('正在读取最近结果…'))
        refresh_button.configure(state='disabled')
        def done(items,error):
            if app.closing or not window.winfo_exists() or generation!=state['generation']:return
            state['loading']=False;state['error']=error
            refresh_button.configure(state='normal')
            if error is not None:choose()
            else:state['items']={item['folder']:item for item in items};render();state['initialized']=True
            if state['pending']:state['pending']=False;refresh()
        app.run_background(lambda:inventory(root),done)
    window.bind('<Control-f>',lambda _:(field.entry.focus_set(),'break')[1])
    window.bind('<F5>',lambda _:(refresh(),'break')[1])
    table.bind('<<TreeviewSelect>>',choose);table.bind('<Double-1>',lambda _:open_result('auto'));table.bind('<Return>',lambda _:open_result('auto'))
    refresh_button=Action(footer,'刷新结果',refresh,135);refresh_button.pack(side='right');window.bind('<Escape>',lambda _:window.destroy())
    from control_flow import install as flow
    flow(footer)
    def retranslate():
        for key,label in [('date','提取时间 / UTC'),('video','视频文件'),('track','赛道'),('hz','实际原始 / Hz'),('kind','可用报告')]:table.heading(key,text=label)
        for widget in footer.winfo_children():
            if hasattr(widget,'paint'):widget.paint()
        render()
    window.retranslate=retranslate
    def dispose(event):
        if event.widget is window:
            for variable in (search,count,status):variable.__del__();variable._tk=None
    window.bind('<Destroy>',dispose,add='+')
    window.results_search=search;window.results_search_field=field;window.refresh_results=refresh;window.results_state=state;window.results_table=table;window.results_buttons=buttons;window.results_count=count;window.results_status=status
    refresh();return window
