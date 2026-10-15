"""Recovery, scope isolation, lazy IO, maintenance safety and measured follow-up."""
import json,sys,tempfile,unittest,copy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from tests.test_career_analysis import entry,conditions

def write(path,value):
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value),encoding='utf-8')

class RecoveryTests(unittest.TestCase):
 def test_review_retry_reuses_fastest_summary_and_compression_errors_are_visible(self):
  from report_state import save,STEPS
  from session_reports import make_report
  from session_compression import after_report
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
   f=Path(t);steps={k:dict(state='ready') for k in STEPS};steps['review']['state']='error';save(f,steps);summary=dict(status='saved',file='fastest_lap.html');write(f/'fastest_lap_summary.json',summary)
   with patch('session_reports.render_review') as review,patch('session_compression.after_report'):
    self.assertEqual(make_report(f,isolated=False)['state'],'ready');self.assertEqual(review.call_args.args[1],summary)
   with patch('session_compression.enabled',return_value=True),patch('session_compression.compress',return_value=dict(errors=[dict(file='inputs.csv',error='failed')])):
    with self.assertRaises(OSError):after_report(f)
   self.assertTrue((f/'storage_compression_error.txt').exists())
 def test_legacy_html_alone_is_incomplete_and_is_not_rewritten(self):
  from report_state import current
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
   f=Path(t);(f/'review.html').write_bytes(b'legacy');self.assertEqual(current(f)['state'],'incomplete');self.assertEqual((f/'review.html').read_bytes(),b'legacy');self.assertFalse((f/'report_status.json').exists())
 def test_partial_retry_preserves_successful_stages_and_archives_failed_output(self):
  from session_reports import make_report
  from report_state import current
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
   f=Path(t);(f/'inputs.csv').write_bytes(b'original telemetry');(f/'review.html').write_bytes(b'old partial output')
   write(f/'report_status.json',dict(version=2,steps={k:dict(state='pending') for k in ('analysis','endurance','fastest','review','images','compression')}))
   with patch('session_reports.analyze_session') as analysis,patch('session_reports.endurance.analyze') as endurance,patch('session_reports.export_fastest',return_value=(None,None)) as fastest,patch('session_reports.render_review',side_effect=OSError('render failed')) as review,patch('race_report.generate') as images,patch('session_compression.after_report') as compression:
    value=make_report(f,isolated=False);self.assertEqual(value['state'],'partial');self.assertEqual(value['steps']['compression']['state'],'blocked');compression.assert_not_called();images.assert_called_once()
    review.side_effect=None;value=make_report(f,isolated=False)
    self.assertEqual(value['state'],'ready');analysis.assert_called_once();endurance.assert_called_once();fastest.assert_called_once();images.assert_called_once();compression.assert_called_once();self.assertEqual(review.call_count,2)
    self.assertFalse((f/'report_error.txt').exists());self.assertTrue(list((f/'_report_history/errors').glob('*/report_error.txt')));self.assertEqual(next((f/'_report_history/retries').glob('*/review.html')).read_bytes(),b'old partial output')
   self.assertEqual((f/'inputs.csv').read_bytes(),b'original telemetry');self.assertEqual(current(f)['state'],'ready')
 def test_failed_analysis_blocks_dependents_but_not_images_and_recovers(self):
  from session_reports import make_report
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
   f=Path(t)
   with patch('session_reports.analyze_session',side_effect=ValueError('bad analysis')) as analysis,patch('session_reports.endurance.analyze') as endurance,patch('session_reports.export_fastest',return_value=(None,None)),patch('session_reports.render_review') as review,patch('race_report.generate') as images,patch('session_compression.after_report'):
    value=make_report(f,isolated=False);self.assertEqual(value['state'],'partial');endurance.assert_not_called();review.assert_not_called();images.assert_called_once()
    analysis.side_effect=None;self.assertEqual(make_report(f,isolated=False)['state'],'ready');endurance.assert_called_once();review.assert_called_once();images.assert_called_once()
 def test_worker_does_not_turn_partial_receipt_into_ready(self):
  from report_state import save,STEPS
  from report_worker import run
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
   f=Path(t);steps={k:dict(state='ready') for k in STEPS};steps['images']['state']='error';save(f,steps)
   with patch('report_worker.can_report',return_value=True),patch('report_worker.subprocess.run',return_value=SimpleNamespace(returncode=0)):
    self.assertEqual(run(f,f)['state'],'partial')
 def test_snapshot_uses_memory_receipt_without_disk_io(self):
  from report_state import remember
  from recording_status import snapshot
  f=ROOT/'_local/no-such-report';remember(f,dict(state='ready'))
  e=SimpleNamespace(recorder=SimpleNamespace(file=None,report_folder=str(f),report_state='error'),latest=None)
  with patch('pathlib.Path.open',side_effect=AssertionError('UI poll must not read disk')):self.assertEqual(snapshot(e)['state'],'saved')

class ScopeAndIOTests(unittest.TestCase):
 def test_progress_never_mixes_mode_or_phase_into_reliable_gain(self):
  from comparable_progress import analyse
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
   root=Path(t)
   for i,(mode,phase) in enumerate((('online',10),('single',10),('online',5))):write(root/f'Logs/{i}/session.json',dict(entry()['session'],race_mode=mode,session=phase,started_utc=f'2026-10-0{i+1}T10:00:00Z',status='complete'))
   profiles=dict(excluded=0,laps=[dict(number=i,time_s=100+i/10,length_m=5000,conditions=conditions()) for i in range(1,4)])
   with patch('comparable_progress.profiles',return_value=profiles):
    value=analyse(root,entry());self.assertEqual(len(value['sessions']),1);self.assertIsNone(value['summary'])
    value=analyse(root,entry(),dict(cross_mode=True,cross_phase=True));self.assertEqual(len(value['sessions']),3);self.assertEqual(sum(s['qualified'] for s in value['sessions']),1);self.assertIsNone(value['summary'])
 def test_legacy_analysis_headers_do_not_materialize_curves(self):
  from analysis_headers import load,save
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
   f=Path(t);value=dict(laps=[dict(number=1,time_s=90,profile=[[i,i/10] for i in range(5000)],trajectory=[[0,0]])],recent_stability={'count':1});write(f/'session_analysis.json',value)
   with patch('json_store.DiskTable',side_effect=AssertionError('Do not spill or load curves')):self.assertEqual(load(f)['laps'],[dict(number=1,time_s=90)])
   save(f,value)
   with patch('analysis_headers.Reader',side_effect=AssertionError('Use small sidecar')):self.assertEqual(load(f)['laps'][0]['number'],1)
   (f/'session_analysis.json').write_text('{"laps":[]}')
   self.assertEqual(load(f)['laps'],[])
 def test_lazy_selection_opens_one_curve_and_index_rebuild_uses_only_headers(self):
  from training_cache import Laps
  from training_report import cache_path,profile_index
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
   root=Path(t);folder=root/'Logs/a';folder.mkdir(parents=True);(folder/'inputs.csv').write_text('fixture');write(folder/'session.json',{})
   p=cache_path(root,folder);p.parent.mkdir(parents=True);headers=[dict(number=1,file='one.json'),dict(number=2,file='missing.json')];write(p,dict(laps=headers,excluded=0,error=None));write(p.parent/'one.json',dict(number=1,data=[[1,2]]))
   self.assertEqual(list(Laps(p.parent,headers).selected({1})),[dict(number=1,data=[[1,2]])])
   with patch('training_cache.Laps.__iter__',side_effect=AssertionError('No curves for index')):self.assertEqual(profile_index(root,folder)['laps'],headers)
 def test_fuel_prediction_is_ten_hz_but_events_invalidate_immediately(self):
  from vehiclelab import FuelPlanner
  from tests.test_vehicle import sample
  p=FuelPlanner();last=None
  with patch.object(p,'estimate',wraps=p.estimate) as estimate:
   for i in range(1000):
    s=sample(i/100);p.update(s);last=p.estimate_cached(s)
   self.assertLessEqual(estimate.call_count,105);self.assertGreaterEqual(estimate.call_count,100);self.assertEqual(p.previous['et'],9.99)
   calls=estimate.call_count;s=dict(s,finish=1,et=9.991);p.update(s);p.estimate_cached(s);self.assertEqual(estimate.call_count,calls+1)
   s=copy.deepcopy(s);s['et']=9.992;s['vehicle']['fuel_l']+=2;p.update(s);p.estimate_cached(s);self.assertEqual(estimate.call_count,calls+2)

class MaintenanceTests(unittest.TestCase):
 def test_clear_allowlist_retains_originals_exports_goals_and_settings(self):
  from cache_management import clear,inventory
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
   root=Path(t);keep=['Logs/a/inputs.csv','ImportedLogs/b/session.json','PersonalRecords/AchievementCards/card.png','PersonalRecords/TrainingGoals/goal.json','PersonalRecords/training_settings.json','library_notes.json']
   for name in keep:write(root/name,{'original':True})
   for name in ('PersonalRecords/TrainingCache/file.json','PersonalRecords/Cache/file.json','EventCatalog/index.json'):write(root/name,{'cache':True})
   before={n:(root/n).read_bytes() for n in keep}
   with self.assertRaises(ValueError):clear(root,['training','races'])
   self.assertTrue((root/'PersonalRecords/TrainingCache/file.json').exists())
   with self.assertRaises(ValueError):clear(root,['training'],active=True)
   self.assertGreater(clear(root,['training','records','catalog']),0);self.assertEqual(before,{n:(root/n).read_bytes() for n in keep});self.assertFalse(any(x['bytes'] for x in inventory(root) if x['clearable']))
 def test_conflicts_expose_both_sources_without_modification(self):
  from result_conflicts import rows,provenance
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
   f=Path(t);write(f/'session.json',dict(started_utc='2026-10-01T10:00Z',ended_utc='2026-10-01T10:30Z'));write(f/'race_summary.json',dict(finish_flag=0));before=(f/'session.json').read_bytes()
   e=dict(position_conflicts={'finish_class_place':dict(telemetry=4,official=3)},linked_folder=str(f),source_xml='race.xml',started_utc='2026-10-01T09:59Z')
   self.assertEqual(rows(e)[0][1][1:3],('P4','P3'));text=provenance(e);self.assertIn('10:30Z',text);self.assertIn('09:59Z',text);self.assertIn('race.xml',text);self.assertEqual(before,(f/'session.json').read_bytes())

class GoalTests(unittest.TestCase):
 def test_goal_freezes_reference_only_evaluates_future_sessions_and_requires_samples(self):
  from training_goals import create,evaluate,goals,close
  def lap(n,delta):return dict(number=n,time_s=100+delta,length_m=5000,conditions=conditions(),data=[[0,0,1,0,0,0,100],[2500,50+delta,1,0,0,0,100],[5000,100+delta,1,0,0,0,100]])
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
   root=Path(t);zone=dict(name='固定区间',start=0,end=2500,apex=1000,source='user_distance',median_loss_s=.5,std_s=.1,count=3);r=dict(reference=dict(folder=str(root/'Logs/old'),number=1),entry=entry(),policy={},unknown=[],samples=[])
   reference=lap(1,0)
   with patch('training_goals.selected_profiles',return_value=iter([reference])):goal=create(root,r,zone)
   reference['data'][1][1]=99;self.assertEqual(goal['reference']['data'][1][1],50)
   goal['created_utc']='2026-10-01T00:00:00+00:00';write(root/'PersonalRecords/TrainingGoals'/(goal['id']+'.json'),goal)
   for name,date,mode in (('old','2026-09-30','online'),('future','2026-10-02','online'),('single','2026-10-03','single')):write(root/f'Logs/{name}/session.json',dict(entry()['session'],started_utc=date+'T10:00:00Z',status='complete',race_mode=mode))
   value=[lap(i,d) for i,d in enumerate((.1,.2,.3),1)]
   with patch('training_goals.profile_index',return_value=dict(laps=value)),patch('training_goals.selected_profiles',side_effect=lambda *args:iter(value)):
    out=evaluate(root,goal);self.assertEqual(len(out['sessions']),1);s=out['sessions'][0];self.assertTrue(s['qualified']);self.assertAlmostEqual(s['gain_s'],.3);self.assertEqual(s['count'],3)
    value.pop();out=evaluate(root,goal);self.assertIsNone(out['sessions'][0]['gain_s'])
   self.assertNotIn('reference',goals(root)[0]);close(root,goal);self.assertFalse(goals(root));self.assertTrue((root/'PersonalRecords/TrainingGoals'/(goal['id']+'.json')).exists())

if __name__=='__main__':unittest.main()
