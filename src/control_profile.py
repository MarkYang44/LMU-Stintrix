"""Edit per-car tyre thresholds without starting telemetry collection."""
from i18n import tr,Label
import tkinter as tk
from control_fields import Select,Field
from tkinter import ttk,messagebox
from app_config import ROOT
from control_widgets import px,Switch
from control_video_widgets import Action
from control_theme import T
import vehiclelab


def show(owner,target=None):
    previous=getattr(owner,'profile_dialog',None)
    if previous and previous.winfo_exists():
        previous.lift()
        if target in previous.profile_fields:previous.profile_focus(target)
        return previous
    window=tk.Toplevel(owner.root);owner.profile_dialog=window;window.title(tr('Stintrix · 车型轮胎阈值'));window.geometry(f'{px(window,680)}x{px(window,680)}');window.minsize(px(window,620),px(window,650))
    window.configure(bg=T.CARD);window.transient(owner.root)
    footer=tk.Frame(window,bg=T.CARD);footer.pack(side='bottom',fill='x',padx=24,pady=(0,18))
    from control_video_widgets import ScrollPage
    page=ScrollPage(window);page.pack(fill='both',expand=True,padx=18,pady=(18,8));frame=page.body;frame.configure(bg=T.CARD)
    window.bind('<MouseWheel>',lambda event:page.wheel(event.delta))
    data_path=getattr(owner,'data_path',ROOT);config=vehiclelab.load_settings(data_path/'vehicle_settings.json');latest=owner.hud.engine.latest if owner.active() else None
    car=tk.StringVar(window,value=latest['vehicle'] if latest else '*');enabled=tk.BooleanVar(window)
    Label(frame,text='车型阈值',bg=T.CARD,fg=T.FG,font=('Microsoft YaHei UI',16,'bold')).pack(anchor='w')
    Label(frame,text='* 为通用默认；报警按车型保存。',bg=T.CARD,fg=T.MUTED).pack(anchor='w',pady=(5,15))
    Label(frame,text='车型',bg=T.CARD,fg=T.MUTED).pack(anchor='w')
    box=Select(frame,textvariable=car,values=list(dict.fromkeys([car.get(),'*',*config['profiles']])),style='Lab.TCombobox');box.pack(fill='x',pady=6)
    source=tk.StringVar(window);source_label=Label(frame,textvariable=source,bg=T.CARD,fg=T.MUTED,justify='left',anchor='w');source_label.pack(fill='x',pady=(0,8))
    source_label.bind('<Configure>',lambda e:e.widget.configure(wraplength=max(100,e.width)))
    Switch(frame,'启用该车型温度 / 胎压 / 胎况报警',enabled,lambda:None).pack(fill='x',pady=8)
    variables={};fields={};traces=[]
    from control_validation import Feedback
    from preference_error import PreferenceError
    feedback=Feedback()
    for key,title in [('temp_min','胎面中温下限 / °C'),('temp_max','胎面中温上限 / °C'),('pressure_min','胎压下限 / kPa'),('pressure_max','胎压上限 / kPa'),('wear_min','胎况字段下限 / %')]:
        tile=tk.Frame(frame,bg=T.CARD);tile.pack(fill='x');row=tk.Frame(tile,bg=T.CARD);row.pack(fill='x',pady=6);Label(row,text=title,bg=T.CARD,fg=T.MUTED).pack(side='left')
        var=tk.StringVar(window);variables[key]=var;field=Field(row,textvariable=var,width=15);field.pack(side='right');fields[key]=field
        feedback.add(key,field,title,Label(tile,text='',bg=T.CARD,fg=T.RED));traces.append((var,var.trace_add('write',lambda *_,k=key:feedback.clear(k))))
    from control_confirm import draft_choice,register
    from control_forms import equal
    current=[car.get()];baseline={};state=tk.StringVar(window);buttons={};saved=[False]
    def snapshot():return dict(alerts=enabled.get(),**{key:var.get() for key,var in variables.items()})
    def dirty():return any(not equal(value,baseline.get(key)) for key,value in snapshot().items())
    def update(*_):
        state.set(tr('有未保存修改') if dirty() else tr('设置与已保存值一致'))
        source.set(tr('通用默认（*）：供未单独设置的车型使用。') if current[0]=='*' else tr('已保存该车型的专属阈值。') if saved[0] else tr('沿用通用默认；保存后建立该车型的专属阈值。'))
        if buttons:
            buttons['reset'].configure(state='normal' if dirty() else 'disabled')
            buttons['save'].configure(state='normal' if dirty() or not saved[0] else 'disabled')
            buttons['defaults'].label='载入内置默认' if current[0]=='*' else '载入通用默认';buttons['defaults'].paint()
    def fill(name,values=None):
        config=vehiclelab.load_settings(data_path/'vehicle_settings.json')
        value=config['profiles'].get(name,config['profiles'].get('*',vehiclelab.DEFAULT_PROFILE));baseline.clear();baseline.update(value);saved[0]=name in config['profiles']
        value=values or value;enabled.set(value['alerts'])
        for key,var in variables.items():var.set(str(value[key]))
        current[0]=name;car.set(name);feedback.clear();update()
    def save(close_window=True):
        try:
            value=vehiclelab.load_settings(data_path/'vehicle_settings.json');profiles=dict(value['profiles']);numbers={}
            for key,var in variables.items():
                try:numbers[key]=float(var.get())
                except ValueError:raise PreferenceError('请输入有效数值',key) from None
            profiles[current[0].strip() or '*']=vehiclelab.profile(dict(alerts=enabled.get(),**numbers))
            owner.update_module('vehicle',dict(profiles=profiles));owner.profile_draft=None;fill(current[0])
            if close_window:window.destroy()
            else:state.set(tr('已保存；可以继续编辑其他车型。'))
            return True
        except (ValueError,OSError) as error:
            if not feedback.show(error):messagebox.showerror(tr('设置未保存'),str(error),parent=window)
            return False
    def switch(_=None):
        requested=car.get()
        if requested==current[0]:return
        if dirty():
            answer=draft_choice(window)
            if answer=='cancel' or (answer=='save' and not save(False)):car.set(current[0]);return
        owner.profile_draft=None;fill(requested)
    def close(after=None,exiting=False):
        if dirty():
            answer=draft_choice(window,closing=True,exiting=exiting)
            if answer=='cancel':return
            if answer=='save' and not save(False):return
            owner.profile_draft=dict(car=current[0],values=snapshot()) if answer=='keep' else None
        else:owner.profile_draft=None
        window.destroy()
        if after:after()
    def defaults():
        value=vehiclelab.DEFAULT_PROFILE if current[0]=='*' else vehiclelab.load_settings(data_path/'vehicle_settings.json')['profiles'].get('*',vehiclelab.DEFAULT_PROFILE)
        enabled.set(value['alerts'])
        for key,var in variables.items():var.set(str(value[key]))
        feedback.clear();update()
    def focus_field(key):
        from control_validation import reveal
        window.update_idletasks();reveal(fields[key]);fields[key].focus_set()
    draft=getattr(owner,'profile_draft',None);fill(draft['car'] if draft else car.get(),draft['values'] if draft else None)
    box.bind('<<ComboboxSelected>>',switch);window.protocol('WM_DELETE_WINDOW',close);register(owner,window,close)
    for var in (enabled,*variables.values()):traces.append((var,var.trace_add('write',update)))
    Label(footer,textvariable=state,bg=T.CARD,fg=T.MUTED,font=(T.FONT,9)).pack(anchor='w',pady=(5,8))
    actions=tk.Frame(footer,bg=T.CARD);actions.pack(fill='x')
    for key,label,command,width,primary in [('save','保存并继续',lambda:save(False),140,True),('reset','撤销本次修改',lambda:fill(current[0]),150,False),('defaults','载入通用默认',defaults,150,False),('close','关闭',close,90,False)]:
        buttons[key]=Action(actions,label,command,width,primary);buttons[key].pack(side='left')
    from control_flow import install
    install(actions);update()
    def translate():
        update()
        for button in buttons.values():button.configure(width=max(px(button,90),button.font.measure(tr(button.label))+px(button,36)));button.paint()
        actions.event_generate('<Configure>',width=actions.winfo_width())
    window.retranslate=translate
    from control_motion import keyboard_action
    window.bind('<Control-s>',lambda _:(keyboard_action(window,lambda:save(False)),'break')[1])
    window.bind('<Escape>',lambda _:(keyboard_action(window,close),'break')[1])
    def recorded_cars(result,error):
        if owner.closing or not window.winfo_exists():return
        if not error:box.configure(values=list(dict.fromkeys(['*',car.get(),*config['profiles'],*(v['vehicle'] for v in result if v.get('vehicle'))])))
    from library import inventory
    owner.run_background(lambda:inventory(data_path),recorded_cars)
    window.profile_fields=fields;window.profile_variables=variables;window.profile_save=save;window.profile_errors=feedback
    window.profile_car=car;window.profile_switch=switch;window.profile_dirty=dirty;window.profile_close=close
    window.profile_focus=focus_field;window.profile_buttons=buttons;window.profile_source=source;window.profile_box=box;window.profile_page=page
    def dispose(event):
        if event.widget is window:
            for variable,token in traces:variable.trace_remove('write',token)
            for variable in (car,enabled,state,source,*variables.values()):variable.__del__();variable._tk=None
    window.bind('<Destroy>',dispose,add='+')
    if target in fields:focus_field(target)
    return window
