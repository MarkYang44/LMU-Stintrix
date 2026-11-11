"""F1 keyboard sheet: every in-app shortcut at a glance, grouped by where it works.

Like the command palette it floats inside the main window and opens without
motion; Esc, F1 or a click outside closes it and returns focus. Game hotkeys
for the HUD stay in their own window, one click away.
"""
import tkinter as tk
from control_theme import T
from i18n import tr
from control_widgets import px

GROUPS=(
    ('全局',(('Ctrl K','快速跳转：页面、操作、设置、赛道与车型'),('Ctrl 1–7','切换到左侧对应页面'),('Ctrl F','聚焦当前页的搜索框'),('F1','打开或关闭快捷键一览'))),
    ('列表',(('↑ ↓','移动选中行'),('Enter','打开复盘或完整圈曲线'),('Ctrl A','全选当前列表'),('Ctrl C','复制选中行'),('Ctrl Shift C','复制当前单元格'),('F5','刷新赛事与纪录列表'))),
    ('输入与选择',(('Esc','清空搜索框，或关闭浮层'),('← →','切换分段选项与分区标签'),('Home End','跳到第一个或最后一个选项'),('Ctrl S','保存当前参数模块'))),
)


class ShortcutSheet:
    def __init__(self,app):self.app=app;self.frame=None;self.previous=None;self.click=None

    @property
    def opened(self):return self.frame is not None and self.frame.winfo_exists()

    def toggle(self,_=None):
        if self.opened:self.close()
        else:self.open()
        return 'break'

    def open(self):
        app=self.app;root=app.root
        if self.opened:return
        palette=getattr(app,'palette',None)
        if palette is not None:palette.close(False)
        self.previous=root.focus_get()
        self.frame=frame=tk.Frame(root,bg=T.BG,takefocus=True);halo=px(root,6)
        edge=tk.Frame(frame,bg=T.EDGE);edge.pack(fill='both',expand=True,padx=halo,pady=halo)
        inner=tk.Frame(edge,bg=T.CARD);inner.pack(fill='both',expand=True,padx=1,pady=1)
        head=tk.Frame(inner,bg=T.CARD);head.pack(fill='x',padx=px(root,20),pady=(px(root,16),px(root,6)))
        tk.Label(head,text=tr('键盘快捷键'),bg=T.CARD,fg=T.FG,font=(T.FONT,13,'bold'),anchor='w').pack(side='left')
        tk.Label(head,text=tr('F1 / Esc 关闭'),bg=T.CARD,fg=T.MUTED,font=(T.FONT,9),anchor='e').pack(side='right')
        body=tk.Frame(inner,bg=T.CARD);body.pack(fill='x',padx=px(root,20))
        # Keys keep their natural column; descriptions start right after the widest key.
        body.columnconfigure(0,weight=0);body.columnconfigure(1,weight=1)
        row=0
        from platform_runtime import offline_only,page_ids,shortcut_hint
        for group,items in GROUPS:
            tk.Label(body,text=tr(group),bg=T.CARD,fg=T.ACCENT,font=(T.FONT,9,'bold'),anchor='w').grid(row=row,column=0,columnspan=2,sticky='w',pady=(px(root,12),px(root,4)));row+=1
            for keys,text in items:
                if offline_only() and keys=='Ctrl 1–7':keys='Ctrl 1–'+str(len(page_ids()))
                keys=shortcut_hint(keys)
                cell=tk.Frame(body,bg=T.CARD);cell.grid(row=row,column=0,sticky='w',pady=px(root,3))
                for key in keys.split(' '):
                    chip=tk.Frame(cell,bg=T.EDGE);chip.pack(side='left',padx=(0,px(root,4)))
                    tk.Label(chip,text=key,bg=T.FIELD,fg=T.FG,font=(T.MONO,9),padx=px(root,6),pady=1).pack(padx=1,pady=1)
                tk.Label(body,text=tr(text),bg=T.CARD,fg=T.FG,font=(T.FONT,10),anchor='w').grid(row=row,column=1,sticky='w',padx=(px(root,10),0));row+=1
        foot=tk.Frame(inner,bg=T.CARD);foot.pack(fill='x',padx=px(root,20),pady=(px(root,14),px(root,16)))
        tk.Label(foot,text=tr('macOS 可使用 Command 代替 Control。' if offline_only() else '游戏中控制 HUD 的按键在「设置 → 界面与系统」里设置。'),bg=T.CARD,fg=T.MUTED,font=(T.FONT,9),anchor='w').pack(side='left')
        def hotkeys():
            from control_shortcuts import show
            self.close(False);show(app)
        if not offline_only():self.hotkeys=app.button(foot,'全局快捷键',hotkeys,False,120);self.hotkeys.pack(side='right')
        for sequence in ('<Escape>','<F1>'):frame.bind(sequence,lambda _:(self.close(True),'break')[1])
        frame.bind('<Destroy>',self.dispose,add='+')
        self.click=root.bind('<Button-1>',self.outside,add='+')
        width=max(px(root,460),min(px(root,620),root.winfo_width()-px(root,120)))
        frame.place(in_=root,relx=.5,y=px(root,78),anchor='n',width=width);frame.lift();frame.focus_set()

    def outside(self,event):
        widget=event.widget
        while widget is not None:
            if widget is self.frame:return
            widget=getattr(widget,'master',None)
        self.close(False)

    def close(self,restore=True):
        if not self.opened:return
        previous=self.previous;self.frame.destroy()
        if restore and previous is not None:
            try:
                if previous.winfo_exists():previous.focus_set()
            except (tk.TclError,KeyError):pass

    def dispose(self,event):
        if event.widget is not self.frame:return
        if self.click:
            try:self.app.root.unbind('<Button-1>',self.click)
            except tk.TclError:pass
        self.click=None;self.frame=None
