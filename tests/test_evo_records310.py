"""EVO-only lap evidence, simulator boundaries, official assets and UI wiring."""
import csv,json,os,sys,tempfile,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


def fixture(root,vehicle='Ferrari 296 GTB'):
    from app_config import COLUMNS
    from acevo import EXTRA
    folder=Path(root)/'Logs'/'evo';folder.mkdir(parents=True)
    meta=dict(simulator_id='ac_evo',track='Nurburgring',track_layout='GP',track_length=5000,vehicle=vehicle,
        driver='Fixture',session=5,status='complete',source='AC EVO / read-only SharedFileOut v1',
        started_utc='2026-10-27T10:00:00Z',samples=301,telemetry_gap_count=0)
    (folder/'session.json').write_text(json.dumps(meta),'utf-8')
    with (folder/'inputs.csv').open('w',encoding='utf-8',newline='') as stream:
        out=csv.DictWriter(stream,fieldnames=(*COLUMNS,*EXTRA));out.writeheader()
        for i in range(301):
            lap=i//100+1;offset=i%100
            out.writerow(dict(time_s=i*.2,utc='2026-10-27T10:00:00Z',lap=lap,lap_distance_m=offset*50,
                throttle=.12345678901234567,brake=.23456789012345678,steering=-0.0,
                filtered_throttle=.7777777777777778,filtered_brake=.3333333333333333,filtered_steering=-.2,
                speed_kmh=173.123456789,lap_invalidated=int(lap==3),in_pits=0,track_length_m=5000,
                evo_lap_time_ms=offset*200,evo_last_lap_time_ms=20000 if lap>1 else 0,evo_graphics_packet=i))
    return folder


class Rules(unittest.TestCase):
    def test_verified_evo_lap_exports_exact_inputs_and_reuses_metadata_index(self):
        from evo_laps import export,index
        from personal_records import records
        from race_model import build_model
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'Simulators/ac_evo';folder=fixture(root);before=(folder/'inputs.csv').read_bytes()
            summary=export(folder);self.assertEqual(summary['lap']['number'],2);self.assertEqual(summary['lap']['time_s'],20)
            data=json.loads((folder/'fastest_lap.json').read_text('utf-8'))
            self.assertEqual(len(data['data']),100);self.assertEqual(data['data'][0][2],.12345678901234567)
            self.assertEqual(data['data'][0][4],.7777777777777778);self.assertFalse(data['lap']['boundary_interpolation'])
            self.assertIsNone(data['lap']['start_session_time_s']);self.assertEqual((folder/'inputs.csv').read_bytes(),before)
            with patch('evo_laps.scan',side_effect=AssertionError('duplicate scan')):
                self.assertEqual(index(folder)['fastest']['num'],2)
                self.assertEqual(len(records(root)),1);self.assertEqual(build_model(folder)['fastest']['num'],2)

    def test_legacy_sparse_reset_pit_invalid_and_skipped_laps_are_not_personal_bests(self):
        from evo_laps import scan
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            for mode in ('legacy','gap','reset','pit','invalid','skip','teleport'):
                folder=fixture(Path(t)/mode)
                with (folder/'inputs.csv').open(encoding='utf-8',newline='') as s:reader=csv.DictReader(s);fields=reader.fieldnames;rows=list(reader)
                for i,row in enumerate(rows):
                    if mode=='legacy':row['evo_last_lap_time_ms']=''
                    if mode=='gap' and i>=150:row['time_s']=str(float(row['time_s'])+5)
                    if mode=='reset' and i==150:row['evo_lap_time_ms']='0'
                    if mode=='pit' and i==150:row['in_pits']='1'
                    if mode=='invalid' and i==150:row['lap_invalidated']='1'
                    if mode=='skip' and i>=200:row['lap']=str(int(row['lap'])+1)
                    if mode=='teleport' and i==170:row['lap_distance_m']='0'
                with (folder/'inputs.csv').open('w',encoding='utf-8',newline='') as s:writer=csv.DictWriter(s,fieldnames=fields);writer.writeheader();writer.writerows(rows)
                self.assertIsNone(scan(folder)['fastest'],mode)

    def test_personal_records_separate_game_layout_and_road_car_model(self):
        from personal_records import records
        from evo_laps import export
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'Simulators/ac_evo';a=fixture(root);export(a)
            b=fixture(Path(t)/'other',vehicle='Ferrari 296 GT3');export(b)
            import shutil
            shutil.copytree(b,root/'Logs/other-car')
            bad=fixture(Path(t)/'foreign');meta=json.loads((bad/'session.json').read_text());meta.pop('simulator_id')
            (bad/'session.json').write_text(json.dumps(meta));shutil.copytree(bad,root/'Logs/lmu')
            values=records(root);self.assertEqual(len(values),2)
            self.assertEqual({v['session']['simulator_id'] for v in values},{'ac_evo'})
            self.assertNotEqual(values[0]['identity'],values[1]['identity'])
            self.assertFalse((root/'Logs/lmu/fastest_lap_summary.json').exists())

    def test_official_model_matching_and_racecom_adapter_preserve_layout_and_unknown_fields(self):
        from evo_art import catalog,item
        from evo_laps import model
        from racecom_bridge import adapt
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t);folder=fixture(root);value=adapt(model(folder))
            self.assertEqual(value['track'],'Nurburgring · GP');self.assertIsNone(value['start_place'])
            self.assertTrue(all(l['s1'] is None for l in value['laps']))
            names=[e['name'] for e in catalog()['cars']];self.assertIn('Ferrari 296 GTB (2021)',names)
            self.assertGreaterEqual(len(catalog()['tracks']),20)
            for e in catalog()['cars']+catalog()['tracks']:self.assertTrue(e['url'].startswith('https://assettocorsa.gg/wp-content/uploads/'))
            art=root/'assets/evo';art.mkdir(parents=True);(art/'car-ferrari-296-gtb.jpg').write_bytes(b'fixture')
            self.assertIsNotNone(item('cars','Ferrari 296 GTB',root=root));self.assertIsNone(item('cars','Ferrari 296 GT3',root=root))


class UI(unittest.TestCase):
    def test_evo_layout_gallery_personal_record_and_report_actions(self):
        script=r'''
import sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from unittest.mock import patch
from control_center import ControlCenter
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.5):
  until=time.monotonic()+s
  while time.monotonic()<until:app.root.update();time.sleep(.005)
 app.show_page(1);pump()
 assert 'layout' in app.tree.displaycolumns,app.tree.displaycolumns
 assert {'laps','journal'}<=set(app.review_actions)
 for p in (3,4,5,6):app.show_page(p);pump()
 loader=app.record_loaders['best'];pump(1)
 assert len(loader.page.rows)==1
 assert 'training' not in loader.page.buttons
 app.set_theme('light');pump();app.toggle_language();pump();app.set_theme('dark');pump()
 assert not errors,errors
 app.request_close();pump()
print('EVO UI OK')
'''
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t);folder=fixture(root/'Simulators/ac_evo')
            from evo_laps import export
            export(folder)
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=35)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

if __name__=='__main__':unittest.main()
