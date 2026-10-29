"""Report recovery UI; the existing worker still owns step and backup semantics."""
from pathlib import Path
import os
from control_worklist import WorkList,existing
from report_state import current,LABELS,STEPS
from race_model import read_json
from track_names import display,search_text
from i18n import tr

STATES=dict(ready='已完成',partial='部分失败',error='失败',deferred='等待处理条件',queued='等待处理',building='正在生成',incomplete='未完成',pending='等待处理',blocked='受前序步骤影响')


def readable(receipt,simulator='lmu'):
    from simulator_profiles import profile
    if not isinstance(receipt,dict):return False
    try:expected=profile(simulator).reports.steps
    except ValueError:return False
    steps=receipt.get('steps')
    return isinstance(steps,dict) and all(isinstance(steps.get(name),dict) for name in expected)


def details(item):
    receipt=item['receipt'];lines=[Path(item['folder']).name]
    if receipt.get('reason'):lines.append(tr(str(receipt['reason'])))
    simulator=item.get('meta',{}).get('simulator_id','lmu')
    if not readable(receipt,simulator):return '\n'.join(lines)
    from simulator_profiles import profile
    order=sorted(profile(simulator).reports.steps,key=lambda name:receipt.get('steps',{}).get(name,{}).get('state')=='ready')
    for name in order:
        step=receipt.get('steps',{}).get(name,{})
        lines.append(tr(LABELS[name])+' · '+tr(STATES.get(step.get('state'),'未完成')))
        if step.get('error'):lines.append(str(step['error']))
    return '\n'.join(lines)


def entries(root):
    from session_groups import superseded
    root=Path(root).resolve();hidden=superseded(root);out=[]
    for category in ('Logs','ImportedLogs','RecoveredLogs'):
        for path in (root/category).glob('*/session.json'):
            folder=path.parent.resolve()
            if not path.resolve().is_relative_to(root) or not folder.is_relative_to(root) or folder in hidden:continue
            meta=read_json(path,{})
            if not isinstance(meta,dict) or meta.get('status') in ('recording','write_error'):continue
            from simulators import accepts
            if not accepts(root,meta):continue
            receipt=current(folder);invalid=not readable(receipt,meta.get('simulator_id','lmu'))
            if invalid:receipt=dict(state='error',steps={},reason='报告状态格式无法读取，请打开记录目录检查；原文件已保留。')
            out.append(dict(folder=str(folder),meta=meta,receipt=receipt,read_error=invalid,review_exists=(folder/'review.html').is_file()))
    return sorted(out,key=lambda item:str(item['meta'].get('started_utc','')),reverse=True)


def show(app,initial=()):
    old=existing(app,'report_tasks_window')
    if old:
        if initial:old.report_focus.locate(initial)
        return old
    def row(item):
        meta=item['meta'];receipt=item['receipt']
        return (str(meta.get('started_utc',''))[:19],display(meta.get('track','')),meta.get('vehicle',''),tr(STATES.get(receipt.get('state'),'未完成')),' / '.join(tr(LABELS[k]) for k,v in receipt.get('steps',{}).items() if k in LABELS and v.get('state')!='ready'))
    view=WorkList(app,'报告任务与分步重试',[('date','时间（UTC）',170),('track','赛道',160),('car','车型',180),('state','报告状态',100),('steps','未完成步骤',240)],lambda item:item['folder'],row,filters=dict(pending='未完成报告',all='全部报告'),accept=lambda item,value:value=='all' or item['receipt'].get('state')!='ready',detail=details,hint='搜索赛道、车型或状态；选择待完成报告重试，成功步骤保留。需先停止 HUD。',searchable=lambda item:search_text(item['meta'].get('track','')))
    window=view.window;app.report_tasks_window=window
    from control_report_focus import Focus
    window.report_focus=Focus(view)
    def idle():
        from control_maintenance import offline_ready
        return offline_ready(app)
    def refresh(notice='成功步骤会保留，只重试失败项及受影响的步骤；旧报告错误信息仍留存。'):
        view.load(lambda:entries(app.data_path),notice)
    def retry():
        targets=[item for item in view.selected_items() if item['receipt'].get('state')!='ready' and not item.get('read_error')]
        if not targets:return
        def operation(item):
            from report_worker import run,defer,ReportDeferred
            folder=Path(item['folder']).resolve()
            if not folder.is_relative_to(Path(app.data_path).resolve()):raise ValueError('记录目录不可用或已移动')
            meta=read_json(folder/'session.json',{})
            from simulators import accepts
            if not isinstance(meta,dict) or not accepts(app.data_path,meta):raise ValueError('只能重试当前游戏的赛事报告')
            if meta.get('status') in ('recording','write_error'):raise ValueError('记录尚未完成，不能重试报告')
            receipt=current(folder)
            if not readable(receipt,meta.get('simulator_id','lmu')):raise ValueError('报告状态格式无法读取，请打开记录目录检查；原文件已保留。')
            if receipt.get('state')=='ready':return dict(folder=str(folder),path=str(folder),skipped=True)
            try:run(folder,app.data_path)
            except ReportDeferred as error:defer(folder,error)
            receipt=current(folder)
            return dict(folder=str(folder),path=str(folder),errors=[] if receipt.get('state')=='ready' else [details(dict(folder=str(folder),meta=meta,receipt=receipt))])
        def done(value):
            if view.alive():refresh('重试已结束；未完成项保留在任务清单中，可查看详情或继续重试。')
        from control_batch import start
        app.report_retry_job=start(app,'报告分步重试任务',targets,operation,names=[display(item['meta'].get('track',''))+' · '+str(item['meta'].get('started_utc',''))[:19] for item in targets],on_done=done,result_actions=True)
        view.say('重试在批量任务窗口中进行；可逐项查看结果、继续或重试失败项。');view.sync()
    def copy():view.table.copy_text('\n\n'.join(details(item) for item in view.selected_items()));view.say('已复制报告步骤详情')
    def open_report():
        item=view.selected_items()[0];path=Path(item['folder'])/'review.html'
        try:
            if not path.resolve().is_relative_to(Path(app.data_path).resolve()) or not path.is_file():raise ValueError('结果文件不存在或已移动')
            os.startfile(str(path))
        except (OSError,ValueError) as error:view.say(str(error))
    def open_folder():
        folder=Path(view.selected_items()[0]['folder'])
        try:
            if not folder.resolve().is_relative_to(Path(app.data_path).resolve()) or not folder.is_dir():raise ValueError('记录目录不可用或已移动')
            os.startfile(str(folder))
        except (OSError,ValueError) as error:view.say(str(error))
    def progress():
        from control_batch import show
        app.batch_job=app.report_retry_job;show(app)
    view.action('retry','重试选中未完成报告',retry,210,True,lambda:idle() and any(item['receipt'].get('state')!='ready' and not item.get('read_error') for item in view.selected_items()))
    view.action('copy','复制步骤详情',copy,160,enabled=lambda:bool(view.selected_items()))
    view.action('open','打开赛事复盘',open_report,160,enabled=lambda:len(view.selected_items())==1 and view.selected_items()[0].get('review_exists',False))
    view.action('folder','打开记录目录',open_folder,165,enabled=lambda:len(view.selected_items())==1)
    view.action('progress','查看重试进度',progress,170,enabled=lambda:getattr(app,'report_retry_job',None) is not None and app.report_retry_job.window.winfo_exists())
    view.action('refresh','刷新任务',refresh,135,enabled=lambda:not getattr(getattr(app,'report_retry_job',None),'busy',False))
    window.bind('<F5>',lambda _:view.buttons['refresh'].invoke());refresh()
    if initial:window.report_focus.locate(initial)
    return window
