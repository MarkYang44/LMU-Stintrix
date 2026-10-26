"""Explicit cache actions; originals stay under the backend's read-only allowlist."""
from pathlib import Path
import os
from control_worklist import WorkList,existing
from cache_management import inventory,clear
from i18n import tr


def show(app):
    old=existing(app,'cache_panel_window')
    if old:return old
    def row(item):return (tr(item['name']),f"{item['bytes']/1048576:.2f}",item['files'],tr('可清理，按需重建') if item['clearable'] else tr('保留，不在此处删除'))
    def detail(item):return tr(item['name'])+'\n'+item['path']+'\n'+tr('所选内容：{files} 个文件，{size} MiB').format(files=item['files'],size=f"{item['bytes']/1048576:.2f}")
    view=WorkList(app,'缓存与导出文件',[('name','内容',220),('size','占用 / MiB',120),('files','文件数',90),('kind','处理方式',220)],lambda item:item['key'],row,filters=dict(all='全部内容',clearable='仅可重建缓存'),accept=lambda item,mode:mode=='all' or item['clearable'],detail=detail,hint='搜索名称或处理方式；仅有占用的可重建缓存可清理。清理前需停止 HUD 并等待任务结束。原始赛事与用户导出文件保留。')
    window=view.window;app.cache_panel_window=window
    def idle():
        from control_maintenance import offline_ready
        return offline_ready(app)
    def refresh(notice='只清理可重建缓存；赛事、用户图片、训练目标、标签和常用视图均保留。',**values):view.load(lambda:inventory(app.data_path),notice,**values)
    def mutate(operation,notice):
        if not idle():view.say('请先停止 HUD 并等待分析任务结束，再清理缓存');return
        app.maintenance_busy=True;view.say('正在整理缓存，请稍候…');view.sync()
        def done(value,error):
            app.maintenance_busy=False
            if not app.closing:app.status.set(str(error) if error else tr('缓存维护已完成'))
            if not view.alive():return
            if error:view.say(str(error));view.sync();return
            if notice=='缓存已清理，释放 {size} MiB':refresh(notice,size=f'{value/1048576:.2f}')
            else:refresh(notice)
        app.run_background(operation,done)
    def clean():
        chosen=list(view.selected_items());keys=[item['key'] for item in chosen]
        if not chosen or any(not item['clearable'] for item in chosen):return
        from control_danger import confirm
        details=[tr(item['name'])+f" · {item['bytes']/1048576:.2f} MiB\n"+item['path'] for item in chosen]
        if not confirm(window,'清理所选缓存','清理以下可重建缓存？',details,action='清理所选缓存',warning='仅删除可重建缓存，原始赛事与导出文件保留。'):return
        # The dialog runs a nested event loop. Recheck runtime state afterwards.
        mutate(lambda:clear(app.data_path,keys),'缓存已清理，释放 {size} MiB')
    def organize():
        from cache_budget import enforce
        mutate(lambda:enforce(app.data_path,force=True),'缓存已按容量上限整理')
    def open_folder():
        target=Path(view.selected_items()[0]['path']);root=Path(app.data_path).resolve()
        try:
            if not target.resolve().is_relative_to(root):raise ValueError('记录目录不可用或已移动')
            path=target if target.is_dir() else target.parent
            while not path.is_dir() and path!=root:path=path.parent
            os.startfile(str(path))
            if path!=target and not target.exists():view.say('目录尚未创建，已打开最近的父目录。')
        except (OSError,ValueError) as error:view.say(str(error))
    view.action('clean','清理所选缓存',clean,170,enabled=lambda:idle() and bool(view.selected_items()) and all(item['clearable'] for item in view.selected_items()) and any(item['bytes'] for item in view.selected_items()))
    view.action('organize','按上限整理',organize,145,enabled=idle)
    view.action('open','打开目录',open_folder,135,enabled=lambda:len(view.selected_items())==1)
    view.action('refresh','刷新占用',refresh,135,enabled=lambda:not getattr(app,'maintenance_busy',False))
    window.bind('<F5>',lambda _:view.buttons['refresh'].invoke());refresh();return window
