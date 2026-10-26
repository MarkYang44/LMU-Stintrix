"""Stopping hides presentation at once while preserving writes and the center."""
import csv,json,os,threading,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from tests import test_ui_efficiency as helpers


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def settle(self,app,condition,seconds=5):
        end=time.monotonic()+seconds
        while not condition() and time.monotonic()<end:self.pump(app,.025)
        self.assertTrue(condition())
    def begin(self,panels=False,error=False):
        from hud_layouts import defaults,LayoutStore
        from report_state import save,STEPS
        app,root,errors=self.app();snapshot=defaults();snapshot['mode']='controls'
        if panels:
            for p in snapshot['panels'].values():p['visible']=True
        LayoutStore(root).save('fixture',snapshot,defaults());original=(root/'hud_layouts.json').read_bytes();gate=threading.Event();self.addCleanup(gate.set)
        def report(folder):
            gate.wait(5);steps={k:dict(state='error' if error and k=='images' else 'ready') for k in STEPS};save(folder,steps)
        for name,value in [('hud.ROOT',root),('engine.ROOT',root)]:
            guard=patch(name,value);guard.start();self.addCleanup(guard.stop)
        guard=patch('recorder.Recorder._report',side_effect=report);guard.start();self.addCleanup(guard.stop)
        app.start(True);hud=app.hud;self.settle(app,lambda:hud.engine.recorder.samples>10);return app,root,errors,hud,gate,original
    def test_stop_hides_main_and_all_five_addons_before_reports_finish(self):
        from hud_presentation import windows
        app,root,errors,hud,gate,original=self.begin(True);self.assertEqual(len(windows(hud)),6);folder=hud.engine.recorder.folder;app.stop_hud()
        self.assertTrue(hud.closing)
        for window in windows(hud).values():self.assertEqual(window.state(),'withdrawn')
        self.pump(app,.12);self.assertTrue(app.root.winfo_exists());self.assertFalse(app.closing);self.assertFalse(app.start_button.enabled);self.assertFalse(app.demo_button.enabled);self.assertFalse(app.stop_button.enabled);self.assertIn('保存',app.stop_button.cget('text'));self.assertIn('HUD',app.live_label.cget('text'))
        self.assertEqual((root/'hud_layouts.json').read_bytes(),original);gate.set();self.settle(app,lambda:app.hud is None);self.assertTrue(app.start_button.enabled);self.assertIn('HUD 已关闭',app.live_label.cget('text'))
        meta=json.loads((folder/'session.json').read_text());self.assertEqual(meta['status'],'complete')
        with (folder/'inputs.csv').open(newline='',encoding='utf-8-sig') as stream:self.assertEqual(sum(1 for _ in csv.DictReader(stream)),meta['samples'])
        self.assertFalse((root/'vehicle_settings.json').exists());self.assertFalse((root/'endurance_settings.json').exists());self.assertFalse(errors)
    def test_repeated_stop_and_early_start_do_not_replace_the_draining_engine(self):
        app,root,errors,hud,gate,_=self.begin();engine=hud.engine;app.stop_hud();app.stop_hud();app.start(True);self.assertIs(app.hud,hud);self.assertIs(app.hud.engine,engine)
        gate.set();self.settle(app,lambda:app.hud is None);app.start(True);self.assertIsNot(app.hud.engine,engine);self.pump(app,.08);self.assertEqual(app.hud.root.state(),'normal');app.stop_hud();self.settle(app,lambda:app.hud is None);self.assertFalse(errors)
    def test_cancelled_stop_keeps_the_hud_visible_and_sampling(self):
        app,root,errors,hud,gate,_=self.begin();before=hud.engine.recorder.samples
        with patch('control_batch.running',return_value=Mock(allow_exit=Mock(return_value=False))):app.stop_hud()
        self.pump(app,.1);self.assertFalse(hud.closing);self.assertEqual(hud.root.state(),'normal');self.assertGreater(hud.engine.recorder.samples,before);self.assertIn('继续记录',app.status.get());gate.set();app.stop_hud();self.settle(app,lambda:app.hud is None);self.assertFalse(errors)
    def test_save_error_remains_visible_after_hud_closes(self):
        app,root,errors,hud,gate,_=self.begin(error=True);app.stop_hud();gate.set();self.settle(app,lambda:app.hud is None);self.pump(app,.12);self.assertIn('HUD 已关闭',app.live_label.cget('text'));self.assertIn('部分',app.live_label.cget('text'));self.assertTrue(app.start_button.enabled);self.assertFalse(errors)
    def test_language_theme_and_narrow_layout_keep_saving_state_and_actions(self):
        app,root,errors,hud,gate,_=self.begin();app.stop_hud();app.set_theme('light');app.toggle_language();self.pump(app,.15);self.assertFalse(app.start_button.enabled);self.assertEqual(app.stop_button.cget('text'),'Saving…');self.assertIn('HUD hidden',app.live_label.cget('text'))
        for button in (app.start_button,app.stop_button):self.assertLessEqual(button.winfo_rootx()+button.winfo_width(),app.root.winfo_rootx()+app.root.winfo_width())
        gate.set();self.settle(app,lambda:app.hud is None);self.pump(app,.12);self.assertIn('HUD closed',app.live_label.cget('text'));self.assertIn('Restart',app.start_button.cget('text'));self.assertFalse(app.recording_detail.winfo_manager());self.assertFalse(errors)
    def test_attached_center_survives_its_original_hud_and_can_restart_and_exit(self):
        import tkinter as tk
        from hud import App
        from control_center import ControlCenter
        from report_state import save,STEPS
        parent,root,errors=self.app();gate=threading.Event();self.addCleanup(gate.set)
        def report(folder):gate.wait(5);save(folder,{k:dict(state='ready') for k in STEPS})
        with patch('hud.ROOT',root),patch('engine.ROOT',root),patch('recorder.Recorder._report',side_effect=report),patch.dict(os.environ,{'LMU_STINTRIX_HOTKEYS':'0'}):
            hud=App(demo=True,root=tk.Toplevel(parent.root));center=ControlCenter(tk.Toplevel(hud.root),hud);hud.control_center=center;self.settle(parent,lambda:hud.engine.recorder.samples>10);service=hud.shortcuts;center.stop_hud();self.assertTrue(center.root.winfo_exists());self.assertFalse(center.closing);self.assertFalse(center.attached);self.assertTrue(center.owns_shortcuts);self.assertFalse(service.closed)
            gate.set();self.settle(parent,lambda:center.hud is None);self.assertTrue(center.root.winfo_exists());center.start(True);self.pump(parent,.1);self.assertTrue(center.active());self.assertIs(center.hud.shortcuts,service);center.stop_hud();self.settle(parent,lambda:center.hud is None);host=center.hud_host_root;center.close();self.pump(parent,.1);self.assertFalse(host.winfo_exists());self.assertTrue(service.closed);self.assertTrue(parent.root.winfo_exists());self.assertFalse(errors)
    def test_stopping_after_finish_does_not_open_an_extra_recording_or_change_saved_samples(self):
        from telemetry import extract
        from tests.test_core import fixture
        from engine import Engine
        from report_state import save,STEPS
        app,root,errors=self.app();finished=threading.Event();sample=extract(fixture());origin=time.monotonic()
        class Reader:
            def read(self):return dict(sample,session=10,et=time.monotonic()-origin+1,session_clock=time.monotonic()-origin+1,finish=1 if finished.is_set() else 0)
            def close(self):pass
        def factory(*args,**kwargs):return Engine(*args,reader_factory=Reader,**kwargs)
        def report(folder):save(folder,{k:dict(state='ready') for k in STEPS})
        with patch('hud.ROOT',root),patch('engine.ROOT',root),patch('hud.Engine',side_effect=factory),patch('recorder.Recorder._report',side_effect=report):
            app.start();hud=app.hud;self.settle(app,lambda:hud.engine.recorder.samples>5);finished.set();self.settle(app,lambda:hud.engine.recorder.file is None and hud.engine.last_folder is not None);folder=hud.engine.last_folder;before=(folder/'session.json').read_bytes();app.stop_hud();self.settle(app,lambda:app.hud is None);self.assertEqual(len(list((root/'Logs').glob('*/session.json'))),1);self.assertEqual((folder/'session.json').read_bytes(),before);self.assertTrue(app.root.winfo_exists());self.assertFalse(errors)
    def test_exit_during_attached_background_save_finishes_without_an_orphan_host(self):
        import tkinter as tk
        from hud import App
        from control_center import ControlCenter
        from report_state import save,STEPS
        parent,root,errors=self.app();gate=threading.Event();self.addCleanup(gate.set)
        def report(folder):gate.wait(5);save(folder,{k:dict(state='ready') for k in STEPS})
        with patch('hud.ROOT',root),patch('engine.ROOT',root),patch('recorder.Recorder._report',side_effect=report),patch.dict(os.environ,{'LMU_STINTRIX_HOTKEYS':'0'}):
            hud=App(demo=True,root=tk.Toplevel(parent.root));center=ControlCenter(tk.Toplevel(hud.root),hud);hud.control_center=center;self.settle(parent,lambda:hud.engine.recorder.samples>5);host=hud.root;center.stop_hud();center.close();self.assertTrue(host.winfo_exists());gate.set();self.settle(parent,lambda:not host.winfo_exists());self.pump(parent,.15);self.assertTrue(parent.root.winfo_exists());self.assertFalse(errors)
    def test_stopping_a_waiting_hud_closes_display_without_claiming_a_saved_race(self):
        from engine import Engine
        app,root,errors=self.app()
        class Reader:
            def read(self):raise OSError('Waiting fixture')
            def close(self):pass
        def factory(*args,**kwargs):return Engine(*args,reader_factory=Reader,**kwargs)
        with patch('hud.ROOT',root),patch('engine.ROOT',root),patch('hud.Engine',side_effect=factory):
            app.start();hud=app.hud;self.pump(app,.08);self.assertIsNone(hud.engine.recorder.file);app.stop_hud();self.settle(app,lambda:app.hud is None);self.pump(app,.12);self.assertEqual(app.live_label.cget('text'),'HUD 已关闭');self.assertTrue(app.start_button.enabled);self.assertFalse(list((root/'Logs').glob('*/session.json')));self.assertFalse(errors)
