"""Task groups for video, archives, reports/storage and external renderer."""
import tkinter as tk
from tkinter import filedialog,messagebox
from control_theme import T
from control_fields import Field
from control_widgets import Switch
from i18n import tr
import renderer_config


def build(app):
    from control_sections import TaskSections
    sections=TaskSections(app,[('video','视频分析'),('packages','赛事包'),('storage','报告与存储'),('renderer','外部生成器')],'data_section')
    app.data_tasks=sections
    outer=app.content
    try:
        app.content=sections.frames['video']
        body=app.card('视频提取油刹曲线','三种输入：普通 POV、距离与计时 HUD、视频与同圈遥测；估算结果单独保存')
        from control_video import show as video_analysis
        actions=app.row(body);app.button(actions,'视频分析与标定',lambda:video_analysis(app,app.data_path),True,190)
        from control_video_results import show as recent_videos
        app.button(actions,'最近提取结果',lambda:recent_videos(app,app.data_path),False,170)
        app.content=sections.frames['packages']
        body=app.card('赛事包 / ZIP · 7z','每场一个包；相同版本重复导出复用已有文件，不执行内容校验')
        import archive_preferences
        preferences=archive_preferences.load(app.data_path)
        app.archive_format=tk.StringVar(app.root,value='ZIP' if preferences['format']=='zip' else '7z')
        app.archive_verify=tk.BooleanVar(app.root,value=preferences['verify'])
        def save_archive():
            archive_preferences.save(app.data_path,app.archive_format.get().lower(),app.archive_verify.get())
        app.choice(body,'导出格式',app.archive_format,['ZIP','7z'],save_archive)
        app.label(body,'不计算文件哈希、不在导出后重读整个包；保留正常解压与安全路径处理。',9,T.MUTED).pack(anchor='w',pady=4)
        app.sessions(body,True,True);row=app.row(body);app.button(row,'批量导出选中赛事',app.export_package,True,180);app.button(row,'导入赛事包',app.import_package,False,145)
        app.button(row,'导入官方遥测',app.import_native,False,155)
        app.content=sections.frames['storage']
        body=app.card('报告与缓存维护','分步重试失败报告，查看缓存与用户导出文件占用')
        from control_maintenance import reports,caches
        actions=app.row(body);app.button(actions,'报告任务与分步重试',lambda:reports(app),False,190);app.button(actions,'缓存与导出文件',lambda:caches(app),False,175)
        body=app.card('无损节省磁盘空间','赛后无损存储完整采样与报告；保留图片质量，可导出或恢复 CSV')
        app.label(body,app.selected_count,9,T.ACCENT).pack(anchor='w')
        app.button(app.row(body),'选择要整理的赛事',lambda:sections.select('packages'),False,190)
        from session_compression import enabled
        app.storage_auto=tk.BooleanVar(app.root,value=enabled(app.data_path))
        from session_compression import column_enabled
        from cache_budget import limit
        app.storage_columnar=tk.BooleanVar(app.root,value=column_enabled(app.data_path));app.cache_limit=tk.StringVar(app.root,value=str(limit(app.data_path)))
        def save_storage():
            from storage import atomic_json
            from race_model import read_json
            settings=read_json(app.data_path/'storage_settings.json',{})
            settings.update(auto_compress=app.storage_auto.get(),columnar=app.storage_columnar.get(),cache_limit_mb=int(app.cache_limit.get()))
            atomic_json(app.data_path/'storage_settings.json',settings)
        row=app.row(body);app.label(row,'赛后自动压缩',10,T.MUTED).pack(side='left')
        Switch(row,'',app.storage_auto,save_storage).pack(side='right',fill='x',expand=True)
        Switch(body,'新赛事使用分块列式存储',app.storage_columnar,save_storage).pack(fill='x',pady=4)
        app.choice(body,'可重建缓存上限 / MiB',app.cache_limit,['128','256','512','1024','2048'],save_storage)
        row=app.row(body);app.button(row,'压缩选中赛事',app.compress_selected,False,165)
        app.button(row,'转换选中赛事为列式',lambda:app.storage_operation('columnar'),False,190)
        row=app.row(body);app.button(row,'导出原始 CSV',lambda:app.storage_operation('csv'),False,165)
        app.button(row,'导出独立复盘页',lambda:app.storage_operation('html'),False,175)
        app.button(row,'恢复选中赛事为 CSV',lambda:app.storage_operation('restore'),False,195)
        app.content=sections.frames['renderer']
        body=app.card('RaceCom 原版图像','直接调用你自己的 Image Generate.exe；原版版式、字体、颜色与车辆校准保留')
        config=renderer_config.load();app.renderer_mode=tk.StringVar(app.root,value=config['mode']);app.renderer_path=tk.StringVar(app.root,value=config['executable'])
        app.renderer_baseline={'renderer_mode':config['mode'],'renderer_path':config['executable']}
        app.choice(body,'生成方式',app.renderer_mode,['racecom','native'],labels={'racecom':'RaceCom 原版','native':'Stintrix 兼容版'})
        entry=Field(body,textvariable=app.renderer_path,font=('Segoe UI',10));entry.pack(fill='x',pady=8)
        def choose():
            path=filedialog.askopenfilename(parent=app.root,title=tr('选择 RaceCom 的 Image Generate.exe'),filetypes=[('RaceCom 图像生成器','*.exe')])
            if path:app.renderer_path.set(path)
        def save():
            try:renderer_config.save(dict(mode=app.renderer_mode.get(),executable=app.renderer_path.get()));app.status.set(tr('图像生成器已配置；下一场结束自动生成到赛事文件夹'))
            except (ValueError,OSError) as e:messagebox.showerror(tr('配置未保存'),str(e),parent=app.root)
        row=app.row(body);app.button(row,'选择生成器',choose,False,140);app.button(row,'保存配置',save,True,140)
        app.label(body,'racecom = 原版版式；native = Stintrix 兼容版式。\nGitHub 下载包不包含 RaceCom 程序、商标图片或个人记录。',9,T.MUTED).pack(anchor='w',pady=8)
    finally:app.content=outer
    sections.select(getattr(app,'data_section','video'))
