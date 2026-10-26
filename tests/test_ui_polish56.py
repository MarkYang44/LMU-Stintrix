"""Maintenance workflows use isolated data, real receipts and explicit user actions."""
import json,os,threading,unittest
from pathlib import Path
from unittest.mock import patch
from tests import test_ui_efficiency as helpers


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value),'utf-8')


def session(root,name,state='error'):
    from report_state import STEPS
    folder=root/'Logs'/name;folder.mkdir(parents=True)
    write(folder/'session.json',dict(status='complete',started_utc='2026-10-20T12:00:00Z',track='Monza',vehicle='BMW'))
    (folder/'inputs.csv').write_bytes(b'original evidence\n')
    steps={key:dict(state='ready') for key in STEPS}
    if state!='ready':steps['review']=dict(state=state,error='Long readable failure details')
    write(folder/'report_status.json',dict(version=2,state=state,steps=steps));return folder


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def test_report_search_refresh_and_copy_keep_stable_folder_selection(self):
        from control_maintenance import reports
        app,root,errors=self.app();a=session(root,'a');b=session(root,'b','ready');w=reports(app);view=w.worklist;self.pump(app,.4)
        self.assertIs(reports(app),w);self.assertEqual(view.table.get_children(),(str(a),));view.table.selection_set((str(a),));self.pump(app,.05)
        self.assertIn('Long readable failure',view.details.get('1.0','4.0'));view.query.set('missing');self.pump(app,.12);self.assertFalse(view.table.selection());view.search.clear();self.assertEqual(view.table.selection(),(str(a),))
        view.buttons['refresh'].invoke();self.pump(app,.4);self.assertEqual(view.table.selection(),(str(a),))
        w.focus_force();w.event_generate('<Control-f>');self.pump(app,.05);self.assertIs(w.focus_get(),view.search.entry)
        view.query.set('Monza');view.search.entry.event_generate('<Escape>');self.pump(app,.05);self.assertEqual(view.query.get(),'');self.assertTrue(w.winfo_exists())
        with patch.object(view.table,'copy_text') as copy:view.buttons['copy'].invoke();self.assertIn('Long readable failure',copy.call_args.args[0])
        view.view.set('all');view.render();self.assertEqual(set(view.table.get_children()),{str(a),str(b)});self.assertFalse(errors)
    def test_report_retry_skips_ready_and_continues_after_one_failure(self):
        from control_maintenance import reports
        app,root,errors=self.app();bad=session(root,'bad');good=session(root,'good');ready=session(root,'ready','ready');original={str(p):p.read_bytes() for folder in (bad,good,ready) for p in (folder/'session.json',folder/'inputs.csv')}
        w=reports(app);self.pump(app,.4);view=w.worklist;view.view.set('all');view.render();view.table.selection_set(view.table.get_children());self.pump(app,.05);calls=[]
        def run(folder,data):
            calls.append(folder.name)
            if folder.name=='bad':raise RuntimeError('one failed')
            value=json.loads((folder/'report_status.json').read_text());value['state']='ready'
            for step in value['steps'].values():step['state']='ready'
            write(folder/'report_status.json',value)
        with patch('report_worker.run',side_effect=run):view.buttons['retry'].invoke();self.pump(app,.8)
        self.assertEqual(set(calls),{'bad','good'});self.assertEqual(sorted(app.report_retry_job.states),['失败','已完成']);self.assertEqual(view.table.get_children(),tuple(str(p) for p in (bad,good,ready)))
        self.assertTrue(all(Path(name).read_bytes()==value for name,value in original.items()));self.assertFalse(errors)
    def test_malformed_receipt_is_visible_but_never_overwritten(self):
        from control_maintenance import reports
        app,root,errors=self.app();folder=session(root,'malformed');path=folder/'report_status.json';write(path,dict(version=2,state='error',steps=['unrecognized']));before=path.read_bytes()
        w=reports(app);self.pump(app,.4);view=w.worklist;view.table.selection_set((str(folder),));self.pump(app,.05)
        self.assertIn('原文件已保留',view.details.get('1.0','end'));self.assertFalse(view.buttons['retry'].enabled);self.assertTrue(view.buttons['folder'].enabled)
        with patch('control_report_tasks.os.startfile') as opener:view.buttons['folder'].invoke();opener.assert_called_once_with(str(folder))
        self.assertEqual(path.read_bytes(),before);self.assertFalse(errors)
    def test_report_deferred_job_remains_retryable_and_blocks_record_start(self):
        from control_maintenance import reports
        from report_worker import ReportDeferred
        app,root,errors=self.app();folder=session(root,'deferred');w=reports(app);self.pump(app,.4);view=w.worklist;view.table.selection_set((str(folder),));self.pump(app,.05);gate=threading.Event();entered=threading.Event()
        def run(*_):entered.set();gate.wait(3);raise ReportDeferred('wait for memory')
        try:
            with patch('report_worker.run',side_effect=run),patch('hud.App') as hud:
                view.buttons['retry'].invoke();self.assertTrue(entered.wait(1));app.start();hud.assert_not_called();gate.set();self.pump(app,.7)
            self.assertEqual(app.report_retry_job.states,['部分失败']);self.assertTrue(app.report_retry_job.retry_button.enabled);self.assertTrue((folder/'report_pending.json').exists());self.assertFalse(errors)
            app.report_retry_job.hide();view.buttons['progress'].invoke();self.pump(app,.05);self.assertEqual(app.report_retry_job.window.state(),'normal')
        finally:gate.set()
    def test_cache_selection_cancel_and_frozen_confirm_preserve_originals(self):
        from control_maintenance import caches
        app,root,errors=self.app();cache=root/'PersonalRecords/TrainingCache/data.bin';cache.parent.mkdir(parents=True);cache.write_bytes(b'cache');race=root/'Logs/original.bin';race.parent.mkdir(parents=True);race.write_bytes(b'original')
        w=caches(app);self.pump(app,.4);view=w.worklist;self.assertIs(caches(app),w)
        view.table.selection_set(('training','races'));self.pump(app,.05);self.assertFalse(view.buttons['clean'].enabled)
        view.table.selection_set(('training',));self.pump(app,.05)
        with patch('control_danger.confirm',return_value=False):view.buttons['clean'].invoke()
        self.assertEqual(cache.read_bytes(),b'cache')
        def confirm(*args,**kwargs):
            self.assertIn(str(cache.parent),args[3][0]);view.table.selection_set(('races',));return True
        with patch('control_danger.confirm',side_effect=confirm):view.buttons['clean'].invoke();self.pump(app,.6)
        self.assertFalse(cache.exists());self.assertEqual(race.read_bytes(),b'original');self.assertIn('释放',view.status.get());self.assertFalse(errors)
    def test_cache_rechecks_runtime_after_confirm(self):
        from control_maintenance import caches
        app,root,errors=self.app();path=root/'PersonalRecords/TrainingCache/x';path.parent.mkdir(parents=True);path.write_text('cache');w=caches(app);self.pump(app,.4);view=w.worklist;view.table.selection_set(('training',));self.pump(app,.05);active=[False]
        def confirm(*_args,**_kwargs):active[0]=True;return True
        with patch.object(app,'active',side_effect=lambda:active[0]),patch('control_danger.confirm',side_effect=confirm),patch('control_cache_panel.clear') as clear:
            view.buttons['clean'].invoke();clear.assert_not_called();active[0]=False
        from types import SimpleNamespace
        from control_maintenance import offline_ready
        app.hud=SimpleNamespace(closing=True,root=app.root)
        try:self.assertFalse(app.active());self.assertFalse(offline_ready(app));view.sync();self.assertFalse(view.buttons['clean'].enabled)
        finally:app.hud=None
        self.assertTrue(path.exists());self.assertFalse(errors)
    def test_cache_worker_can_finish_after_window_close_and_recording_stays_locked(self):
        from control_maintenance import caches,busy
        app,root,errors=self.app();w=caches(app);self.pump(app,.4);view=w.worklist;gate=threading.Event();entered=threading.Event()
        def organize(*_args,**_kwargs):entered.set();gate.wait(3);return {}
        try:
            with patch('cache_budget.enforce',side_effect=organize),patch('hud.App') as hud:
                view.buttons['organize'].invoke();self.assertTrue(entered.wait(1));self.assertTrue(busy(app));app.start(True);hud.assert_not_called();w.destroy();gate.set();self.pump(app,.5)
            self.assertFalse(busy(app));self.assertFalse(errors)
        finally:gate.set()
    def test_split_next_and_undo_preserve_sources_and_selection(self):
        from control_split_checks import show
        app,root,errors=self.app();folders=[session(root,name) for name in ('a','b','c','d')];original={str(p):p.read_bytes() for folder in folders for p in (folder/'session.json',folder/'inputs.csv')}
        def part(folder):return dict(folder=str(folder),track='Monza',vehicle='BMW',date='2026-10-20T12:00:00Z')
        pairs=[dict(id=str(folders[i])+'\n'+str(folders[i+1]),first=part(folders[i]),second=part(folders[i+1]),gap_s=20,reason='waiting') for i in (0,2)]
        with patch('control_split_checks.candidates',side_effect=lambda items,checked:[p for p in pairs if p['id'] not in checked]):
            w=show(app);self.pump(app,.4);view=w.worklist;self.assertIs(show(app),w);self.assertFalse(view.buttons['checked'].enabled);view.table.selection_set((pairs[0]['id'],));self.pump(app,.05)
            view.buttons['checked'].invoke();self.pump(app,.4);self.assertEqual(view.table.selection(),(pairs[1]['id'],));self.assertTrue(view.buttons['undo'].enabled)
            view.buttons['undo'].invoke();self.pump(app,.4);self.assertEqual(view.table.selection(),(pairs[0]['id'],));self.assertFalse(view.buttons['undo'].enabled)
        self.assertTrue(all(Path(name).read_bytes()==value for name,value in original.items()));self.assertFalse(errors)
    def test_load_failure_and_late_result_do_not_overwrite_current_list(self):
        from control_worklist import WorkList
        app,root,errors=self.app();view=WorkList(app,'test',[('name','Name',150)],lambda item:item,lambda item:(item,));gate=threading.Event()
        try:
            view.load(lambda:(gate.wait(3),['old'])[1],'old');view.load(lambda:['new'],'new');self.pump(app,.3);gate.set();self.pump(app,.3);self.assertEqual(view.table.get_children(),('new',))
            view.load(lambda:(_ for _ in ()).throw(ValueError('read failed')),'ignored');self.pump(app,.3);self.assertEqual(view.status.get(),'read failed');self.assertEqual(view.table.get_children(),('new',));self.assertFalse(view.loading);view.window.destroy();self.assertFalse(errors)
        finally:gate.set()
    def test_maintenance_theme_language_and_search_keep_context(self):
        from control_maintenance import reports,caches
        app,root,errors=self.app();folder=session(root,'a');windows=[reports(app),caches(app)];self.pump(app,.4);view=windows[0].worklist;view.table.selection_set((str(folder),));self.pump(app,.05);view.query.set('Monza')
        for _ in range(2):
            app.toggle_language();app.set_theme('light');app.set_theme('dark');self.pump(app,.15)
            from i18n import tr
            for button in view.buttons.values():self.assertLess(button.font.measure(tr(button.label)),button.winfo_width())
        self.assertEqual(view.query.get(),'Monza');self.assertEqual(view.table.selection(),(str(folder),));self.assertFalse(errors)


class Rules(unittest.TestCase):
    def test_split_marks_preserve_unknown_fields_and_reject_corrupt_state(self):
        import tempfile
        from tests.test_ui_efficiency import ROOT
        from split_checks import mark,unmark
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            root=Path(tmp);path=root/'EventCatalog/split_checks.json';write(path,dict(custom=17,checked=['other']))
            self.assertTrue(mark(root,'pair'));self.assertTrue(unmark(root,'pair'));self.assertEqual(json.loads(path.read_text()),dict(version=1,custom=17,checked=['other']))
            path.write_bytes(b'corrupt original');before=path.read_bytes()
            for operation in (mark,unmark):
                with self.assertRaises(ValueError):operation(root,'pair')
                self.assertEqual(path.read_bytes(),before)
