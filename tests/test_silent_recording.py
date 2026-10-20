"""Visibility must never change recording or verified result semantics."""
import csv,json,os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from event_result_label import label
from recording_visibility import load,save


class RecordingVisibilityTests(unittest.TestCase):
    def test_result_uses_only_confirmed_class_finish_and_status(self):
        for phase in ('Race','Qualify'):
            f=dict(phase=phase,trust='telemetry',outcome='finished',finish_class=4,finish=1)
            self.assertEqual(label(f),'P4')
            self.assertEqual(label(dict(f,finish_class=None)),'—')
            for outcome in ('dnf','dq'):self.assertEqual(label(dict(f,outcome=outcome)),outcome.upper())
            for trust in ('observed','unknown','conflict'):self.assertEqual(label(dict(f,trust=trust)),'—')
        self.assertEqual(label(dict(phase='Practice',trust='telemetry',outcome='finished',finish_class=1)),'—')
        for bad in (True,0,-1,1.5):self.assertEqual(label(dict(phase='Race',trust='official',outcome='finished',finish_class=bad)),'—')

    def test_preferences_round_trip_and_invalid_defaults(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as d:
            p=Path(d)/'recording_visibility.json';self.assertFalse(load(p))
            save(p,True);self.assertTrue(load(p));save(p,False);self.assertFalse(load(p))
            for value in ('bad','[]','{"silent_recording":"false"}'):
                p.write_text(value,'utf8');self.assertFalse(load(p))

    @unittest.skipUnless(os.name=='nt','Windows Tk HUD')
    def test_native_review_list_shows_class_qualifying_result_and_dnf(self):
        import control_center
        from tests.test_event_catalog import CatalogTests,write
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as d:
            root=Path(d);fixture=CatalogTests()
            a=fixture.folder(root,'qualifying')
            meta=json.loads((a/'session.json').read_text('utf8'));meta['session']=5;write(a/'session.json',meta)
            b=fixture.folder(root,'retired')
            write(a/'race_summary.json',dict(finish_flag=1,finish_class_place=7,finish_place=2))
            write(b/'race_summary.json',dict(finish_flag=2,finish_class_place=3,finish_place=1))
            with patch('control_center.ROOT',root),patch('control_center.ControlCenter.repair_windows_entry'):
                center=control_center.ControlCenter()
                try:
                    center.show_page(1);until=time.monotonic()+5
                    while not center.tree.get_children() and time.monotonic()<until:center.root.update();time.sleep(.01)
                    result=center.tree.columns.index('result')
                    values={Path(center.items[int(i)]['folder']).name:row[result] for i,row in center.tree.rows.items()}
                    self.assertEqual(values,dict(qualifying='P7',retired='DNF'))
                finally:center.close()

    @unittest.skipUnless(os.name=='nt','Windows Tk HUD')
    def test_silent_engine_keeps_recording_and_restores_panels(self):
        import control_center,vehiclelab,endurance
        from storage import atomic_json
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as d:
            root=Path(d);save(root/'recording_visibility.json',True)
            atomic_json(root/'vehicle_settings.json',vehiclelab.settings(dict(tyres_enabled=True,strategy_enabled=True)))
            atomic_json(root/'endurance_settings.json',endurance.settings(dict(pit_enabled=True,stint_enabled=True,weather_enabled=True)))
            with patch('control_center.ROOT',root),patch('hud.ROOT',root),patch('engine.ROOT',root),patch('recorder.make_report'),patch('control_center.ControlCenter.repair_windows_entry'):
                center=control_center.ControlCenter();errors=[];center.root.report_callback_exception=lambda *a:errors.append(a)
                def wait(check,seconds=5):
                    until=time.monotonic()+seconds
                    while time.monotonic()<until:
                        center.root.update();time.sleep(.01)
                        if check():return
                    self.fail('Native recording/visibility did not settle')
                try:
                    center.start(True);app=center.hud;engine=app.engine;rec=engine.recorder
                    wait(lambda:rec.samples>10)
                    self.assertEqual(app.root.state(),'withdrawn')
                    self.assertFalse(app.vehicle_panels.windows);self.assertFalse(app.endurance_panels.windows)
                    before=rec.samples
                    center.silent_mode.set(False);center.set_silent_recording();center.root.update()
                    self.assertIs(app.engine,engine);self.assertIs(engine.recorder,rec)
                    self.assertEqual(app.root.state(),'normal')
                    self.assertEqual(len(app.vehicle_panels.windows),2);self.assertEqual(len(app.endurance_panels.windows),3)
                    self.assertTrue(all(w.state()=='normal' for p in (app.vehicle_panels,app.endurance_panels) for w in p.windows.values()))
                    center.silent_mode.set(True);center.set_silent_recording()
                    # Turning an optional overlay on while silent may not reveal it.
                    app.vehicle_panels.refresh_visibility();app.endurance_panels.refresh_visibility()
                    wait(lambda:rec.samples>before+10)
                    self.assertTrue(all(w.state()=='withdrawn' for p in (app.vehicle_panels,app.endurance_panels) for w in p.windows.values()))
                    self.assertTrue(all(getattr(app,k+'_on').get() for k in ('tyres','strategy','pit','stint','weather')))
                    self.assertTrue(load(root/'recording_visibility.json'))
                    center.stop_hud();wait(lambda:not app.root.winfo_exists())
                    inputs=list(root.glob('DemoLogs/*/inputs.csv'));self.assertEqual(len(inputs),1)
                    with inputs[0].open(encoding='utf-8-sig') as f:self.assertGreater(len(list(csv.DictReader(f))),10)
                    self.assertTrue((inputs[0].parent/'vehicle.csv').is_file());self.assertTrue((inputs[0].parent/'race_summary.json').is_file())
                    self.assertFalse(errors)
                finally:
                    center.close()
                    import tkinter as tk
                    try:
                        while center.root.winfo_exists():center.root.update();time.sleep(.01)
                    except tk.TclError:pass
