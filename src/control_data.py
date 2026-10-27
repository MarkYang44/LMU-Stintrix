"""Compact archive/storage tasks share one browser and reliable immediate preferences."""
import tkinter as tk
from control_theme import T
from control_fields import Select
from control_widgets import Switch
from control_flow import install
from control_sections import TaskSections,Disclosure
from control_immediate_save import ImmediateSave


def hint(app,parent,text):
    label=app.label(parent,text,9,T.MUTED);label.pack(fill='x',pady=4)
    label.bind('<Configure>',lambda e:label.configure(wraplength=max(100,e.width)));return label


def build(app):
    from simulator_profiles import profile
    game=profile(getattr(app,'simulator','lmu'));supported=game.capabilities
    items=([('video','视频分析')] if supported.video_analysis else [])+[('packages','赛事包'),('storage','报告与存储'),('renderer','外部生成器')]
    sections=TaskSections(app,items,'data_section');app.data_tasks=sections;outer=app.content
    try:
        if supported.video_analysis:
            app.content=sections.frames['video']
            body=app.card('视频提取油刹曲线','三种输入：普通 POV、距离与计时 HUD、视频与同圈遥测；估算结果单独保存')
            from control_video import show as video_analysis
            from control_video_results import show as recent_videos
            actions=app.row(body);install(actions);app.button(actions,'视频分析与标定',lambda:video_analysis(app,app.data_path),True,190);app.button(actions,'最近提取结果',lambda:recent_videos(app,app.data_path),False,170)
        app.content=sections.frames['packages'];body=app.card('',compact=True)
        import archive_preferences
        preferences=archive_preferences.load(app.data_path);app.archive_format=tk.StringVar(app.root,value='ZIP' if preferences['format']=='zip' else '7z');app.archive_verify=tk.BooleanVar(app.root,value=preferences['verify'])
        def save_archive(changes,draft):
            archive_preferences.save(app.data_path,draft['format'].lower(),False)
            return dict(format='ZIP' if archive_preferences.load(app.data_path)['format']=='zip' else '7z')
        row=app.row(body);app.label(row,'导出格式',10,T.MUTED).pack(side='left',padx=(0,8))
        box=Select(row,textvariable=app.archive_format,values=['ZIP','7z'],width=9);box.pack(side='left')
        details=Disclosure(body,app,'archive-details','赛事包说明',header=row)
        app.archive_save=ImmediateSave(app,body,dict(format=app.archive_format),save_archive,'archive');box.bind('<<ComboboxSelected>>',lambda _:app.archive_save.submit())
        hint(app,details.body,'每场一个包；相同版本重复导出复用已有文件，不执行内容校验')
        hint(app,details.body,'不计算文件哈希、不在导出后重读整个包；保留正常解压与安全路径处理。')
        packages=tk.Frame(body,bg=T.CARD);packages.pack(fill='x')
        app.content=sections.frames['storage'];selection=app.card('选择与处理赛事',compact=True)
        summary=tk.Frame(selection,bg=T.CARD);summary.pack(fill='x');storage=tk.Frame(selection,bg=T.CARD)
        body=app.card('无损节省磁盘空间','赛后无损存储完整采样与报告；保留图片质量，可导出或恢复 CSV',compact=True)
        from session_compression import enabled,column_enabled
        from cache_budget import limit
        app.storage_auto=tk.BooleanVar(app.root,value=enabled(app.data_path));app.storage_columnar=tk.BooleanVar(app.root,value=column_enabled(app.data_path));app.cache_limit=tk.StringVar(app.root,value=str(limit(app.data_path)))
        def save_storage(changes,draft):
            from storage import atomic_json
            from preference_error import read_object
            path=app.data_path/'storage_settings.json';settings=read_object(path)
            for key,value in changes.items():settings[key]=int(value) if key=='cache_limit_mb' else bool(value)
            atomic_json(path,settings)
            return dict(auto_compress=enabled(app.data_path),columnar=column_enabled(app.data_path),cache_limit_mb=str(limit(app.data_path)))
        app.storage_save=ImmediateSave(app,body,dict(auto_compress=app.storage_auto,columnar=app.storage_columnar,cache_limit_mb=app.cache_limit),save_storage,'storage')
        Switch(body,'赛后自动压缩',app.storage_auto,app.storage_save.submit).pack(fill='x',pady=3)
        Switch(body,'新赛事使用分块列式存储',app.storage_columnar,app.storage_save.submit).pack(fill='x',pady=3)
        app.choice(body,'可重建缓存上限 / MiB',app.cache_limit,['128','256','512','1024','2048'],app.storage_save.submit)
        app.storage_buttons={};actions=app.row(body);install(actions)
        for key,title,command in [('compress','压缩选中赛事',app.compress_selected),('columnar','转换选中赛事为列式',lambda:app.storage_operation('columnar')),('restore','恢复选中赛事为 CSV',lambda:app.storage_operation('restore'))]:
            app.storage_buttons[key]=app.button(actions,title,command,False,150)
        body=app.card('报告与缓存维护','分步重试失败报告，查看缓存与用户导出文件占用',compact=True)
        from control_maintenance import reports,caches
        actions=app.row(body);install(actions);app.button(actions,'报告任务与分步重试',lambda:reports(app),False,190);app.button(actions,'缓存与导出文件',lambda:caches(app),False,175)
        app.content=sections.frames['renderer'];body=app.card('RaceCom 原版图像','复用 LMU 已配置的原版引擎；EVO 标识和图片目录独立。' if game.catalogue=='official' else '直接调用你自己的 Image Generate.exe；原版版式、字体、颜色与车辆校准保留')
        from control_renderer import RendererEditor
        app.renderer_editor=RendererEditor(app,body)
    finally:app.content=outer
    from control_data_browser import DataBrowser
    browser=DataBrowser(app,outer,packages,storage,summary);app.data_browser=browser;sections.on_select=browser.mount
    sections.select(getattr(app,'data_section','video'))
