"""Combined filtering and independent layout records without data rewrites."""
import json,sys,tempfile,unittest
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'));sys.path.insert(0,str(ROOT))
from review_filters import filtered
from track_names import layout
from personal_records import records
from tests import test_personal_records
from laps import export_fastest

class ReviewFilterTests(unittest.TestCase):
    def setUp(self):
        self.items=[dict(date=d,session_type=p,track=t,vehicle=c,folder=str(i)) for i,(d,p,t,c) in enumerate([
            ('2026-10-12T23:00:00+01:00','Race','Monza','BMW'),('2026-10-12T18:00:00Z','Qualify','Spa','Porsche'),
            ('2026-10-10T12:00:00Z','Race','Monza','Porsche'),('2026-10-01T12:00:00Z','Race','Spa','BMW')])]
        self.now=datetime(2026,10,13,12,tzinfo=timezone.utc)
    def test_combined_fields_and_inclusive_utc_date_range_keep_inventory_ids(self):
        state=dict(phase='Race',track='Monza',car='BMW',start='2026-10-12',end='2026-10-12')
        self.assertEqual([i for i,_ in filtered(self.items,state,now=self.now)],[0])
        self.assertEqual([i for i,_ in filtered(self.items,dict(period=2),now=self.now)],[0,1,2])
        self.assertEqual([i for i,_ in filtered(self.items,{},'蒙扎',self.now)],[0,2])
        with self.assertRaises(ValueError):filtered(self.items,dict(start='2026-10-13',end='2026-10-12'))
        with self.assertRaises(ValueError):filtered(self.items,dict(start='bad'))
    def test_all_sort_modes_preserve_row_identity_and_source_order(self):
        before=json.dumps(self.items)
        for order in range(8):self.assertEqual({i for i,_ in filtered(self.items,dict(sort=order))},{0,1,2,3})
        self.assertEqual([i for i,_ in filtered(self.items,dict(sort=1))],[3,2,1,0])
        self.assertEqual(json.dumps(self.items),before)
    def test_layout_names_are_visible_for_every_track_and_unknowns_are_explicit(self):
        import i18n
        i18n.set_language('zh')
        for track,a,b in [('Monza','Monza GP','Monza No Chicane'),('Silverstone','Silverstone Grand Prix','Silverstone International'),('Fuji Speedway','Fuji Speedway GP','Fuji Speedway Short'),('Custom Circuit','North Loop','South Loop')]:
            self.assertNotEqual(layout(track,a,5000),layout(track,b,5000))
        self.assertIn('无减速弯',layout('Monza','Monza No Chicane',5000))
        self.assertIn('布局未记录',layout('Spa',None,5000))
        self.assertIn('North Loop',layout('Custom Circuit','North Loop',5000))
    def test_same_length_different_layouts_never_share_a_personal_best(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            fixture=test_personal_records.FeatureTests()
            for name in ('Monza GP','Monza No Chicane','Short','International'):
                folder=fixture.session(t,name.replace(' ','_'),track='Monza',track_layout=name)
                export_fastest(folder,ROOT/'src/compare.html')
            self.assertEqual(len(records(t)),4)

if __name__=='__main__':unittest.main()
