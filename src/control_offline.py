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


def choose_icon(app,game):
    title=tr('选择 LMU 图标' if game=='lmu' else '选择 AC EVO 图标')
    path=filedialog.askopenfilename(parent=app.root,title=title,filetypes=[(tr('图片'),'*.png *.ico *.icns *.jpg *.jpeg *.webp *.bmp')])
    if not path:return
    from simulator_icons import import_icon
    try:import_icon(game,path)
    except ValueError as error:
        from tkinter import messagebox
        app.status.set(tr('操作未完成：')+tr(str(error)));__import__('control_confirm').notice(app.root,'操作未完成',str(error));return
    from control_simulator import refresh_icons
    refresh_icons(app);app.status.set(tr('已更新游戏图标'))


def reset_icons(app):
    from simulator_icons import reset_icon
    for game in ('lmu','ac_evo'):reset_icon(game)
    from control_simulator import refresh_icons
    refresh_icons(app);app.status.set(tr('已恢复默认游戏图标'))


def preferences(app):
    body=app.card('离线分析工作区','导入 Windows 记录后，直接使用共享的分析、对比、报告与个人纪录功能。')
    app.label(body,'LMU 与 AC EVO 的赛事分别保存；切换左侧模拟器可查看对应资料库。',10,T.MUTED).pack(fill='x',pady=6)
    row=app.row(body)
    app.button(row,'导入赛事包',app.import_package,True,150)
    app.button(row,'导入 Windows 赛事文件夹',lambda:import_folder(app),False,230)
    body=app.card('游戏图标','Mac 不安装游戏，程序也不分发游戏图片；可以选择你自己的图标文件。')
    app.label(body,'例如从 Windows 游戏目录复制的 evo.ico；图标只保存在本机资料库。',10,T.MUTED).pack(fill='x',pady=6)
    row=app.row(body)
    app.button(row,'选择 LMU 图标',lambda:choose_icon(app,'lmu'),False,150)
    app.button(row,'选择 AC EVO 图标',lambda:choose_icon(app,'ac_evo'),False,170)
    app.button(row,'恢复默认图标',lambda:reset_icons(app),False,150)
    body=app.card('本机数据目录','应用更新或替换不会改动资料库；原始数据按完整精度保留。')
    app.label(body,str(app.data_path),10,T.MUTED).pack(fill='x',pady=6)
    app.button(app.row(body),'打开数据目录',lambda:open_path(app.data_path),False,160)
    body=app.card('报告与可视化','HTML 报告可离线打开；圈速单与赛事日志由内置原生引擎生成。')
    app.label(body,'已导入的 Windows 报告图片保留；需要时可在赛事操作中重新生成。',10,T.MUTED).pack(fill='x',pady=6)
    app.button(app.row(body),'报告与存储',lambda:app.request_page(3),False,160)
    from control_app_preferences import build as app_preferences
    app_preferences(app)
