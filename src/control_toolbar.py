"""Fixed page actions, with unavailable operations clearly disabled."""
import tkinter as tk
from control_theme import T
from i18n import tr
from control_widgets import px
from control_motion import keyboard_action
from simulator_profiles import profile


def install(app):
    old=getattr(app,'form_bar',None)
    if old and old.winfo_exists():old.destroy()
    app.form_bar=None
    host=app.shell.action_host
    host.pack_propagate(True)
    previous=getattr(app,'toolbar_layout_binding',None)
    if previous:
        widget,token=previous
        if widget.winfo_exists():widget.unbind('<Configure>',token)
        app.toolbar_layout_binding=None
    if app.page==0:
        from control_recent_session import install
        install(app)
    elif profile(getattr(app,'simulator','lmu')).catalogue=='official' and app.page in (1,4,5):
        from evo_control import toolbar
        toolbar(app)
    elif app.page==1:
        host.pack(fill='x',before=app.shell.scroll.master,pady=(0,8))
        app.review_actions={'open':app.button(host,'打开赛事复盘',lambda:app.report('review.html'),True,130),
            'laps':app.button(host,'圈速单',lambda:app.report('圈速单.png'),False,100),
            'journal':app.button(host,'比赛日志',lambda:app.report('比赛日志.png'),False,110),
            'compare':app.button(host,'圈 A / 圈 B',app.selected_laps,False,135)}
        from control_action_menu import ActionMenu,MenuAction
        from control_event_filters import edit_note
        from control_split_checks import show as split_checks
        from control_delete import remove
        from control_participation import edit as edit_mode,eligible
        count=lambda:len(app.tree.selection()) if app.tree else 0
        single=lambda:count()==1;any_selected=lambda:count()>0
        button=app.button(host,'更多操作 ▾',lambda:menu.toggle(),False,110)
        from control_danger import Danger
        delete=Danger(host,'删除选中记录',lambda:remove(app),145);delete.pack(side='left',padx=(0,6))
        app.review_actions['delete']=delete
        actions=[
            MenuAction('copy-cell','复制此单元格',lambda:app.tree.copy_cell(),'复制',any_selected,'Ctrl+Shift+C；复制当前单元格的完整文字',visible=any_selected),
            MenuAction('copy-rows','复制选中行',lambda:app.tree.copy_rows(),'复制',any_selected,'Ctrl+C；复制显示列，可粘贴到表格',visible=any_selected),
            MenuAction('fastest','查看最快圈',lambda:app.report('fastest_lap.html'),'查看与对比',single,'选择 1 场赛事，查看最快完整圈'),
            MenuAction('compare','跨场最快圈对比',app.compare_sessions,'查看与对比',lambda:count()==2,'选择 2 场同布局赛事进行对比'),
            MenuAction('export','导出赛事包',app.export_package,'整理与管理',any_selected,'可批量导出已选赛事，保留原始记录'),
            MenuAction('note','收藏与标签',lambda:app.with_selection(lambda v:edit_note(app,v[0],app.refresh)),'整理与管理',single,'选择 1 场赛事，编辑收藏、标签与备注'),
            MenuAction('mode','更正参赛方式',lambda:app.with_selection(lambda v:edit_mode(app,v,app.refresh),None),'整理与管理',lambda:any_selected() and all(eligible(app,app.items[int(i)]) for i in app.tree.selection()),'支持多选；默认仅更正未知记录'),
            MenuAction('split','检查疑似拆分',lambda:split_checks(app),'整理与管理',hint='检查是否存在同场拆分记录'),
            MenuAction('library','完整记录管理',app.library,'整理与管理',hint='打开完整记录管理窗口'),
            MenuAction('all','全选当前列表',lambda:app.tree.selection_set(app.tree.get_children()),'整理与管理',lambda:bool(app.tree and app.tree.get_children())),
            MenuAction('clear','清除选择',lambda:app.tree.selection_set(()),'整理与管理',any_selected),
            MenuAction('reference','选择实时参考圈',lambda:app.hud_action('select_reference'),'实时参考',app.active,'启动 HUD 后可选择实时参考圈',visible=app.active),
            MenuAction('toggle','开启 / 关闭参考',app.toggle_reference,'实时参考',app.active,'启动 HUD 后可切换参考状态',visible=app.active),
            MenuAction('delete','删除选中赛事',lambda:remove(app),'删除',any_selected,'仅处理已选赛事，执行前仍需确认',True)]
        from control_table_layouts import actions as column_actions
        layouts=column_actions(app.tree)
        for action in layouts:action.group='整理与管理'
        index=next(i for i,a in enumerate(actions) if a.key=='all');actions[index:index]=layouts
        menu=ActionMenu(button,actions,'赛事操作',lambda:app.selected_count.get());app.review_menu=menu
        label=app.label(host,app.selected_count,9,T.MUTED);label.pack(side='left',padx=4)
        buttons=[*[value for key,value in app.review_actions.items() if key!='delete'],button,delete]
        def layout(event):
            if event.widget is not host or not all(child.winfo_exists() for child in [*buttons,label]):return
            x=y=height=0;gap=px(host,6)
            for child in buttons:
                child.pack_forget();w=child.winfo_reqwidth();h=child.winfo_reqheight()
                if x and x+w>event.width:y+=height+gap;x=height=0
                child.place(x=x,y=y,width=min(event.width,w),height=h);x+=w+gap;height=max(height,h)
            label.pack_forget();label.place_forget()
            if event.width-x>=label.winfo_reqwidth():label.place(x=x,y=y+height/2,anchor='w');total=y+height
            else:
                label.place(x=0,y=y+height+gap,width=event.width);total=y+height+gap+label.winfo_reqheight()
            host.pack_propagate(False);host.configure(height=total)
        app.toolbar_layout_binding=(host,host.bind('<Configure>',layout))
        label.bind('<Configure>',lambda _:host.event_generate('<Configure>',width=host.winfo_width()))
        from control_list_context import install as context_actions
        context_actions(app.tree,menu,app.update_selection_count)
        update(app)
    elif app.page==3:
        browser=getattr(app,'data_browser',None)
        if browser is not None and browser.alive():browser.install_actions(host)
    elif app.page in (4,5) and app.guide_page is not None:
        app.guide_page.install_actions(host)
    elif app.page==6 and getattr(app,'personal_record_view','best')=='best':
        page=getattr(app,'record_loaders',{}).get('best')
        if page is not None and page.page is not None and page.page.alive():page.page.install_actions(host)
    elif app.page==2:
        from control_form_bar import FormBar
        app.form_bar=FormBar(app)
        host.pack(fill='x',before=app.shell.scroll.master,pady=(0,8))
        from control_settings_search import Search
        app.settings_search=Search(app,host)
        anchors=tk.Frame(host,bg=T.BG);anchors.pack(fill='x')
        for label,target in getattr(app,'settings_anchors',[]):
            def jump(body=target):
                module=getattr(body,'form_module',None)
                if module:app.form_bar.select(module)
                reveal=getattr(body,'reveal_anchor',None)
                if reveal:reveal()
                app.root.update_idletasks();y=body.winfo_rooty()-app.content.winfo_rooty()-20
                app.scroll.yview_moveto(max(0,y)/max(1,app.content.winfo_height()))
            app.button(anchors,label,jump,False,110)


def update(app):
    from control_maintenance import update as update_maintenance,busy as maintenance_busy
    update_maintenance(app)
    if app.page==3:
        browser=getattr(app,'data_browser',None)
        if browser is not None:browser.sync()
    for key,button in getattr(app,'review_actions',{}).items():
        if not button.winfo_exists():continue
        if key=='compare' and getattr(app,'simulator','lmu')=='ac_evo':
            from evo_control import update_compare
            update_compare(app,button);continue
        ready=bool(app.tree and len(app.tree.selection())==1) if key in ('open','laps','journal') else bool(app.tree and app.tree.selection()) if key=='delete' else bool(getattr(app,'items',[]))
        state='normal' if ready else 'disabled'
        if button.cget('state')!=state:button.configure(state=state)
    if app.page==0:
        from control_hud_stop import saving
        pending=saving(app)
        labels=[('start_button','▶  重新启动记录' if getattr(app,'hud_stopped',False) and not pending else '▶  启动记录'),('stop_button','正在保存…' if pending else '停止并保存')]
        for name,title in labels:
            button=getattr(app,name,None)
            if button is not None and button.winfo_exists() and button.label!=title:
                button.configure(text=title,width=max(px(button,160 if name=='start_button' else 140),button.font.measure(tr(title))+px(button,36)));button.master.event_generate('<Configure>',width=button.master.winfo_width())
        for name,ready in [('start_button',not app.active() and not pending and not maintenance_busy(app)),('stop_button',app.active()),('demo_button',not app.active() and not pending and not maintenance_busy(app))]:
            button=getattr(app,name,None)
            if button is not None and button.winfo_exists() and button.enabled!=ready:button.configure(state='normal' if ready else 'disabled')
        for button in getattr(app,'live_actions',[]):
            if button.winfo_exists() and button.enabled!=app.active():button.configure(state='normal' if app.active() else 'disabled')
