"""Settings forms and in-memory drafts, independent of shell rebuilds."""
import tkinter as tk
from tkinter import messagebox
from control_fields import Field
from control_theme import T
from i18n import tr

LABELS={'mode':{'fixed':'固定频率','dynamic':'动态频率'},'draw_mode':{'sync':'跟随采样','manual':'手动刷新'},'target_mode':{'auto':'自动识别','laps':'按圈数','time':'按时间'},'rate_mode':{'conservative':'保守估算','median':'中位数'}}

FILES={'sampling':'settings.json','vehicle':'vehicle_settings.json','endurance':'endurance_settings.json'}


def equal(a,b):
    if a==b:return True
    try:return float(a)==float(b)
    except (ValueError,TypeError):return False


def capture(deck,previous=None):
    drafts={name:dict(values) for name,values in (previous or {}).items()}
    pages=list(deck.pages.values())
    if deck.active is not None and not any(page is deck.active for page in pages):pages.append(deck.active)
    for page in pages:
        for module,variables in page.forms.items():
            baseline=page.form_baselines.get(module,{})
            drafts[module]={key:var.get() for key,var in variables.items() if not equal(var.get(),baseline.get(key))}
    return drafts


def build(center,body,module,specs,choices=()):
    import sampling,vehiclelab,endurance
    path=center.data_path/FILES[module]
    load={'sampling':sampling,'vehicle':vehiclelab,'endurance':endurance}[module].load_settings
    source=load(path);variables={};baseline={key:str(value) for key,value in source.items()}
    drafts=getattr(center,'form_drafts',{}).get(module,{})
    state=tk.StringVar(center.root)
    hint=center.label(body,state,9,T.MUTED);hint.pack(anchor='w',pady=(0,6))
    save_button=None;complete=False
    def dirty(*_):
        changed=any(not equal(v.get(),baseline[k]) for k,v in variables.items())
        state.set(tr('有未保存修改') if changed else tr('设置与已保存值一致'))
        hint.configure(fg=T.ACCENT if changed else T.MUTED)
        if save_button is not None:save_button.configure(state='normal' if changed and complete else 'disabled')
    def refresh():
        current=load(path)
        for key,var in variables.items():
            if equal(var.get(),baseline[key]):var.set(str(current[key]))
        baseline.update({k:str(v) for k,v in current.items()});dirty()
    # Register before yielding so a language switch during incremental page
    # construction preserves fields the user has already edited.
    center.pages.register(module,variables,refresh,baseline)
    save_button=center.button(center.row(body),'应用并保存',lambda:save(),True,145);save_button.configure(state='disabled')
    def variable(key):
        var=tk.StringVar(center.root,value=drafts.get(key,str(source[key])));variables[key]=var
        var.trace_add('write',dirty);return var
    for key,label in specs:
        row=center.row(body);center.label(row,label,10,T.MUTED).pack(side='left')
        Field(row,textvariable=variable(key),width=15,font=('Segoe UI',11)).pack(side='right',padx=4)
        yield
    for key,label,options in choices:
        center.choice(body,label,variable(key),options,labels=LABELS.get(key));yield
    def save():
        try:
            center.update_module(module,{key:var.get() for key,var in variables.items()})
            baseline.update({k:str(v) for k,v in load(path).items()})
            center.form_drafts.pop(module,None);dirty()
        except (ValueError,OSError) as error:messagebox.showerror(tr('设置未保存'),str(error),parent=center.root)
    complete=True;dirty()
    yield
