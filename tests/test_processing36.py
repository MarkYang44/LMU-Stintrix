"""CSV projection equivalence and fewer steps in the track-first A/B workflow."""
import csv,io,os,random,unittest
from unittest.mock import patch
from tests import test_selected_laps as fixtures
ROOT=fixtures.ROOT


class Processing(unittest.TestCase):
    def test_projection_keeps_tuple_shape_duplicates_short_rows_and_missing_columns(self):
        from csv_projection import projector
        rng=random.Random(36)
        for _ in range(160):
            fields=[rng.choice(('a','b','c','utc')) for i in range(rng.randrange(1,15))]
            columns=[rng.choice((*fields,'absent')) for i in range(rng.randrange(15))]
            project=projector(fields,columns)
            for size in (0,len(fields)-1,len(fields),len(fields)+2):
                row=[rng.choice(('',None,'-0.0','.12345678901234567','时间,"甲"\r\n下一行')) for i in range(size)]
                expected=dict(zip(fields,row));expected.update({k:None for k in fields[len(row):]})
                # The last duplicate is missing when its position exceeds the row.
                self.assertEqual(project(row),tuple(expected.get(k,'') for k in columns))
                self.assertIsInstance(project(row),tuple)
                self.assertEqual(len(row),size)
        for columns in ((),('a',),('a','a'),('b','a')):
            self.assertEqual(projector(('a','b'),columns)(['1','2']),tuple({'a':'1','b':'2'}[k] for k in columns))


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    from tests import test_ui_efficiency as helpers
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump

    def test_same_session_reuses_verified_laps_and_preserves_independent_selection_and_translation(self):
        from control_lap_pair import show
        from tests.test_ui_polish57 import records,LAPS
        app,root,errors=self.app();items=records(root);jobs=[]
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append((work,done))):
            window=show(app,root);c=window.pair_controls;jobs.pop(0)[1](items,None)
            self.assertFalse(c['quick']['same'].enabled)
            c['track'].set('monza');c['choose_track']();label=c['event_boxes']['A'].values[0]
            c['events']['A'].set(label);c['scan']('A');self.assertFalse(c['quick']['same'].enabled)
            jobs.pop(0)[1](dict(laps=LAPS,session=items[0]),None)
            self.assertIn('2 个有效圈',c['summaries']['A'].get());c['quick']['same'].invoke()
            self.assertFalse(jobs);self.assertEqual(c['events']['A'].get(),c['events']['B'].get())
            self.assertEqual([c['state']['laps'][k][c['numbers'][k].get()] for k in ('A','B')],[1,2]);self.assertTrue(c['compare'].enabled)
            before=c['numbers']['B'].get();c['quick']['same'].invoke();self.assertEqual(c['numbers']['B'].get(),before);self.assertFalse(jobs)
            c['quick']['swap'].invoke();self.assertEqual([c['state']['laps'][k][c['numbers'][k].get()] for k in ('A','B')],[2,1])
            app.set_theme('light');app.toggle_language();window.maxsize(4096,4096);window.geometry('860x680');self.pump(app,.2)
            self.assertIn('2 valid laps',c['summaries']['B'].get());self.assertEqual(c['track'].get(),'monza')
            self.assertTrue(c['compare'].enabled)
            bottom=c['footer'].winfo_rooty()
            for action in c['quick'].values():
                self.assertLessEqual(action.winfo_rooty()+action.winfo_height(),bottom)
                self.assertLessEqual(action.winfo_rootx()+action.winfo_width(),window.winfo_rootx()+window.winfo_width())
            c['track'].set('');c['choose_track']();self.assertFalse(c['quick']['same'].enabled);self.assertFalse(c['state']['rows']['B']);self.assertFalse(errors)

    def test_search_is_debounced_enter_and_clear_are_immediate_without_reindexing_or_selection_loss(self):
        from control_lap_pair import show
        from tests.test_ui_polish57 import records
        app,root,errors=self.app();jobs=[]
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append((work,done))):
            window=show(app,root);c=window.pair_controls;jobs.pop(0)[1](records(root),None)
            c['track'].set('monza');c['choose_track']();c['events']['A'].set(c['event_boxes']['A'].values[0]);selected=c['events']['A'].get()
            with patch('control_lap_pair.search_text',side_effect=AssertionError('Search must reuse its index')):
                for query in ('b','bm','bmw'):c['query'].set(query)
                before=tuple(c['event_boxes']['A'].values);self.assertIsNotNone(c['search'].pending)
                self.pump(app,.15);self.assertIsNone(c['search'].pending);self.assertEqual(c['events']['A'].get(),selected)
                c['query'].set('no matching event');c['search'].flush();self.assertFalse(c['event_boxes']['A'].values)
                c['search'].clear();self.assertEqual(len(c['event_boxes']['A'].values),len(before));self.assertEqual(c['events']['A'].get(),selected)
                c['query'].set('pending');window.destroy();self.pump(app,.15)
            self.assertFalse(errors)


if __name__=='__main__':unittest.main()
