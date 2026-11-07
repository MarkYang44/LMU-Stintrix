"""Sessions of a layout and car read as their distance to that combination's personal best."""
import os,unittest
from tests import test_ui_polish69 as helpers


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.UI.app;pump=helpers.UI.pump;settle=helpers.UI.settle

    def test_every_non_best_lap_shows_its_gap_to_the_personal_best(self):
        app,root,errors=self.app(True);app.root.geometry('1400x900');app.request_page(1);self.settle(app,lambda:bool(app.tree and app.tree.get_children()))
        t=app.tree;lap=t.columns.index('lap');times={iid:t.rows[iid][lap] for iid in t.get_children()}
        gaps={times[iid]:round(value,3) for iid,value in t.gaps.items()}
        self.assertEqual(gaps,{'2:26.400':.3,'2:26.700':.6,'2:27.000':.9,'1:42.400':.3,'1:42.700':.6,'1:43.000':.9})
        self.assertFalse(set(t.gaps)&set(t.marked));self.pump(app,.1)
        texts=[t.viewport.itemcget(i,'text') for i in t.viewport.find_all() if t.viewport.type(i)=='text']
        self.assertIn('+0.300',texts);self.assertIn('PB',texts)
        other=next(i for i in t.get_children() if times[i]=='2:26.400');t.selection_set((other,));self.pump(app,.05)
        self.assertTrue(app.selection_line.full[0].endswith('最快圈 2:26.400 · 距 PB +0.300'));self.assertFalse(errors)
