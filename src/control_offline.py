"""Small offline-only UI; all analysis actions still belong to shared pages."""
from tkinter import filedialog
from control_theme import T
from i18n import tr
from platform_runtime import open_path


def import_folder(app):
    from control_transfers import available
    if not available(app):return
    folder=filedialog.askdirectory(parent=app.root,title=tr('选择包含 session.json 的 Windows 赛事文件夹'))
    if not folder:return
    from session_import import import_folder as copy
    from control_batch import start
    start(app,'赛事文件夹导入任务',[folder],lambda source:copy(app.data_path,source),on_done=lambda _:app.refresh())


def preferences(app):
    body=app.card('离线分析工作区','导入 Windows 记录后，直接使用共享的分析、对比、报告与个人纪录功能。')
    app.label(body,'LMU 与 AC EVO 的赛事分别保存；切换左侧模拟器可查看对应资料库。',10,T.MUTED).pack(fill='x',pady=6)
    row=app.row(body)
    app.button(row,'导入赛事包',app.import_package,True,150)
    app.button(row,'导入 Windows 赛事文件夹',lambda:import_folder(app),False,230)
    body=app.card('本机数据目录','应用更新或替换不会改动资料库；原始数据按完整精度保留。')
    app.label(body,str(app.data_path),10,T.MUTED).pack(fill='x',pady=6)
    app.button(app.row(body),'打开数据目录',lambda:open_path(app.data_path),False,160)
    body=app.card('报告与可视化','HTML 报告可离线打开；圈速单与赛事日志由内置原生引擎生成。')
    app.label(body,'已导入的 Windows 报告图片保留；需要时可在赛事操作中重新生成。',10,T.MUTED).pack(fill='x',pady=6)
    app.button(app.row(body),'报告与存储',lambda:app.request_page(3),False,160)
