"""Podium browsing context, bounded detail jobs and source-version safety."""
import json,os,sys,tempfile,unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]
from tests import test_ui_efficiency as helpers
from tests import test_ui_polish62 as fixtures


def podiums(root,count=12):
    items=fixtures.histories(root,count)['entries']
    for i,e in enumerate(items):
        e.update(started_utc=e['observed_utc'],place=1+i%3,fastest_s=e['time_s'],team='Fixture Team',track='Track A' if i%2==0 else 'Track B',summary=dict(grid_place=10,finish_place=7,grid_class_place=4,finish_class_place=1+i%3,class_size=10),xml_only=False)
        e['session'].update(session=10,race_mode='online');folder=Path(e['folder']);(folder/'session.json').write_text(json.dumps(e['session']));(folder/'review.html').write_text('fixture')
    return dict(entries=items,counts={p:sum(e['place']==p for e in items) for p in (1,2,3)},missing_class_results=1,conflicts=0)


def detail(e):
    return dict(marker=e['folder'],start=dict(fuel_l=30.,track_temp_c=25.,wetness=0.,rain=0.),end=dict(fuel_l=20.,track_temp_c=26.,wetness=0.,rain=0.),recorded_s=300.,race_s=280.,fastest_s=e['fastest_s'],completed_laps=3,pace=[dict(time_s=100.,lap=1,lap_s=100.,eligible=True,best=True),dict(time_s=200.,lap=2,lap_s=101.,eligible=False,best=False)],inputs=[(0,[0.,0.],[1.,.5]),(599,[.5,0.],[1.,1.])],partial=False)


class Rules(unittest.TestCase):
    def test_detail_key_ignores_annotations_but_tracks_physical_compression_and_summary(self):
        from control_record_details import key
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            e=podiums(tmp,1)['entries'][0];before=key(e);other=deepcopy(e);other.update(tags=['training'],favorite=True);self.assertEqual(before,key(other));file=Path(e['folder'])/'inputs.csv.stc';file.write_bytes(b'changed');self.assertNotEqual(before,key(e));before=key(e);other=deepcopy(e);other['summary']['race_finished_et']=400.;self.assertNotEqual(before,key(other))
    def test_cache_has_two_snapshots_and_reader_never_queues_intermediate_selection(self):
        from control_record_details import DetailLoader
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            jobs=[];app=SimpleNamespace(run_background=lambda work,done:jobs.append((work,done)));page=SimpleNamespace(alive=lambda:True,feedback=SimpleNamespace(busy=Mock()),apply_detail=Mock(),detail_waiting=Mock());loader=DetailLoader(app);loader.attach(page,detail);entries=podiums(tmp,5)['entries']
            for e in entries:loader.select(e)
            self.assertEqual(len(jobs),1);jobs[0][1](jobs[0][0](),None);self.assertEqual(len(jobs),2);self.assertEqual(jobs[1][0].args[0]['folder'],entries[-1]['folder']);jobs[1][1](jobs[1][0](),None);self.assertEqual(page.apply_detail.call_args.args[0]['marker'],entries[-1]['folder']);loader.select(entries[2]);jobs[2][1](jobs[2][0](),None);self.assertEqual(len(loader.cache),2)
    def test_xml_only_key_tracks_official_values(self):
        from control_record_details import key
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            e=podiums(tmp,1)['entries'][0];e.update(xml_only=True,official_result=dict(laps=[dict(time_s=100.)]));before=key(e);e['official_result']['laps'][0]['time_s']=99.9;self.assertNotEqual(before,key(e))

    def test_failed_selection_is_not_retried_when_an_unrelated_read_also_fails(self):
        from control_record_details import DetailLoader
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            jobs=[];app=SimpleNamespace(run_background=lambda work,done:jobs.append(done));page=SimpleNamespace(alive=lambda:True,feedback=SimpleNamespace(busy=Mock()),apply_detail=Mock(),detail_waiting=Mock());loader=DetailLoader(app);loader.attach(page,detail);a,b=podiums(tmp,2)['entries']
            loader.select(a);jobs[0](None,'A failed');loader.select(b);loader.select(a);jobs[1](None,'B failed');loader.select(a);self.assertEqual(len(jobs),2);self.assertEqual(page.apply_detail.call_args.args,(None,'A failed'));loader.select(a,True);self.assertEqual(len(jobs),3);self.assertLessEqual(len(loader.failures),2)

    def test_empty_worker_error_stays_a_failure_and_can_be_retried(self):
        from control_record_details import DetailLoader
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            jobs=[];app=SimpleNamespace(run_background=lambda work,done:jobs.append(done));page=SimpleNamespace(alive=lambda:True,feedback=SimpleNamespace(busy=Mock()),apply_detail=Mock(),detail_waiting=Mock());loader=DetailLoader(app);loader.attach(page,detail);e=podiums(tmp,1)['entries'][0]
            loader.select(e);jobs[0](None,'');self.assertFalse(loader.cache);self.assertTrue(page.apply_detail.call_args.args[1]);loader.select(e);self.assertEqual(len(jobs),1);loader.select(e,True);self.assertEqual(len(jobs),2)

    def test_background_exception_without_message_never_looks_successful(self):
        from background import BackgroundTasks
        tasks=BackgroundTasks(1)
        try:
            future=tasks.submit(lambda:(_ for _ in ()).throw(OSError()),Mock());future.result(timeout=3);completed=list(tasks.completions());self.assertEqual(len(completed),1);self.assertIsNone(completed[0][1]);self.assertEqual(completed[0][2],'OSError')
        finally:tasks.close()


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump;tab=fixtures.UI.tab
    def mount(self,app,root,value=None):
        value=value or podiums(root)
        with patch('control_podiums.read_index',return_value=value),patch('control_podiums.detail',side_effect=detail):
            app.personal_record_view='podium';app.show_page(6);self.pump(app,.35)
        return app.record_loaders['podium'].page,value
    def test_same_selected_race_filters_and_annotations_reuse_detail_snapshot(self):
        app,root,errors=self.app();value=podiums(root)
        with patch('control_podiums.detail',side_effect=detail) as loaded,patch('control_podiums.read_index',return_value=value):
            app.personal_record_view='podium';app.show_page(6);self.pump(app,.35);p=app.record_loaders['podium'].page;self.assertEqual(loaded.call_count,1);picture=p.header.picture;self.assertIsNotNone(picture);p.query.set('BMW');p.choose_category(p.selected['place']);self.pump(app,.1);self.assertEqual(loaded.call_count,1);self.assertIs(p.header.picture,picture)
            for e in value['entries']:e['tags']=['changed note']
            p.loader.read();self.pump(app,.25);self.assertEqual(loaded.call_count,1)
        self.assertIsNotNone(p.state['data']);self.assertFalse(errors)
    def test_rapid_selection_reads_running_and_latest_only_and_drops_stale_payload(self):
        app,root,errors=self.app();p,value=self.mount(app,root);jobs=[]
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append((work,done))):
            for row in p.table.order[1:4]:p.table.selection_set((row,))
            wanted=p.selected['folder'];self.assertEqual(len(jobs),1);self.assertIsNone(p.state['data']);jobs[0][1](detail(jobs[0][0].args[0]),None);self.assertEqual(len(jobs),2);self.assertIsNone(p.state['data']);jobs[1][1](detail(jobs[1][0].args[0]),None)
        self.assertEqual(p.state['data']['marker'],wanted);self.assertLessEqual(len(p.details.cache),2);self.assertFalse(errors)
    def test_selecting_cached_record_cancels_pending_request_without_showing_running_record(self):
        app,root,errors=self.app();p,value=self.mount(app,root);first=p.selected['folder'];first_id=p.table.selection()[0];jobs=[]
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append((work,done))):
            p.table.selection_set((p.table.order[1],));p.table.selection_set((p.table.order[2],));p.table.selection_set((first_id,));self.assertEqual(p.state['data']['marker'],first);jobs[0][1](detail(jobs[0][0].args[0]),None);self.assertEqual(len(jobs),1)
        self.assertEqual(p.state['data']['marker'],first);self.assertFalse(errors)
    def test_physical_source_change_invalidates_snapshot(self):
        app,root,errors=self.app();p,value=self.mount(app,root);(Path(p.selected['folder'])/'inputs.csv.stc').write_bytes(b'new source')
        with patch('control_podiums.detail',side_effect=detail) as loaded:p.choose();self.pump(app,.25);self.assertEqual(loaded.call_count,1)
        self.assertFalse(errors)
    def test_detail_failure_waits_for_explicit_retry_and_preserves_selection(self):
        app,root,errors=self.app();p,value=self.mount(app,root);row=p.table.order[1]
        with patch('control_podiums.detail',side_effect=OSError('read fixture')) as loaded:
            p.table.selection_set((row,));self.pump(app,.25);self.assertTrue(p.buttons['retry'].enabled);p.query.set('BMW');self.pump(app,.1);self.assertEqual(loaded.call_count,1);self.assertEqual(p.table.selection(),(row,))
        with patch('control_podiums.detail',side_effect=detail):p.buttons['retry'].invoke();self.pump(app,.25)
        self.assertFalse(p.state['error']);self.assertFalse(p.buttons['retry'].enabled);self.assertIsNotNone(p.state['data']);self.assertFalse(errors)
    def test_empty_filter_clears_details_hover_and_disables_unavailable_actions(self):
        app,root,errors=self.app();p,value=self.mount(app,root);self.assertTrue(p.state['dots']);p.query.set('no matching fixture');self.assertIsNone(p.selected);self.assertIsNone(p.state['data']);self.assertEqual(p.state['dots'],[]);self.assertFalse(p.buttons['card'].enabled);self.assertFalse(p.buttons['review'].enabled);self.assertFalse(p.feedback.tasks)
        self.assertTrue(all(b.enabled for b in p.category_buttons.values()));self.assertTrue(all(b.label.endswith('0') for b in p.category_buttons.values()));self.assertFalse(errors)
    def test_award_counts_follow_query_and_category(self):
        app,root,errors=self.app();p,value=self.mount(app,root);p.query.set('Track A');self.assertEqual(len(p.table.rows),6);self.assertTrue(p.category_buttons[0].label.endswith('6'));self.assertTrue(all(p.category_buttons[i].label.endswith('2') for i in (1,2,3)));p.choose_category(3);self.assertEqual(len(p.table.rows),2);self.assertFalse(errors)
    def test_sibling_return_preserves_category_search_selection_scroll_and_loaded_snapshot(self):
        app,root,errors=self.app();p,value=self.mount(app,root,podiums(root,36))
        with patch('control_podiums.detail',side_effect=detail):p.choose_category(2);self.pump(app,.25)
        p.query.set('BMW');p.table.selection_set((p.table.order[5],))
        with patch('control_podiums.detail',side_effect=detail):self.pump(app,.25)
        selected=p.identity(p.selected);p.table.set_offset(100);variables=list(p.variables.values())
        with patch('control_official_results.read_results',return_value=fixtures.official(root)):self.tab(app,'官方战绩')
        self.assertTrue(p.disposed);self.assertIsNone(p.details.page);self.assertTrue(all(v._tk is None for v in variables))
        with patch('control_podiums.read_index',return_value=value),patch('control_podiums.detail') as loaded:self.tab(app,'领奖台记录');loaded.assert_not_called()
        current=app.record_loaders['podium'].page;self.assertEqual(current.state['category'],2);self.assertEqual(current.query.get(),'BMW');self.assertEqual(current.identity(current.selected),selected);self.assertEqual(current.table.offset,100);self.assertIsNotNone(current.state['data']);self.assertFalse(errors)
        variables=list(current.variables.values())
        try:
            app.close()
            try:self.pump(app,.1)
            except __import__('tkinter').TclError:pass
            self.assertTrue(current.disposed);self.assertIsNone(current.details.page);self.assertTrue(all(v._tk is None for v in variables));self.assertFalse(errors)
        finally:
            try:gone=not app.root.winfo_exists()
            except __import__('tkinter').TclError:gone=True
            if gone:app.close=lambda:None

    def test_detail_completion_after_leaving_page_has_no_destroyed_tk_access(self):
        app,root,errors=self.app();p,value=self.mount(app,root);jobs=[]
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append((work,done))):
            p.table.selection_set((p.table.order[1],));app.show_page(0);self.pump(app,.05);jobs[0][1](None,'late fixture')
        self.assertTrue(p.disposed);self.assertIsNone(p.details.page);self.assertIsNone(p.details.pending);self.assertFalse(errors)
    def test_refresh_reorders_rows_without_reading_unchanged_details(self):
        app,root,errors=self.app();p,value=self.mount(app,root);p.table.selection_set((p.table.order[3],))
        with patch('control_podiums.detail',side_effect=detail):self.pump(app,.25)
        selected=p.identity(p.selected);p.table.set_offset(80);changed=dict(value,entries=list(reversed(deepcopy(value['entries']))))
        with patch.object(p.loader,'reader',new=lambda:changed),patch('control_podiums.detail') as loaded:p.loader.read();self.pump(app,.25);loaded.assert_not_called()
        self.assertEqual(p.identity(p.selected),selected);self.assertEqual(p.table.offset,80);self.assertFalse(errors)
    def test_primary_and_report_buttons_keep_independent_entry_points(self):
        app,root,errors=self.app();p,value=self.mount(app,root)
        with patch('control_record_browser.os.startfile') as opened:p.primary();opened.assert_called_once_with(str(Path(p.selected['folder'])/'review.html'))
        with patch('control_report_images.show') as opened:p.buttons['laps'].invoke();p.buttons['journal'].invoke();self.assertEqual(opened.call_count,2);self.assertEqual([c.args[-1] for c in opened.call_args_list],['圈速单.png','比赛日志.png'])
        self.assertFalse(errors)
    def test_xml_only_record_has_timings_without_invented_inputs_and_opens_original(self):
        from podium_records import detail as actual
        app,root,errors=self.app();value=podiums(root,1);e=value['entries'][0];e.update(xml_only=True,official_result=fixtures.official(root,1)['entries'][0])
        with patch('control_podiums.read_index',return_value=value),patch('control_podiums.detail',side_effect=actual):app.personal_record_view='podium';app.show_page(6);self.pump(app,.35)
        p=app.record_loaders['podium'].page;self.assertTrue(p.state['data']['xml_only']);self.assertIn('灰色不代表处罚',p.pace_hint.cget('text'));self.assertEqual(p.state['data']['inputs'],[]);self.assertFalse(p.buttons['review'].enabled);self.assertFalse(p.buttons['laps'].enabled);self.assertFalse(p.buttons['journal'].enabled);self.assertTrue(p.buttons['xml'].enabled)
        with patch('control_record_browser.os.startfile') as opened:p.primary();opened.assert_called_once_with(e['official_result']['source_xml'])
        self.assertFalse(errors)
    def test_actual_language_switch_and_minimum_width_keep_category_and_actions_readable(self):
        import i18n
        app,root,errors=self.app();p,value=self.mount(app,root);p.choose_category(p.selected['place']);selected=p.identity(p.selected)
        try:
            with patch('control_podiums.read_index',return_value=value):app.toggle_language();self.pump(app,.3)
            p=app.record_loaders['podium'].page;self.assertEqual(p.identity(p.selected),selected)
            for mode in ('light','dark'):
                app.set_theme(mode);app.root.geometry('1060x700');self.pump(app,.15)
                for b in p.buttons.values():self.assertGreater(b.winfo_width(),b.font.measure(i18n.tr(b.label))+15);self.assertLessEqual(b.winfo_rootx()+b.winfo_width(),app.root.winfo_rootx()+app.root.winfo_width()+1)
            self.assertFalse(errors)
        finally:i18n.set_language('zh')

    def test_missing_pedal_samples_have_explicit_empty_state(self):
        app,root,errors=self.app();p,value=self.mount(app,root);empty=detail(p.selected);empty['inputs']=[]
        with patch('control_podiums.detail',return_value=empty):p.details.select(p.selected,True);self.pump(app,.25)
        canvas=p.curves['inputs'];texts=[canvas.itemcget(i,'text') for i in canvas.find_all() if canvas.type(i)=='text'];self.assertTrue(any('没有可用的油门' in t for t in texts));self.assertFalse(errors)

    def test_explicit_refresh_also_retries_a_failed_detail_without_changing_selection(self):
        app,root,errors=self.app();p,value=self.mount(app,root);row=p.table.order[1]
        with patch('control_podiums.detail',side_effect=OSError('retry fixture')):p.table.selection_set((row,));self.pump(app,.25)
        selected=p.identity(p.selected);self.assertTrue(p.state['error'])
        with patch('control_podiums.detail',side_effect=detail) as loaded:p.buttons['refresh'].invoke();self.pump(app,.3);self.assertEqual(loaded.call_count,1)
        self.assertEqual(p.identity(p.selected),selected);self.assertFalse(p.state['error']);self.assertIsNotNone(p.state['data']);self.assertFalse(errors)
