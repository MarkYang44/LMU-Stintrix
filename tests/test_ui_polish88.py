"""Segmented guide filters and the rail's recording dot."""
import os,time,unittest
from unittest.mock import patch
from tests import test_ui_polish69 as helpers


def wait(root,condition,seconds=3):
    deadline=time.monotonic()+seconds
    while not condition() and time.monotonic()<deadline:root.update();time.sleep(.005)
    return condition()


def walk(widget):
    for child in widget.winfo_children():yield child;yield from walk(child)


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.UI.app;pump=helpers.UI.pump;settle=helpers.UI.settle

    def test_three_way_guide_filters_apply_in_one_click(self):
        from control_widgets import Segmented
        from control_fields import Select
        app,root,errors=self.app();app.request_page(4);self.settle(app);g=app.guide_page;g.toggle_filters();self.pump(app,.1)
        found=[w for w in walk(g.filter_fields) if isinstance(w,(Segmented,Select))]
        control=lambda key:next(w for w in found if w.variable is g.variables[key])
        self.assertIsInstance(control('group'),Segmented);self.assertIsInstance(control('favorite'),Segmented);self.assertIsInstance(control('car'),Select)
        group=control('group');self.assertEqual(group.caption(group.values[0]),'全部')
        left,right=group.spans[1];group.event_generate('<Button-1>',x=round((left+right)/2),y=10);self.settle(app)
        self.assertEqual(app.guide_page.state['group'],'LMGT3');self.assertEqual(app.guide_page.filter_button.label,'筛选条件 · 1');self.assertFalse(errors)

    def test_rail_marks_the_run_page_while_a_hud_records(self):
        app,root,errors=self.app();app.request_page(1);self.settle(app);navigation=app.shell.navigation
        self.assertFalse(navigation.find_withtag('live'))
        with patch.object(app,'active',return_value=True):
            self.assertTrue(wait(app.root,lambda:bool(navigation.find_withtag('live'))));self.assertTrue(navigation.live)
        self.assertTrue(wait(app.root,lambda:not navigation.find_withtag('live')));self.assertFalse(errors)
