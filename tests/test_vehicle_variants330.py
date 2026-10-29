"""Explicit No BOP records keep ordinary class PBs and original lap evidence."""
import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
CAR='Ferrari 296 LMGT3 Evo';UNRESTRICTED=CAR+' (No BOP)'


def fixture(root,name,time_s,vehicle=CAR,date='2026-10-28T21:00:00Z',category='Logs',**extra):
    folder=Path(root)/category/name;folder.mkdir(parents=True)
    meta=dict(simulator_id='lmu',track='Autodromo Nazionale Monza',track_layout='Autodromo Nazionale Monza',vehicle=vehicle,vehicle_class='GT3',driver='Fixture Driver',status='complete',started_utc=date,session=5,race_mode='online',source='Fixture',**extra)
    lap=dict(number=4,time_s=time_s,track_length_m=5780.64,validity='verified',lap_invalidated=False,in_pits=False,sample_count=3)
    record=dict(format='inputscope.fastest-lap',version=1,id=name+':4',session=meta,lap=lap,conditions={},data_columns=['distance_m','lap_time_s','throttle','brake','filtered_throttle','filtered_brake','speed_kmh'],data=[[0,0,-0.0,.1234567890123456,0,0,100],[2000,30,1,0,1,0,150],[5700,90,.5,.2,.5,.2,180]])
    (folder/'session.json').write_text(json.dumps(meta),'utf-8')
    (folder/'fastest_lap.lap.json').write_text(json.dumps(record),'utf-8')
    (folder/'fastest_lap_summary.json').write_text(json.dumps(dict(status='saved',file='fastest_lap.lap.json',session=meta,lap=lap,conditions={})),'utf-8')
    return folder


class Rules(unittest.TestCase):
    def test_explicit_variant_never_infers_from_date_pace_or_event_words(self):
        from lap_identity import performance_variant,vehicle_class
        for car in (CAR,CAR+' Halloween',CAR+' No BOP prototype',CAR+' (Not No BOP)'):
            self.assertEqual(performance_variant(dict(vehicle=car,started_utc='2026-10-28T23:03:41Z',time_s=107.823303)), '')
        for name in (UNRESTRICTED,CAR+' (no-bop)',CAR+' ( NO BOP )'):
            self.assertEqual(performance_variant(dict(vehicle=name)),'no_bop')
            self.assertEqual(vehicle_class(dict(vehicle=name,vehicle_class='GT3')),'LMGT3')
        self.assertEqual(performance_variant(dict(vehicle=CAR,vehicle_variant='no_bop')),'no_bop')
        from control_record_art import vehicle_picture
        normal=vehicle_picture(CAR);special=vehicle_picture(UNRESTRICTED)
        self.assertEqual(normal['image'],special['image']);self.assertEqual(special['reference_model'],'Ferrari 296 LMGT3')
        self.assertIsNone(vehicle_picture('Ferrari mystery prototype (No BOP)'))

    def test_bests_history_and_inventory_separate_without_touching_evidence(self):
        from personal_records import entries,records
        from record_history import history
        from library import inventory
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            a=fixture(temp,'standard',151.332,vehicle='McLaren 720S LMGT3 Evo',date='2026-10-01T12:00:00Z')
            b=fixture(temp,'standard-later',152.0,date='2026-10-28T20:00:00Z')
            c=fixture(temp,'unrestricted',108.809357,UNRESTRICTED,date='2026-10-28T21:03:52Z',vehicle_variant='no_bop')
            d=fixture(temp,'unrestricted-best',107.823303,UNRESTRICTED,date='2026-10-28T23:03:41Z',category='ImportedLogs')
            sources={p:p.read_bytes() for folder in (a,b,c,d) for p in folder.iterdir()}
            values=entries(temp);winners=records(temp);self.assertEqual(len(winners),2)
            standard=next(v for v in winners if len(v['identity'])==4);special=next(v for v in winners if len(v['identity'])>4)
            self.assertEqual(standard['time_s'],151.332);self.assertEqual(special['time_s'],107.823303)
            self.assertEqual(special['session']['vehicle'],UNRESTRICTED);self.assertEqual({v['vehicle_class'] for v in winners},{'LMGT3'})
            self.assertEqual(next(v for v in values if Path(v['folder'])==b.resolve())['identity'],standard['identity'])
            h=history(temp)['entries'];self.assertEqual(len(h),3)
            changed=next(v for v in h if v['time_s']==107.823303);self.assertAlmostEqual(changed['improvement_s'],108.809357-107.823303)
            self.assertIsNone(next(v for v in h if v['time_s']==108.809357)['improvement_s'])
            rows=inventory(temp);self.assertEqual(next(v for v in rows if Path(v['folder'])==d.resolve())['vehicle'],UNRESTRICTED)
            self.assertEqual({p:p.read_bytes() for p in sources},sources)
            # Other unrestricted models also retain a separate variant identity.
            fixture(temp,'different-unrestricted',100,'Porsche 911 GT3 R LMGT3 (No BOP)',category='RecoveredLogs')
            self.assertEqual(len(records(temp)),3)

    def test_corrected_curve_caption_invalidates_reuse_preserving_lap_bytes(self):
        from personal_records import entries
        from curve_exports import save,signature
        from control_record_browser import curve_identity
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            folder=fixture(temp,'one',107.823303);entry=entries(temp)[0];source=Path(entry['file']);original=source.read_bytes();calls=[]
            def write(page,template,records):
                calls.append(dict(records[0]['session']));Path(page).write_text(json.dumps(calls[-1]),'utf-8')
            with patch('laps.write_compare',side_effect=write):
                first=save(temp,entry);self.assertEqual(save(temp,entry),first);self.assertEqual(len(calls),1)
                old_identity=curve_identity(entry);old_signature=signature(entry)
                entry['session']=dict(entry['session'],vehicle=UNRESTRICTED,vehicle_variant='no_bop')
                self.assertNotEqual(curve_identity(entry),old_identity);self.assertNotEqual(signature(entry),old_signature)
                second=save(temp,entry);self.assertNotEqual(first,second);self.assertEqual(calls[-1]['vehicle'],UNRESTRICTED)
                self.assertEqual(save(temp,entry),second);self.assertEqual(len(calls),2)
            self.assertEqual(source.read_bytes(),original)


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_two_rows_caption_filter_and_themes_in_private_process(self):
        script=r"""
import sys,time
from pathlib import Path
from unittest.mock import patch
root=Path.cwd();sys.path[:0]=[str(root/'src'),str(root)]
from tests.test_vehicle_variants330 import fixture,CAR,UNRESTRICTED
folder=Path(sys.argv[1]);fixture(folder,'standard',151.332);fixture(folder,'no-bop',107.823303,UNRESTRICTED,vehicle_variant='no_bop')
import control_center,i18n
errors=[]
def descendants(w):
 for child in w.winfo_children():yield child;yield from descendants(child)
with patch('control_center.ROOT',folder):
 center=control_center.ControlCenter();center.root.report_callback_exception=lambda *a:errors.append(str(a))
 def pump(condition,seconds=8):
  deadline=time.monotonic()+seconds
  while time.monotonic()<deadline:
   center.root.update();time.sleep(.01)
   if condition():return
  raise AssertionError('Native record page did not settle')
 try:
  center.show_page(6)
  def page():return next((getattr(w,'record_browser',None) for w in descendants(center.content) if getattr(w,'record_browser',None)),None)
  pump(lambda:page() and len(page().rows)==2);browser=page()
  assert {r[1]['session']['vehicle'] for r in browser.rows}=={CAR,UNRESTRICTED}
  assert {r[1]['vehicle_class'] for r in browser.rows}=={'LMGT3'}
  key=next(r[0] for r in browser.rows if r[1]['session']['vehicle']==UNRESTRICTED)
  browser.table.selection_set((key,));pump(lambda:UNRESTRICTED in browser.car_label.cget('text'))
  browser.query.set('No BOP');pump(lambda:len(browser.rows)==1)
  browser.query.set('');pump(lambda:len(browser.rows)==2)
  center.set_theme('light');pump(lambda:page() and len(page().rows)==2)
  center.toggle_language();pump(lambda:page() and len(page().rows)==2);browser=page()
  assert 'No BOP' in str(browser.modes.hint.cget('text'))
  assert len(browser.rows)==2 and not errors,errors
 finally:center.close();i18n.set_language('zh')
"""
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            result=subprocess.run([sys.executable,'-c',script,temp],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=25,creationflags=0x08000000)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
