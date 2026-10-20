"""Fixed page actions, with unavailable operations clearly disabled."""
import tkinter as tk
from control_theme import T
from i18n import tr


def install(app):
    host=app.shell.action_host
    if app.page==1:
        host.pack(fill='x',before=app.shell.scroll.master,pady=(0,8))
        app.review_actions={'open':app.button(host,'打开赛事复盘',lambda:app.report('review.html'),True,150),
            'compare':app.button(host,'圈 A / 圈 B 选择器',app.selected_laps,False,165)}
        menu=tk.Menu(host,tearoff=False,bg=T.CARD,fg=T.FG,activebackground=T.SELECT,activeforeground=T.FG)
        from control_event_filters import edit_note
        from control_split_checks import show as split_checks
        from control_delete import remove
        commands=[('查看圈速单',lambda:app.report('圈速单.png')),('查看比赛日志',lambda:app.report('比赛日志.png')),
            ('查看最快圈',lambda:app.report('fastest_lap.html')),('跨场最快圈对比',app.compare_sessions),('导出赛事包',app.export_package),
            ('收藏与标签',lambda:app.with_selection(lambda v:edit_note(app,v[0],app.refresh))),('检查疑似拆分',lambda:split_checks(app)),
            ('完整记录管理',app.library),('全选当前列表',lambda:app.tree.selection_set(app.tree.get_children())),('清除选择',lambda:app.tree.selection_set(()))]
        for label,command in commands:menu.add_command(label=tr(label),command=command)
        menu.add_separator();menu.add_command(label=tr('选择实时参考圈'),command=lambda:app.hud_action('select_reference'))
        menu.add_command(label=tr('开启 / 关闭参考'),command=app.toggle_reference)
        menu.add_separator();menu.add_command(label=tr('删除选中赛事'),command=lambda:remove(app),foreground=T.RED)
        def popup():
            count=len(app.tree.selection()) if app.tree else 0;chosen=count>0;active=app.active()
            for index in [0,1,2,5]:menu.entryconfigure(index,state='normal' if count==1 else 'disabled')
            for index in [4,14]:menu.entryconfigure(index,state='normal' if chosen else 'disabled')
            menu.entryconfigure(3,state='normal' if count==2 else 'disabled')
            for index in [11,12]:menu.entryconfigure(index,state='normal' if active else 'disabled')
            try:menu.tk_popup(button.winfo_rootx(),button.winfo_rooty()+button.winfo_height())
            finally:menu.grab_release()
        button=app.button(host,'更多操作',popup,False,110);app.review_menu=menu
        app.label(host,app.selected_count,9,T.MUTED).pack(side='left',padx=4)
        update(app)
    elif app.page==2:
        host.pack(fill='x',before=app.shell.scroll.master,pady=(0,8))
        for label,target in getattr(app,'settings_anchors',[]):
            def jump(body=target):
                app.root.update_idletasks();y=body.winfo_rooty()-app.content.winfo_rooty()-20
                app.scroll.yview_moveto(max(0,y)/max(1,app.content.winfo_height()))
            app.button(host,label,jump,False,110)


def update(app):
    for key,button in getattr(app,'review_actions',{}).items():
        if not button.winfo_exists():continue
        ready=bool(app.tree and len(app.tree.selection())==1) if key=='open' else bool(getattr(app,'items',[]))
        state='normal' if ready else 'disabled'
        if button.cget('state')!=state:button.configure(state=state)
    if app.page==0:
        for name,ready in [('start_button',not app.active()),('stop_button',app.active()),('demo_button',not app.active())]:
            button=getattr(app,name,None)
            if button is not None and button.winfo_exists() and button.enabled!=ready:button.configure(state='normal' if ready else 'disabled')
        for button in getattr(app,'live_actions',[]):
            if button.winfo_exists() and button.enabled!=app.active():button.configure(state='normal' if app.active() else 'disabled')
