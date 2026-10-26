"""One truthful stop/save state for toolbar, run page and retained report links."""
from i18n import tr


def saving(app):
    hud=app.hud
    return bool(hud is not None and hud.closing and not getattr(hud,'stopped',False) and hud.root.winfo_exists())


def retire(app):
    hud=app.hud
    if hud is None or not (getattr(hud,'stopped',False) or not hud.root.winfo_exists()):return
    from recording_status import snapshot
    app.recent.observe(hud,app.run_background)
    state=snapshot(hud.engine);app.last_report_folder=getattr(hud.engine.recorder,'report_folder',None)
    app.last_recording_status=state if state['state'] in ('saved','building','error') else None;app.hud=None
    if getattr(app,'hud_stopped',False):
        text=tr('HUD 已关闭')+(' · '+tr(state['text']) if app.last_recording_status else '')
        app.status.set(text)


def detail(hud):
    recorder=hud.engine.recorder
    if hud.engine.thread.is_alive() or recorder.file is not None:return 'HUD 已隐藏 · 正在保存记录'
    from recording_status import snapshot
    state=snapshot(hud.engine)
    if state['state']=='error':return 'HUD 已隐藏 · 请检查保存或报告错误'
    return 'HUD 已隐藏 · 正在完成后台报告' if state['state']=='building' else 'HUD 已隐藏 · 正在完成后台任务'
