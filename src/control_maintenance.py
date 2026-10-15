"""User-visible report retries and safe, opt-in cache maintenance."""
import os,tkinter as tk
from pathlib import Path
from tkinter import messagebox
from control_theme import T
from control_list import SessionList
from record_presentation import number
from i18n import tr

def shell(app,title,columns):
    window=tk.Toplevel(app.root);window.title(tr(title));window.geometry('1050x650');window.configure(bg=T.BG)
    footer=tk.Frame(window,bg=T.CARD);footer.pack(side='bottom',fill='x',padx=18,pady=(0,18))
    body=tk.Frame(window,bg=T.CARD);body.pack(fill='both',expand=True,padx=18,pady=18)
    app.label(body,title,18,T.FG,True).pack(anchor='w',pady=10)
    table=SessionList(body,columns=[k for k,_,_ in columns],height=8,selectmode='extended')
    for key,label,width in columns:table.heading(key,text=label);table.column(key,width=width,minwidth=70,stretch=True)
    table.pack(fill='both',expand=True,pady=8);text=tk.StringVar(window);label=app.label(body,text,10);label.pack(fill='x',pady=10);label.bind('<Configure>',lambda e:label.configure(wraplength=max(100,e.width)))
    return window,footer,table,text

def reports(app):
    from report_state import current,LABELS
    from race_model import read_json
    window,body,table,text=shell(app,'报告任务与分步重试',[('date','时间（UTC）',170),('track','赛道',170),('state','报告状态',110),('steps','未完成步骤',260)])
    state={'items':[],'busy':False}
    labels=dict(ready='已完成',partial='部分失败',error='失败',deferred='等待内存',queued='等待处理',building='正在生成',incomplete='未完成')
    def refresh():
        def work():
            out=[]
            from session_groups import superseded
            hidden=superseded(app.data_path)
            for category in ('Logs','ImportedLogs','RecoveredLogs'):
                for path in (app.data_path/category).glob('*/session.json'):
                    if not path.resolve().is_relative_to(app.data_path.resolve()) or path.parent.resolve() in hidden:continue
                    meta=read_json(path,{})
                    if meta.get('status') in ('recording','write_error'):continue
                    receipt=current(path.parent);out.append(dict(folder=str(path.parent),meta=meta,receipt=receipt))
            return sorted(out,key=lambda e:e['meta'].get('started_utc',''),reverse=True)
        def done(value,error):
            if not window.winfo_exists():return
            if error:text.set(error);return
            state['items']=value;table.replace([(str(i),(e['meta'].get('started_utc','')[:19],e['meta'].get('track',''),tr(labels.get(e['receipt']['state'],'等待处理')),' / '.join(tr(LABELS[k]) for k,v in e['receipt']['steps'].items() if v.get('state')!='ready'))) for i,e in enumerate(value)],());text.set(tr('成功步骤会保留，只重试失败项及受影响的步骤；旧报告错误信息仍留存。'))
        app.run_background(work,done)
    def retry():
        if state['busy']:return
        selected=[state['items'][int(i)] for i in table.selection()]
        if not selected:return
        if app.active() or app.tasks.busy:text.set(tr('请先停止 HUD 并等待分析任务结束，再重试报告'));return
        state['busy']=True;text.set(tr('正在重试未完成步骤…'))
        def work():
            from report_worker import run,defer,ReportDeferred
            out=[]
            for e in selected:
                try:run(e['folder'],app.data_path)
                except ReportDeferred as error:defer(e['folder'],error)
                out.append((e['folder'],current(e['folder'])))
            return out
        def done(value,error):
            state['busy']=False
            if not window.winfo_exists():return
            if error:text.set(error);return
            refresh()
        app.run_background(work,done)
    actions=app.row(body);app.button(actions,'重试未完成步骤',retry,True,180);app.button(actions,'刷新任务',refresh,False,135)
    refresh();return window

def caches(app):
    from cache_management import inventory,clear
    window,body,table,text=shell(app,'缓存与导出文件',[('name','内容',220),('size','占用 / MiB',120),('files','文件数',90),('kind','处理方式',210)])
    state={'items':{}}
    def refresh():
        def done(value,error):
            if not window.winfo_exists():return
            if error:text.set(error);return
            state['items']={v['key']:v for v in value};table.replace([(v['key'],(tr(v['name']),f"{v['bytes']/1048576:.2f}",v['files'],tr('可清理，按需重建') if v['clearable'] else tr('保留，不在此处删除'))) for v in value],());text.set(tr('只清理可重建缓存；赛事、用户图片、训练目标、标签和常用视图均保留。'))
        app.run_background(lambda:inventory(app.data_path),done)
    def clean():
        keys=list(table.selection())
        if not keys:return
        if app.active() or app.tasks.busy:text.set(tr('请先停止 HUD 并等待分析任务结束，再清理缓存'));return
        if any(not state['items'][k]['clearable'] for k in keys):text.set(tr('只能清理明确标为可重建的缓存'));return
        total=sum(state['items'][k]['bytes'] for k in keys)
        if not messagebox.askyesno(tr('清理所选缓存'),tr('仅删除可重建缓存，原始赛事与导出文件保留。')+f'\n{total/1048576:.2f} MiB',parent=window):return
        def done(value,error):
            if window.winfo_exists():text.set(error or tr('缓存已清理'));refresh()
        app.run_background(lambda:clear(app.data_path,keys),done)
    def open_folder():
        ids=table.selection()
        if ids:
            path=Path(state['items'][ids[0]]['path']);path=path if path.is_dir() else path.parent
            if path.is_dir():os.startfile(str(path))
    actions=app.row(body);app.button(actions,'清理所选缓存',clean,False,155);app.button(actions,'打开目录',open_folder,False,125);app.button(actions,'刷新占用',refresh,False,125)
    refresh();return window
