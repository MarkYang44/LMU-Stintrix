"""The HUD's right-click menus.

They are built each time they open, so labels follow the interface language
and the radio marks show the panel's current mode, size and opacity. Items use
the Run & HUD page's names and order; hotkeys sit in the accelerator column
instead of inside labels; what this simulator cannot do is left out instead of
shown disabled; and every preference opens its section of the control
center's Settings page, the single place where settings are edited.
"""
import tkinter as tk
from control_theme import T
from i18n import tr

SIZES=(('440x170','小面板 · 440 × 170'),('640x228','标准面板 · 640 × 228'),('840x300','高清面板 · 840 × 300'))
OPACITY=(.75,.9,1.)
MODES=(('normal','标准面板',''),('curves','纯净 · 仅曲线','F9'),('controls','纯净 · 曲线 + 踏板 / 方向盘','F11'))
PANELS=(('tyres','四轮轮胎温度 / 胎压 / 胎况'),('strategy','燃油、虚拟能量与续航策略'),('pit','进站计时与补给'),('stint','Stint 长距离节奏'),('weather','天气与赛道趋势'))
EVO=(('instruments','紧凑仪表条 · 挡位 / 转速'),('assists','ABS / TC / ESC 实际干预标记'))
# Settings sections (the Settings page's tab keys) and what opens each.
SETTINGS=(('输入采样','采样与刷新…','F10',None),('车辆策略','轮胎、燃油与能量策略…','','vehicle_telemetry'),('耐力与天气','进站、Stint 与天气…','','endurance'))
PANEL_SETTINGS={'tyres':'车辆策略','strategy':'车辆策略','pit':'耐力与天气','stint':'耐力与天气','weather':'耐力与天气'}


def menu(parent):
    return tk.Menu(parent,tearoff=False,bg=T.CARD,fg=T.FG,activebackground=T.BUTTON,activeforeground=T.INK)


class Builder:
    """Adds translated entries; keeps the menu's transient variables alive."""
    def __init__(self,root):
        self.root=root;self.top=menu(root);self.variables=[]
    def variable(self,kind,value):
        variable=kind(self.root,value=value);self.variables.append(variable);return variable
    def command(self,owner,label,action,accelerator=''):
        owner.add_command(label=tr(label),command=action,accelerator=accelerator)
    def check(self,owner,label,variable,action,accelerator=''):
        owner.add_checkbutton(label=tr(label),variable=variable,command=action,accelerator=accelerator)
    def radio(self,owner,label,variable,value,action=None,accelerator=''):
        owner.add_radiobutton(label=tr(label),variable=variable,value=value,command=action,accelerator=accelerator)
    def cascade(self,label,fill,accelerator=''):
        sub=menu(self.top);fill(sub)
        if sub.index('end') is not None:self.top.add_cascade(label=tr(label),menu=sub,accelerator=accelerator)
        else:sub.destroy()
    def separator(self,owner=None):
        owner=owner or self.top;end=owner.index('end')
        if end is not None and owner.type(end)!='separator':owner.add_separator()


def current_size(app):
    size=f'{app.root.winfo_width()}x{app.root.winfo_height()}'
    return size if any(size==value for value,_ in SIZES) else ''


def build(app):
    caps=app.capabilities;b=Builder(app.root);top=b.top
    b.command(top,'打开控制中心',app.open_control_center)
    b.separator()
    if caps.reference_laps:b.check(top,'显示参考圈差',app.reference_on,app.apply_reference,'F6')
    b.command(top,'开启鼠标穿透',app.toggle_clickthrough,'F8')
    def modes(sub):
        for value,label,key in MODES:b.radio(sub,label,app.hud_mode,value,app.apply_clean_mode,key)
    b.cascade('显示模式',modes)
    def channels(sub):
        labels=getattr(app.profile,'input_labels',('原始输入','游戏过滤后'))
        for value,label in zip(('raw','filtered'),labels):b.radio(sub,label,app.input_channel,value,app.apply_input_channel)
    b.cascade('输入通道',channels,'F7')
    def waveform(sub):
        for seconds in ('5','10','20'):b.radio(sub,seconds+' 秒',app.window,seconds)
    b.cascade('波形窗口',waveform)
    def panels(sub):
        variables={'tyres':app.tyres_on,'strategy':app.strategy_on,'pit':app.pit_on,'stint':app.stint_on,'weather':app.weather_on}
        for key,label in PANELS:
            if not caps.panel(key):continue
            owner=app.vehicle_panels if key in ('tyres','strategy') else app.endurance_panels
            b.check(sub,label,variables[key],lambda k=key,o=owner:o.toggle(k))
        if caps.driving_instruments:
            for key,label in EVO:
                variable=app.evo_hud_vars[key];b.check(sub,label,variable,lambda k=key,v=variable:app.set_evo_hud(k,v.get()))
    b.cascade('附加面板',panels)
    if caps.reference_laps:
        def reference(sub):
            source=b.variable(tk.StringVar,'auto' if app.reference_auto.get() and not app.reference_locked.get() else 'fixed')
            def choose_source():
                automatic=source.get()=='auto';app.reference_locked.set(not automatic)
                if automatic:app.reference_auto.set(True)
                app.apply_reference()
            b.radio(sub,'自动匹配同车同赛道',source,'auto',choose_source)
            b.radio(sub,'固定当前参考圈',source,'fixed',choose_source)
            b.separator(sub)
            b.radio(sub,'最快完整圈',app.reference_kind,'fastest',app.apply_reference)
            b.radio(sub,'典型稳定圈（至少 3 圈）',app.reference_kind,'stable',app.apply_reference)
            b.separator(sub)
            b.command(sub,'选择参考圈文件…',app.select_reference)
        b.cascade('参考圈',reference)
    def window(sub):
        size=b.variable(tk.StringVar,current_size(app))
        for value,label in SIZES:b.radio(sub,label,size,value,lambda v=value:app.root.geometry(v))
        b.separator(sub)
        alpha=float(app.root.attributes('-alpha'));opacity=b.variable(tk.StringVar,f'{alpha:.2f}')
        for value in OPACITY:
            b.radio(sub,tr('不透明度 {value}%').format(value=int(value*100)),opacity,f'{value:.2f}',lambda v=value:app.root.attributes('-alpha',v))
    b.cascade('面板尺寸与不透明度',window)
    b.separator()
    def records(sub):
        b.command(sub,'打开记录文件夹',app.open_logs)
        if caps.full_review:b.command(sub,'打开赛事复盘…',app.review_csv)
        if caps.lap_comparison:b.command(sub,'最快圈曲线对比',app.open_fastest_compare)
        if caps.training:b.command(sub,'完整记录管理',app.show_library)
        if caps.native_import:
            b.separator(sub);b.command(sub,'导入 LMU 官方遥测…',app.import_native_dialog)
    b.cascade('记录与复盘',records)
    b.command(top,'性能诊断',app.show_diagnostics)
    def settings(sub):
        for section,label,key,capability in SETTINGS:
            if capability is None or getattr(caps,capability):b.command(sub,label,lambda s=section:app.open_settings(s),key)
        b.separator(sub)
        b.command(sub,'HUD 布局…',lambda:app.open_center_tool('layouts'))
        b.command(sub,'全局快捷键…',lambda:app.open_center_tool('shortcuts'))
    b.cascade('设置',settings)
    b.separator()
    b.command(top,'切换到真实遥测' if app.engine.demo else '切换到演示数据',app.toggle_demo)
    return b


def show(owner,event,builder):
    """Open a freshly built menu; the previous one is released on the next open,
    after any command it started has run."""
    previous=getattr(owner,'context_menu',None)
    if previous is not None:
        try:previous.top.destroy()
        except tk.TclError:pass
    owner.context_menu=builder
    try:builder.top.tk_popup(event.x_root,event.y_root)
    finally:builder.top.grab_release()


def popup(app,event):
    show(app,event,build(app))


def panel(app,kind,hide):
    """A side panel's menu: its settings section, hiding it, the control center."""
    b=Builder(app.root);section=PANEL_SETTINGS[kind]
    label=next(label for key,label,_,_ in SETTINGS if key==section)
    b.command(b.top,label,lambda:app.open_settings(section))
    b.command(b.top,'隐藏该面板',lambda:hide(kind))
    b.separator();b.command(b.top,'打开控制中心',app.open_control_center)
    return b


def popup_panel(app,kind,hide,event):
    show(app,event,panel(app,kind,hide))
