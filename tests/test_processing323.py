"""Bounded exact matrix reads and game-correct, metadata-only achievement cards."""
import io,json,math,os,shutil,subprocess,sys,tempfile,tracemalloc,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


class Data(unittest.TestCase):
    def test_selected_batches_preserve_values_and_bound_decoder_work_and_memory(self):
        from json_store import Reader
        from analysis_spool import DiskTable
        class Decoder(json.JSONDecoder):
            calls=0
            def raw_decode(self,*a,**kw):self.calls+=1;return super().raw_decode(*a,**kw)
        rows=[[i*.12345678901234567,-0.0,None,2**53] for i in range(20000)]
        source=json.dumps(dict(data=rows,tail='赛车 🏁',profile=[[1,None],[2,-0.0]]),ensure_ascii=False)
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            reader=Reader(io.StringIO(source),t);reader.decoder=Decoder();tracemalloc.start()
            try:value=reader.value();reader.space();peak=tracemalloc.get_traced_memory()[1]
            finally:tracemalloc.stop()
            try:
                self.assertIsInstance(value['data'],DiskTable);self.assertEqual(list(value['data']),rows)
                self.assertEqual(list(value['profile']),[[1,None],[2,-0.0]]);self.assertEqual(value['tail'],'赛车 🏁');self.assertFalse(reader.peek())
                self.assertLess(math.copysign(1,value['data'][3][1]),0);self.assertLess(reader.decoder.calls,500);self.assertLess(peak,2_000_000)
            finally:value['data'].close();value['profile'].close()

    def test_card_detail_skips_curve_tables_but_keeps_current_conditions_and_source(self):
        from personal_records import detail
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            path=Path(t)/'record.json';conditions=dict(fuel_l=11.123456789012345,wetness=0.0,note='中文 🏁',nested={'value':None})
            value=dict(conditions=conditions,lap=dict(track_length_m=5000),data=[[i,0,.123456789,.23456789] for i in range(5000)])
            path.write_text(json.dumps(value,ensure_ascii=False),'utf-8');before=path.read_bytes()
            with patch('json_store.DiskTable',side_effect=AssertionError('Card must not materialize a curve')):
                self.assertEqual(detail(dict(file=str(path)),curve=False),dict(conditions=conditions))
            complete=detail(dict(file=str(path)));self.assertEqual(complete['conditions'],conditions);self.assertTrue(complete['curve'])
            self.assertEqual(path.read_bytes(),before)
            path.write_text('{"data":[[1],[2,]],"conditions":{}}','utf-8')
            with self.assertRaises(ValueError):detail(dict(file=str(path)),curve=False)

    @unittest.skipUnless(os.name=='nt','Windows fonts')
    def test_evo_card_uses_own_facts_cached_model_and_brand_without_lmu_fallback(self):
        from achievement_card import payload,compose
        from tests.test_record_intelligence import entry
        from evo_art import catalog
        from PIL import Image,ImageDraw
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'Simulators/ac_evo';assets=root/'assets/evo';assets.mkdir(parents=True)
            e=entry();e['session'].update(simulator_id='ac_evo',vehicle='Ferrari 296 GTB',session=5);e['lap'].update(sample_count=100,timing_source='evo_last_laptime_ms');e['race_mode']='online';e['vehicle_class']='Unknown · Ferrari 296 GTB'
            car=next(c for c in catalog()['cars'] if 'Ferrari 296 GTB' in c['name']);brand=catalog()['branding'][0]
            for item,color,size in ((car,(9,199,71),(640,320)),(brand,(12,34,56),(300,60))):
                p=assets/item['file'];p.parent.mkdir(parents=True,exist_ok=True);Image.new('RGB',size,color).save(p,format='PNG')
            value=payload(e,dict(conditions={}),root=root);self.assertEqual(value['game'],'Assetto Corsa EVO')
            self.assertEqual(value['vehicle_caption'],'Ferrari 296 GTB')
            facts=dict(value['conditions']);self.assertIn('100',facts.values());self.assertNotIn('fuel_l',facts);self.assertNotIn('driver',value);self.assertNotIn('date',value)
            seen=[];original=ImageDraw.ImageDraw.text
            def text(draw,xy,label,*a,**kw):seen.append(str(label));return original(draw,xy,label,*a,**kw)
            with patch('control_record_art.vehicle_picture',side_effect=AssertionError('EVO must not use LMU images')),patch.object(ImageDraw.ImageDraw,'text',text):image=compose(value)
            self.assertEqual(image.size,(1920,1080));self.assertEqual(image.getpixel((300,500)),(9,199,71));self.assertEqual(image.getpixel((1800,70)),(12,34,56))
            self.assertFalse(any('LE MANS ULTIMATE' in s for s in seen));self.assertTrue(any('ASSETTO CORSA EVO' in s for s in seen))
            seen.clear()
            with patch('evo_art.local_asset',return_value=None),patch('evo_art.item',return_value=None),patch('control_record_art.vehicle_picture',side_effect=AssertionError('No cross-game fallback')),patch.object(ImageDraw.ImageDraw,'text',text):compose(value)
            self.assertIn('ASSETTO CORSA EVO',seen);self.assertTrue(any('Ferrari 296 GTB' in s for s in seen))


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_evo_card_metadata_preview_privacy_export_and_window_reuse(self):
        script=r'''
import sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from unittest.mock import patch
from control_center import ControlCenter
from personal_records import records
import personal_records
from control_achievement import show
from PIL import Image
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.2):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 e=records(app.data_path)[0]
 with patch('personal_records.load',wraps=personal_records.load) as read:
  w=show(app,e);pump(1);c=w.achievement_controls;assert c['state']['image'] is not None and c['buttons']['export'].enabled
  read.assert_called_once_with(e['file'],fields=('conditions',))
  assert 'curve' not in c['state']['details']
 c['name'].set(True);c['request']();pump(.6);assert c['buttons']['export'].enabled
 assert show(app,e) is w and c['name'].get()
 approved=c['state']['image'].tobytes()
 with patch('control_achievement.os.startfile') as opened:c['generate']();pump(.7);assert opened.call_count==1
 path=Path(c['output'].get());assert path.is_relative_to(app.data_path/'PersonalRecords/AchievementCards')
 with Image.open(path) as saved:assert saved.size==(1920,1080) and saved.convert('RGB').tobytes()==approved
 app.set_theme('light');app.toggle_language();pump(.6);assert c['name'].get() and c['state']['image'] is not None
 w.destroy();assert not errors,errors;app.request_close();pump(.2)
print('EVO achievement: metadata-only read, privacy, approved PNG and retained UI choices OK')
'''
        from tests.test_evo_records310 import fixture
        from evo_laps import export
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=fixture(Path(t)/'Simulators/ac_evo');export(folder);before={p:p.read_bytes() for p in (folder/'session.json',folder/'inputs.csv',folder/'fastest_lap.json')}
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for p,value in before.items():self.assertEqual(p.read_bytes(),value)


if __name__=='__main__':unittest.main()
