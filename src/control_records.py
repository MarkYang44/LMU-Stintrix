"""Native personal-best browser with conditions and a bounded curve canvas."""
import os
import tkinter as tk
from i18n import tr
from control_theme import T
from control_fields import Field
from control_list import SessionList
from personal_records import records,detail,entries,select_records
from race_mode import mode,LABELS
from control_mode_filters import ModeControls
from control_event_filters import replace_rows,edit_note
from event_catalog import attach
from record_presentation import present
from track_names import display,search_text,layout
from control_metrics import Metrics
from control_record_art import RecordHeader
from control_feedback import CountBadge,record_improvements,TabIndicator
from control_motion import Motion,blend


def show(app):
    """Sibling views share the existing personal-records navigation entry."""
    outer=app.content;row=app.row(outer);indicator=TabIndicator(outer);indicator.pack(fill='x');view=tk.Frame(outer,bg=T.BG);view.pack(fill='x')
    from simulator_profiles import capabilities
    supported=capabilities(getattr(app,'simulator','lmu'))
    choices=[('best','赛道最快圈')]
    if supported.official_results:choices.append(('podium','领奖台记录'))
    if supported.record_history:choices.append(('history','纪录履历'))
    if supported.official_results:choices.append(('official','官方战绩'))
    buttons=[];selected=getattr(app,'personal_record_view','best')
    if selected not in dict(choices):selected='best'
    def mount(kind):
        if kind not in dict(choices):return
        if getattr(view,'mounted',None)==kind:return
        token=app.shell.cover_page() if app.pages.building is None and not app.shell.covering else None
        browser=getattr(view,'record_browser',None)
        if browser is not None and not browser.disposed:browser.capture()
        view.mounted=kind
        app.personal_record_view=kind;app.scan_generation+=1
        from control_disposal import release
        from control_pages import Page
        for widget in view.winfo_children():release(Page(widget),app)
        for key,button in buttons:
            button.primary=key==kind;button.paint()
            if key==kind:indicator.select(button)
        app.content=view
        try:
            if kind=='podium':
                from control_podiums import show as show_podiums
                show_podiums(app)
            elif kind=='official':
                from control_official_results import show as show_official
                show_official(app)
            elif kind=='history':
                from control_history import show as show_history
                show_history(app)
            else:show_best(app)
        finally:app.content=outer
        app.scroll.yview_moveto(0)
        if app.pages.building is None:app.install_toolbar()
        if token is not None:app.shell.reveal_page(token)
    for kind,label in choices:
        buttons.append((kind,app.button(row,label,lambda k=kind:mount(k),kind==selected,155)))
    app.personal_record_tabs=dict(buttons)
    mount(selected)


def show_best(app):
    from control_best import BestPage
    return BestPage(app)
