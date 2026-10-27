"""Shared report lifecycle, immutable capability boundaries and page/action wiring."""
import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


class Reports(unittest.TestCase):
    def test_evo_independent_partial_retry_defer_and_completed_outputs_are_preserved(self):
        from session_reports import make_report
        from report_worker import ReportDeferred
        from simulator_profiles import profile
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=Path(t);raw=b'original EVO capture bytes';(folder/'inputs.csv').write_bytes(raw)
            (folder/'session.json').write_text(json.dumps(dict(status='complete',simulator_id='ac_evo')),'utf-8')
            (folder/'review.html').write_bytes(b'prior report')
            with patch('evo_laps.export',side_effect=ValueError('missing exact lap evidence')) as fastest,patch('evo_reports.overview') as review,patch('race_report.generate') as images,patch('session_compression.after_report') as compress:
                result=make_report(folder,isolated=False)
                self.assertEqual(tuple(result['steps']),profile('ac_evo').reports.steps);self.assertEqual(result['state'],'partial')
                review.assert_called_once();images.assert_called_once();compress.assert_called_once()
                self.assertFalse((folder/'fastest_lap_error.txt').exists())
                fastest.side_effect=ReportDeferred('wait for memory')
                with self.assertRaises(ReportDeferred):make_report(folder,isolated=False)
                self.assertEqual(json.loads((folder/'report_status.json').read_text())['steps']['fastest']['state'],'deferred')
                fastest.side_effect=None;self.assertEqual(make_report(folder,isolated=False)['state'],'ready')
                make_report(folder,isolated=False)
                self.assertEqual(fastest.call_count,3);review.assert_called_once();images.assert_called_once();compress.assert_called_once()
            self.assertEqual((folder/'inputs.csv').read_bytes(),raw);self.assertEqual((folder/'review.html').read_bytes(),b'prior report')


class Capabilities(unittest.TestCase):
    def test_profiles_are_read_only_choose_lazy_readers_and_keep_clocks_distinct(self):
        from simulator_profiles import profile,PROFILES
        from simulators import reader_factory
        from dataclasses import FrozenInstanceError
        lmu,evo=profile('lmu'),profile('ac_evo')
        with self.assertRaises(TypeError):PROFILES['new']=lmu
        with self.assertRaises(FrozenInstanceError):evo.capabilities.training=True
        with self.assertRaises(ValueError):profile('foreign')
        self.assertEqual(reader_factory('lmu').__module__,'telemetry');self.assertEqual(reader_factory('ac_evo').__module__,'acevo')
        self.assertTrue(lmu.capabilities.reference_laps);self.assertFalse(evo.capabilities.reference_laps)
        self.assertEqual([evo.capabilities.panel(k) for k in ('main','tyres','strategy','pit','stint','weather')],[True,False,False,False,False,False])
        self.assertNotEqual(lmu.clock_source,evo.clock_source);self.assertNotEqual(lmu.input_labels,evo.input_labels)
        self.assertFalse(lmu.defer_reports_during_capture);self.assertTrue(evo.defer_reports_during_capture)
        child=subprocess.run([sys.executable,'-c',"import sys;sys.path.insert(0,'src');import simulator_profiles,simulators;assert not {'tkinter','telemetry','acevo'}&sys.modules.keys()"],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(child.returncode,0,child.stderr)


class UI(unittest.TestCase):
    def test_both_games_restore_selection_drafts_and_keep_hud_commands_separate(self):
        script=r'''
import sys,time,json,traceback
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from unittest.mock import patch
from control_center import ControlCenter
from simulator_profiles import profile
import layout_actions
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.geometry('1300x900+20+20');app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(seconds=.3):
  end=time.monotonic()+seconds
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 for i in range(24):
  folder=app.data_path/'Logs'/str(i);folder.mkdir(parents=True)
  (folder/'session.json').write_text(json.dumps(dict(simulator_id=app.simulator,status='complete',track='Circuit '+str(i),vehicle='Car',driver='Fixture',session=10,started_utc=f'2026-10-27T10:{i:02}:00Z')),'utf-8')
 app.show_page(1);pump(.8);app.search.set('Circuit');app.populate();pump()
 keys=app.tree.get_children();chosen=keys[7];app.tree.selection_set((chosen,));app.tree.scroller.move(4)
 selected=app.items[int(chosen)]['folder'];app.toggle_language();pump(.8)
 assert app.search.get()=='Circuit'
 assert [app.items[int(k)]['folder'] for k in app.tree.selection()]==[selected]
 assert app.tree.offset==4
 app.show_page(0);pump();app.set_hud('mode','controls');app.set_hud('window','20');pump()
 assert layout_actions.current(app.data_path)['mode']=='controls'
 assert layout_actions.current(app.data_path)['window']=='20'
 app.set_theme('light');app.toggle_language();pump()
 assert app.mode_label.get()=='纯净 · 曲线 + 踏板 / 方向盘' and app.window.get()=='20'
 assert layout_actions.current(app.data_path)['mode']=='controls'
 if not app.capabilities.vehicle_telemetry:
  before=(app.data_path/'hud_layouts.json').read_bytes() if (app.data_path/'hud_layouts.json').exists() else None
  app.set_panel_visibility('vehicle','tyres',True)
  after=(app.data_path/'hud_layouts.json').read_bytes() if (app.data_path/'hud_layouts.json').exists() else None
  assert before==after and not (app.data_path/'vehicle_settings.json').exists()
 else:
  app.show_page(2);pump();draft=app.pages.active.forms['sampling'];draft['fixed_hz'].set('777');app.show_page(0);app.show_page(2);pump();assert app.pages.active.forms['sampling']['fixed_hz'].get()=='777'
 assert app.profile is profile(app.simulator);assert not errors,errors
 app.close();pump(.1)
print('Page context and delegated HUD actions OK')
'''
        for game in ('lmu','ac_evo'):
            with self.subTest(game=game),tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
                env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR=game,LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
                child=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=35)
                self.assertEqual(child.returncode,0,child.stdout+child.stderr)

if __name__=='__main__':unittest.main()
