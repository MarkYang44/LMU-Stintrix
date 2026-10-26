"""Settings forms and in-memory drafts, independent of shell rebuilds."""
import tkinter as tk
from tkinter import messagebox
from control_fields import Field
from control_theme import T
from i18n import tr

LABELS={'mode':{'fixed':'固定频率','dynamic':'动态频率'},'draw_mode':{'sync':'跟随采样','manual':'手动刷新'},'target_mode':{'auto':'自动识别','laps':'按圈数','time':'按时间'},'rate_mode':{'conservative':'保守估算','median':'中位数'}}

FILES={'sampling':'settings.json','vehicle':'vehicle_settings.json','endurance':'endurance_settings.json'}


def close_forms(center,done):
    """Validate every draft before saving any; keep unsaved modules on failure."""
    drafts={key:value for key,value in capture(center.pages,getattr(center,'form_drafts',{})).items() if value}
    if not drafts:done();return
    from control_confirm import ask
    answer=ask(center.root,'有未保存修改','参数页仍有未保存修改。退出前可保存全部，或明确放弃。',[('save','保存参数并退出'),('discard','放弃参数修改并退出'),('cancel','继续编辑')])
    if answer=='cancel':return
    if answer=='discard':center.form_drafts={};done();return
    import sampling,vehiclelab,endurance
    modules=dict(sampling=sampling,vehicle=vehiclelab,endurance=endurance)
    center.form_drafts=drafts
    for name,values in list(drafts.items()):
        module=modules[name]
        try:
            combined={**module.load_settings(center.data_path/FILES[name]),**values}
            (module.validate_settings if name=='sampling' else module.settings)(combined)
        except ValueError:
            center.show_page(2)
            for _,body in center.settings_anchors:
                if getattr(body,'form_module',None)==name:body.form_validate(True);break
            return
    saved=[]
    try:
        for name,values in list(drafts.items()):
            center.update_module(name,values);center.form_drafts.pop(name,None);saved.append(name)
            for page in center.pages.pages.values():
                if name in page.forms:
                    page.form_baselines[name].update({key:var.get() for key,var in page.forms[name].items()})
        done()
    except (ValueError,OSError) as error:
        text=(tr('部分参数已保存；未完成项仍保留。')+'\n' if saved else '')+str(error)
        center.status.set(tr('设置未保存')+' · '+text)
        messagebox.showerror(tr('设置未保存'),text,parent=center.root)


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
    from control_validation import Feedback
    from control_settings_search import register
    feedback=Feedback()
    drafts=getattr(center,'form_drafts',{}).get(module,{})
    state=tk.StringVar(center.root)
    hint=center.label(body,state,9,T.MUTED);hint.pack(anchor='w',pady=(0,6))
    save_button=None;complete=False;conditions={}
    def dirty(*_):
        changed=any(not equal(v.get(),baseline[k]) for k,v in variables.items())
        state.set(tr('有未保存修改') if changed else tr('设置与已保存值一致'))
        hint.configure(fg=T.ACCENT if changed else T.MUTED)
        if save_button is not None:save_button.configure(state='normal' if changed and complete else 'disabled')
        bar=getattr(center,'form_bar',None)
        if complete and bar and bar.winfo_exists():bar.refresh(module)
        for key,(field,label,note) in conditions.items():
            mode=variables.get('mode');draw=variables.get('draw_mode')
            active=(mode is None or (mode.get()=='fixed' if key=='fixed_hz' else mode.get()=='dynamic')) if key!='draw_hz' else draw is None or draw.get()=='manual'
            label.configure(fg=T.FG if active else T.MUTED)
            note.configure(text='' if active else tr('仅手动刷新时生效' if key=='draw_hz' else '仅固定采样时生效' if key=='fixed_hz' else '仅动态采样时生效'))
            # Keep fields editable: an invalid retained value can always be repaired.
            field.entry.configure(fg=T.FG if active else T.MUTED)
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
    def validation(focus=False):
        values={**load(path),**{key:var.get() for key,var in variables.items()}}
        validator={'sampling':sampling.validate_settings,'vehicle':vehiclelab.settings,'endurance':endurance.settings}[module]
        try:validator(values);feedback.clear();return True
        except ValueError as error:
            feedback.show(error,False)
            if focus and getattr(error,'fields',()):
                item=feedback.fields.get(error.fields[0])
                if item:
                    widget=item[0];center.root.update_idletasks();y=widget.winfo_rooty()-center.content.winfo_rooty();center.scroll.yview_moveto(max(0,y-45)/max(1,center.content.winfo_height()));widget.focus_set()
            state.set(tr('请修正标记的设置'));return False
    for key,label in specs:
        tile=tk.Frame(body,bg=T.CARD);tile.pack(fill='x');row=center.row(tile);center.label(row,label,10,T.MUTED).pack(side='left')
        field=Field(row,textvariable=variable(key),width=15,font=('Segoe UI',11));field.pack(side='right',padx=4)
        if module=='sampling' and key in ('fixed_hz','min_hz','max_hz','change_pct_s','hold_s','brake_pct','draw_hz'):
            note=center.label(tile,'',9,T.MUTED);note.pack(fill='x');conditions[key]=(field,row.winfo_children()[0],note)
        error_hint=center.label(tile,'',9,T.RED);feedback.add(key,field,label,error_hint);register(center,key,label,field,module)
        field.entry.bind('<FocusOut>',lambda _:validation() if complete else None,add='+')
        variables[key].trace_add('write',lambda *_,k=key:feedback.clear(k))
        yield
    for key,label,options in choices:
        tile=tk.Frame(body,bg=T.CARD);tile.pack(fill='x');field=center.choice(tile,label,variable(key),options,labels=LABELS.get(key))
        feedback.add(key,field,label,center.label(tile,'',9,T.RED));register(center,key,label,field,module)
        variables[key].trace_add('write',lambda *_,k=key:feedback.clear(k));yield
    def save():
        if not validation(True):return
        try:
            center.update_module(module,{key:var.get() for key,var in variables.items()})
            baseline.update({k:str(v) for k,v in load(path).items()})
            center.form_drafts.pop(module,None);dirty()
        except (ValueError,OSError) as error:
            if not feedback.show(error):messagebox.showerror(tr('设置未保存'),str(error),parent=center.root)
    def reset():
        current=load(path)
        for key,var in variables.items():var.set(str(current[key]))
        baseline.update({key:str(value) for key,value in current.items()});center.form_drafts.pop(module,None);feedback.clear();dirty()
    body.form_feedback=feedback;body.form_validate=validation;body.form_save=save;body.form_module=module
    body.form_reset=reset;body.form_changed=lambda:sum(not equal(var.get(),baseline[key]) for key,var in variables.items())
    if not hasattr(center,'form_panels'):center.form_panels={}
    center.form_panels[module]=body
    complete=True;dirty()
    yield
