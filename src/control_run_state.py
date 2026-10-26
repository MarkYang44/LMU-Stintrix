"""One effective display snapshot for the idle page and the next HUD launch."""
from hud_layouts import LayoutStore
import layout_actions
from i18n import tr
from copy import deepcopy

MODES={'normal':'标准面板','curves':'纯净 · 仅曲线','controls':'纯净 · 曲线 + 踏板 / 方向盘'}


def setup(app):
    if app.active():return layout_actions.current(app.data_path,app.hud)
    token=tuple((p.stat().st_mtime_ns,p.stat().st_size) if p.exists() else None for p in [app.data_path/name for name in ('hud_layouts.json','vehicle_settings.json','endurance_settings.json')])
    cached=getattr(app,'_idle_display_cache',None)
    if cached is None or token!=cached[0]:app._idle_display_cache=(token,layout_actions.current(app.data_path))
    return deepcopy(app._idle_display_cache[1])


def refresh(app):
    if app.page!=0 or not hasattr(app,'run_layout_summary') or not app.run_layout_summary.winfo_exists():return
    try:
        snapshot=setup(app);path=app.data_path/'hud_layouts.json';token=(path.stat().st_mtime_ns,path.stat().st_size) if path.exists() else None
        cached=getattr(app,'_layout_catalog_cache',None)
        if cached is None or cached[0]!=token:app._layout_catalog_cache=(token,LayoutStore(app.data_path).load())
        store=app._layout_catalog_cache[1];name=store.get('active') or tr('自定义显示')
        if store.get('active') and snapshot!=store['profiles'].get(store['active']):name+=' · '+tr('已调整')
        for variable,value in [(app.mode_label,MODES[snapshot['mode']]),(app.window,snapshot['window'])]:
            if variable.get()!=value:variable.set(value)
        for _,key,variable in getattr(app,'panel_visibility_switches',[]):
            value=snapshot['panels'][key]['visible']
            if variable.get()!=value:variable.set(value)
        from control_hud_stop import saving
        text=tr('当前画面' if app.active() else 'HUD 已隐藏' if saving(app) else '下次启动')+' · '+name+' · '+tr(MODES[snapshot['mode']])+' · '+tr('显示面板')+f" {sum(p['visible'] for p in snapshot['panels'].values())}"
        if getattr(app,'silent_mode',None) and app.silent_mode.get():text+=' · '+tr('静默记录')
        if app.run_layout_summary.cget('text')!=text:app.run_layout_summary.configure(text=text)
    except (OSError,ValueError) as error:app.run_layout_summary.configure(text=tr(str(error)))
