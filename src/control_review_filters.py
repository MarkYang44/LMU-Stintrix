"""Shared event filters in the race-review library."""
from control_event_filters import EventControls
from control_feedback import CountBadge
from control_widgets import px
from event_filters import DEFAULTS
from i18n import tr

REVIEW_FIELDS=(('track','赛道'),('vehicle_class','车辆组别'),('car','车型'),('phase','阶段'),
    ('mode','参赛方式'),('period','时间范围（UTC）'),('outcome','比赛成绩'),('favorite','收藏'))

class ReviewFilters(EventControls):
    def __init__(self,parent,app):
        self.disclosure=None
        super().__init__(parent,app,app.populate,'review_filter_state',filter_fields=REVIEW_FIELDS)
        self.bind_query(app.search)
        self.count=CountBadge(parent)
    def attach(self,button,table):
        """Rows come first: the eight facets fold behind one button and active
        conditions stay visible as removable chips directly above the table."""
        self.disclosure=button;self.compact(table)
        if not getattr(self.app,'review_filters_open',False):self.pack_forget();self.sync_chips()
        self.sync_disclosure()
    def toggle_filters(self):
        opened=not bool(self.winfo_manager());self.app.review_filters_open=opened
        if opened:self.pack(fill='x',pady=8,before=self.compact_target)
        else:self.pack_forget()
        self.sync_chips();self.sync_disclosure()
    def active_count(self):
        return sum(value!=DEFAULTS.get(key) for key,value in self.state.items() if key in self.variables and key!='sort')
    def sync_disclosure(self):
        button=self.disclosure
        if button is None or not button.winfo_exists():return
        count=self.active_count();title=tr('筛选条件')+(f' · {count}' if count else '')
        if button.label!=title:button.configure(text=title,width=max(px(button,112),button.font.measure(title)+px(button,36)))
        button.configure(selected=bool(self.winfo_manager()))
    def update_chips(self):
        super().update_chips();self.sync_disclosure()
