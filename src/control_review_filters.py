"""Shared event filters in the race-review library."""
from control_event_filters import EventControls
from control_feedback import CountBadge

class ReviewFilters(EventControls):
    def __init__(self,parent,app):
        super().__init__(parent,app,app.populate,'review_filter_state')
        self.bind_query(app.search)
        self.count=CountBadge(parent)
