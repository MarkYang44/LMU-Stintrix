"""Local launchpad: HUD, categorized preferences and direct session actions."""
from platform_runtime import open_path
from i18n import tr,Label
import json
from json_store import load as load_json
import os
import threading
from types import SimpleNamespace
from pathlib import Path
import tkinter as tk
from control_theme import T
from tkinter import ttk,filedialog,messagebox
from app_config import ROOT, SIMULATOR
from background import BackgroundTasks
from control_widgets import GlassCard,Pill,Switch,CardGrid,LaunchArtwork,segmented_row,backdrop,px
from control_fields import Select,Field
from paths import ASSETS
from platform_runtime import offline_only,page_ids,title as window_title,install_mac_keys,install_touchpad,wheel_steps
from control_shell import Shell
from control_list import SessionList
import branding
import control_settings
import renderer_config
import sampling
import vehiclelab
import endurance
import control_theme

PAGES=('运行与 HUD','赛事复盘','采样与遥测','图像与数据','赛道指南','车型图鉴','个人赛道纪录')
SUBTITLES=('比赛中保持专注。所有控制，在这里。','搜索时间、赛道或车辆；双击记录或按 Enter 打开复盘。','分别配置输入采样、轮胎策略与耐力赛遥测。','视频分析、赛事包与本地报告，按任务处理。','赛道特性、练习建议与车型选择。','车型优缺点、适配赛道与并排对比。','赛道最快圈与领奖台记录，记录每一次突破。')


class ControlCenter:
    def __init__(self,root=None,hud=None):
        # Closed Tcl interpreters can remain in widget cycles. Reclaim them on
        # their GUI thread before another image worker can trigger collection.
        import gc
        gc.collect()
        self.root=root or tk.Tk();self.hud=hud;self.closing=False;self.attached=hud is not None
        self.data_path=ROOT;self.form_drafts={};
        self.simulator=SIMULATOR
        from simulator_profiles import profile
        self.profile=profile(self.simulator);self.capabilities=self.profile.capabilities
        from control_context import BrowseMemory
        self.browsing=BrowseMemory();self.guide_page=None;self.guide_state={};self.tasks=BackgroundTasks();self.items=[];self.scan_generation=0;self.scanning=False;self.page=0
        import i18n
        i18n.load(ROOT/'interface_settings.json')
        control_theme.load(ROOT/'interface_settings.json')
        self.root.title(tr(window_title(self.profile)));self.root.configure(bg=T.BG)
        self.root.protocol('WM_DELETE_WINDOW',self.hide if self.attached else self.request_close)
        from race_model import read_json
        self.reference_settings=read_json(ROOT/'reference_settings.json',{})
        self.reference_kind=tk.StringVar(self.root,value=self.reference_settings.get('kind','fastest'))
        self.reference_on=tk.BooleanVar(self.root,value=bool(self.reference_settings.get('enabled',False)))
        self.reference_auto=tk.BooleanVar(self.root,value=bool(self.reference_settings.get('automatic',True)))
        self.reference_locked=tk.BooleanVar(self.root,value=bool(self.reference_settings.get('locked',False)))
        self.engine=SimpleNamespace(lock=threading.Lock(),reference=None,aligner=None)
        self.status=tk.StringVar(self.root,value=tr('就绪 · 记录仅保存在本机'))
        from recent_session import RecentSession
        from shortcut_service import ShortcutService
        self.recent=RecentSession(ROOT);shared_shortcuts=getattr(hud,'shortcuts',None);self.owns_shortcuts=shared_shortcuts is None
        self.shortcuts=shared_shortcuts or ShortcutService(ROOT,lambda:self.hud if self.active() else None,self.show,lambda text:self.status.set(tr(text)))
        if shared_shortcuts is not None:self.shortcuts.notify=lambda text:self.status.set(tr(text))
        from control_palette import Palette
        from control_shortcut_sheet import ShortcutSheet
        self.palette=Palette(self);self.shortcut_sheet=ShortcutSheet(self)
        self.build_shell()
        branding.apply(self.root)
        # Bind to this toplevel only, leaving the HUD's high-rate event loop alone.
        self.root.bind('<MouseWheel>',self.wheel)
        self.root.bind('<Control-f>',self.focus_search)
        # Ctrl+K reaches any page, action, setting or guide entry by typing.
        for sequence in ('<Control-k>','<Control-K>'):self.root.bind(sequence,self.palette.toggle)
        # F1 lists every in-app shortcut; game hotkeys stay one click away.
        self.root.bind('<F1>',self.shortcut_sheet.toggle)
        # Ctrl+1–7 follow the numbered rail entries. Keyboard page changes
        # commit instantly: repeated shortcuts must never wait on motion.
        from control_motion import keyboard_action
        self.visible_pages=page_ids()
        page_actions={}
        for number,index in enumerate(self.visible_pages,1):
            action=lambda _,i=index:(keyboard_action(self.root,lambda:self.request_page(i)),'break')[1]
            self.root.bind(f'<Control-Key-{number}>',action);page_actions[str(number)]=action
        install_mac_keys(self.root,self.request_close,lambda:self.request_page(2),pages=page_actions);install_touchpad(self.root)
        self.show_page(1 if offline_only() else 0);backdrop(self.root)
        from control_repaint import Presentation
        self.presentation=Presentation(self.root);self.root._stintrix_presentation=self.presentation
        self.job=self.root.after(50,self.tick)
        self.repair_windows_entry()

    def configure_styles(self):
        style=ttk.Style(self.root);style.theme_use('clam')
        style.configure('Scope.Treeview',background=T.CARD,fieldbackground=T.CARD,foreground=T.FG)
        style.configure('Scope.Treeview.Heading',background=T.FIELD,foreground=T.MUTED)
        style.map('Scope.Treeview',background=[('selected',T.SELECT)],foreground=[('selected',T.FG)])
        style.configure('Lab.TCombobox',fieldbackground=T.FIELD,background=T.FIELD,foreground=T.FG,arrowcolor=T.MUTED,padding=7,borderwidth=0,font=(T.FONT,10))
        style.configure('TCombobox',fieldbackground=T.FIELD,background=T.FIELD,foreground=T.FG,arrowcolor=T.MUTED)
        style.map('TCombobox',fieldbackground=[('readonly',T.FIELD)],foreground=[('readonly',T.FG)],selectbackground=[('readonly',T.SELECT)],selectforeground=[('readonly',T.FG)])
        for kind in ('Entry','Spinbox'):
            for name,value in (('background',T.FIELD),('foreground',T.FG),('insertBackground',T.FG)):
                self.root.option_add('*'+kind+'.'+name,value)
        style.configure('Lab.Vertical.TScrollbar',background=T.EDGE,troughcolor=T.BG,borderwidth=0,arrowsize=0,width=px(self.root,7))
        style.layout('Lab.Vertical.TScrollbar',[('Vertical.Scrollbar.trough',{'sticky':'ns','children':[('Vertical.Scrollbar.thumb',{'expand':1,'sticky':'nswe'})]})])
        style.map('Lab.Vertical.TScrollbar',background=[('active',T.ACCENT)])
        style.configure('Lab.Horizontal.TScrollbar',background=T.EDGE,troughcolor=T.CARD,borderwidth=0,arrowsize=0,width=px(self.root,7))
        style.layout('Lab.Horizontal.TScrollbar',[('Horizontal.Scrollbar.trough',{'sticky':'ew','children':[('Horizontal.Scrollbar.thumb',{'expand':1,'sticky':'nswe'})]})])
        style.map('Lab.Horizontal.TScrollbar',background=[('active',T.ACCENT)])
        style.map('Lab.TCombobox',fieldbackground=[('readonly',T.FIELD)],foreground=[('readonly',T.FG)],selectbackground=[('readonly',T.FIELD)],selectforeground=[('readonly',T.FG)])
        self.root.option_add('*TCombobox*Listbox.background',T.FIELD);self.root.option_add('*TCombobox*Listbox.foreground',T.FG)
        self.root.option_add('*TCombobox*Listbox.selectBackground',T.SELECT)
    def build_shell(self):
        self.configure_styles()
        self.page_titles=PAGES;self.page_subtitles=SUBTITLES
        if self.profile.catalogue=='official':
            self.page_subtitles=(*SUBTITLES[:2],'配置输入采样、HUD 刷新与练习赛记录。','共享赛事选择，管理归档、无损存储和报告重试。','查看赛道布局与官方线路图。','按品牌与车型组别筛选官方图片。','赛道最快圈与纪录履历，保留每一次突破。')
        if offline_only():
            self.page_titles=(*PAGES[:2],'离线偏好设置',*PAGES[3:])
            self.page_subtitles=(*self.page_subtitles[:2],'主题、语言与本机资料库；分析数据不会写入应用程序。',*self.page_subtitles[3:])
        self.visible_pages=page_ids()
        self.shell=Shell(self.root,[self.page_titles[i] for i in self.visible_pages],self.request_page,self.status,self.toggle_theme,self.toggle_language,self.palette.toggle,page_ids=self.visible_pages)
        self.scroll=self.shell.scroll;self.content=self.shell.content;self.content_item=self.shell.item
        self.title=self.shell.title;self.subtitle=self.shell.subtitle
        from control_pages import PageDeck
        self.pages=PageDeck(self,self.shell.content)
        from control_simulator import install
        install(self)
    def toggle_theme(self):self.set_theme('light' if T.mode=='dark' else 'dark')

    def set_theme(self,mode):
        if mode==T.mode:return
        try:control_theme.save(ROOT/'interface_settings.json',mode)
        except (OSError,ValueError) as error:self.status.set(tr('主题未保存：') + str(error));return
        previous=T.mode
        control_theme.set_mode(mode)
        self.configure_styles()
        selector=getattr(self.root,'_stintrix_active_select',None)
        if selector:selector.close(False)
        control_theme.recolor(self.root,previous)
        self.shell.refresh_brand()
        self.shell.theme_var.set(T.mode)
        gallery=getattr(self,'evo_gallery',None)
        if gallery is not None and gallery.winfo_exists() and gallery.state.get('detail'):gallery.refresh()
        backdrop(self.root)
        if self.active():self.hud.apply_theme()
        video=getattr(self,'video_window',None)
        if video is not None and video.winfo_exists():video.video_wizard.refresh_palette()

    def toggle_language(self):
        import i18n
        target='en' if i18n.language=='zh' else 'zh'
        try:i18n.save(ROOT/'interface_settings.json',target)
        except (OSError,ValueError) as error:self.status.set(tr('语言未保存：')+str(error));return
        self.rebuild_interface()
        self.root.title(tr(window_title(self.profile)))
        self.status.set(tr('就绪 · 记录仅保存在本机'))
        i18n.refresh(self.root)

    def rebuild_interface(self):
        from control_view_state import rebuild_interface
        return rebuild_interface(self)

    def label(self,parent,text,size=10,color=None,bold=False):
        return Label(parent,text='' if isinstance(text,tk.Variable) else text,textvariable=text if isinstance(text,tk.Variable) else None,
            bg=parent.cget('bg'),fg=color or T.FG,font=(T.FONT,size,'bold' if bold else 'normal'),anchor='w',justify='left')

    def card(self,title,subtitle='',parent=None,compact=False):
        card=GlassCard(parent or self.content,compact=compact)
        if parent:parent.add(card)
        else:card.pack(fill='x',pady=(0,px(self.root,18)))
        body=card.body
        if title:body.heading=self.label(body,title,14,T.FG,True);body.heading.pack(anchor='w',pady=(0,5))
        if subtitle:
            label=self.label(body,subtitle,9,T.MUTED);label.pack(fill='x',pady=(0,px(self.root,14)))
            label.bind('<Configure>',lambda e:label.configure(wraplength=max(100,e.width)))
        return body

    def button(self,parent,text,command,primary=False,width=140):
        from control_video_widgets import Action
        button=Action(parent,text,command,width,primary);button.pack(side='left',padx=(0,px(self.root,9)),pady=4);return button

    def row(self,parent):
        row=tk.Frame(parent,bg=parent.cget('bg'));row.pack(fill='x',pady=5);return row

    def choice(self,parent,label,var,choices,command=None,labels=None):
        row=self.row(parent);caption=self.label(row,label,10,T.MUTED);caption.pack(side='left')
        box=Select(row,textvariable=var,values=choices,state='readonly',width=26,labels=labels)
        box.pack(side='right',padx=4);box.bind('<<ComboboxSelected>>',lambda _:command() if command else None)
        row.stacked=False
        def layout(event):
            stacked=event.width<caption.winfo_reqwidth()+box.winfo_reqwidth()+px(row,14)
            if stacked==row.stacked:return
            row.stacked=stacked;caption.pack_forget();box.pack_forget()
            if stacked:
                caption.pack(anchor='w',pady=(0,4));box.pack(fill='x',padx=4)
            else:
                caption.pack(side='left');box.pack(side='right',padx=4)
        row.bind('<Configure>',layout)
        return box

    def wheel(self,event):
        if str(event.widget).startswith(str(self.content)) and not isinstance(event.widget,(ttk.Treeview,ttk.Combobox,Select)):
            import sys
            self.shell.scroller.add(-wheel_steps(event)*px(self.root,20 if sys.platform=='darwin' else 65))
            return 'break'

    def show(self):
        self.root.deiconify();self.root.lift();self.root.focus_force()
    def hide(self):self.root.withdraw()
    def active(self):
        return self.hud is not None and not self.hud.closing and self.hud.root.winfo_exists()

    def request_page(self,index):
        if offline_only() and index==0:index=1
        for overlay in (getattr(self,'palette',None),getattr(self,'shortcut_sheet',None)):
            if overlay is not None:overlay.close(False)
        self.pages.request(index)

    def show_page(self,index,progressive=False):
        from control_view_state import show_page
        return show_page(self,index,progressive)

    def records_page(self):
        from control_records import show
        show(self)

    def tracks_page(self):
        from control_guide import show
        show(self,'tracks')

    def cars_page(self):
        from control_guide import show
        show(self,'cars')

    def run_page(self):
        from control_run_state import setup,refresh as refresh_display
        try:initial=setup(self)
        except (OSError,ValueError):
            from hud_layouts import defaults
            initial=defaults()
        body=self.card('',compact=True)
        if self.simulator=='ac_evo':
            self.label(body,'AC EVO · 紧凑仪表、实际干预标记、有效圈对比与个人纪录已适配。',9,T.MUTED).pack(fill='x',pady=(0,8))
        from control_feedback import ConnectionFeedback
        live_row=self.row(body);live_row.pack_configure(pady=0);self.run_primary_row=live_row;self.connection_feedback=ConnectionFeedback(live_row);self.connection_feedback.pack(side='left',padx=(0,6));self.connection_feedback.set('waiting')
        self.live_label=self.label(live_row,'等待启动',11,T.ACCENT);self.live_label.pack(side='left')
        self.recording_detail=self.label(body,'',9,T.MUTED)
        self.start_button=self.button(live_row,'▶  启动记录',self.start,True,160);self.stop_button=self.button(live_row,'停止并保存',self.stop_hud,False,140)
        # One primary control: start while idle, stop-and-save while a HUD records.
        for button in (self.stop_button,self.start_button):button.pack_forget()
        (self.stop_button if self.active() else self.start_button).pack(side='right',padx=(8,0),pady=2)
        def arrange_primary(event,label=self.live_label,start=self.start_button,stop=self.stop_button):
            if all(w.winfo_exists() for w in (label,start,stop)):label.configure(wraplength=max(100,event.width-sum(b.winfo_reqwidth() for b in (start,stop) if b.winfo_manager())-px(label,48)))
        live_row.bind('<Configure>',arrange_primary)
        self.run_layout_summary=self.label(body,'',9,T.MUTED);self.run_layout_summary.pack(fill='x',pady=1)
        self.run_layout_summary.bind('<Configure>',lambda e:self.run_layout_summary.configure(wraplength=max(100,e.width)))
        import recording_visibility
        self.silent_mode=tk.BooleanVar(self.root,value=getattr(self.hud,'silent_recording',recording_visibility.load(ROOT/'recording_visibility.json')))
        row=self.row(body)
        row.pack_configure(pady=0)
        Switch(row,'静默记录 · 隐藏全部 HUD',self.silent_mode,self.set_silent_recording,compact=True).pack(side='left')
        from control_layouts import show as layouts
        from control_shortcuts import show as shortcuts
        self.button(row,'HUD 布局',lambda:layouts(self),False,145)
        self.button(row,'全局快捷键',lambda:shortcuts(self),False,135)
        self.demo_button=self.button(row,'演示模式',lambda:self.start(True),False,110)
        # Live HUD controls join this row only while a HUD runs; idle, the demo
        # takes their place, so nothing sits disabled waiting to be useful.
        self.live_actions=[self.button(row,'鼠标穿透 / 解锁',lambda:self.hud_action('toggle_clickthrough'),False,172),self.button(row,'性能诊断',lambda:self.hud_action('show_diagnostics'),False,130)]
        for button in self.live_actions:button.flow_hidden=True
        self.run_tools_row=row
        def arrange_tools(event,tools=row):
            if not tools.winfo_exists():return
            from control_flow import lines,place
            gap=px(tools,8);children=[child for child in tools.winfo_children() if child.winfo_exists() and not getattr(child,'flow_hidden',False)]
            for child in tools.winfo_children():child.pack_forget();child.place_forget()
            # The compact switch shares a centre line with the taller buttons.
            tools.pack_propagate(False);tools.configure(height=place(lines(children,event.width,gap),event.width,gap))
        row.bind('<Configure>',arrange_tools)
        policy=self.label(body,self.profile.recording_hint,9,T.MUTED);policy.pack(fill='x');policy.bind('<Configure>',lambda e:policy.configure(wraplength=max(100,e.width)))
        grid=CardGrid(self.content);grid.pack(fill='x')
        body=self.card('油门 / 刹车 / 转向','输入通道、显示模式与波形窗口',grid)
        self.mode=tk.StringVar(self.root,value=initial['mode'])
        modes={'标准面板':'normal','纯净 · 仅曲线':'curves','纯净 · 曲线 + 踏板 / 方向盘':'controls'}
        self.mode_label=tk.StringVar(self.root,value=next(k for k,v in modes.items() if v==self.mode.get()))
        current=sampling.load_settings(ROOT/'settings.json');self.channel=tk.StringVar(self.root,value='游戏过滤后' if current['input_channel']=='filtered' else '原始输入')
        self.window=tk.StringVar(self.root,value=initial['window'])
        # Small, frequent HUD choices: every option visible, one click applies.
        segmented=lambda label,variable,values,command,captions,titles=None:segmented_row(body,label,variable,values,command,captions,titles)
        self.run_choices={
            'mode':segmented('显示模式',self.mode_label,list(modes),lambda:self.set_hud('mode',modes[self.mode_label.get()]),{'标准面板':'标准','纯净 · 仅曲线':'仅曲线','纯净 · 曲线 + 踏板 / 方向盘':'曲线 + 踏板'},{name:name for name in modes}),
            'channel':segmented('输入通道',self.channel,['原始输入','游戏过滤后'],lambda:self.set_hud('channel','filtered' if self.channel.get()=='游戏过滤后' else 'raw'),dict(zip(('原始输入','游戏过滤后'),self.profile.input_labels))),
            'window':segmented('波形窗口',self.window,['5','10','20'],lambda:self.set_hud('window',self.window.get()),{'5':'5 秒','10':'10 秒','20':'20 秒'})}
        # The card's spare height shows what these choices draw; it grows to
        # match the panel card beside it, so both columns end on one line.
        from control_hud_preview import HudPreview
        from control_layouts import show as open_layouts
        self.hud_preview=HudPreview(body,self.mode_label,self.window,modes,lambda:open_layouts(self));self.hud_preview.pack(fill='both',expand=True,pady=(px(body,10),px(body,2)))
        body=self.card('EVO 驾驶信息' if self.capabilities.driving_instruments else '附加遥测面板','按需开启，让比赛视野保持清爽',grid)
        if self.capabilities.driving_instruments:
            import evo_hud
            self.evo_hud_vars={}
            for key,title in (('instruments','紧凑仪表条 · 挡位 / 转速'),('assists','ABS / TC / ESC 实际干预标记')):
                var=tk.BooleanVar(self.root,value=evo_hud.load(ROOT)[key]);self.evo_hud_vars[key]=var
                def change(k=key,v=var):
                    try:
                        if self.active():self.hud.set_evo_hud(k,v.get())
                        else:evo_hud.save(ROOT,k,v.get())
                    except (OSError,ValueError) as error:self.status.set(str(error))
                Switch(body,title,var,change).pack(fill='x',pady=2)
            hint=self.label(body,'显示开关不影响完整保存；彩色刻度表示已采集的实际介入，? 表示未知。',9,T.MUTED);hint.pack(fill='x',pady=(4,8))
            hint.bind('<Configure>',lambda e:hint.configure(wraplength=max(100,e.width)))
        if self.simulator=='ac_evo':self.label(body,'轮胎与策略面板暂未适配',10,T.MUTED).pack(fill='x',pady=(0,8))
        vehicle=vehiclelab.load_settings(ROOT/'vehicle_settings.json');end=endurance.load_settings(ROOT/'endurance_settings.json')
        switches=[]
        for module,key,title in [('vehicle','tyres','四轮轮胎温度 / 胎压 / 胎况'),('vehicle','strategy','燃油、虚拟能量与续航策略'),('endurance','pit','进站计时与补给'),('endurance','stint','Stint 长距离节奏'),('endurance','weather','天气与赛道趋势')]:
            if self.capabilities.driving_instruments and not self.capabilities.panel(key):continue
            value=tk.BooleanVar(self.root,value=initial['panels'][key]['visible'])
            switch=Switch(body,title,value,lambda m=module,k=key,v=value:self.set_panel_visibility(m,k,v.get()));switch.pack(fill='x',pady=2)
            if not self.capabilities.panel(key):switch.configure(state='disabled')
            switches.append((module,key,value))
        self.panel_visibility_switches=switches

        channel=self.channel
        def refresh_run():
            channel.set('游戏过滤后' if sampling.load_settings(ROOT/'settings.json')['input_channel']=='filtered' else '原始输入')
            refresh_display(self)
        self.refresh_run_configuration=lambda:refresh_display(self)
        refresh_display(self)
        self.pages.on_resume(refresh_run)

        # A one-time setup: one compact row, details only on request.
        body=self.card('',compact=True);head=self.row(body);head.pack_configure(pady=0)
        self.label(head,'Windows 快捷启动',11,T.FG,True).pack(side='left')
        from control_sections import Disclosure
        options=Disclosure(body,self,'windows-entry','管理启动入口',header=head).body
        hint=self.label(options,'添加后可在开始菜单 / Windows 搜索中输入 Stintrix 或 LMU 启动；迁移程序后可再次更新入口',9,T.MUTED);hint.pack(fill='x')
        hint.bind('<Configure>',lambda e:hint.configure(wraplength=max(100,e.width)))
        row=self.row(options)
        self.button(row,'添加 / 更新开始菜单',self.register_app,False,185)
        self.button(row,'移除开始菜单入口',lambda:self.register_app(True),False,170)
        self.label(options,'可在 Windows 搜索结果中右键固定到开始菜单或任务栏。',9,T.MUTED).pack(anchor='w',pady=6)

    def register_app(self,remove=False):
        from windows_integration import register
        self.work(lambda:register(remove,verify=True),self.registration_result)

    def registration_result(self,result):
        if result['removed']:self.status.set(tr('开始菜单入口已移除，程序和数据仍保留'))
        elif result.get('recognized'):self.status.set(tr('Windows 应用目录已识别 LMU Stintrix · 可从开始菜单打开'))
        else:self.status.set(tr('快捷方式已更新，但 Windows 尚未列出应用；可稍后再次更新入口'))

    def repair_windows_entry(self):
        if offline_only():return
        from windows_integration import needs_repair,register
        if self.attached or not needs_repair():return
        def done(result,error):
            if self.closing:return
            if error:self.status.set(tr('开始菜单入口未更新：') + error)
            else:self.registration_result(result)
        self.run_background(lambda:register(verify=True),done)

    def start(self,demo=False):
        if offline_only():return
        from control_run_actions import start
        return start(self,demo)

    def set_silent_recording(self):
        from control_run_actions import set_silent_recording
        return set_silent_recording(self)

    def stop_hud(self):
        from control_run_actions import stop_hud
        return stop_hud(self)

    def hud_action(self,method):
        from control_run_actions import hud_action
        return hud_action(self,method)

    def set_hud(self,key,value):
        from control_run_actions import set_hud
        return set_hud(self,key,value)

    def set_panel_visibility(self,module,key,value):
        from control_run_actions import set_panel_visibility
        return set_panel_visibility(self,module,key,value)

    def run_background(self,work,done):return self.tasks.submit(work,done)
    def work(self,work,done=None):
        self.status.set(tr('正在处理…'));work_key=object();self.shell.status_feedback.busy(work_key)
        def finish(result,error):
            self.shell.status_feedback.busy(work_key,False)
            if error:self.status.set(tr('操作未完成：') + error);messagebox.showerror('Stintrix',error,parent=self.root)
            else:
                self.status.set(tr('已完成 · 数据保存在本机'))
                if done:done(result)
        self.run_background(work,finish)

    def sessions(self,body,multiple=False,checkboxes=False,selection_buttons=True,compact_actions=False,height=9,filter_toggle=True,fill=False):
        from control_search import SearchField
        row=self.row(body);self.label(row,'搜索',10,T.MUTED).pack(side='left',padx=(0,8));self.search=tk.StringVar(self.root);entry=SearchField(row,textvariable=self.search,command=self.populate)
        self.search_target=entry;entry.pack(side='left',fill='x',expand=True)
        filters=self.button(row,'筛选条件',lambda:self.review_filters.toggle_filters(),False,112) if filter_toggle else None
        self.review_refresh=self.button(row,'刷新记录',self.refresh,False,112)
        from control_review_filters import ReviewFilters
        self.review_filters=ReviewFilters(body,self)
        self.search.set(self.browsing.query(self.page))
        self.tree=SessionList(body,columns=('date','type','result','mode','track','car','lap','layout','class','trust','quality'),height=height,selectmode='extended' if multiple else 'browse',checkboxes=checkboxes)
        self.tree.simulator=self.simulator
        for key,title,width in [('date','时间（UTC）',180),('type','阶段',76),('result','完赛名次',90),('mode','参赛方式',90),('track','赛道',200),('car','车辆',175),('lap','最快圈',132),('layout','具体布局',180),('class','组别',85),('trust','成绩依据',110),('quality','数据质量',135)]:
            self.tree.heading(key,text=title);self.tree.column(key,width=px(self.root,width),minwidth=px(self.root,60),stretch=key in ('track','car'))
        from control_table_preferences import install as table_preferences
        table_preferences(self,self.tree,'review',self.review_filters)
        self.tree.pack(fill='x',pady=(6,2))
        # What is selected reads directly above the rows, at a constant height.
        from control_selection import SelectionLine
        self.selection_line=SelectionLine(body);self.selection_line.pack(fill='x',pady=(8,0),before=self.tree)
        if filters is not None:self.review_filters.attach(filters,self.tree)
        self.tree.bind('<Double-1>',lambda _:self.report('review.html'))
        self.tree.bind('<Return>',lambda _:self.report('review.html'))
        if checkboxes:
            self.selected_count=tk.StringVar(self.root,value='已选 0 场')
            self.tree.selection_changed=self.update_selection_count
            if selection_buttons:self.selection_buttons(body)
            self.tree.bind('<<TreeviewSelect>>',lambda _:self.update_selection_count())
        if not compact_actions:
            actions=self.row(body)
            from control_event_filters import edit_note
            self.button(actions,'收藏与标签',lambda:self.with_selection(lambda v:edit_note(self,v[0],self.refresh)),False,135)
            from control_split_checks import show as split_checks
            self.button(actions,'检查疑似拆分',lambda:split_checks(self),False,155)
        # Trust, completeness and lap counts join the selection line above the list.
        self.event_detail=tk.StringVar(self.root)
        self.tree.bind('<<TreeviewSelect>>',lambda _:self.describe_selection(),add='+')
        if fill:self.fill_list(self.tree)
        tree=self.tree
        def refresh_key(_=None):
            if tree.winfo_exists() and tree.winfo_ismapped():self.refresh();return 'break'
        token=self.root.bind('<F5>',refresh_key,add='+')
        tree.bind('<Destroy>',lambda e:self.root.unbind('<F5>',token) if e.widget is tree else None,add='+')
        self.refresh()

    def focus_search(self,_=None):
        guide=getattr(self,'guide_page',None)
        if guide is not None and guide.search_entry.winfo_exists():return guide.focus_search()
        gallery=getattr(self,'evo_gallery',None)
        if gallery is not None and gallery.winfo_exists() and gallery.winfo_ismapped():return gallery.focus_search()
        if self.page==2:
            search=getattr(self,'settings_search',None)
            if search is not None and search.field.winfo_exists():return search.focus()
        field=getattr(self,'search_target',None)
        if field is not None and field.winfo_exists() and field.winfo_ismapped():
            field.focus_set();field.entry.selection_range(0,'end');return 'break'

    def describe_selection(self):
        if not hasattr(self,'event_detail'):return
        ids=self.tree.selection() if self.tree else ()
        if not ids:
            self.event_detail.set('');preview=getattr(self,'evo_preview',None)
            if preview is not None and preview.winfo_exists():preview.clear()
            self.show_selection_line();return
        preview=getattr(self,'evo_preview',None)
        if preview is not None and preview.winfo_exists():preview.select(self.items[int(ids[0])])
        from event_catalog import normalize
        from event_filters import TRUST,QUALITY
        f=normalize(self.items[int(ids[0])]);scope=tr('最快圈条件') if f.get('condition_scope')=='fastest_lap' else tr('已记录有效圈条件')
        value=tr(TRUST.get(f.get('trust'),'未知'))+' · '+tr(QUALITY.get(f.get('quality'),'完整性未知'))+' · '+scope
        if f.get('valid_laps') is not None:value+=' · '+tr('有效圈')+' '+str(f['valid_laps'])
        if f.get('gap_count') is not None:value+=' · '+tr('采样缺口')+' '+str(f['gap_count'])
        if f.get('trust')=='observed':value+=' · '+tr('末次观测排名不是确认完赛成绩')
        self.event_detail.set(value);self.show_selection_line()

    def show_selection_line(self):
        line=getattr(self,'selection_line',None)
        if line is None or not line.winfo_exists():return
        from control_selection import facts
        line.set(*facts(self))

    def selection_buttons(self,body):
        row=self.row(body)
        self.button(row,'全选当前列表',lambda:self.tree.selection_set(self.tree.get_children()),False,128)
        self.button(row,'清除选择',lambda:self.tree.selection_set(()),False,108)
        self.label(row,self.selected_count,9,T.MUTED).pack(side='right',padx=8)

    def update_selection_count(self):
        self.update_toolbar()
        if self.tree and self.tree.checkboxes:self.selected_count.set(tr('已选 {selected} 场 / 列表 {total} 场').format(selected=len(self.tree.selection()),total=len(self.tree.get_children())))

    def refresh(self):
        from library import inventory
        if self.tree and self.tree.winfo_exists() and not self.tree.get_children():self.tree.set_empty('正在读取赛事记录…')
        generation=self.scan_generation
        def done(result,error):
            if self.closing or generation!=self.scan_generation:return
            if error:
                self.status.set(error)
                if self.tree and self.tree.winfo_exists():self.tree.set_empty('记录读取失败，可重试。','重新加载',self.refresh)
                return
            selected={self.items[int(i)]['folder'] for i in self.tree.selection()} if self.tree else set()
            self.items=result;chosen=[str(i) for i,item in enumerate(result) if item['folder'] in selected]
            self.recent.adopt(result)
            restoring=getattr(self,'restore_list_context',False)
            if restoring and not selected:chosen=self.browsing.selected(self.page,result)
            if hasattr(self,'review_filters') and self.review_filters.winfo_exists():self.review_filters.update_options(result)
            self.populate(chosen)
            if restoring:
                self.browsing.restore(self,True);self.restore_list_context=False
                if self.page==1 and getattr(self,'session_location',None) and self.tree.selection():self.session_locator.reveal(self.tree.selection()[0])
            self.status.set(f"{len(result)}{tr(' 场本地记录 · 旧 Practice 记录仍保留')}")
        self.run_background(lambda:inventory(ROOT),done)

    def populate(self,selected=None):
        from track_names import display,search_text
        from record_presentation import session_type
        if self.tree is None or not self.tree.winfo_exists():return
        selected=self.tree.selection() if selected is None else selected;query=self.search.get().strip().casefold();rows=[]
        from review_filters import filtered
        try:matches=self.review_filters.pairs(self.items,query)
        except ValueError as error:self.status.set(tr(str(error)));return
        locator=getattr(self,'session_locator',None) if self.page==1 else None;located=None
        if locator is not None:matches,located=locator.augment(matches)
        if located is not None:selected=[located]
        for i,value in matches:
            time=value.get('time_s');lap=f'{int(time//60)}:{time%60:06.3f}' if time else '—'
            from event_catalog import normalize
            from event_filters import TRUST,QUALITY
            from track_names import layout
            f=normalize(value)
            from event_result_label import label as result_label
            rows.append((str(i),(value['date'][:19].replace('T',' '),session_type(value['session_type']),result_label(f),tr(__import__('race_mode').LABELS[value.get('race_mode','unknown')]),display(value['track']),value['vehicle'],lap,layout(f['track'],f['layout'],f.get('length_m')),f.get('vehicle_class',''),tr(TRUST.get(f.get('trust'),'未知')),tr(QUALITY.get(f.get('quality'),'完整性未知')))))
        self.tree.marked,self.tree.gaps=self.personal_bests(gaps=True)
        from control_event_filters import replace_rows
        replace_rows(self.tree,rows,selected)
        if located is not None:locator.reveal(located)
        if not self.items:self.tree.set_empty('还没有赛事记录；完成比赛或导入赛事包后会显示在这里。','导入赛事包',self.import_package)
        elif not rows:self.tree.set_empty('没有符合当前搜索或筛选条件的记录。','清除搜索与筛选',self.review_filters.reset)
        if hasattr(self,'review_filters') and self.review_filters.winfo_exists():self.review_filters.count.set(len(rows))
        self.update_selection_count()
        self.describe_selection()
        fit=getattr(self.tree,'fill_list',None)
        if fit:fit()

    def personal_bests(self,gaps=False):
        """Row ids holding the best lap for a circuit layout and car driven more than once.

        With gaps, also each other session's distance to that best, in seconds.
        """
        from event_catalog import normalize
        groups={}
        for index,value in enumerate(self.items):
            time=value.get('time_s')
            if not time or value.get('status') in ('recording','write_error'):continue
            f=normalize(value);groups.setdefault((f.get('track') or value.get('track'),f.get('layout'),value.get('vehicle')),[]).append((time,index))
        groups=[entries for entries in groups.values() if len(entries)>1]
        marked={str(min(entries)[1]) for entries in groups}
        if not gaps:return marked
        distance={}
        for entries in groups:
            best=min(entries)[0]
            for time,index in entries:
                if str(index) not in marked:distance[str(index)]=time-best
        return marked,distance

    def fill_list(self,table):
        """A long list uses the window's height instead of stopping above an empty band.

        Short lists hug their rows (plus one, at least four); the height
        follows window resizes and every search or filter result.
        """
        state={'job':None}
        def resize():
            state['job']=None
            if not table.winfo_exists() or not table.winfo_ismapped():return
            self.root.update_idletasks()
            top=table.viewport.winfo_rooty()-self.scroll.winfo_rooty()+self.scroll.canvasy(0)
            available=self.scroll.winfo_height()-top-px(self.root,40)
            count=len(table.order)
            # A long list ends exactly at the window edge (a partly shown row
            # says there is more); a short one hugs its rows.
            if count and count+1<=available/table.rowheight:target=round(max(4,count+1)*table.rowheight)
            else:target=round(max(4*table.rowheight,available))
            if int(table.viewport.cget('height'))!=target:table.viewport.configure(height=target)
        def schedule(_=None):
            if state['job'] is None and table.winfo_exists():state['job']=table.after_idle(resize)
        token=self.scroll.bind('<Configure>',schedule,add='+')
        table.bind('<Destroy>',lambda e:self.scroll.unbind('<Configure>',token) if e.widget is table else None,add='+')
        table.fill_list=schedule;schedule()

    def selection(self,count=1):
        chosen=[self.items[int(i)] for i in self.tree.selection()] if self.tree else []
        if count is None and not chosen:raise ValueError('请至少勾选一场赛事记录')
        if count is not None and len(chosen)!=count:raise ValueError(f'请选择 {count} 场赛事记录')
        if any(v['status'] in ('recording','write_error') for v in chosen):raise ValueError('请等记录完整保存后再操作')
        return chosen

    def with_selection(self,action,count=1):
        try:action(self.selection(count))
        except (ValueError,OSError) as error:self.status.set(str(error))

    def report(self,name):
        def action(items):
            folder=Path(items[0]['folder']);path=folder/name
            if name.endswith('.png'):
                from control_report_images import show
                show(self,folder,name)
            elif path.is_file():open_path(path)
            else:
                from session_reports import make_report
                self.work(lambda:(make_report(folder),str(path))[1],open_path)
        self.with_selection(action)

    def review_page(self):
        body=self.card('')
        from control_session_location import SessionLocation
        self.session_locator=SessionLocation(self,body)
        self.sessions(body,True,True,False,compact_actions=True,fill=True)

    def clear_toolbar(self):
        if not hasattr(self,'shell'):return
        from control_flow import uninstall
        uninstall(self.shell.action_host)
        bar=getattr(self,'form_bar',None)
        if bar and bar.winfo_exists():bar.destroy()
        self.form_bar=None
        for child in self.shell.action_host.winfo_children():child.destroy()
        self.shell.action_host.pack_forget();self.review_actions={}

    def install_toolbar(self):
        from control_toolbar import install
        self.clear_toolbar();install(self)

    def update_toolbar(self):
        from control_toolbar import update
        update(self)

    def toggle_reference(self):
        if self.active():self.hud.reference_on.set(not self.hud.reference_on.get());self.hud.apply_reference()
        else:self.status.set(tr('请先启动 HUD'))

    def selected_laps(self):
        from control_lap_pair import show
        try:
            chosen=self.selection(None) if self.tree and self.tree.selection() else []
            show(self,ROOT,[Path(v['folder']) for v in chosen[:2]])
        except (ValueError,OSError) as error:self.status.set(str(error))

    def compare_sessions(self):
        if self.simulator=='ac_evo':
            from control_evo_compare import fastest
            self.with_selection(lambda items:fastest(self,items),None);return
        from laps import write_compare
        def action(items):
            if any(not v['fastest_file'] for v in items):raise ValueError('这两场赛事需要已有最快完整圈')
            def build():
                from lap_comparison import export_pair
                return export_pair(ROOT,[(v['folder'],v['lap']) for v in items],ASSETS/'compare.html')['comparison']
            def opened(page):
                from control_lap_pair import remember_result
                remember_result(self,ROOT,page);open_path(page)
            self.work(build,opened)
        self.with_selection(action,2)

    def library(self,initial=None):
        selected=initial if initial is not None else [v['folder'] for v in self.selection(None)] if self.tree and self.tree.selection() else []
        from management import show_library
        from session_reports import render_review,make_report
        return show_library(self,ROOT,render_review,make_report,selected)

    def apply_reference(self):
        from storage import atomic_json
        self.reference_settings.update(enabled=self.reference_on.get(),automatic=self.reference_auto.get(),
            locked=self.reference_locked.get(),kind=self.reference_kind.get())
        atomic_json(ROOT/'reference_settings.json',self.reference_settings)
        self.status.set(tr('参考圈已保存，启动 HUD 时自动载入'))

    def form(self,body,module,specs,choices=()):
        from control_forms import build
        yield from build(self,body,module,specs,choices)

    def update_module(self,module,values):
        control_settings.apply(module,values,self.hud if self.active() else None);self.status.set(tr('设置已保存') + (tr('并应用到 HUD') if self.active() else tr('，启动 HUD 时生效')))
        if module=='sampling':
            from control_sampling_intro import refresh
            refresh(self)

    def settings_page(self):
        self.settings_anchors=[];self.settings_index=[];self.form_panels={}
        from control_sampling_intro import build as intro
        body,practice_switch=intro(self);self.settings_anchors.append(('接口',body))
        from control_settings_search import register as search_setting,register_routes
        search_setting(self,'practice_recording','记录练习赛',practice_switch,'记录策略');register_routes(self,practice_switch)
        yield
        body=self.card('输入采样与 HUD 刷新','完整采样按原始精度保存；有效更新频率由游戏与硬件决定')
        self.settings_anchors.append(('输入采样',body))
        from control_settings_search import FORMS,TYRES
        yield from self.form(body,'sampling',*map(list,FORMS['sampling']))
        body=self.card('轮胎、燃油与能量策略')
        self.settings_anchors.append(('车辆策略',body))
        yield from self.form(body,'vehicle',*map(list,FORMS['vehicle']))
        from control_profile import show
        profile_button=self.button(self.row(body),'车型轮胎阈值',lambda:show(self),False,160)
        from control_settings_search import register as search_setting
        for key,label in TYRES:
            search_setting(self,key,label,profile_button,'vehicle',lambda k=key:show(self,target=k))
        def opacity():
            from control_layouts import show as layouts
            from control_validation import reveal
            window=layouts(self);window.update_idletasks();field=window.layout_errors.fields['opacity'][0];reveal(field);field.focus_set()
        search_setting(self,'opacity','HUD 透明度 / 不透明度',profile_button,'界面布局',opacity)
        body=self.card('进站、Stint 与天气')
        self.settings_anchors.append(('耐力与天气',body))
        yield from self.form(body,'endurance',list(FORMS['endurance'][0]))

    def data_page(self):
        from control_data import build
        build(self)

    def storage_operation(self,kind):
        from control_transfers import storage_operation
        return storage_operation(self,kind)

    def compress_selected(self):
        from control_transfers import compress_selected
        return compress_selected(self)

    def export_package(self):
        from control_transfers import export_package
        return export_package(self)

    def import_package(self):
        from control_transfers import import_package
        return import_package(self)

    def import_native(self):
        from control_transfers import import_native
        return import_native(self)

    def tick(self):
        if self.closing:return
        if self.owns_shortcuts:self.shortcuts.drain()
        if self.closing:return
        from control_recent_session import update as update_recent
        update_recent(self)
        from control_hud_stop import retire,saving
        retire(self);self.update_toolbar()
        navigation=getattr(getattr(self,'shell',None),'navigation',None);live=self.active()
        if navigation is not None and navigation.winfo_exists() and getattr(navigation,'live',False)!=live:navigation.live=live;navigation.paint()
        import time
        now=time.monotonic()
        if self.page==0 and now-getattr(self,'run_summary_at',0)>=1:
            self.run_summary_at=now;self.refresh_run_configuration()
        if not self.closing and now-getattr(self,'report_retry_at',0)>=5:
            self.report_retry_at=now
            from report_worker import pending,resume_pending
            from runtime_activity import busy as capture_busy
            if not self.tasks.busy and not capture_busy():
                self.run_background(lambda:resume_pending(ROOT),lambda result,error:None)
        if self.closing:return
        for done,result,error in self.tasks.completions():
            try:done(result,error)
            except (OSError,ValueError,tk.TclError) as e:self.status.set(tr('操作未完成：') + str(e))
        if not self.active() and not self.tasks.busy and now-getattr(self,'cache_budget_at',0)>60:
            self.cache_budget_at=now
            from cache_budget import enforce
            self.run_background(lambda:enforce(ROOT),lambda result,error:None)
        if self.page==0 and saving(self):
            from control_hud_stop import detail
            self.connection_feedback.set('saving');self.live_label.configure(text=tr(detail(self.hud)))
            self.recording_detail.configure(text=tr('HUD 已关闭；可继续浏览，后台保存完成后可重新启动记录。'))
            if not self.recording_detail.winfo_manager():self.recording_detail.pack(fill='x',pady=(0,5),before=self.run_primary_row)
        elif self.page==0 and self.hud and self.hud.root.winfo_exists():
            engine=self.hud.engine;poll,fresh=engine.actual_rates()
            from recording_status import snapshot
            recording=snapshot(engine)
            self.connection_feedback.set('recording' if recording['state']=='recording' else 'connected' if recording['state'] in ('live','saved') else 'waiting')
            text=tr(recording['text'])
            if self.live_label.cget('text')!=text:self.live_label.configure(text=text)
            detail=f"{engine.status}{tr(' · 读取 ')}{poll:.0f}{tr(' / 有效 ')}{fresh:.0f} Hz"
            if recording['gaps'] is not None:detail+=' · '+tr('采样缺口')+' '+str(recording['gaps'])
            if self.recording_detail.cget('text')!=detail:self.recording_detail.configure(text=detail)
            if not self.recording_detail.winfo_manager():self.recording_detail.pack(fill='x',pady=(0,5),before=self.run_primary_row)
            values=[(self.channel,'游戏过滤后' if self.hud.input_channel.get()=='filtered' else '原始输入'),
                (self.mode_label,{'normal':'标准面板','curves':'纯净 · 仅曲线','controls':'纯净 · 曲线 + 踏板 / 方向盘'}[self.hud.hud_mode.get()]),
                (self.window,self.hud.window.get())]
            for variable,value in values:
                if variable.get()!=value:variable.set(value)
            for module,key,variable in getattr(self,'panel_visibility_switches',[]):
                settings=self.hud.vehicle_settings if module=='vehicle' else self.hud.endurance_settings
                value=self.hud.layout_visibility.get(key,settings[key+'_enabled']) if self.capabilities.panel(key) else False
                if variable.get()!=value:variable.set(value)
        elif self.page==0:
            saved=getattr(self,'last_recording_status',None)
            folder=getattr(self,'last_report_folder',None)
            if folder:
                from report_state import latest
                from recording_status import report_snapshot
                value=latest(folder)
                if value:saved=report_snapshot(value['state']);self.last_recording_status=saved
            self.connection_feedback.set('connected' if saved and saved['state']=='saved' else 'waiting')
            text=tr(saved['text']) if saved else tr('已停止') if self.hud else tr('等待启动')
            if getattr(self,'hud_stopped',False):text=tr('HUD 已关闭')+(' · '+tr(saved['text']) if saved else '')
            self.live_label.configure(text=text)
            if hasattr(self,'recording_detail'):self.recording_detail.pack_forget()
        self.job=self.root.after(100,self.tick)

    def request_close(self,after_close=None):
        from control_confirm import close_editors
        from control_forms import close_forms
        from control_batch import running
        job=running(self)
        if job is not None and not job.allow_exit():return
        hud=self.hud if self.active() else None
        job=running(hud) if hud is not None else None
        if job is not None and not job.allow_exit():return
        video=getattr(self,'video_window',None)
        if video is not None and video.winfo_exists() and not video.video_wizard.allow_exit():return
        from control_renderer import close_draft
        def finish():close_draft(self,lambda:close_forms(self,lambda:self.close(after_close)))
        close_editors(self,lambda:close_editors(hud,finish) if hud is not None else finish())

    def close(self,after_close=None):
        if not self.closing:
            self.after_close=after_close
            if self.owns_shortcuts:self.shortcuts.close()
            video=getattr(self,'video_window',None)
            if video is not None and video.winfo_exists():video.video_wizard.cancel.set()
            history=getattr(self,'video_history_window',None)
            if history is not None and history.winfo_exists():history.history_state['cancel'].set()
            self.closing=True;self.shell.detach();self.presentation.cancel();self.pages.cancel_request();self.pages.cancel_build();self.tasks.close();self.root.after_cancel(self.job);self.shell.motion.cancel();self.shell.navigation.motion.cancel();self.shell.scroller.cancel()
            loader=getattr(self,'report_image_loader',None)
            if loader is not None:loader.close()
            if self.active():self.hud.close()
        if self.tasks.busy or (self.hud and not getattr(self.hud,'stopped',False) and self.hud.root.winfo_exists()):self.root.after(50,self.close);return
        for _ in self.tasks.completions():pass
        variables=[value for value in vars(self).items() if isinstance(value[1],tk.Variable)]
        forms=[value for page in self.pages.pages.values() for form in page.forms.values() for value in form.values()]
        self.clear_toolbar();self.pages.dispose();self.shell.navigation.command=None
        selector=getattr(self,'simulator_selector',None)
        if selector is not None and selector.winfo_exists():selector.destroy()
        self.root._brand_images=[]
        for name,variable in variables:
            variable.__del__();variable._tk=None
        for variable in forms:
            if variable._tk is not None:variable.__del__();variable._tk=None
        host=getattr(self,'hud_host_root',None);self.root.destroy()
        if host is not None and host.winfo_exists():host.destroy()
        callback=getattr(self,'after_close',None)
        self.after_close=None
        if callback:callback()


def show_attached(hud):
    center=getattr(hud,'control_center',None)
    if center and center.root.winfo_exists():center.show()
    else:
        center=ControlCenter(tk.Toplevel(hud.root),hud);hud.control_center=center
