"""Settings forms and in-memory drafts, independent of shell rebuilds."""
import tkinter as tk
from tkinter import messagebox
from control_fields import Field
from control_theme import T
from i18n import tr

LABELS={'mode':{'fixed':'固定频率','dynamic':'动态频率'},'draw_mode':{'sync':'跟随采样','manual':'手动刷新'},'target_mode':{'auto':'自动识别','laps':'按圈数','time':'按时间'},'rate_mode':{'conservative':'保守估算','median':'中位数'}}
# Sampling fields that only apply to one mode, grouped so each condition is
# explained once above its fields instead of beneath every affected value.
CONDITIONS={'fixed_hz':'fixed','min_hz':'dynamic','max_hz':'dynamic','change_pct_s':'dynamic','hold_s':'dynamic','brake_pct':'dynamic','draw_hz':'manual'}
NOTES={'fixed':('仅固定采样时生效','以下 {count} 项仅固定采样时生效'),'dynamic':('仅动态采样时生效','以下 {count} 项仅动态采样时生效'),
    'manual':('仅手动刷新时生效','以下 {count} 项仅手动刷新时生效')}

FILES={'sampling':'settings.json','vehicle':'vehicle_settings.json','endurance':'endurance_settings.json'}


class Status:
    """Right-aligned card-header state: silent when saved, fades in when edited."""
    def __init__(self,body,center):
        from control_motion import Motion
        self.body=body;self.heading=getattr(body,'heading',None);self.state=('',None)
        self.label=center.label(body,'',9,T.ACCENT,True);self.motion=Motion(self.label)
        if self.heading is not None:self.heading.bind('<Configure>',self.place,add='+')
    def place(self,_=None):
        if not self.label.winfo_exists() or not self.state[0]:return
        from control_widgets import px
        heading=self.heading
        y=heading.winfo_y()+heading.winfo_height()//2 if heading is not None and heading.winfo_height()>1 else px(self.body,14)
        self.label.place(relx=1.0,x=0,y=y,anchor='e')
    def show(self,text,color):
        if (text,color)==self.state or not self.label.winfo_exists():return
        previous=self.state;self.state=(text,color)
        # Leaving is instant; arriving blends from the card so it reads as news.
        if not text:self.motion.cancel();self.label.place_forget();return
        from control_motion import blend
        start=color if previous[0] and previous[1]==color else T.CARD
        self.label.configure(text=text);self.place()
        self.motion.animate('status',lambda t:self.label.configure(fg=blend(start,color,t)),160)


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
        from control_confirm import notice
        notice(center.root,'设置未保存',text)


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


def segmented(center,tile,label,variable,options,labels=None):
    """A mode with two or three options reads and switches in one click."""
    from control_widgets import segmented_row
    return segmented_row(tile,label,variable,options,None,labels or {})


class FormGrid:
    """Two balanced columns once a card is wide enough, one column before that.

    Each label stays next to its value instead of a page width away. Modes
    share the first row; every condition group starts a new row, so showing
    or hiding its note never moves a field into the other column. Tiles and
    notes stay children of the card body and are only placed in this frame.
    """
    def __init__(self,body):
        self.frame=tk.Frame(body,bg=T.CARD);self.frame.pack(fill='x');self.items=[];self.columns=1
        for column in (0,1):self.frame.columnconfigure(column,weight=1,uniform='form')
        self.frame.bind('<Configure>',lambda e:self.arrange() if self.wanted(e.width)!=self.columns else None,add='+')
    def wanted(self,width):
        from control_widgets import px
        return 2 if width>=px(self.frame,760) else 1
    def add(self,tile,group=None):self.items.append(('tile',tile,group));self.arrange()
    def note(self,note,group):note.visible=False;self.items.append(('note',note,group))
    def show(self,note,visible):
        if getattr(note,'visible',False)!=visible:note.visible=visible;self.arrange()
    def arrange(self):
        from control_widgets import px
        self.columns=columns=self.wanted(self.frame.winfo_width());gap=px(self.frame,9);row=column=0;previous=object()
        for kind,widget,group in self.items:
            if not widget.winfo_exists():continue
            if group!=previous and column:row+=1;column=0
            previous=group
            if kind=='note':
                if widget.visible:widget.grid(in_=self.frame,row=row,column=0,columnspan=2,sticky='ew',pady=(4,0));row+=1
                else:widget.grid_forget()
                continue
            wide=columns==2
            widget.grid(in_=self.frame,row=row,column=column if wide else 0,columnspan=1 if wide else 2,sticky='new',padx=((0,gap) if column==0 else (gap,0)) if wide else 0)
            column+=1
            if column>=columns:row+=1;column=0


def build(center,body,module,specs,choices=()):
    import sampling,vehiclelab,endurance
    path=center.data_path/FILES[module]
    load={'sampling':sampling,'vehicle':vehiclelab,'endurance':endurance}[module].load_settings
    source=load(path);variables={};baseline={key:str(value) for key,value in source.items()}
    from control_validation import Feedback
    from control_settings_search import register
    feedback=Feedback()
    drafts=getattr(center,'form_drafts',{}).get(module,{})
    # A quiet header status replaces the old status line and per-card save
    # button: the fixed form bar (and Ctrl+S) is the single save surface.
    badge=Status(body,center);body.form_status=badge;complete=False;conditions={}
    grid=FormGrid(body);body.form_grid=grid
    def dirty(*_):
        changed=sum(not equal(v.get(),baseline[k]) for k,v in variables.items())
        badge.show('● '+tr('已修改 {count} 项').format(count=changed) if changed else '',T.ACCENT)
        bar=getattr(center,'form_bar',None)
        if complete and bar and bar.winfo_exists():bar.refresh(module)
        mode=variables.get('mode');draw=variables.get('draw_mode')
        for group,(note,anchor,members) in conditions.items():
            active=(draw is None or draw.get()=='manual') if group=='manual' else mode is None or mode.get()==group
            for field,label in members:
                label.configure(fg=T.FG if active else T.MUTED)
                # Keep fields editable: an invalid retained value can always be repaired.
                field.entry.configure(fg=T.FG if active else T.MUTED)
            if active:grid.show(note,False);continue
            single,several=NOTES[group]
            note.configure(text=tr(single) if len(members)==1 else tr(several).format(count=len(members)))
            grid.show(note,True)
    def refresh():
        current=load(path)
        for key,var in variables.items():
            if equal(var.get(),baseline[key]):var.set(str(current[key]))
        baseline.update({k:str(v) for k,v in current.items()});dirty()
    # Register before yielding so a language switch during incremental page
    # construction preserves fields the user has already edited.
    center.pages.register(module,variables,refresh,baseline)
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
            badge.show(tr('请修正标记的设置'),T.RED);return False
    # Modes come first: they decide which of the following values apply.
    for key,label,options in choices:
        tile=tk.Frame(body,bg=T.CARD);grid.add(tile,'modes');field=segmented(center,tile,label,variable(key),options,LABELS.get(key))
        feedback.add(key,field,label,center.label(tile,'',9,T.RED));register(center,key,label,field,module)
        variables[key].trace_add('write',lambda *_,k=key:feedback.clear(k));yield
    for key,label in specs:
        group=CONDITIONS.get(key) if module=='sampling' else None
        tile=tk.Frame(body,bg=T.CARD)
        if group and group not in conditions:
            # One caption per group, placed above it only while the group is inactive.
            note=center.label(body,'',9,T.MUTED);grid.note(note,group);conditions[group]=(note,tile,[])
        grid.add(tile,group);row=center.row(tile);caption=center.label(row,label,10,T.MUTED);caption.pack(side='left')
        field=Field(row,textvariable=variable(key),width=15,font=(T.LATIN,11));field.pack(side='right',padx=4)
        if group:conditions[group][2].append((field,caption))
        error_hint=center.label(tile,'',9,T.RED);feedback.add(key,field,label,error_hint);register(center,key,label,field,module)
        field.entry.bind('<FocusOut>',lambda _:validation() if complete else None,add='+')
        variables[key].trace_add('write',lambda *_,k=key:feedback.clear(k))
        yield
    def save():
        if not validation(True):return
        try:
            center.update_module(module,{key:var.get() for key,var in variables.items()})
            baseline.update({k:str(v) for k,v in load(path).items()})
            center.form_drafts.pop(module,None);dirty()
        except (ValueError,OSError) as error:
            if not feedback.show(error):__import__('control_confirm').notice(center.root,'设置未保存',str(error))
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
