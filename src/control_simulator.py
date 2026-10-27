"""One persistent game selector; restart only after all existing close guards finish."""
import tkinter as tk
from control_fields import Select
from simulators import GAMES,SHORT,launch
from i18n import tr


def install(app):
    app.shell.breadcrumb.pack_forget()
    app.simulator_choice=tk.StringVar(app.root,value=app.simulator)
    from simulator_icons import load
    from control_widgets import px
    box=Select(app.shell.breadcrumb.master,textvariable=app.simulator_choice,values=list(GAMES),
        labels={key:SHORT[key]+' · '+name for key,name in GAMES.items()},images=load(app.root,px(app.root,26)),width=33)
    box.pack(side='left');app.simulator_selector=box
    from control_tooltip import Tooltip
    tip=Tooltip(box)
    box.bind('<Enter>',lambda _:tip.request('simulator',tr('切换模拟器；自动停止保存后重新打开控制中心'),box.winfo_rootx(),box.winfo_rooty()+box.winfo_height()),add='+')
    box.bind('<Leave>',lambda _:tip.hide(),add='+')
    box.bind('<Destroy>',lambda _:tip.hide(),add='+')
    def change(_=None):
        target=app.simulator_choice.get();app.simulator_choice.set(app.simulator)
        if target==app.simulator or app.closing:return
        from paths import base_data_directory
        base=base_data_directory()
        app.status.set(tr('正在保存并切换模拟器…'))
        app.request_close(after_close=lambda:launch(base,target))
    box.bind('<<ComboboxSelected>>',change)
