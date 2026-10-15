"""Participation evidence, filtered PB selection and mode-isolated history."""
import csv,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from race_mode import mode,xml_mode,build,overlay,annotate
from review_filters import filtered
from personal_records import select_records
from history_view import series
from tests.test_career_analysis import XML,driver
from official_results import parse,refresh

class ModeTests(unittest.TestCase):
 def test_only_explicit_xml_setting_and_sdk_client_are_accepted(self):
  self.assertEqual(xml_mode('Multiplayer'),'online');self.assertEqual(xml_mode('Race Weekend'),'single');self.assertEqual(xml_mode(''),'unknown')
  self.assertEqual(mode({'session':10}),'unknown')
  from telemetry import extract
  from tests.test_core import fixture
  d=fixture();d.scoring.scoringInfo.mGameMode=2;self.assertEqual(extract(d)['race_mode'],'online')
  for n in (0,1,3):d.scoring.scoringInfo.mGameMode=n;self.assertEqual(extract(d)['race_mode'],'unknown')
 def test_xml_epoch_overlay_does_not_rewrite_original_metadata_or_use_nearby_other_race(self):
  from race_mode import dated
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
   root=Path(t);p=root/'r.xml';p.write_text(XML.format(drivers=driver()).replace('<TrackVenue>','<Setting>Race Weekend</Setting><TrackVenue>'));r=parse(p,['Me'])[0]
   f=root/'Logs/a';f.mkdir(parents=True);m=dict(track='Track',track_layout='GP',vehicle=r['vehicle'],driver='Me',session=10,started_utc=r['started_utc']);(f/'session.json').write_text(json.dumps(m));(f/'inputs.csv').write_text('session_time_s\n0\n');before=(f/'session.json').read_bytes()
   result=build(root,[r],[(f,m,dated(m['started_utc']))]);self.assertEqual(annotate(m,f,result)['race_mode'],'single');self.assertEqual((f/'session.json').read_bytes(),before)
   (f/'inputs.csv').write_text('session_time_s\n600\n');self.assertFalse(build(root,[r],[(f,m,dated(m['started_utc']))]))
 def test_mode_filter_runs_before_personal_best_selection_and_sort_keeps_unknown_last(self):
  identity=('track','gp',5000,'lmgt3');values=[dict(identity=identity,time_s=s,race_mode=m,track='Track',layout='GP',vehicle_class='LMGT3') for s,m in ((90,'single'),(95,'online'),(99,'unknown'))]
  self.assertEqual(select_records(values,'online')[0]['time_s'],95)
  rows=[dict(e,date='2026-10-01',folder=str(i)) for i,e in enumerate(values)]
  self.assertEqual([i for i,_ in filtered(rows,{'mode':'online'})],[1]);self.assertEqual([e['race_mode'] for _,e in filtered(rows,{'sort':9})],['online','single','unknown'])
 def test_merge_index_is_reversible_and_never_hides_sources_without_complete_target(self):
  from session_groups import superseded
  from library import inventory
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
   root=Path(t);a=root/'Logs/a';b=root/'RecoveredLogs/b';a.mkdir(parents=True);b.mkdir(parents=True)
   m=dict(track='Track',vehicle='Car',session=10,started_utc='2026-10-01T00:00:00Z',status='complete')
   (a/'session.json').write_text(json.dumps(m));(b/'session.json').write_text(json.dumps(dict(m,recovery_sources=[str(a.resolve())])));(b/'inputs.csv').write_text('session_time_s\n0\n')
   (root/'SessionGroups').mkdir();(root/'SessionGroups/index.json').write_text(json.dumps(dict(links={'Logs/a':'RecoveredLogs/b'})))
   self.assertEqual(superseded(root),{a.resolve()});self.assertEqual(len(inventory(root)),1);self.assertTrue((a/'session.json').is_file())
   (b/'session.json').write_text(json.dumps(dict(m,status='recording',recovery_sources=[str(a.resolve())])));self.assertFalse(superseded(root));self.assertEqual(len(inventory(root)),2)
 def test_progress_series_never_connects_online_with_single_player(self):
  a=dict(identity=('x',),session={'vehicle':'Car'},race_mode='single',observed_utc='2026-10-01T00:00:00Z');b=dict(a,race_mode='online',observed_utc='2026-10-02T00:00:00Z')
  self.assertEqual(series([a,b],b),[b])

if __name__=='__main__':unittest.main()
