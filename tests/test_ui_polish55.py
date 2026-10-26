"""Cross-window workflow checks with isolated local fixtures and no real records."""
import json,os,unittest,threading
from pathlib import Path
from unittest.mock import patch
from tests import test_ui_efficiency as helpers


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def test_pair_search_keeps_choices_and_does_not_scan_unselected_sessions(self):
        from control_lap_pair import show
        app,root,errors=self.app()
        records=[dict(folder=str(root/f'Logs/{i}'),key=f'Logs/{i}',track=track,track_layout='Full',track_length_m=5000,vehicle=car,date='2026-10-20',session_type='Race',status='complete') for i,(track,car) in enumerate([('Monza','BMW'),('Fuji Speedway','Ferrari')])]
        laps=[dict(number=1,time_s=100,track_length_m=5000),dict(number=2,time_s=98,track_length_m=5000)]
        with patch('control_lap_pair.inventory',return_value=records),patch('control_lap_pair.valid_laps',return_value=laps) as scan,patch('control_lap_pair.finished_metadata',return_value=records[0]):
            w=show(app,root);self.pump(app,.4);c=w.pair_controls
            before=[v.get() for v in c['events'].values()];numbers=[v.get() for v in c['numbers'].values()]
            c['query'].set('富士 Ferrari');self.assertEqual(len(c['event_boxes']['A'].values),1)
            c['query'].set('no matches');self.assertEqual(c['event_boxes']['A'].values,[])
            self.assertEqual([v.get() for v in c['events'].values()],before);self.assertEqual([v.get() for v in c['numbers'].values()],numbers)
            c['search'].clear();self.assertEqual(len(c['event_boxes']['B'].values),2);self.assertEqual(scan.call_count,2)
            app.root.focus_force();w.focus_force();w.event_generate('<Control-f>');self.pump(app,.05);self.assertIs(w.focus_get(),c['search'].entry)
            w.destroy();self.pump(app,.05)
        self.assertFalse(errors)
    def test_batch_filters_and_copy_errors_do_not_change_retry_scope(self):
        from control_batch import start
        app,root,errors=self.app();calls=[]
        def work(v):
            calls.append(v)
            if v in (1,3) and calls.count(v)==1:raise ValueError(f'failure detail {v}')
            return dict(value=v)
        job=start(app,'赛事包导出任务',[1,2,3],work,names=['one','two','three']);self.pump(app,.4)
        job.view.set('failed');job.query.set('three');job.render();self.assertEqual(job.table.get_children(),('2',))
        with patch.object(job.table,'copy_text') as copy:
            job.copy_button.invoke();value=copy.call_args.args[0];self.assertIn('failure detail 1',value);self.assertIn('failure detail 3',value);self.assertNotIn('two',value)
        job.retry_button.invoke();self.pump(app,.4);self.assertEqual(calls,[1,2,3,1,3]);self.assertFalse(job.table.get_children());self.assertFalse(job.copy_button.enabled)
        job.view.set('all');job.search_field.clear();self.assertEqual(len(job.table.get_children()),3);self.assertFalse(errors)
    def test_pending_filter_tracks_running_and_unprocessed_items(self):
        from control_batch import start
        app,root,errors=self.app();gate=threading.Event();entered=threading.Event()
        def work(v):entered.set();gate.wait(3);return v
        try:
            job=start(app,'赛事包导入任务',[1,2],work);self.assertTrue(entered.wait(1));self.pump(app,.15)
            job.view.set('pending');job.render();self.assertEqual(len(job.table.get_children()),2);job.stop_after()
        finally:gate.set()
        self.pump(app,.4);self.assertEqual(job.states,['已完成','等待处理']);self.assertEqual(job.table.get_children(),('1',));self.assertTrue(job.resume_button.enabled);self.assertFalse(errors)
    def test_video_filter_restores_selection_and_enter_uses_available_report(self):
        from control_video_results import show
        app,root,errors=self.app()
        for name,track in [('one','Monza'),('two','Fuji Speedway')]:
            folder=root/'VideoCurves'/name;folder.mkdir(parents=True)
            (folder/'curve.json').write_text(json.dumps(dict(format='stintrix.video-curves',version=1,identity=dict(track=track),video_file=name+'.mp4',quality={},rows=[])),'utf-8')
            (folder/'report_120hz.html').write_text('report','utf-8')
        w=show(app,root);self.pump(app,.4);table=w.results_table;key=str(root/'VideoCurves/one');table.selection_set((key,));self.pump(app,.05)
        w.results_search.set('Fuji');self.pump(app,.12);self.assertEqual(table.selection(),());self.assertFalse(w.results_buttons['history'].enabled)
        w.results_search_field.clear();self.assertEqual(table.selection(),(key,));self.assertFalse(w.results_buttons['raw'].enabled);self.assertTrue(w.results_buttons['smooth'].enabled)
        w.focus_force();w.results_search_field.entry.focus_set()
        with patch('control_video_results.os.startfile') as opener:
            w.results_search_field.entry.event_generate('<Return>');self.pump(app,.05);opener.assert_not_called()
            table.viewport.focus_set();table.viewport.event_generate('<Return>');self.pump(app,.05);opener.assert_called_once_with(str(root/'VideoCurves/one/report_120hz.html'))
        self.assertFalse(errors)
    def test_history_switch_is_explicit_and_preserves_unsubmitted_inputs(self):
        from tests.test_video_history import fixture
        from control_video_history import show
        app,root,errors=self.app();_,_,first=fixture(root/'VideoCurves/one');_,_,second=fixture(root/'VideoCurves/two')
        with patch('video_history.history_laps',return_value=[]):
            old=show(app,root,first);self.pump(app,.4);self.assertEqual(old.history_path,first.resolve())
            with patch('control_video_history.filedialog.askopenfilename') as picker:self.assertIs(show(app,root),old);picker.assert_not_called()
            old.history_controls['marks'].insert('1.0','T1 = 0:12.500');self.assertTrue(old.history_dirty())
            with patch('control_video_history.ask',return_value='cancel'):self.assertIs(show(app,root,second),old)
            self.assertEqual(old.history_controls['marks'].get('1.0','end-1c'),'T1 = 0:12.500')
            with patch('control_video_history.ask',return_value='discard'):new=show(app,root,second)
            self.pump(app,.4);self.assertFalse(old.winfo_exists());self.assertEqual(new.history_path,second.resolve());self.assertIn('fixture.mp4',new.history_controls['source'].cget('text'))
        self.assertFalse(errors)
    def test_busy_history_does_not_silently_replace_video_and_close_protects_draft(self):
        from tests.test_video_history import fixture
        from control_video_history import show
        app,root,errors=self.app();_,_,first=fixture(root/'VideoCurves/one');_,_,second=fixture(root/'VideoCurves/two');gate=threading.Event()
        try:
            with patch('video_history.history_laps',side_effect=lambda *args:(gate.wait(3),[])[1]):
                w=show(app,root,first);self.pump(app,.1);self.assertTrue(w.history_state['busy']);self.assertIs(show(app,root,second),w);self.assertEqual(w.history_path,first.resolve())
                w.history_controls['marks'].insert('1.0','test');self.assertTrue(w.history_dirty());gate.set();self.pump(app,.4)
            self.assertTrue(w.history_dirty());done=[]
            with patch('control_video_history.ask',return_value='cancel'):w.history_controls['close'](lambda:done.append(True),exiting=True)
            self.assertTrue(w.winfo_exists());self.assertEqual(done,[])
            with patch('control_video_history.ask',return_value='discard'):w.history_controls['close'](lambda:done.append(True),exiting=True)
            self.assertEqual(done,[True]);self.assertTrue(w.history_state['cancel'].is_set());self.assertFalse(errors)
        finally:gate.set()
    def test_auxiliary_language_and_theme_switch_keep_search_and_draft_state(self):
        from control_batch import start
        from control_video_history import show
        from tests.test_video_history import fixture
        app,root,errors=self.app();_,_,path=fixture(root/'VideoCurves/one')
        job=start(app,'赛事包导出任务',[1],lambda _:None,names=['sample']);self.pump(app,.3);job.query.set('sample');job.view.set('failed');job.render()
        with patch('video_history.history_laps',return_value=[]):w=show(app,root,path);self.pump(app,.3)
        w.history_controls['marks'].insert('1.0','T1 = 0:12.500');w.history_controls['binding'].set(True)
        for _ in range(2):
            app.toggle_language();app.set_theme('light');app.set_theme('dark');self.pump(app,.15)
            self.assertEqual(job.query.get(),'sample');self.assertEqual(job.view.get(),'failed');self.assertTrue(w.history_controls['binding'].get());self.assertTrue(w.history_dirty())
        self.assertFalse(errors)
