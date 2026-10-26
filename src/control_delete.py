"""One explicit confirmation for a frozen batch of permanent local deletions."""
import tkinter as tk
from tkinter import messagebox
from control_theme import T
from i18n import tr
import session_delete

def busy(center):
    reports=getattr(getattr(getattr(center.hud,'engine',None),'recorder',None),'pending_reports',[])
    if center.tasks.busy or any(thread.is_alive() for thread in reports):
        center.status.set(tr('请等待当前记录任务完成'));return True
    return False

def confirm(center,items):
    from track_names import display
    from control_danger import confirm as ask
    details=[' · '.join((item['date'][:19],item['session_type'],display(item['track']),item['vehicle'])) for item in items]
    return ask(center.root,'删除赛事记录',tr('永久删除选中的赛事记录？')+f' ({len(items)})',details,warning='将从本机删除所选赛事的全部记录、圈文件与报告，无法恢复。')


def remove(center):
    if busy(center):return
    def chosen(items):
        if not confirm(center,items):return
        if busy(center):return
        data=center.data_path;keys=tuple(item['key'] for item in items)
        def done(result):
            if center.tree:center.refresh()
            center.status.set(tr('记录已永久删除')+f": {len(result['deleted'])} / {len(keys)}")
            errors=result['failed']+result['warnings']
            if errors:
                messagebox.showwarning(tr('部分赛事未能删除'), '\n'.join(key+' · '+tr(error) for key,error in errors),parent=center.root)
        center.work(lambda:session_delete.remove_many(data,keys),done)
    center.with_selection(chosen,count=None)
