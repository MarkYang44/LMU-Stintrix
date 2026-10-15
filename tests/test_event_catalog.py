"""Metadata filtering, provenance, incremental I/O and continuity UI contracts."""
import json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from event_catalog import snapshot,normalize,result,weather,attach
from event_filters import filtered,layout_key
from personal_records import select_records
from recording_status import snapshot as recording_snapshot

def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value),encoding='utf-8')

class CatalogTests(unittest.TestCase):
 def folder(self,root,name='a',**overrides):
  folder=Path(root)/'Logs'/name
  write(folder/'session.json',dict(track='Monza',track_layout='GP',track_length=5781,vehicle='BMW M4 LMGT3',vehicle_class='GT3',driver='Fixture',session=10,started_utc='2026-10-14T10:00:00Z',ended_utc='2026-10-14T10:30:00Z',status='complete',duration_s=1800,**overrides))
  (folder/'inputs.csv').write_text('raw telemetry must not be opened',encoding='utf-8')
  write(folder/'fastest_lap_summary.json',dict(status='saved',lap=dict(time_s=100,number=1,validity='verified',track_length_m=5781),candidates=[dict(eligible=True,validity='verified')],conditions=dict(fuel_l=20,wetness=0,rain=0,track_temp_c=25,tyre_front_name='Medium',tyre_rear_name='Medium')))
  return folder
 def test_cache_does_not_read_raw_or_rewrite_historical_evidence_and_only_rebuilds_changed_folder(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
   a=self.folder(tmp);b=self.folder(tmp,'b');before=(a/'session.json').read_bytes();actual=Path.open
   def guarded(path,*args,**kwargs):
    if path.suffix=='.csv':raise AssertionError('Filtering read raw CSV')
    return actual(path,*args,**kwargs)
   with patch.object(Path,'open',guarded):first=snapshot(tmp)
   index=Path(tmp)/'EventCatalog/index.json';mtime=index.stat().st_mtime_ns
   with patch('event_catalog.build',side_effect=AssertionError('Cache hit rebuilt event')):self.assertEqual(snapshot(tmp),first)
   self.assertEqual(index.stat().st_mtime_ns,mtime);self.assertEqual((a/'session.json').read_bytes(),before)
   write(b/'race_summary.json',dict(finish_flag=3))
   import event_catalog
   with patch('event_catalog.build',wraps=event_catalog.build) as build:
    value=snapshot(tmp);self.assertEqual(build.call_count,1);self.assertEqual(value[str(b.resolve())]['outcome'],'dq')
 def test_result_status_is_separate_from_recording_complete_and_last_observed_rank(self):
  self.assertEqual(result(dict(finish_place=1)),('unknown','observed'))
  for flag,status in ((1,'finished'),(2,'dnf'),(3,'dq')):self.assertEqual(result(dict(finish_flag=flag)),(status,'telemetry'))
  self.assertEqual(result(dict(finish_flag=True)),('unknown','unknown'))
  self.assertEqual(result(dict(finished=True,finish_status='DQ'),True),('dq','official'))
  self.assertEqual(result(dict(finished=True),True,True),('unknown','conflict'))
 def test_unknown_weather_fuel_and_missing_duration_are_not_zero_or_dry(self):
  self.assertEqual(weather({}),'unknown');self.assertEqual(weather(dict(wetness=0,rain=None)),'unknown');self.assertEqual(weather(dict(wetness=-1,rain=0)),'unknown')
  e=dict(_facets=dict(weather='unknown',quality='unknown'),track='T',date='2026-10-14T10:00:00Z')
  for state in (dict(weather='dry'),dict(fuel_max='30'),dict(duration_max='60'),dict(min_laps='0')):self.assertEqual(filtered([e],state),[])
 def test_streaming_legacy_headers_exclude_curve_arrays_and_capture_mixed_conditions(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
   a=self.folder(tmp);write(a/'session_analysis.json',dict(laps=[dict(validity='verified',conditions=dict(wetness=v,rain=0,fuel_l=20),profile=[[i,1,2] for i in range(1500)]) for v in (0,.5)],recent_stability=dict(std=.3,count=3)))
   with patch('analysis_spool.DiskTable',side_effect=AssertionError('Index allocated a curve matrix')):
    f=snapshot(tmp)[str(a.resolve())]
   self.assertEqual(f['weather'],'mixed');self.assertEqual(f['stability_s'],.3);self.assertLess(len(json.dumps(f)),2500)
 def test_official_overlay_replaces_unconfirmed_last_rank_without_mutating_race_summary(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
   a=self.folder(tmp);write(a/'race_summary.json',dict(finish_place=1,finish_class_place=1));before=(a/'race_summary.json').read_bytes()
   write(Path(tmp)/'OfficialResults/index.json',dict(entries=[dict(linked_folder=str(a.resolve()),link_status='matched',finished=True,finish_status='Finished Normally',grid_place=20,grid_class_place=10,finish_place=12,finish_class_place=3)]))
   f=snapshot(tmp)[str(a.resolve())];self.assertEqual((f['trust'],f['finish_class'],f['class_gain']),('official',3,7));self.assertEqual(before,(a/'race_summary.json').read_bytes())
 def test_layout_class_and_car_filters_apply_before_selecting_pb(self):
  identity=('monza','gp',5781,'LMGT3')
  values=[dict(identity=identity,track='Monza',layout='GP',vehicle_class='LMGT3',time_s=t,session=dict(vehicle=car),conditions=dict(wetness=wet,rain=0)) for t,car,wet in ((90,'BMW',.1),(95,'Porsche',0),(96,'BMW',0))]
  allowed=[e for _,e in filtered(values,dict(weather='dry',car='BMW'))];self.assertEqual(select_records(allowed)[0]['time_s'],96)
  a=normalize(values[0]);b={**a,'layout':'No Chicane'};self.assertNotEqual(layout_key(a),layout_key(b))
  self.assertEqual(len(filtered(values,dict(layout=layout_key(a),vehicle_class='LMGT3'))),3)
 def test_podium_and_gains_require_confirmed_race_finish_not_qualifying_or_dnf(self):
  base=dict(phase='Race',outcome='finished',trust='telemetry',finish_class=1,class_gain=2)
  entries=[dict(_facets={**base,**change},date=f'2026-10-{i+1:02}T10:00:00Z') for i,change in enumerate(({},dict(outcome='dnf'),dict(trust='observed'),dict(phase='Qualify'),dict(trust='conflict')))]
  self.assertEqual([i for i,_ in filtered(entries,dict(outcome='podium'))],[0]);self.assertEqual([i for i,_ in filtered(entries,dict(outcome='gain'))],[0])
 def test_numeric_validation_unknown_last_and_normalized_utc_tie_break(self):
  entries=[dict(date=d,track='Monza',_facets=dict(finish_class=p)) for d,p in (('2026-10-14T11:00:00+02:00',3),('2026-10-14T10:00:00Z',3),('2026-10-14T12:00:00Z',None))]
  self.assertEqual([i for i,_ in filtered(entries,dict(sort=11))],[1,0,2]);self.assertEqual([i for i,_ in filtered(entries,dict(sort=4))],[2,1,0])
  for s in (dict(fuel_min='nan'),dict(min_laps='1.5'),dict(duration_min='5',duration_max='2'),dict(start='wrong')):
   with self.assertRaises(ValueError):filtered(entries,s)
 def test_invalid_sentinels_sparse_stability_and_corrupt_summary_stay_unknown(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
   a=self.folder(tmp);b=self.folder(tmp,'b');write(b/'fastest_lap_summary.json',dict(lap=['bad data']))
   write(a/'session_analysis.json',dict(laps=[dict(validity='verified',conditions=dict(fuel_l=-1))],recent_stability=dict(count=1,std=0)))
   values=snapshot(tmp);self.assertEqual(len(values),2);f=values[str(a.resolve())];self.assertIsNone(f['stability_s']);self.assertIsNone(f['fuel_l_min'])
   e=dict(_facets=f,conditions=dict(fuel_l=-1,tc_level=999));self.assertEqual(filtered([e],dict(fuel_max='30')),[]);self.assertEqual(filtered([e],dict(tc_max='10')),[])
 def test_gap_records_can_still_match_has_valid_lap_without_claiming_no_gaps(self):
  e=dict(_facets=dict(quality='gaps',has_valid_lap=True,gap_count=1))
  self.assertEqual(len(filtered([e],dict(quality='valid'))),1);self.assertEqual(normalize(e)['quality'],'gaps')
 def test_notes_preserve_existing_annotations_and_source_metadata(self):
  from library import save_note
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
   a=self.folder(tmp);write(Path(tmp)/'library_notes.json',{'Logs/a':dict(favorite=True,tags=['practice'])});save_note(tmp,'Logs/a','test',True)
   values=attach(tmp,[dict(folder=str(a),track='Monza')]);f=normalize(values[0]);self.assertTrue(f['favorite']);self.assertEqual(f['tags'],['practice']);self.assertEqual(len(filtered(values,dict(favorite='yes',tag='practice',traffic='yes'))),1)
 def test_suspected_split_only_offers_review_and_dismissal_never_changes_sources(self):
  from split_checks import candidates,mark
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
   a=self.folder(tmp);b=self.folder(tmp,'b');m=json.loads((b/'session.json').read_text());m.update(started_utc='2026-10-14T10:31:00Z',ended_utc='2026-10-14T11:00:00Z');write(b/'session.json',m)
   values=attach(tmp,[dict(folder=str(p),track='Monza',session=json.loads((p/'session.json').read_text())) for p in (a,b)]);rows=candidates(values);self.assertEqual(len(rows),1);mark(tmp,rows[0]['id']);self.assertTrue((a/'inputs.csv').exists());self.assertTrue((b/'inputs.csv').exists());self.assertFalse(candidates(values,[rows[0]['id']]))
 def test_recording_status_preserves_open_writer_during_stale_frames_and_distinguishes_report_errors(self):
  r=SimpleNamespace(file=object(),meta=dict(telemetry_gap_count=2),report_state='idle');e=SimpleNamespace(recorder=r,last_fresh_at=10,recording_failure=None)
  self.assertEqual(recording_snapshot(e,11)['state'],'recording');self.assertEqual(recording_snapshot(e,200)['state'],'waiting');self.assertIsNotNone(r.file)
  r.file=None;r.report_state='building';self.assertEqual(recording_snapshot(e)['state'],'building');r.report_state='error';self.assertIn('记录已保存',recording_snapshot(e)['text']);e.recording_failure='disk full';self.assertIn('保存失败',recording_snapshot(e)['text'])

if __name__=='__main__':unittest.main()
