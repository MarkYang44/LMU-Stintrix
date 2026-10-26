"""Analysis drafts, request coalescing, snapshot exports and small-window recovery."""
import json,os,sys,tempfile,threading,unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from tests import test_ui_efficiency as helpers
from tests import test_career_analysis as fixtures


def training():
    zones=[dict(name='制动区 '+str(i+1),source='automatic',start=i*500,end=(i+1)*500,apex=i*500+250,median_loss_s=.4,std_s=.1,count=4,slower_fraction=.8,differences=dict(brake_m=3,minimum_kmh=-2,full_m=5)) for i in range(3)]
    return dict(entry=fixtures.entry(),reference=dict(number=1,time_s=100,session=dict(started_utc='2026-10-20T12:00:00Z')),count=4,unknown=[],priorities=zones,excluded=0,condition_excluded=0,errors=[])


def comparable():
    return dict(entry=fixtures.entry(),policy=dict(__import__('condition_match').DEFAULTS),sessions=[dict(observed_utc='2026-10-20T12:00:00Z',folder='folder/'+str(i),count=3,median_s=100-i,best_s=99-i,std_s=.1,qualified=True,unknown=[],fuel_range_l=[30,31],session=dict(session=10,race_mode='online')) for i in range(3)],summary=dict(pace_gain_s=1,consistency_gain_s=.1),excluded=dict(unknown=1,different=2))


class Rules(unittest.TestCase):
    def test_preferences_merge_unknown_fields_and_reject_corrupt_original(self):
        from control_analysis_window import analyse
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            path=Path(tmp)/'settings.json';path.write_text(json.dumps(dict(custom=dict(keep=7),fuel_l=3)))
            self.assertEqual(analyse(lambda policy:policy['fuel_l'],path,dict(fuel_l=2)),2);self.assertEqual(json.loads(path.read_text())['custom'],dict(keep=7))
            with patch('storage.atomic_json',side_effect=AssertionError('Do not rewrite unchanged preferences')):self.assertEqual(analyse(lambda p:p['fuel_l'],path,dict(fuel_l=2)),2)
            for data in ('broken','[]'):
                path.write_text(data)
                with self.assertRaises(ValueError):analyse(lambda _:self.fail('Do not analyse corrupt settings'),path,{})
                self.assertEqual(path.read_text(),data)
    def test_settings_write_failure_prevents_scan(self):
        from control_analysis_window import analyse
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp,patch('storage.atomic_json',side_effect=OSError('write fixture')):
            with self.assertRaises(OSError):analyse(lambda _:self.fail('No scan after write failure'),Path(tmp)/'settings.json',{})
    def test_identity_includes_source_version_and_conditions(self):
        from control_analysis_window import key
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            e=fixtures.entry();e.update(folder=tmp,file=str(Path(tmp)/'lap.json'));p=Path(e['file']);p.write_text('{}');first=key(e);self.assertEqual(first,key(deepcopy(e)));p.write_text('{"version":2}');self.assertNotEqual(first,key(e));other=deepcopy(e);other['conditions']['fuel_l']=40;self.assertNotEqual(key(e),key(other))


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def panel(self,app,root,kind='training',response=None):
        module='training_report.report' if kind=='training' else 'comparable_progress.analyse';value=response or (training() if kind=='training' else comparable());e=fixtures.entry();e.update(folder=str(root/'Logs/fixture'),file=str(root/'Logs/fixture/lap.json'))
        guard=patch(module,return_value=value);guard.start();self.addCleanup(guard.stop)
        if kind=='training':from control_training import show
        else:from control_comparable import show
        w=show(app,e);self.pump(app,.3);return w,w.analysis_panel,e
    def test_same_record_reuses_window_and_edited_conditions_without_rescan(self):
        from control_comparable import show
        app,root,errors=self.app();w,p,e=self.panel(app,root,'comparable');p.form.inputs['fuel_l'].set('1.3')
        with patch('comparable_progress.analyse') as scan:self.assertIs(show(app,deepcopy(e)),w);scan.assert_not_called()
        self.assertEqual(p.form.inputs['fuel_l'].get(),'1.3');self.assertFalse(p.buttons['export'].enabled);other=show(app,dict(e,folder=str(root/'Logs/other')));self.pump(app,.2);self.assertIsNot(w,other);self.assertEqual(len(app.analysis_windows),2);self.assertFalse(errors)
    def test_training_scope_requests_are_coalesced_to_latest_and_exports_wait(self):
        app,root,errors=self.app();w,p,e=self.panel(app,root);old=p.result;gate=threading.Event();entered=threading.Event();calls=[]
        def scan(*args):calls.append(args[-1]);entered.set();gate.wait(4);return training()
        p.scanner=lambda policy:scan(policy)
        try:
            p.apply();self.assertTrue(entered.wait(1));p.policies['include_unknown'].set(True);p.apply();p.policies['cross_mode'].set(True);p.apply();self.assertEqual(len(calls),1);self.assertIs(p.result,old);self.assertFalse(p.buttons['export'].enabled);gate.set();self.pump(app,.4);self.assertEqual(len(calls),2);self.assertTrue(calls[-1]['include_unknown']);self.assertTrue(calls[-1]['cross_mode']);self.assertTrue(p.buttons['export'].enabled)
        finally:gate.set()
        self.assertFalse(errors)
    def test_unsubmitted_comparable_draft_rejects_late_result_and_invalid_field_never_writes(self):
        app,root,errors=self.app();w,p,e=self.panel(app,root,'comparable');old=p.result;jobs=[];before=p.preference.read_bytes();p.form.inputs['fuel_l'].set('1');p.scanner=lambda _:comparable()
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append(done)):
            p.apply();p.form.inputs['fuel_l'].set('1.5');jobs[0](comparable(),None);self.assertIs(p.result,old);self.assertFalse(p.buttons['export'].enabled)
            p.form.inputs['min_laps'].set('3.5');p.apply();self.assertEqual(len(jobs),1);self.assertTrue(p.form.expanded);self.assertTrue(p.form.fields['min_laps'].error);self.assertIn('分析条件未应用',p.status.get())
        self.assertEqual(p.preference.read_bytes(),before);self.assertFalse(errors)
    def test_reverting_pending_conditions_deduplicates_scan(self):
        app,root,errors=self.app();w,p,e=self.panel(app,root);jobs=[];calls=[]
        with patch.object(app,'run_background',side_effect=lambda work,done:(calls.append(work),jobs.append(done))):
            p.apply();p.apply();self.assertEqual(len(calls),1);p.policies['include_unknown'].set(True);p.apply();self.assertIsNotNone(p.pending);p.policies['include_unknown'].set(False);p.apply();self.assertIsNone(p.pending);jobs[0](training(),None);self.assertEqual(len(calls),1);self.assertTrue(p.ready())
        self.assertFalse(errors)
    def test_scope_auto_updates_are_debounced(self):
        app,root,errors=self.app();w,p,e=self.panel(app,root);calls=[];p.scanner=lambda policy:(calls.append(policy),training())[1]
        p.policies['include_unknown'].set(True);p.schedule();p.policies['include_unknown'].set(False);p.schedule();p.policies['cross_phase'].set(True);p.schedule();self.assertFalse(calls);self.pump(app,.4);self.assertEqual(len(calls),1);self.assertFalse(calls[0]['include_unknown']);self.assertTrue(calls[0]['cross_phase']);self.assertFalse(errors)
    def test_export_uses_frozen_result_once_and_locks_inputs_until_saved(self):
        app,root,errors=self.app();w,p,e=self.panel(app,root,'comparable');old=p.result;gate=threading.Event();entered=threading.Event();values=[]
        def save(value):values.append(value);entered.set();gate.wait(4);path=root/'saved.html';path.write_text('fixture');return str(path)
        p.exporter=save
        try:
            with patch('control_analysis_window.os.startfile'):
                p.export();self.assertTrue(entered.wait(1));p.export();p.apply();self.assertEqual(len(values),1);self.assertIs(values[0],old);self.assertEqual(p.form.fields['fuel_l'].entry.cget('state'),'disabled');self.assertFalse(p.buttons['scan'].enabled);gate.set();self.pump(app,.35)
            self.assertTrue(p.buttons['export'].enabled);self.assertEqual(p.form.fields['fuel_l'].entry.cget('state'),'normal');self.assertEqual(p.output.get(),str(root/'saved.html'))
        finally:gate.set()
        self.assertFalse(errors)
    def test_saved_report_can_reopen_after_browser_failure_and_deleted_file_is_explained(self):
        app,root,errors=self.app();w,p,e=self.panel(app,root);path=root/'saved.html';p.exporter=lambda _:(path.write_text('fixture'),str(path))[1]
        with patch('control_analysis_window.os.startfile',side_effect=OSError('browser fixture')):p.export();self.pump(app,.3)
        self.assertIn('浏览器未能打开',p.status.get());self.assertTrue(path.is_file());self.assertTrue(p.buttons['open'].enabled);self.assertEqual(p.output.get(),str(path))
        with patch('control_analysis_window.os.startfile') as opened:p.open_last();opened.assert_called_once_with(str(path))
        path.unlink();p.open_last();self.assertIn('移动或删除',p.status.get());self.assertFalse(errors)
    def test_save_failure_keeps_previous_report_and_can_retry(self):
        app,root,errors=self.app();w,p,e=self.panel(app,root);old=p.result;path=root/'saved.html';path.write_text('keep');p.output.set(str(path));p.exporter=lambda _:(_ for _ in ()).throw(OSError('save fixture'))
        p.export();self.pump(app,.25);self.assertEqual(p.output.get(),str(path));self.assertEqual(path.read_text(),'keep');self.assertIs(p.result,old);self.assertTrue(p.buttons['export'].enabled);self.assertIn('可重试',p.status.get());self.assertFalse(errors)
    def test_scan_failure_preserves_view_but_requires_successful_retry_before_export(self):
        app,root,errors=self.app();w,p,e=self.panel(app,root);old=p.result;rows=dict(p.table.rows);p.scanner=lambda _:(_ for _ in ()).throw(OSError('analysis fixture'));p.apply();self.pump(app,.25)
        self.assertIs(p.result,old);self.assertEqual(p.table.rows,rows);self.assertFalse(p.buttons['export'].enabled);self.assertTrue(p.buttons['scan'].enabled);p.scanner=lambda _:training();p.apply();self.pump(app,.3);self.assertTrue(p.ready());self.assertFalse(errors)
    def test_close_during_export_still_saves_and_reports_path_without_opening_browser(self):
        app,root,errors=self.app();w,p,e=self.panel(app,root);gate=threading.Event();entered=threading.Event();path=root/'saved.html'
        def save(_):entered.set();gate.wait(4);path.write_text('fixture');return str(path)
        p.exporter=save
        try:
            with patch('control_analysis_window.os.startfile') as opened:p.export();self.assertTrue(entered.wait(1));w.destroy();gate.set();self.pump(app,.3);opened.assert_not_called()
            self.assertTrue(path.is_file());self.assertIn(str(path),app.status.get());self.assertFalse(app.analysis_windows)
        finally:gate.set()
        self.assertFalse(errors)
    def test_closing_scan_and_late_result_do_not_call_destroyed_tk(self):
        app,root,errors=self.app();w,p,e=self.panel(app,root);callbacks=[]
        with patch.object(app,'run_background',side_effect=lambda work,done:callbacks.append(done)):p.apply();w.destroy();callbacks[0](training(),None)
        self.assertFalse(app.analysis_windows);self.assertFalse(errors)
    def test_dirty_close_and_application_exit_use_existing_explicit_editor_guard(self):
        app,root,errors=self.app();w,p,e=self.panel(app,root,'comparable');p.form.inputs['fuel_l'].set('1');self.assertTrue(p.edited)
        with patch('control_confirm.ask',return_value='cancel') as ask:p.close();self.assertTrue(w.winfo_exists());app.request_close();self.assertFalse(app.closing);self.assertEqual(ask.call_count,2)
        with patch('control_confirm.ask',return_value='discard'):p.close()
        self.assertFalse(app.analysis_windows);self.assertFalse(errors)
    def test_training_goal_double_click_is_blocked_and_same_zone_requires_new_analysis(self):
        app,root,errors=self.app();w,p,e=self.panel(app,root);gate=threading.Event();entered=threading.Event();calls=[]
        def create(*args):calls.append(args);entered.set();gate.wait(4);return dict(id='fixture')
        try:
            with patch('training_goals.create',side_effect=create):
                p.buttons['goal'].invoke();self.assertTrue(entered.wait(1));p.buttons['goal'].invoke();self.assertEqual(len(calls),1);gate.set();self.pump(app,.3);self.assertFalse(p.buttons['goal'].enabled);self.assertIn('已建立',p.status.get());p.apply();self.pump(app,.3);self.assertTrue(p.buttons['goal'].enabled)
        finally:gate.set()
        self.assertFalse(errors)
    def test_goal_failure_is_retryable_and_selection_survives_reordered_training_results(self):
        app,root,errors=self.app();w,p,e=self.panel(app,root);p.table.selection_set(('1',));self.pump(app,.1);name=p.zone_state['selected']['name']
        with patch('training_goals.create',side_effect=OSError('goal fixture')):p.buttons['goal'].invoke();self.pump(app,.25)
        self.assertTrue(p.buttons['goal'].enabled);self.assertIn('未建立',p.status.get());value=training();value['priorities'].reverse();p.scanner=lambda _:value;p.apply();self.pump(app,.3);self.assertEqual(p.zone_state['selected']['name'],name);self.assertFalse(errors)
    def test_comparable_same_timestamp_rows_have_distinct_identities_and_restore_selection(self):
        app,root,errors=self.app();w,p,e=self.panel(app,root,'comparable');self.assertEqual(len(p.table.rows),3);p.table.selection_set(('1',));self.pump(app,.1);folder=p.selection_state['selected']['folder'];value=comparable();value['sessions'].reverse();p.scanner=lambda _:value;p.apply();self.pump(app,.3);self.assertEqual(p.selection_state['selected']['folder'],folder);self.assertFalse(errors)
    def test_closing_queued_analysis_keeps_latest_applied_scope_and_shutdown_waits(self):
        app,root,errors=self.app();w,p,e=self.panel(app,root);gate=threading.Event();entered=threading.Event();calls=[]
        def scanner(policy):
            calls.append(policy)
            if len(calls)==1:entered.set();gate.wait(4)
            return training()
        p.scanner=scanner
        try:
            p.apply();self.assertTrue(entered.wait(1));p.policies['include_unknown'].set(True);p.apply();self.assertIsNotNone(p.pending)
            with patch('control_confirm.ask',side_effect=AssertionError('Submitted conditions need no discard prompt')):p.close()
            app.close();self.assertTrue(app.tasks.busy);gate.set()
            import time,tkinter as tk
            end=time.monotonic()+4
            while time.monotonic()<end:
                try:
                    if not app.root.winfo_exists():break
                    app.root.update();time.sleep(.005)
                except tk.TclError:break
            self.assertEqual(len(calls),2);self.assertTrue(json.loads(p.preference.read_text())['include_unknown']);self.assertFalse(errors)
        finally:gate.set();app.close=lambda:None
    def test_real_html_exports_are_unique_readable_and_use_current_result(self):
        app,root,errors=self.app()
        for kind in ('training','comparable'):
            w,p,e=self.panel(app,root,kind)
            with patch('control_analysis_window.os.startfile') as opened:p.export();self.pump(app,.3);opened.assert_called_once()
            first=Path(p.output.get());original=first.read_bytes();self.assertIn(b'<!doctype html',original);self.assertIn(b'<svg',original);self.assertIn('BMW M4 LMGT3',original.decode('utf-8'))
            with patch('control_analysis_window.os.startfile'):p.export();self.pump(app,.3)
            self.assertNotEqual(p.output.get(),str(first));self.assertEqual(first.read_bytes(),original);self.assertTrue(Path(p.output.get()).is_file());w.destroy()
        self.assertFalse(errors)
    def test_minimum_size_theme_language_keep_drafts_metric_and_fixed_actions(self):
        from control_theme import T
        import i18n
        app,root,errors=self.app();w,p,e=self.panel(app,root,'comparable');p.form.expand();p.form.inputs['fuel_l'].set('1.1');p.metric.set('best_s');p.chart.set([]);p.say('分析条件有修改，请应用后更新结果');w.geometry('780x560');app.set_theme('light');app.toggle_language();self.pump(app,.4)
        self.assertEqual(p.form.inputs['fuel_l'].get(),'1.1');self.assertEqual(p.metric.get(),'best_s');self.assertIn('Conditions changed',p.status.get());self.assertGreater(p.metric_choice.winfo_width(),max(p.metric_choice.font.measure(i18n.tr(label)) for label in p.metric_choice.labels.values())+30);self.assertLess(p.metric_choice.winfo_width(),w.winfo_width()/2);self.assertEqual(p.path.cget('readonlybackground'),T.FIELD);self.assertFalse(p.buttons['export'].enabled);self.assertGreater(p.scroll.canvas.winfo_height(),150)
        for b in p.buttons.values():self.assertGreater(b.winfo_width(),b.font.measure(i18n.tr(b.label))+15);self.assertLessEqual(b.winfo_rootx()+b.winfo_width(),w.winfo_rootx()+w.winfo_width()+1);self.assertLessEqual(b.winfo_rooty()+b.winfo_height(),w.winfo_rooty()+w.winfo_height())
        p.scroll.scroll_to('moveto',0);self.pump(app,.1);before=p.scroll.position();p.table.viewport.event_generate('<MouseWheel>',delta=-120);self.pump(app,.3);self.assertGreater(p.scroll.position(),before)
        p.scroll.scroll_to('moveto',0);p.table.replace([(str(i),tuple('fixture' for _ in p.table.columns)) for i in range(30)],());self.pump(app,.1);p.table.viewport.event_generate('<MouseWheel>',delta=-120);self.pump(app,.3);self.assertGreater(p.table.offset,0);self.assertEqual(p.scroll.position(),0)
        for metric in ('median_s','best_s'):
            p.metric.set(metric);p.metric_choice.paint();self.assertEqual(p.metric_choice.itemcget(p.metric_choice.caption,'text'),p.metric_choice.display(metric))
        self.assertFalse(errors)

if __name__=='__main__':unittest.main()
