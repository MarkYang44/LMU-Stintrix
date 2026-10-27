"""Explicit compact/full layouts retain the previous custom presentation."""
from i18n import tr


def compact(table,defaults):
    if {'date','track','layout','car','time','gain'}<=set(table.columns):
        keys=['date','track','layout','car','time','gain']
        return dict(visible=keys,frozen=['date','track'],widths={**defaults['widths'],'date':140,'track':150,'layout':155,'car':180,'time':105,'gain':100})
    required={'date','track','lap','car'}
    if not required<=set(table.columns):return defaults
    evo=getattr(table,'simulator','lmu')=='ac_evo'
    keys=['date','track','layout','lap','car','type'] if evo else ['date','track','lap','car','type','result']
    widths={**defaults['widths'],'date':140,'track':160 if evo else 180,'layout':185,'lap':92,'car':165,'type':76,'result':90}
    return dict(visible=[k for k in keys if k in table.columns],frozen=['date','track'],widths=widths)


def install(app,table,key,defaults,persist,snapshot):
    if not {'date','track','lap','car'}<=set(table.columns):return
    from control_table_preferences import load,checked
    try:table.previous_layout=load(app.data_path)['tables'].get(key,{}).get('previous_layout')
    except (OSError,ValueError):table.previous_layout=None
    def use(name):
        old=getattr(table,'preferences_window',None)
        if old is not None and old.winfo_exists():old.column_close(lambda:use(name));return False
        try:
            saved=load(app.data_path)['tables'].get(key,{})
            value=compact(table,defaults) if name=='compact' else defaults if name=='full' else saved.get('previous_layout')
            value=checked(value,table);previous=snapshot()
            if value==previous:
                if not saved or checked(saved,table)!=value:persist(value)
            else:persist(value,previous);table.previous_layout=previous
            app.status.set(tr('列布局已应用并记住；可恢复上次布局'));return True
        except (OSError,ValueError) as error:app.status.set(tr('列布局未保存：{error}').format(error=tr(str(error)) or type(error).__name__));return False
    table.apply_layout_preset=use


def actions(table):
    from control_action_menu import MenuAction
    if not hasattr(table,'apply_layout_preset'):return []
    return [MenuAction('compact-columns','紧凑列布局',lambda:table.apply_layout_preset('compact'),'显示'),
        MenuAction('full-columns','完整列布局',lambda:table.apply_layout_preset('full'),'显示'),
        MenuAction('previous-columns','恢复上次列布局',lambda:table.apply_layout_preset('previous'),'显示',lambda:table.previous_layout is not None)]
