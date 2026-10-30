"""Shared event filters in the race-review library."""
from control_event_filters import EventControls
from control_feedback import CountBadge

REVIEW_FIELDS=(('track','赛道'),('vehicle_class','车辆组别'),('car','车型'),('phase','阶段'),
    ('mode','参赛方式'),('period','时间范围（UTC）'),('outcome','比赛成绩'),('favorite','收藏'))

class ReviewFilters(EventControls):
    def __init__(self,parent,app):
        super().__init__(parent,app,app.populate,'review_filter_state',filter_fields=REVIEW_FIELDS)
        self.bind_query(app.search)
        self.count=CountBadge(parent)
