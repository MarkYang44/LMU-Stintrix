"""Recording and HUD commands; page widgets delegate through the existing API."""
import tkinter as tk
from i18n import tr


def start(app,demo=False):
    if app.active():
        if not app.hud.silent_recording:app.hud.root.lift()
        app.status.set(tr('记录已在运行；请先停止后切换真实 / 演示模式'));return
    from control_maintenance import busy as maintenance_busy
    if maintenance_busy(app):app.status.set(tr('离线维护正在处理，请完成后再启动记录'));return
    if app.hud is not None and app.hud.root.winfo_exists():app.status.set(tr('正在保存上一场记录，请稍候'));return
    video=getattr(app,'video_window',None)
    if video is not None and video.winfo_exists():video.video_wizard.cancel.set()
    history=getattr(app,'video_history_window',None)
    if history is not None and history.winfo_exists():history.history_state['cancel'].set()
    from hud import App
    app.last_recording_status=None
    app.hud_stopped=False
    app.hud=App(demo,root=tk.Toplevel(app.root),on_menu=app.show,shortcuts=app.shortcuts)
    if hasattr(app,'mode_label') and not app.hud.layout_snapshot:
        mode={'标准面板':'normal','纯净 · 仅曲线':'curves','纯净 · 曲线 + 踏板 / 方向盘':'controls'}[app.mode_label.get()]
        app.hud.hud_mode.set(mode);app.hud.apply_clean_mode();app.hud.window.set(app.window.get())
    app.status.set(tr('DEMO · 合成数据') if demo else tr('静默记录已启动 · 等待 LMU 遥测') if app.hud.silent_recording else tr('HUD 已启动 · 等待 LMU 遥测'))
    if app.simulator=='ac_evo':app.status.set(tr('DEMO · 合成数据') if demo else tr('HUD 已启动 · 等待 AC EVO 遥测'))


def set_silent_recording(app):
    import recording_visibility
    enabled=app.silent_mode.get()
    recording_visibility.save(app.data_path/'recording_visibility.json',enabled)
    if app.active():recording_visibility.apply(app.hud,enabled)
    app.status.set(tr('静默记录已开启 · 全部 HUD 隐藏，记录规则不变') if enabled else tr('静默记录已关闭 · 恢复 HUD 显示'))
    app.refresh_run_configuration()


def stop_hud(app):
    if app.active():
        hud=app.hud;app.status.set(tr('正在结束录制并生成报告…'));hud.close(keep_control_center=True)
        if not hud.closing:app.status.set(tr('继续记录；未保存修改仍保留'))
        else:
            app.hud_stopped=True;app.status.set(tr('HUD 已隐藏，后台正在完成保存。'))
            from control_hud_stop import retire
            retire(app);app.update_toolbar()


def hud_action(app,method):
    if app.active():getattr(app.hud,method)()
    else:app.status.set(tr('请先启动 HUD，再打开这项实时功能'))


def set_hud(app,key,value):
    if key=='channel':app.update_module('sampling',{'input_channel':value})
    elif app.active():
        if key=='mode':app.hud.hud_mode.set(value);app.hud.apply_clean_mode()
        else:app.hud.window.set(value)
    elif key in ('mode','window'):
        import layout_actions
        try:layout_actions.adjust(app.data_path,**{key:value});app.refresh_run_configuration()
        except (OSError,ValueError) as error:app.status.set(tr(str(error)))


def set_panel_visibility(app,module,key,value):
    from simulator_profiles import capabilities
    if not capabilities(app.simulator).panel(key):return
    from hud_layouts import LayoutStore
    try:
        if not app.active() and LayoutStore(app.data_path).current():
            import layout_actions
            layout_actions.adjust(app.data_path,panels={key:dict(visible=value)})
        app.update_module(module,{key+'_enabled':value});app.refresh_run_configuration()
    except (OSError,ValueError) as error:app.status.set(tr(str(error)))
