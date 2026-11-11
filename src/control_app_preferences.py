"""App-wide preferences that close the Settings page: theme, language, hotkeys, Start menu."""
import sys
import tkinter as tk
from control_theme import T
from control_widgets import segmented_row,px


def row(app,parent,title,hint):
    """One preference line: what it is and why on the left, its control on the right."""
    line=tk.Frame(parent,bg=parent.cget('bg'));line.pack(fill='x',pady=px(parent,6))
    text=tk.Frame(line,bg=line.cget('bg'));text.pack(side='left',fill='x',expand=True)
    app.label(text,title,10,T.MUTED).pack(fill='x')
    note=app.label(text,hint,9,T.MUTED);note.pack(fill='x',pady=(px(parent,2),0))
    note.bind('<Configure>',lambda e:note.configure(wraplength=max(100,e.width)))
    actions=tk.Frame(line,bg=line.cget('bg'));actions.pack(side='right',padx=(px(parent,12),0))
    return actions


def build(app):
    """The same theme and language state as the rail toggles, plus system entries."""
    from platform_runtime import offline_only
    from control_settings_search import register
    body=app.card('界面与系统','主题、语言、全局快捷键与开始菜单入口；修改后立即生效')
    anchors=getattr(app,'settings_anchors',None)
    if anchors is not None:anchors.append(('界面与系统',body))
    shell=app.shell
    theme=segmented_row(body,'界面主题',shell.theme_var,['dark','light'],app.toggle_theme,{'dark':'深色','light':'浅色'},{'dark':'深色主题','light':'浅色主题'})
    language=segmented_row(body,'界面语言',shell.language_var,['zh','en'],app.toggle_language,{'zh':'中文','en':'EN'},{'zh':'中文界面','en':'English interface'})
    register(app,'theme','界面主题',theme,'界面与系统')
    register(app,'language','界面语言',language,'界面与系统')
    app.app_preference_controls=dict(theme=theme,language=language)
    if offline_only():return body
    from control_shortcuts import show as shortcuts
    actions=row(app,body,'全局快捷键','在游戏中控制 HUD 的按键组合，录入后保存即可使用。')
    edit=app.button(actions,'编辑快捷键',lambda:shortcuts(app),False,120,compact=True);edit.pack_configure(padx=0)
    register(app,'shortcuts','全局快捷键',edit,'界面与系统',lambda:shortcuts(app))
    app.app_preference_controls['shortcuts']=edit
    if sys.platform=='win32':
        actions=row(app,body,'Windows 开始菜单','添加后可在开始菜单或 Windows 搜索中输入 Stintrix 或 LMU 启动；迁移程序后再次更新。')
        add=app.button(actions,'添加 / 更新',app.register_app,False,110,compact=True)
        remove=app.button(actions,'移除入口',lambda:app.register_app(True),False,100,compact=True);remove.pack_configure(padx=0)
        register(app,'start_menu','Windows 开始菜单',add,'界面与系统')
        app.app_preference_controls.update(start_menu=add,remove_start_menu=remove)
    return body
