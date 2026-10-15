"""Official source identity, provenance, analytical validity and native entry points."""
import unittest,tempfile,json,sys,time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from official_results import parse,refresh,podium_entries
from condition_match import match
from training_zones import validate,features,feature_time
from telemetry_contract import ReaderMonitor

XML='''<?xml version="1.0"?><!DOCTYPE rF [<!ENTITY rFEnt "rFactor Entity">]><rFactorXML><RaceResults><TrackVenue>Track</TrackVenue><TrackCourse>GP</TrackCourse><TrackLength>5000</TrackLength><Race><DateTime>1790848800</DateTime>{drivers}</Race></RaceResults></rFactorXML>'''
def driver(name='Me',place=1,finished='Finished Normally'):
 return f'<Driver><Name>{name}</Name><isPlayer>1</isPlayer><CarType>BMW M4 LMGT3</CarType><CarClass>LMGT3</CarClass><TeamName>Team</TeamName><GridPos>3</GridPos><ClassGridPos>2</ClassGridPos><Position>{place}</Position><ClassPosition>{place}</ClassPosition><BestLapTime>99.5</BestLapTime><FinishStatus>{finished}</FinishStatus><Laps>5</Laps><Lap num="1" et="100" s1="30" s2="31" s3="39">100</Lap></Driver>'
def conditions():return dict(fuel_l=30.,track_temp_c=25.,ambient_temp_c=23.,wetness=0.,rain=0.,track_grip=0,tc_level=6,abs_level=9,tyre_compound=0,tyre_rear_compound=0)
def entry():return dict(track='Track',layout='GP',length_m=5000,vehicle_class='LMGT3',identity=('track','gp',5000,'lmgt3'),session=dict(track='Track',track_layout='GP',vehicle='BMW M4 LMGT3',driver='Me',session=10,race_mode='online'),lap=dict(track_length_m=5000),conditions=conditions(),folder='unused',file='unused')

class ResultTests(unittest.TestCase):
 def test_multiplayer_humans_do_not_identify_local_driver_and_dtd_is_bounded(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
   p=Path(t)/'race.xml';p.write_text(XML.format(drivers=driver()+driver('Other',2)),encoding='utf-8')
   with self.assertRaisesRegex(ValueError,'exactly one'):parse(p)
   rec=parse(p,['Me'])[0];self.assertEqual(rec['driver'],'Me');self.assertEqual(rec['source_size'],p.stat().st_size);self.assertNotIn('source_hash',rec)
   p.write_text('<!DOCTYPE rF [<!ENTITY other SYSTEM "file:///secret">]><rFactorXML/>')
   with self.assertRaisesRegex(ValueError,'entity'):parse(p,['Me'])
 def test_import_dedup_links_and_preserves_both_game_and_legacy_bytes(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
   root=Path(t)/'app';source=Path(t)/'game';source.mkdir();folder=root/'Logs/a';folder.mkdir(parents=True)
   recpath=source/'race.xml';recpath.write_text(XML.format(drivers=driver()+driver('Other',2)))
   (source/'copy.xml').write_bytes(recpath.read_bytes());r=parse(recpath,['Me'])[0]
   meta=dict(started_utc=r['started_utc'],track='Track',track_layout='GP',vehicle='BMW M4 LMGT3',driver='Me',session=10,status='complete',track_length=5000)
   (folder/'session.json').write_text(json.dumps(meta));(folder/'review.html').write_bytes(b'legacy-original')
   snapshots={p:p.read_bytes() for p in [recpath,source/'copy.xml',folder/'session.json',folder/'review.html']}
   value=refresh(root,source);self.assertEqual(len(value['entries']),1);self.assertEqual(value['entries'][0]['link_status'],'matched');self.assertEqual(podium_entries(root)[0]['place'],1)
   self.assertEqual({p:p.read_bytes() for p in snapshots},snapshots)
 def test_conflicting_result_copies_and_retirements_never_become_awards(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
   root=Path(t)/'app';source=Path(t)/'game';source.mkdir()
   (source/'a.xml').write_text(XML.format(drivers=driver()+driver('Other',2)));(source/'b.xml').write_text(XML.format(drivers=driver(place=2)+driver('Other',1)))
   value=refresh(root,source,'Me');self.assertEqual(value['entries'],[]);self.assertEqual(len(value['conflicts']),1)
   (source/'b.xml').unlink();(source/'a.xml').write_text(XML.format(drivers=driver(finished='DNF')+driver('Other',2)));refresh(root,source,'Me');self.assertFalse(podium_entries(root))
 def test_numbered_practice_and_unchanged_import_reuses_parsed_snapshot(self):
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
   root=Path(t)/'app';source=Path(t)/'game';source.mkdir();p=source/'practice.xml'
   p.write_text(XML.format(drivers=driver()).replace('<Race>','<Practice1>').replace('</Race>','</Practice1>'))
   value=refresh(root,source,'Me');self.assertEqual(value['entries'][0]['phase'],'Practice');self.assertFalse(podium_entries(root))
   with patch('official_results.parse',side_effect=AssertionError('Unchanged XML must not be parsed again')):
    again=refresh(root,source,'Me');self.assertEqual(again['reused_files'],1);self.assertEqual(value['entries'],again['entries'])
   p.write_text(p.read_text().replace('99.5','98.5'));again=refresh(root,source,'Me');self.assertEqual(again['reused_files'],0);self.assertEqual(again['entries'][0]['best_lap_s'],98.5)
 def test_missing_layout_ambiguous_names_and_rank_conflict_are_not_auto_matches(self):
  from official_results import link
  from record_history import dated
  r=parse_record=dict(phase='Race',started_utc='2026-10-01T10:00:00Z',track='Track',layout='GP',vehicle='BMW M4 LMGT3',driver='Me',length_m=5000,grid_place=3,grid_class_place=2,finish_place=1,finish_class_place=1)
  m=dict(session=10,track='Track',track_layout='',vehicle=r['vehicle'],driver='Me',started_utc=r['started_utc'])
  self.assertEqual(link(r,[(Path('x'),m,dated(r['started_utc']))])['link_status'],'unmatched')

class AnalysisTests(unittest.TestCase):
 def test_unknown_conditions_are_exploration_only_and_tyre_names_can_replace_indices(self):
  a=conditions();b=dict(a);b.pop('fuel_l');self.assertFalse(match(a,b)['allowed']);self.assertTrue(match(a,b,dict(include_unknown=True))['allowed'])
  b=dict(a,fuel_l=35);self.assertFalse(match(a,b)['allowed'])
  a.update(tyre_front_name='Medium',tyre_rear_name='Medium');b=dict(a,tyre_compound=8,tyre_rear_compound=8);self.assertTrue(match(a,b)['allowed'])
 def test_zones_no_overlap_no_nan_and_no_cross_layout_settings(self):
  from training_zones import path
  with self.assertRaises(ValueError):validate([dict(name='a',start=0,end=100,apex=50),dict(name='b',start=90,end=200,apex=150)],5000)
  with self.assertRaises(ValueError):validate([dict(name='a',start=0,end=float('nan'),apex=50)],5000)
  a=entry();b=dict(a,layout='Short');self.assertNotEqual(path('x',a),path('x',b))
 def test_coasting_and_abs_intervals_are_observed_and_missing_tc_stays_unknown(self):
  rows=[dict(session_time_s=i*.1,lap_distance_m=i*10,throttle=0,brake=0,abs_active=1 if 2<=i<5 else 0,world_x_m=i,world_z_m=0) for i in range(11)]
  f=features(rows,0,1,100);lap=dict(features=f,data=[[i*10,i*.1,0,0,0,0,100] for i in range(11)])
  zone=dict(start=0,end=100);self.assertAlmostEqual(feature_time(lap,zone,'coast'),1);self.assertAlmostEqual(feature_time(lap,zone,'abs'),.3);self.assertIsNone(feature_time(lap,zone,'tc'))
 def test_progress_uses_medians_minimum_samples_and_excludes_conflicting_copies(self):
  from comparable_progress import analyse
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
   root=Path(t)
   for i in range(2):
    f=root/f'Logs/{i}';f.mkdir(parents=True);m=dict(entry()['session'],started_utc=f'2026-10-0{i+1}T10:00:00Z',status='complete',session=10);(f/'session.json').write_text(json.dumps(m))
   def profile(root,folder):
    base=100 if folder.name=='0' else 99
    return dict(excluded=0,laps=[dict(number=n,time_s=base+x,length_m=5000,conditions=conditions()) for n,x in enumerate((0,.2,-.2),1)])
   with patch('comparable_progress.profiles',side_effect=profile):r=analyse(root,entry());self.assertAlmostEqual(r['summary']['pace_gain_s'],1);self.assertEqual([s['count'] for s in r['sessions']],[3,3])
   f=root/'ImportedLogs/copy';f.mkdir(parents=True);(f/'session.json').write_bytes((root/'Logs/0/session.json').read_bytes())
   def changed(root,folder):
    value=profile(root,folder)
    if folder.name=='copy':value['laps'][0]['time_s']=95
    return value
   with patch('comparable_progress.profiles',side_effect=changed):r=analyse(root,entry());self.assertEqual(r['excluded']['conflicts'],3);self.assertIsNone(r['summary'])
 def test_lightweight_index_avoids_loading_curves_and_missing_coverage_stays_unknown(self):
  from training_report import cache_path,profile_index,measure
  with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
   root=Path(t);folder=root/'Logs/a';folder.mkdir(parents=True)
   (folder/'inputs.csv').write_text('fixture');(folder/'session.json').write_text('{}');p=cache_path(root,folder).with_name('index.json');p.parent.mkdir(parents=True)
   value=dict(laps=[dict(number=1,time_s=100)],excluded=0,error=None);p.write_text(json.dumps(value))
   with patch('training_report.profiles',side_effect=AssertionError('No full curves needed')):self.assertEqual(profile_index(root,folder),value)
  lap=dict(data=[[0,0,0,0,0,0,100],[100,1,0,0,0,0,100]],features=dict(known_s={'coast':.1},coverage={'coast':[[0,10,.1]]},intervals={'coast':[[0,10,.1]]}))
  self.assertIsNone(measure(lap,dict(start=0,end=100,apex=50))['coast_s'])
 def test_no_checksum_audit_skips_asset_byte_reads(self):
  from tools.audit_publication import audit
  with patch('tools.audit_publication.PUBLIC_ASSETS',{'docs/screenshots/a.webp':'unused'}):
   result=audit(['docs/screenshots/a.webp'],lambda _:self.fail('Asset bytes should not be read'),no_checksums=True);self.assertTrue(result['ok'])
 def test_monitor_rejects_invalid_inventory_and_reports_stale_versions(self):
  m=ReaderMonitor();d=SimpleNamespace(generic=SimpleNamespace(gameVersion=12),scoring=SimpleNamespace(scoringInfo=SimpleNamespace(mNumVehicles=20,mInRealtime=True)),telemetry=SimpleNamespace(activeVehicles=20,playerHasVehicle=True))
  self.assertTrue(m.observe(d,dict(et=1),0));self.assertTrue(m.snapshot(2)['stale']);d.generic.gameVersion=13;m.observe(d,dict(et=2),2);self.assertEqual(m.snapshot(2)['version_changes'],1)
  d.telemetry.activeVehicles=105;self.assertFalse(m.observe(d,None,3));self.assertEqual(m.rejected,1)

if __name__=='__main__':unittest.main()
