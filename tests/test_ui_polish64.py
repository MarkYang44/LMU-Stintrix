"""Personal best browsing and compact native library user workflows."""
import os,sys,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tests import test_ui_efficiency as helpers
from tests import test_ui_polish62 as fixtures
from tests.test_ui_polish62 import histories,official


def values(root):
    rows=histories(root,8)['entries']
    for i,e in enumerate(rows):
        e['track']=e['session']['track']='Fixture '+str(i);e['identity']=(e['track'],'GP',5000,'LMGT3')
    return rows


def detail(e):
    return dict(marker=e['folder'],conditions=dict(fuel_l=30.123456789,track_temp_c=25.),vehicle_summary={},curve=[(0,[0.,0.],[1.,.5]),(599,[.5,0.],[1.,1.])])


class Rules(unittest.TestCase):
    def test_detail_identity_tracks_actual_lap_file_and_ignores_annotations(self):
        import tempfile
        from control_best import detail_key
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            e=values(temp)[0];key=detail_key(e);e['tags']=['note'];self.assertEqual(key,detail_key(e))
            Path(e['file']).write_text('new source');self.assertNotEqual(key,detail_key(e))
            key=detail_key(e);e['lap']['number']+=1;self.assertNotEqual(key,detail_key(e))


@unittest.skipUnless(os.name=='nt','Native Tk')
class BestUI(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump;tab=fixtures.UI.tab
    def mount(self,app,root,rows=None):
        rows=rows or values(root)
        with patch('control_records.entries',return_value=rows),patch('control_records.attach',side_effect=lambda _,v:v),patch('control_records.detail',side_effect=detail):
            app.personal_record_view='best';app.show_page(6);self.pump(app,.3)
        return app.record_loaders['best'].page,rows
    def test_search_sort_and_note_refresh_reuse_selected_detail(self):
        app,root,errors=self.app();p,rows=self.mount(app,root)
        with patch('control_records.detail',side_effect=detail) as read:
            for query in ('B','BM','BMW'):p.query.set(query)
            self.pump(app,.1);self.assertEqual(read.call_count,0)
            for e in rows:e['tags']=['changed']
            with patch.object(p.loader,'reader',new=lambda:rows):p.loader.read();self.pump(app,.2)
            self.assertEqual(read.call_count,0)
        self.assertEqual(p.state['data']['conditions']['fuel_l'],30.123456789);self.assertFalse(errors)
    def test_rapid_choices_run_first_and_last_and_ignore_stale_result(self):
        app,root,errors=self.app();p,_=self.mount(app,root);jobs=[]
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append((work,done))):
            for row in p.table.order[1:4]:p.table.selection_set((row,))
            wanted=p.selected['folder'];self.assertEqual(len(jobs),1)
            jobs[0][1](detail(jobs[0][0].args[0]),None);self.assertEqual(len(jobs),2);self.assertIsNone(p.state['data'])
            jobs[1][1](detail(jobs[1][0].args[0]),None)
        self.assertEqual(p.state['data']['marker'],wanted);self.assertLessEqual(len(p.details.cache),2);self.assertFalse(errors)
    def test_actual_file_change_invalidates_detail(self):
        app,root,errors=self.app();p,_=self.mount(app,root);Path(p.selected['file']).write_text('changed')
        with patch('control_records.detail',side_effect=detail) as read:p.render_selection();self.pump(app,.2);self.assertEqual(read.call_count,1)
        self.assertFalse(errors)
    def test_failed_detail_waits_for_retry_and_refresh_recovers(self):
        app,root,errors=self.app();p,rows=self.mount(app,root)
        with patch('control_records.detail',side_effect=OSError('fixture failure')) as read:
            p.table.selection_set((p.table.order[1],));self.pump(app,.2);p.query.set('BMW');self.pump(app,.1);self.assertEqual(read.call_count,1)
        self.assertTrue(p.buttons['retry'].enabled)
        with patch('control_records.detail',side_effect=detail),patch.object(p.loader,'reader',new=lambda:rows):p.refresh_records();self.pump(app,.2)
        self.assertIsNone(p.state['error']);self.assertFalse(p.buttons['retry'].enabled);self.assertFalse(errors)
    def test_empty_selection_disables_actions_and_explains_keyboard_open(self):
        app,root,errors=self.app();p,_=self.mount(app,root);p.query.set('no match');p.search_field.flush() # Enter applies a pending search immediately.
        for key in ('curve','training','card','comparable','note','folder'):self.assertFalse(p.buttons[key].enabled)
        self.assertTrue(all(not b.enabled for b in p.fixed.values()));p.primary();self.assertIn('先选择',p.status.get());self.assertIsNone(p.state['data']);self.assertFalse(errors)
    def test_keyboard_open_uses_selected_record_and_f5_refreshes(self):
        app,root,errors=self.app();p,_=self.mount(app,root)
        app.root.lift();p.table.viewport.focus_force();self.pump(app,.05)
        with patch.object(p.exporter,'create') as opened:
            p.table.viewport.event_generate('<Return>');self.pump(app,.05);opened.assert_called_once_with(p,p.selected)
        with patch.object(p.loader,'read') as refreshed:app.root.event_generate('<F5>');self.pump(app,.05);refreshed.assert_called_once()
        self.assertTrue(p.table.viewport.bind('<Double-1>'));self.assertFalse(errors)
    def test_small_window_pins_time_and_primary_actions_stay_visible(self):
        app,root,errors=self.app();p,_=self.mount(app,root);self.pump(app,.1)
        positions={key:x for key,x,_ in p.table.positions()};self.assertIn('time',p.table.frozen_columns)
        self.assertLess(positions['time']+p.table.actual['time'],p.table.viewport.winfo_width())
        visible=(app.scroll.winfo_rooty()+app.scroll.winfo_height()-p.table.viewport.winfo_rooty())/p.table.rowheight;self.assertGreaterEqual(visible,2)
        y=p.fixed['curve'].winfo_rooty();app.scroll.yview_moveto(.6);self.pump(app,.1);self.assertEqual(p.fixed['curve'].winfo_rooty(),y);self.assertFalse(errors)
    def test_filter_disclosure_keeps_conditions_and_returns_to_same_expanded_state(self):
        app,root,errors=self.app();p,rows=self.mount(app,root);self.assertFalse(p.modes.winfo_manager());p.toggle_filters();self.assertTrue(p.modes.winfo_manager())
        p.query.set('BMW');p.toggle_filters();self.assertEqual(p.query.get(),'BMW');p.toggle_filters()
        with patch('control_official_results.read_results',return_value=official(root)):self.tab(app,'官方战绩')
        with patch('control_records.entries',return_value=rows),patch('control_records.attach',side_effect=lambda _,v:v):self.tab(app,'赛道最快圈')
        self.assertTrue(app.record_loaders['best'].page.modes.winfo_manager());self.assertFalse(errors)
    def test_sibling_return_keeps_selection_scroll_and_snapshot(self):
        app,root,errors=self.app();p,rows=self.mount(app,root)
        with patch('control_records.detail',side_effect=detail):p.table.selection_set((p.table.order[5],));self.pump(app,.2)
        selected=p.identity(p.selected);p.query.set('BMW');p.table.set_offset(80);app.scroll.yview_moveto(.3);self.pump(app,.1);scroll=app.scroll.yview()[0]
        with patch('control_official_results.read_results',return_value=official(root)):self.tab(app,'官方战绩')
        self.assertTrue(p.disposed);self.assertIsNone(p.details.page)
        with patch('control_records.entries',return_value=rows),patch('control_records.attach',side_effect=lambda _,v:v),patch('control_records.detail') as read:self.tab(app,'赛道最快圈');read.assert_not_called()
        current=app.record_loaders['best'].page;self.assertEqual(current.identity(current.selected),selected);self.assertEqual(current.query.get(),'BMW');self.assertAlmostEqual(app.scroll.yview()[0],scroll,places=2);self.assertFalse(errors)
    def test_sibling_disposal_releases_filter_variables_on_gui_thread(self):
        app,root,errors=self.app();p,_=self.mount(app,root);variables=list(p.modes.variables.values())+[p.modes.view,p.modes.summary,p.modes.selection_detail]
        with patch('control_official_results.read_results',return_value=official(root)):self.tab(app,'官方战绩')
        self.assertTrue(all(v._tk is None for v in variables));self.assertFalse(errors)
    def test_export_reuses_source_and_distinct_selection_preserves_old_file(self):
        from tests.test_personal_records import FeatureTests,TEMPLATE
        from laps import export_fastest
        from personal_records import entries
        app,root,errors=self.app();one=FeatureTests().session(root,'one',track='Track One');two=FeatureTests().session(root,'two',track='Track Two');export_fastest(one,TEMPLATE);export_fastest(two,TEMPLATE)
        rows=entries(root);p,_=self.mount(app,root,rows);source={Path(e['file']):Path(e['file']).read_bytes() for e in rows}
        with patch('control_record_browser.os.startfile'):
            p.curve();self.pump(app,.5);first=Path(p.exporter.path);before=first.read_bytes();p.curve();self.pump(app,.1);self.assertEqual(Path(p.exporter.path),first)
            p.table.selection_set((p.table.order[1],));self.pump(app,.2);p.curve();self.pump(app,.5);self.assertNotEqual(Path(p.exporter.path),first);self.assertEqual(first.read_bytes(),before)
        self.assertEqual({path:path.read_bytes() for path in source},source);self.assertFalse(errors)
    def test_busy_export_blocks_repeated_open_and_late_callback_does_not_open_browser(self):
        app,root,errors=self.app();p,_=self.mount(app,root);jobs=[]
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append((work,done))):p.curve();p.curve();self.assertEqual(len(jobs),1)
        app.show_page(0);self.pump(app,.1);result=root/'curve.html';result.write_text('fixture')
        with patch('control_record_browser.os.startfile') as opened:jobs[0][1](str(result),None);opened.assert_not_called()
        self.assertEqual(p.exporter.path,str(result));self.assertFalse(errors)
    def test_late_detail_after_leaving_never_updates_destroyed_controls(self):
        app,root,errors=self.app();p,_=self.mount(app,root);jobs=[]
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append((work,done))):p.table.selection_set((p.table.order[1],))
        app.show_page(0);self.pump(app,.05);jobs[0][1](detail(jobs[0][0].args[0]),None);self.assertIsNone(p.details.page);self.assertFalse(errors)


@unittest.skipUnless(os.name=='nt','Native Tk')
class GuideUI(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def mount(self,app):app.show_page(5);self.pump(app,.25);return app.guide_page
    def select_pair(self,p):
        keys=list(p.library.data['cars'])
        for key in keys[:2]:p.select('car:'+key)
    def test_minimum_first_screen_reveals_first_card(self):
        app,root,errors=self.app();p=self.mount(app)
        self.assertLess(p.results.winfo_rooty()+60,app.scroll.winfo_rooty()+app.scroll.winfo_height());self.assertFalse(p.metadata.winfo_manager());self.assertFalse(errors)
    def test_page_boundary_is_noop_and_page_selector_goes_directly_to_last(self):
        app,root,errors=self.app();p=self.mount(app);card=p.results.winfo_children()[0];self.assertFalse(p.pagers[0][0].enabled)
        p.turn(-1);self.assertTrue(card.winfo_exists());last=len(p.page_boxes[0].values)-1;p.page_number.set(p.page_boxes[0].values[-1]);p.go_page();self.pump(app,.2)
        self.assertEqual(p.state['page'],last);self.assertFalse(p.pagers[0][1].enabled);self.assertTrue(p.pagers[0][0].enabled);self.assertFalse(errors)
    def test_unfavorite_during_comparison_clamps_a_disappearing_last_page(self):
        app,root,errors=self.app();p=self.mount(app);keys=list(p.library.data['cars'])[:22];p.library.favorites['cars']=set(keys);p.variables['favorite'].set('收藏的车型');p.filter_changed();self.pump(app,.25)
        p.turn(7);self.pump(app,.1)
        for key in keys[:2]:p.select('car:'+key)
        p.compare();self.pump(app,.2);p.favorite('cars',keys[0]);self.pump(app,.2)
        self.assertEqual(p.state['page'],6);self.assertEqual(p.state['mode'],'compare');self.assertEqual(len(p.state['comparison']),2);self.assertFalse(errors)
    def test_compare_aligns_rows_on_wide_window_and_returns_to_browse_position(self):
        app,root,errors=self.app();p=self.mount(app);self.select_pair(p);app.root.geometry('1420x960');self.pump(app,.1);app.scroll.yview_moveto(.25);self.pump(app,.1);before=app.scroll.yview()[0]
        p.compare();self.pump(app,.3);self.assertTrue(p.comparison.wide);cells=p.comparison.sections[2][1]
        self.assertEqual(cells[0][0].winfo_y(),cells[1][0].winfo_y());self.assertNotEqual(cells[0][0].winfo_x(),cells[1][0].winfo_x());self.assertFalse(p.filter_card.winfo_manager())
        p.browse();self.pump(app,.2);self.assertAlmostEqual(app.scroll.yview()[0],before,places=2);self.assertFalse(errors)
    def test_three_way_compare_stacks_on_narrow_window_without_losing_content(self):
        app,root,errors=self.app();p=self.mount(app)
        for key in list(p.library.data['cars'])[:3]:p.select('car:'+key)
        p.compare();self.pump(app,.25);self.assertFalse(p.comparison.wide);self.assertEqual(p.card_count,3)
        cells=p.comparison.sections[2][1];self.assertGreater(cells[1][0].winfo_y(),cells[0][0].winfo_y());self.assertFalse(errors)
    def test_comparison_keeps_recommendation_details_and_ctrl_f_reveals_search(self):
        app,root,errors=self.app();p=self.mount(app);self.select_pair(p);app.progressive=True;app.scroll.yview_moveto(.25);self.pump(app,.1);p.compare();self.pump(app,.2)
        def walk(w):
            yield w
            for c in w.winfo_children():yield from walk(c)
        action=next(w for w in walk(p.comparison) if getattr(w,'label','').startswith('推荐它的赛道') and hasattr(w,'invoke'));action.invoke();self.pump(app,.1)
        self.assertTrue(any(getattr(w,'label','')=='查看赛道' for w in walk(p.comparison)))
        app.focus_search();self.pump(app,.2);self.assertEqual(p.state['mode'],'browse');self.assertTrue(p.search_entry.winfo_ismapped());self.assertEqual(app.scroll.yview()[0],0);self.assertEqual(len(p.state['comparison']),2);self.assertFalse(errors)
    def test_filter_favorite_and_metadata_context_survive_theme_language_and_navigation(self):
        app,root,errors=self.app();p=self.mount(app);p.variables['query'].set('BMW');self.pump(app,.25);p.toggle_metadata();p.favorite('cars','bmw-m4-lmgt3');self.select_pair(p)
        app.set_theme('light');app.toggle_language();self.pump(app,.25);p=app.guide_page
        self.assertEqual(p.state['query'],'BMW');self.assertTrue(p.state['metadata']);self.assertTrue(p.metadata.winfo_manager());self.assertEqual(len(p.state['comparison']),2);self.assertIn('bmw-m4-lmgt3',p.library.favorites['cars']);self.assertFalse(errors)
    def test_removing_second_comparison_returns_to_library_and_keeps_first(self):
        app,root,errors=self.app();p=self.mount(app);self.select_pair(p);keys=list(p.state['comparison']);p.compare();self.pump(app,.2);p.select(keys[1]);self.pump(app,.2)
        self.assertEqual(p.state['mode'],'browse');self.assertEqual(p.state['comparison'],keys[:1]);self.assertTrue(p.filter_card.winfo_manager());self.assertFalse(p.compare_button.enabled);self.assertFalse(errors)
