"""Transactional layout commands shared by the editor and shortcut service."""
from hud_layouts import LayoutStore,defaults
import hud_presentation


def current(root,hud=None):
    if hud is not None and not hud.closing:
        hud.root.update_idletasks();return hud_presentation.capture(hud)
    saved=LayoutStore(root).current()
    if saved:return saved
    import vehiclelab,endurance
    result=defaults()
    for kind in ('tyres','strategy','pit','stint','weather'):
        config=vehiclelab.load_settings(root/'vehicle_settings.json') if kind in ('tyres','strategy') else endurance.load_settings(root/'endurance_settings.json')
        p=result['panels'][kind];p['visible']=config[kind+'_enabled']
        if kind+'_position' in config:p['x'],p['y']=config[kind+'_position']
    return result


def perform(root,hud,operation):
    before=current(root,hud);store=LayoutStore(root);snapshot=operation(store,before)
    if hud is not None and not hud.closing:
        try:hud_presentation.apply(hud,snapshot)
        except Exception:
            history=store.load()['history'];store.restore(history[-1]['id'],before)
            hud_presentation.apply(hud,before);raise
    return snapshot


def select(root,hud,name):
    def operation(store,before):
        value=store.select(name,before);return value['profiles'][name]
    return perform(root,hud,operation)


def save(root,hud,name,snapshot):
    def operation(store,before):store.save(name,snapshot,before);return snapshot
    return perform(root,hud,operation)


def restore(root,hud,identifier):
    return perform(root,hud,lambda store,before:store.restore(identifier,before))


def adjust(root,**changes):
    """An explicit idle-page choice overrides the saved presentation, not a profile."""
    before=current(root);snapshot=__import__('copy').deepcopy(before)
    panels=changes.pop('panels',{})
    snapshot.update(changes)
    for kind,values in panels.items():snapshot['panels'][kind].update(values)
    from hud_layouts import normalize
    snapshot=normalize(snapshot)
    if snapshot!=before:LayoutStore(root).change('adjust',before,lambda value:value.update(presentation=snapshot))
    return snapshot


def next_layout(root,hud):
    value=LayoutStore(root).load();names=list(value['profiles'])
    if not names:raise ValueError('先保存至少一套 HUD 布局')
    index=(names.index(value['active'])+1)%len(names) if value['active'] in names else 0
    select(root,hud,names[index]);return names[index]
