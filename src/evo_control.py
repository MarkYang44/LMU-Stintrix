"""EVO first-phase UI: shared input HUD and storage, explicit capability limits."""
import tkinter as tk
from pathlib import Path
from control_theme import T
from control_widgets import Switch
from control_flow import install
from i18n import tr


def builder_for(app,index,fallback):
    if index==1:return lambda:review_page(app)
    if index==2:return lambda:settings_page(app)
    if index==3:return lambda:data_page(app)
    if index==6:
        from control_records import show
        return lambda:show(app)
    if index in (4,5):return lambda:gallery(app,'tracks' if index==4 else 'cars')
    return fallback


def unavailable(app):
    body=app.card('AC EVO · 首期适配','已开放输入 HUD、快捷键、完整输入保存、无损压缩、归档和后台任务。')
    app.label(body,'赛道指南、车型图鉴、个人纪录和圈分析暂未适配。',11,T.MUTED).pack(anchor='w',pady=10)
    app.button(app.row(body),'查看 EVO 赛事记录',lambda:app.request_page(1),True,190)


def review_page(app):
    body=app.card('AC EVO 赛事记录','这里只显示 AC EVO 数据；布局与圈速独立保存，双击打开记录概览。',compact=True)
    app.sessions(body,True,True,False,compact_actions=True)
    preview=app.card('赛道与车辆','官方图片保存在本机；选中赛事即可预览对应赛道和车型。',compact=True)
    app.evo_preview=RecordPreview(preview,app)


def settings_page(app):
    import recording_policy
    app.settings_anchors=[];app.settings_index=[];app.form_panels={}
    body=app.card('AC EVO 数据接口','只读连接游戏共享内存；物理输入与仪表输入分别保存。')
    app.label(body,'计时赛和正赛自动保存；练习与巡航可按需记录。',10,T.MUTED).pack(fill='x')
    practice=tk.BooleanVar(app.root,value=recording_policy.load(app.data_path));app.evo_practice=practice
    def policy():
        recording_policy.save(app.data_path,practice.get())
        if app.active():app.hud.engine.practice_enabled=practice.get()
    Switch(body,'记录练习赛',practice,policy).pack(fill='x',pady=6)
    app.button(app.row(body),'数据接口检查',lambda:interface(app),False,155)
    body=app.card('输入采样与 HUD 刷新','完整采样按原始精度保存；有效更新频率由游戏与硬件决定')
    app.label(body,'建议 HUD 使用手动 60 Hz；输入采样率独立保留。',10,T.MUTED).pack(fill='x',pady=4)
    app.settings_anchors.append(('输入采样',body))
    yield from app.form(body,'sampling',[(k,label) for k,label in [('fixed_hz','固定采样 / Hz'),('min_hz','动态最低 / Hz'),('max_hz','动态最高 / Hz'),('change_pct_s','升频变化阈值 / % 每秒'),('hold_s','降频延迟 / 秒'),('brake_pct','刹车升频阈值 / %'),('draw_hz','手动绘制 / Hz')]],
        [('mode','采样模式',['fixed','dynamic']),('draw_mode','绘制模式',['sync','manual'])])


def interface(app):
    from tkinter import messagebox
    live=dict(getattr(app.hud.engine,'interface_status',{})) if app.active() else None
    def work():
        if live:return live
        import time
        from acevo import SharedReader
        reader=SharedReader()
        try:
            deadline=time.monotonic()+.25
            while time.monotonic()<deadline:
                if reader.read() is not None:break
                time.sleep(.005)
            return reader.interface_status()
        finally:reader.close()
    def done(value,error):
        if app.closing:return
        text=tr('等待 AC EVO 遥测；请启动游戏并进入驾驶。') if error else '\n\n'.join([
            tr('游戏版本标记')+': '+str(value.get('game_version') or tr('未知')),
            tr('玩家通道')+': '+tr('可用' if value.get('channels_available') else '等待玩家遥测'),
            tr('有效更新帧数')+': '+str(value.get('frames',0)),
            tr('仅打开既有共享内存和事件；游戏数据映射始终只读。')])
        messagebox.showinfo('AC EVO',text,parent=app.root)
    app.run_background(work,done)


def data_page(app):
    from control_data import build
    return build(app)


def toolbar(app):
    if app.page in (4,5):
        host=app.shell.action_host;host.pack(fill='x',before=app.shell.scroll.master,pady=(0,8));install(host)
        app.button(host,'下载 / 更新官方图片',lambda:download_art(app),False,195)
        return
    if app.page not in (1,):return
    host=app.shell.action_host;host.pack(fill='x',before=app.shell.scroll.master,pady=(0,8));install(host)
    app.review_actions={'open':app.button(host,'打开记录概览',lambda:app.report('review.html'),True,160)}
    for key,label,name in [('laps','圈速单','圈速单.png'),('journal','赛事日志','比赛日志.png')]:
        app.review_actions[key]=app.button(host,label,lambda n=name:app.report(n),False,110)
    app.review_actions['compare']=app.button(host,'圈 A / 圈 B',lambda:app.compare_sessions() if len(app.tree.selection())>2 else app.selected_laps(),False,140)
    from control_delete import remove
    from control_danger import Danger
    from control_list_context import install as context_menu
    from control_action_menu import ActionMenu,MenuAction
    count=lambda:len(app.tree.selection()) if app.tree else 0
    single=lambda:count()==1;chosen=lambda:count()>0
    button=app.button(host,'更多操作 ▾',lambda:menu.toggle(),False,130)
    from control_event_filters import edit_note
    from control_participation import edit as edit_mode,eligible
    from control_maintenance import reports,offline_ready
    from control_evo_exports import fastest_csv
    from control_evo_lap_overview import show as lap_overview
    from control_evo_compare import last_multi,open_multi
    actions=[MenuAction('records','个人赛道记录',lambda:app.request_page(6),'查看与对比'),
        MenuAction('lap-overview','圈速总览与节奏',lambda:app.with_selection(lambda items:lap_overview(app,items[0]['folder'])),'查看与对比',lambda:single() and offline_ready(app),visible=single),
        MenuAction('compare-best','跨场最快圈对比',app.compare_sessions,'查看与对比',
            lambda:2<=count()<=6 and offline_ready(app) and all(app.items[int(i)].get('fastest_file') for i in app.tree.selection()),
            '选择 2–6 场同布局赛事，直接比较各场最快有效圈',visible=lambda:2<=count()<=6),
        MenuAction('fastest','查看最快圈',lambda:app.report('fastest_lap.html'),'查看与对比',single,visible=single),
        MenuAction('folder','打开赛事目录',lambda:app.with_selection(lambda v:open_directory(app,v[0])),'查看与对比',single,visible=single),
        MenuAction('multi-reopen','打开上次多圈对比',lambda:open_multi(app),'最近对比',lambda:last_multi(app) is not None,'打开已生成的文件，保留当前选择与 A/B 记忆'),
        MenuAction('note','收藏与标签',lambda:app.with_selection(lambda v:edit_note(app,v[0],app.refresh)),'整理与管理',single,visible=single),
        MenuAction('mode','更正参赛方式',lambda:app.with_selection(lambda v:edit_mode(app,v,app.refresh),None),'整理与管理',
            lambda:chosen() and all(eligible(app,app.items[int(i)]) for i in app.tree.selection()),'支持多选；默认仅更正未知记录'),
        MenuAction('library','完整记录管理',app.library,'整理与管理'),
        MenuAction('reports','报告任务与分步重试',lambda:app.with_selection(lambda items:reports(app,[item['folder'] for item in items]),None),'整理与管理',chosen),
        MenuAction('fastest-csv','导出最快圈 CSV（可多选）',lambda:app.with_selection(lambda items:fastest_csv(app,items),None),'整理与管理',lambda:chosen() and offline_ready(app)),
        MenuAction('export','导出赛事包',app.export_package,'整理与管理',chosen),
        MenuAction('import','导入赛事包',app.import_package,'整理与管理'),
        MenuAction('refresh','刷新记录',app.refresh,'整理与管理'),
        MenuAction('copy-cell','复制此单元格',lambda:app.tree.copy_cell(),'复制',chosen,visible=chosen),
        MenuAction('copy-rows','复制选中行',lambda:app.tree.copy_rows(),'复制',chosen,visible=chosen),
        MenuAction('all','全选当前列表',lambda:app.tree.selection_set(app.tree.get_children()),'列表与选项',lambda:bool(app.tree and app.tree.get_children())),
        MenuAction('clear','清除选择',lambda:app.tree.selection_set(()),'列表与选项',chosen,visible=chosen)]
    from control_table_layouts import actions as column_actions
    actions.extend(column_actions(app.tree))
    delete=Danger(host,'删除选中记录',lambda:remove(app),145);delete.pack(side='left',padx=(0,6))
    app.review_actions['delete']=delete
    actions.append(MenuAction('delete','删除选中记录',lambda:remove(app),'赛事管理',chosen,danger=True))
    menu=ActionMenu(button,actions,'赛事操作',lambda:app.selected_count.get())
    app.review_menu=menu;context_menu(app.tree,menu,app.update_selection_count)
    app.update_toolbar()


def update_compare(app,button):
    from control_maintenance import offline_ready
    from control_widgets import px
    selected=app.tree.selection() if app.tree else ();count=len(selected)
    title='跨场最快圈对比' if 3<=count<=6 else '圈 A / 圈 B';caption=(title,tr(title))
    if getattr(button,'evo_compare_caption',None)!=caption:
        button.evo_compare_caption=caption
        button.configure(text=title,width=max(px(button,140),button.font.measure(caption[1])+px(button,36)))
        button.master.event_generate('<Configure>',width=max(1,button.master.winfo_width()))
    ready=bool(app.items) and count<=6 and offline_ready(app)
    if count>=3:ready=ready and all(app.items[int(key)].get('fastest_file') for key in selected)
    if button.enabled!=ready:button.configure(state='normal' if ready else 'disabled')


def open_directory(app,entry):
    import os
    from race_mode_overrides import relative
    from race_model import read_json
    from simulators import accepts
    folder=Path(entry['folder']).resolve();relative(app.data_path,folder)
    if not folder.is_dir() or not accepts(app.data_path,read_json(folder/'session.json',{})):
        raise ValueError('请选择当前游戏的本机赛事记录')
    os.startfile(str(folder))


class RecordPreview(tk.Frame):
    def __init__(self,parent,app):
        super().__init__(parent,bg=T.CARD);self.pack(fill='x');self.app=app;self.key=None;self.images=[]
        self.caption=app.label(self,'选择赛事以查看布局和车辆。',10,T.MUTED);self.caption.pack(fill='x')
        self.panels=tk.Frame(self,bg=T.CARD);self.panels.pack(fill='x')
        app.button(app.row(self),'下载 / 更新官方图片',lambda:download_art(app,self),False,190)
    def clear(self):
        if self.key is None:return
        self.key=None;self.entry=None;self.caption.configure(text=tr('选择赛事以查看布局和车辆。'))
        for child in self.panels.winfo_children():child.destroy()
    def select(self,entry,force=False):
        key=(entry['track'],entry.get('track_layout',''),entry['vehicle'])
        if key==self.key and not force:return
        self.key=key;self.entry=entry
        for child in self.panels.winfo_children():child.destroy()
        from evo_art import item
        from guide_cards import Picture
        self.caption.configure(text=' · '.join(v for v in key if v))
        for kind,name in [('tracks',key[0]),('cars',key[2])]:
            art=item(kind,name,key[1],self.app.data_path)
            panel=tk.Frame(self.panels,bg=T.CARD);panel.pack(side='left',fill='both',expand=True,padx=5)
            if art:Picture(panel,self.app,art)
            else:self.app.label(panel,'图片尚未下载或该型号暂无匹配官方图。',10,T.MUTED).pack(fill='x',pady=18)


def download_art(app,preview=None):
    if getattr(app,'evo_art_busy',False):return
    if app.active():app.status.set(tr('请先停止 HUD，再下载官方图片。'));return
    app.evo_art_busy=True;app.status.set(tr('正在下载官方车辆与赛道图片…'))
    def work():
        from evo_art import download
        return download(app.data_path)
    def done(value,error):
        app.evo_art_busy=False
        if app.closing:return
        app.status.set(str(error) if error else tr('官方图片已缓存：{count} 张，失败 {errors} 张。').format(count=value['downloaded'],errors=len(value['errors'])))
        if preview is not None and preview.winfo_exists() and getattr(preview,'entry',None):preview.select(preview.entry,True)
        gallery_state=getattr(app,'evo_gallery_refresh',None)
        if gallery_state and gallery_state[0].winfo_exists() and gallery_state[0].winfo_ismapped():gallery_state[1]()
    app.run_background(work,done)


def gallery(app,kind):
    from evo_gallery import Gallery
    app.evo_gallery=Gallery(app,kind)


def note(app):
    from control_event_filters import edit_note
    app.with_selection(lambda items:edit_note(app,items[0],app.refresh))
