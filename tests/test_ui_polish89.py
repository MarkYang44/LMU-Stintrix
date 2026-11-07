"""The review list uses the window's height: long lists reach the edge, short ones hug their rows."""
import os,time,unittest
from tests import test_ui_polish69 as helpers


def wait(root,condition,seconds=3):
    deadline=time.monotonic()+seconds
    while not condition() and time.monotonic()<deadline:root.update();time.sleep(.005)
    return condition()


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.UI.app;pump=helpers.UI.pump;settle=helpers.UI.settle

    def test_review_list_fills_tall_windows_and_hugs_short_lists(self):
        app,root,errors=self.app(True);app.root.geometry('1400x1050');app.request_page(1);self.settle(app,lambda:bool(app.tree and app.tree.get_children()))
        t=app.tree;self.assertEqual(len(t.order),8)
        self.assertTrue(wait(app.root,lambda:int(t.viewport.cget('height'))==round(9*t.rowheight)))
        values=t.rows[t.order[0]];t.replace([(str(1000+i),values) for i in range(80)],());t.fill_list()
        card=t.master.master;edge=lambda:app.scroll.winfo_rooty()+app.scroll.winfo_height()-(card.winfo_rooty()+card.winfo_height())
        self.assertTrue(wait(app.root,lambda:int(t.viewport.cget('height'))>round(9*t.rowheight)));self.pump(app,.1)
        self.assertGreaterEqual(edge(),0);self.assertLess(edge(),t.rowheight/2);tall=int(t.viewport.cget('height'))
        app.root.geometry('1400x820');self.assertTrue(wait(app.root,lambda:int(t.viewport.cget('height'))<tall))
        self.assertGreaterEqual(int(t.viewport.cget('height')),round(4*t.rowheight));self.assertFalse(errors)

    def test_data_page_keeps_its_compact_session_list(self):
        app,root,errors=self.app(True);app.show_page(3);self.pump(app,.35);app.data_tasks.select('packages');self.pump(app,.2)
        self.assertFalse(hasattr(app.tree,'fill_list'));self.assertFalse(errors)
