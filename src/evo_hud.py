"""Compact EVO instruments on the existing HUD canvas and render deadline."""
import json
from control_theme import T
from evo_driving import ASSISTS,instruments,marker_segments

DEFAULTS=dict(instruments=True,assists=True)


def load(root):
    try:
        value=json.loads((root/'evo_hud.json').read_text('utf-8-sig'))
        return {k:value[k] if isinstance(value,dict) and type(value.get(k)) is bool else v for k,v in DEFAULTS.items()}
    except (OSError,ValueError):return dict(DEFAULTS)


def save(root,key,value):
    from storage import atomic_json
    if key not in DEFAULTS or type(value) is not bool:raise ValueError('Invalid EVO HUD preference')
    settings=load(root);settings[key]=value;atomic_json(root/'evo_hud.json',settings);return settings


def band_height(w,h,mode,settings):
    if not any(settings.values()):return 0
    return 40*min(w/640,h/268) if mode=='normal' else min(36,h*.35)


def paint(app,w,full_h,h,mode,sample,snapshot,now,window,plot):
    c=app.canvas;settings=app.evo_hud_settings;normal=mode=='normal'
    fg,muted,edge,card=(T.FG,T.MUTED,T.EDGE,T.CARD) if normal else ('#eeede8','#a4a49e','#414143','#171719')
    colors=('#e2b54a','#52b5ff','#c6ca4c')
    band=full_h-h
    if not band:return
    y=h-25*min(w/640,h/228) if normal else h+1
    bottom=full_h-27*min(w/640,h/228) if normal else full_h-1
    mid=(y+bottom)/2;size=max(9,min(14,round((bottom-y)*.37)))
    live=app.live_item
    live('evo_band',c.create_polygon,8,y+6,14,y,w-8,y,w-8,bottom-6,w-14,bottom,8,bottom,
         fill=card,outline=edge)
    model=instruments(sample)
    if settings['instruments']:
        # Fixed slots prevent width shifts between R/N/forward gears and RPM values.
        live('evo_gear',c.create_text,30,mid,text=model['gear'],fill=T.ACCENT if normal else '#c6ca4c',font=('Consolas',-size*2,'bold'))
        live('evo_rpm',c.create_text,58,mid-3,text=model['rpm']+' RPM',fill=fg,anchor='w',font=('Consolas',-size,'bold'))
        fraction=model['fraction'];bar_end=58+max(0,w*.26-58)*min(1,fraction or 0)
        live('evo_rpm_track',c.create_line,58,bottom-5,w*.26,bottom-5,fill=edge,width=2)
        live('evo_rpm_fill',c.create_line,58,bottom-5,bar_end,bottom-5,fill=colors[0] if model['limiter'] else '#c6ca4c',width=2,state='normal' if fraction is not None and fraction>0 else 'hidden')
        live('evo_shift',c.create_text,w*.53,mid,text='LIMIT' if model['limiter'] else 'SHIFT ↑' if model['up'] else '',
             fill=colors[0] if model['limiter'] else '#c6ca4c',anchor='w',font=('Consolas',-size,'bold'))
    if settings['assists']:
        left=w*.69 if settings['instruments'] else 18;step=(w-14-left)/3
        for i,(name,value,color) in enumerate(zip(ASSISTS,model['activity'],colors)):
            active=value==1;known=value in (0,1);x=left+i*step
            live('evo_lamp_'+name,c.create_rectangle,x,mid-5,x+3,mid+5,fill=color if active else edge,outline='')
            live('evo_label_'+name,c.create_text,x+8,mid,text=name+(' ?' if not known else ' ●' if active else ''),anchor='w',
                 fill=color if active else muted,font=('Consolas',-size,'bold'))
        x0,x1,y0,y1=plot
        spans=marker_segments(snapshot,now,window,x0,x1)
        for lane,(intervals,color) in enumerate(zip(spans,colors)):
            ymark=y0+3+lane*4
            for i,(a,b) in enumerate(intervals):
                key=f'evo_mark_{lane}_{i}';new=key not in app.live_items
                live(key,c.create_line,a,ymark,b,ymark,fill=color,width=2)
                if new:c.addtag_withtag('evo_markers',app.live_items[key][0])
            previous=getattr(app,'evo_marker_counts',(0,0,0))[lane]
            for i in range(len(intervals),previous):
                key=f'evo_mark_{lane}_{i}';cached=app.live_items.pop(key,None)
                if cached:c.delete(cached[0])
        app.evo_marker_counts=tuple(map(len,spans))
        c.tag_raise('evo_markers')
