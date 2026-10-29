"""EVO CSV actions reuse the shared batch UI and keep capture mutually exclusive."""
from pathlib import Path
from tkinter import filedialog
from i18n import tr


def fastest_csv(app,items):
    if app.closing or not items:return
    folders=list(dict.fromkeys(str(Path(item['folder']).resolve()) for item in items))
    return _start(app,folders)


def selected_csv(app,root,selections):
    if app.closing or not selections:return
    if Path(root).resolve()!=Path(app.data_path).resolve():raise ValueError('只能导出当前游戏的赛事记录')
    if len(selections)>6 or any(type(n) is not int or n<1 for _,n in selections):raise ValueError('请选择有效圈号')
    values=list(dict.fromkeys((str(Path(folder).resolve()),number) for folder,number in selections))
    if len(values)!=len(selections):raise ValueError('请选择不同的有效圈')
    return _start(app,values,selected=True)


def _start(app,values,selected=False):
    from control_transfers import available
    from control_maintenance import offline_ready
    if not available(app):return
    if not offline_ready(app):app.status.set(tr('请先停止 HUD 并等待后台任务完成，再导出圈 CSV。'));return
    root=Path(app.data_path).resolve()
    destination=filedialog.askdirectory(parent=app.root,title=tr('选择圈 CSV 导出目录'))
    if app.closing or not destination:return
    if not offline_ready(app):app.status.set(tr('请先停止 HUD 并等待后台任务完成，再导出圈 CSV。'));return
    from evo_exports import fastest_csv,lap_csv,Inventory
    inventory=Inventory()
    from control_batch import start
    def done(_):
        inventory.clear()
        if not app.closing:app.status.set(tr('圈 CSV 导出任务已结束；结果可在任务窗口查看。'))
    operation=(lambda pair:lap_csv(root,pair[0],destination,number=pair[1],_inventory=inventory)) if selected else (lambda folder:fastest_csv(root,folder,destination,_inventory=inventory))
    names=[f"{chr(65+i)} · {Path(folder).name} · #{number}" for i,(folder,number) in enumerate(values)] if selected else None
    job=start(app,'所选有效圈 CSV 导出' if selected else '最快有效圈 CSV 导出',values,operation,names=names,destination=destination,on_done=done)
    job.blocks_capture=True
    return job
