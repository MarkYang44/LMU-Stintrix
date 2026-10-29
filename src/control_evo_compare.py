"""Shared EVO session-best action; snapshot on Tk, bounded work off Tk."""
import os
from pathlib import Path
from i18n import tr


def _multi_page(app,root,page,count):
    from simulators import root_identity
    root=Path(root).resolve();page=Path(page).resolve()
    if (root!=Path(app.data_path).resolve() or root_identity(root)!='ac_evo' or type(count) is not int or not 3<=count<=6
            or page.parent!=root/'LapComparisons' or not page.name.startswith('EVO_Multi_') or page.suffix!='.html' or not page.is_file()):
        raise ValueError('多圈对比文件不在当前 AC EVO 目录中')
    return root,page


def remember_multi(app,root,page,count):
    root,page=_multi_page(app,root,page,count)
    contexts=getattr(app,'evo_multi_context',{});app.evo_multi_context=contexts
    contexts[str(root)]=dict(page=str(page),count=count)


def last_multi(app):
    try:
        root=Path(app.data_path).resolve();item=getattr(app,'evo_multi_context',{}).get(str(root))
        if not isinstance(item,dict):return None
        root,page=_multi_page(app,root,item['page'],item['count'])
        return dict(page=str(page),count=item['count'])
    except (OSError,ValueError,KeyError,TypeError):return None


def open_multi(app):
    if app.closing:return False
    item=last_multi(app)
    if item is None:app.status.set(tr('上次多圈对比文件已移动或删除，请重新生成。'));return False
    try:os.startfile(item['page'])
    except OSError as error:app.status.set(tr('打开失败：{error}').format(error=str(error)));return False
    app.status.set(tr('已打开上次 {count} 圈对比；使用已有文件，未重新分析。').format(**item));return True


def fastest(app,items,*,notify=None,finished=None):
    if app.closing:return False
    say=notify or app.status.set
    values=[dict(item) for item in items]
    if not 2<=len(values)<=6:say(tr('请选择 2–6 场已有最快有效圈的赛事'));return False
    if any(not item.get('fastest_file') for item in values):say(tr('所选赛事均需已有最快完整有效圈'));return False
    if any(item.get('status') in ('recording','write_error') for item in values):say(tr('请等记录完整保存后再操作'));return False
    from control_maintenance import offline_ready
    if not offline_ready(app):say(tr('请先停止 HUD 并等待后台任务完成，再对比跨场最快圈。'));return False
    from simulators import root_identity
    root=Path(app.data_path).resolve()
    if root_identity(root)!='ac_evo':raise ValueError('只能对比当前游戏的赛事记录')
    selections=tuple((Path(item['folder']),item['lap']) for item in values)
    app.lap_curve_jobs=getattr(app,'lap_curve_jobs',0)+1;settled=False
    say(tr('正在准备 {count} 场赛事的最快有效圈…').format(count=len(selections)))
    def done(result,error):
        nonlocal settled
        if settled:return
        settled=True;app.lap_curve_jobs=max(0,getattr(app,'lap_curve_jobs',0)-1)
        if finished:finished()
        if app.closing:return
        if error:say(str(error));return
        try:
            page=result['comparison']
            if len(selections)==2:
                from control_lap_pair import remember_result
                remember_result(app,root,page)
            else:remember_multi(app,root,page,len(selections))
            os.startfile(page)
        except (OSError,ValueError) as issue:say(tr('文件已生成，打开失败：')+str(issue))
        else:say(tr('{count} 场最快有效圈对比已打开；原始记录保留。').format(count=len(selections)))
    def work():
        from evo_comparison import export_many
        return export_many(root,selections)
    try:app.run_background(work,done)
    except Exception as error:done(None,error)
    return not settled
