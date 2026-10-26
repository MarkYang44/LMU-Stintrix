"""Manual split review with stable selection and a reversible recent mark."""
import os
from pathlib import Path
from control_worklist import WorkList,existing
from split_checks import candidates,mark,unmark,checked_state
from track_names import display,search_text
from i18n import tr


def show(app):
    old=existing(app,'split_checks_window')
    if old:return old
    def row(item):return (display(item['first']['track']),item['first']['vehicle'],item['first']['date'][:19].replace('T',' '),item['second']['date'][:19].replace('T',' '),f"{item['gap_s']:.1f}",tr(item['reason']))
    def detail(item):return tr('前段')+' · '+Path(item['first']['folder']).name+'\n'+tr('后段')+' · '+Path(item['second']['folder']).name
    view=WorkList(app,'检查疑似拆分',[('track','赛道',150),('car','车型',180),('first','前段时间（UTC）',170),('second','后段时间（UTC）',170),('gap','间隔 / 秒',90),('reason','前段结束原因',180)],lambda item:item['id'],row,detail=detail,hint='搜索赛道、车型或原因；相邻片段不代表同一场，不会自动合并或删除。标记后会选中下一组。',searchable=lambda item:search_text(item['first']['track']))
    window=view.window;app.split_checks_window=window;view.table.multiple=False
    if not hasattr(app,'split_check_undo'):app.split_check_undo=[]
    def refresh(notice='选择一组查看前后片段；“已检查”标记可在本次运行中撤销。'):
        from library import inventory
        view.load(lambda:candidates(inventory(app.data_path),checked_state(app.data_path/'EventCatalog/split_checks.json').get('checked',[])),notice)
    def open_part(which):
        item=view.selected_items()[0];folder=Path(item[which]['folder'])
        try:
            if not folder.resolve().is_relative_to(Path(app.data_path).resolve()) or not folder.is_dir():raise ValueError('记录目录不可用或已移动')
            path=folder/'review.html';os.startfile(str(path if path.is_file() else folder))
        except (OSError,ValueError) as error:view.say(str(error))
    def checked():
        item=view.selected_items()[0];ids=list(view.table.get_children());index=ids.index(item['id']);remaining=[key for key in ids if key!=item['id']]
        try:changed=mark(app.data_path,item['id'])
        except (OSError,ValueError) as error:view.say(str(error));return
        if changed:app.split_check_undo.append(item['id']);app.split_check_undo=app.split_check_undo[-20:]
        view.remembered=(remaining[min(index,len(remaining)-1)],) if remaining else ()
        refresh('已标为检查完成；可继续查看下一组，或撤销最近标记。')
    def undo():
        key=app.split_check_undo[-1]
        try:changed=unmark(app.data_path,key)
        except (OSError,ValueError) as error:view.say(str(error));return
        app.split_check_undo.pop();view.remembered=(key,)
        refresh('最近标记已撤销' if changed else '标记已变化，已刷新列表')
    single=lambda:len(view.selected_items())==1
    view.action('first','查看前段',lambda:open_part('first'),140,enabled=single)
    view.action('second','查看后段',lambda:open_part('second'),140,enabled=single)
    view.action('checked','标为已检查',checked,155,enabled=single)
    view.action('undo','撤销最近标记',undo,165,enabled=lambda:bool(app.split_check_undo))
    view.action('refresh','刷新',refresh,110)
    window.bind('<F5>',lambda _:view.buttons['refresh'].invoke());refresh();return window
