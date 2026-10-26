"""Regressions for Evo art, legacy clean geometry and responsive completion."""
import json,os,tempfile,threading,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
from tests import test_ui_efficiency as helpers


class Rules(unittest.TestCase):
    def test_evo_uses_explicit_same_series_reference_and_unknown_models_do_not_guess(self):
        from control_record_art import vehicle_picture
        base=vehicle_picture('Ferrari 296 LMGT3');evo=vehicle_picture('Ferrari 296 LMGT3 Evo');self.assertEqual(base['image'],evo['image']);self.assertEqual(evo['reference_model'],'Ferrari 296 LMGT3');self.assertNotIn('reference_model',base);self.assertIsNone(vehicle_picture('Ferrari mystery prototype Evo'))
    def test_legacy_clean_dimensions_adapt_but_custom_and_marked_sizes_survive(self):
        from hud_layouts import defaults
        from hud_presentation import apply
        for mode,size,marked,expected in [('controls',(640,228),False,(600,100)),('curves',(640,228),False,(440,100)),('curves',(530,110),False,(530,110)),('controls',(640,228),True,(640,228)),('normal',(640,228),False,(640,228))]:
            snapshot=defaults();snapshot['mode']=mode;snapshot['panels']['main'].update(width=size[0],height=size[1]);before=json.dumps(snapshot)
            if marked:snapshot['geometry_mode']=mode;before=json.dumps(snapshot)
            app=SimpleNamespace(root=Mock(),hud_mode=Mock(),apply_clean_mode=Mock(),window=Mock(),top=Mock(),clickthrough=False,vehicle_panels=None,endurance_panels=None,render_wake=Mock(),silent_recording=False,presentation_hidden=False)
            with patch('hud_presentation.place') as place:apply(app,snapshot);panel=place.call_args.args[1];self.assertEqual((panel['width'],panel['height']),expected)
            self.assertEqual(json.dumps(snapshot),before)
    def test_report_cache_lookup_performs_no_filesystem_resolution(self):
        from report_state import remember,latest
        with patch('pathlib.Path.resolve',side_effect=AssertionError('GUI must not touch the filesystem')):
            value=dict(state='building');remember('test-cache/no-io',value);self.assertIs(latest('test-cache/no-io'),value)
    def test_busy_engine_keeps_cached_rates_and_does_not_wait_for_plot_reconfiguration(self):
        from engine import Engine
        engine=object.__new__(Engine);engine.lock=threading.Lock();engine._rates_at=-float('inf');engine._rates=(1200,100);engine.plot_hz=20;engine.plot_y_scale=80;engine.plot_revision=1
        engine.lock.acquire();started=time.perf_counter()
        try:self.assertEqual(engine.actual_rates(),(1200,100));engine.configure_plot(1000,5,200)
        finally:engine.lock.release()
        self.assertLess(time.perf_counter()-started,.2);self.assertEqual(engine.plot_hz,20);self.assertEqual(engine.plot_revision,1)
    def test_recent_pointer_write_is_background_and_latest_observation_wins(self):
        from recent_session import RecentSession,remember
        from background import BackgroundTasks
        with tempfile.TemporaryDirectory(dir=helpers.ROOT/'_local') as tmp:
            root=Path(tmp);folders=[]
            for name in ('a','b'):
                p=root/'Logs'/name;p.mkdir(parents=True);(p/'session.json').write_text('{"status":"complete","source":"LMU"}');folders.append(p)
            tracker=RecentSession(root);tasks=BackgroundTasks();gate=threading.Event();started=threading.Event()
            def slow(*args):started.set();gate.wait(2);return remember(*args)
            try:
                with patch('recent_session.remember',side_effect=slow):
                    before=time.perf_counter();tracker.observe(SimpleNamespace(engine=SimpleNamespace(last_folder=folders[0])),tasks.submit);self.assertLess(time.perf_counter()-before,.2);self.assertTrue(started.wait(1));tracker.observe(SimpleNamespace(engine=SimpleNamespace(last_folder=folders[1])),tasks.submit);gate.set()
                    deadline=time.monotonic()+3
                    while tasks.busy and time.monotonic()<deadline:time.sleep(.01)
                for done,value,error in tasks.completions():self.assertIsNone(error);done(value,error)
                self.assertEqual(tracker.folder,folders[1].resolve());self.assertEqual(json.loads((root/'recent_session.json').read_text())['folder'],'Logs/b')
            finally:gate.set();tasks.close()
    def test_stop_polls_engine_without_joining_on_the_gui_thread(self):
        from hud import App
        hud=object.__new__(App);hud._editors_closed=True;hud.closing=False;hud.root=Mock();hud.render_stop=Mock();hud.draw_job=None;hud.engine=SimpleNamespace(stop=Mock(),thread=Mock());hud.engine.thread.is_alive.return_value=True
        hud.close();hud.engine.thread.join.assert_called_once_with(timeout=0);hud.root.destroy.assert_not_called();hud.root.after.assert_called_once_with(25,hud.close)
    def test_frozen_version_is_embedded_and_independent_of_workspace_version(self):
        import paths
        with tempfile.TemporaryDirectory(dir=helpers.ROOT/'_local') as tmp:
            root=Path(tmp);(root/'VERSION').write_text('99.0.0');(root/'build-version.json').write_text('{"version":"0.2.73"}')
            with patch.object(paths,'APP_ROOT',root),patch.object(paths,'ASSETS',root),patch('sys.frozen',True,create=True):self.assertEqual(paths.app_version(),'0.2.73')


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def test_record_evo_reference_image_is_visible_and_caption_is_cleared_on_switch(self):
        app,root,errors=self.app(True);app.show_page(6);self.pump(app,.4);p=app.record_loaders['best'].page;p.header.show_vehicle('Ferrari 296 LMGT3 Evo');p.fixed['details'].invoke();self.pump(app,.5);self.assertIsNotNone(p.header.picture);self.assertTrue(p.header.reference_note.winfo_ismapped());self.assertIsNotNone(p.header.picture.image)
        p.header.show_vehicle('Ford Mustang LMGT3');self.pump(app,.1);self.assertIsNone(p.header.reference_note);self.assertIsNotNone(p.header.picture);p.header.show_vehicle('unknown');self.assertIsNone(p.header.picture);self.assertFalse(errors)
    def test_clean_hud_legacy_launch_and_busy_engine_leave_tk_timers_responsive(self):
        from hud import App
        from hud_layouts import LayoutStore,defaults
        import tkinter as tk
        app,root,errors=self.app();snapshot=defaults();snapshot['mode']='controls';LayoutStore(root).save('legacy',snapshot,defaults());before=(root/'hud_layouts.json').read_bytes()
        with patch('hud.ROOT',root),patch('engine.ROOT',root),patch('recorder.Recorder._report'),patch.dict(os.environ,{'LMU_STINTRIX_HOTKEYS':'0'}):
            hud=App(demo=True,root=tk.Toplevel(app.root),shortcuts=Mock());self.pump(app,.08);self.assertEqual((hud.root.winfo_width(),hud.root.winfo_height()),(600,100));self.assertEqual((root/'hud_layouts.json').read_bytes(),before)
            gate=threading.Event();locked=threading.Event()
            def hold():
                with hud.engine.lock:locked.set();gate.wait(1)
            thread=threading.Thread(target=hold);thread.start();self.assertTrue(locked.wait(1));ticks=[]
            hud.root.after(25,lambda:ticks.append(True));self.pump(app,.15);self.assertTrue(ticks)
            gate.set();thread.join(1);hud.close()
            deadline=time.monotonic()+5
            while hud.root.winfo_exists() and time.monotonic()<deadline:self.pump(app,.02)
            self.assertFalse(hud.root.winfo_exists());self.assertFalse(errors)
