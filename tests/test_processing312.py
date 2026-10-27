"""Related checks for one-pass summaries, exact EVO ranges and layout browsing."""
import csv,json,os,struct,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


class Processing(unittest.TestCase):
    def test_vehicle_summary_reads_once_keeps_missing_gaps_and_float_bits(self):
        from vehiclelab import summarize
        rows=[[i*.125,50.,90.,-0.0 if i%7 else None] for i in range(1100)]
        class Once:
            def __init__(self):self.reads=0
            def __iter__(self):
                self.reads+=1
                if self.reads>1:raise AssertionError('Repeated full telemetry traversal')
                yield from rows
        source=Once();value=summarize(dict(columns=['fuel_l','virtual_energy_pct','nullable'],data=source),0,137.375)
        self.assertEqual(source.reads,1)
        self.assertEqual(value['fuel_l'],dict(min=50.,max=50.,mean=50.,start=50.,end=50.))
        self.assertEqual(value['fuel_l_used'],dict(value=0.,reset=False,gap=False,boundary_estimate=True))
        self.assertEqual(struct.pack('<d',value['nullable']['start']),struct.pack('<d',-0.))
        rows[:]=[[0,20,90],[.2,19.8,89.9],[.5,None,None],[1.8,19.4,89.8],[3.5,19,89]]
        result=summarize(dict(columns=['fuel_l','virtual_energy_pct'],data=Once()),0,3.5)
        self.assertEqual(result['fuel_l']['mean'],(20+19.8)*.5*.2/.2)
        self.assertIsNone(result['fuel_l_used']['value']);self.assertTrue(result['fuel_l_used']['gap'])
        rows[:]=[[0,20,90],[.2,21,91]]
        result=summarize(dict(columns=['fuel_l','virtual_energy_pct'],data=Once()),0,.2)
        self.assertTrue(result['fuel_l_used']['reset']);self.assertFalse(result['fuel_l_used']['gap'])

    def test_evo_seek_and_projected_packed_lap_preserve_exact_samples(self):
        from tests.test_evo_records310 import fixture
        from evo_laps import index,export
        from column_store import convert
        from lap_scan_index import raw_rows
        from telemetry_file import Path as ReadPath
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=fixture(t);path=folder/'inputs.csv'
            with path.open(encoding='utf-8',newline='') as f:
                reader=csv.DictReader(f);fields=reader.fieldnames;pattern=list(reader)[:100]
            with path.open('w',encoding='utf-8',newline='') as f:
                writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
                for i in range(5001):
                    row=dict(pattern[i%100],time_s=i*.2,lap=i//100+1,lap_invalidated=int(i//100+1!=42),evo_last_lap_time_ms=20000)
                    row['utc']='quoted, "utc"\r\nnext line' if i==2100 else row['utc'];writer.writerow(row)
            original=path.read_bytes();value=index(folder);self.assertEqual(value['fastest']['num'],42);self.assertGreaterEqual(len(value['cookies']),3)
            calls=[]
            def track(*args,**kwargs):calls.append(kwargs);yield from raw_rows(*args,**kwargs)
            with patch('evo_laps.scan',side_effect=AssertionError('Repeated index scan')),patch('lap_scan_index.raw_rows',track):export(folder)
            first=json.loads((folder/'fastest_lap.json').read_text('utf-8'));self.assertEqual(len(first['data']),100)
            self.assertEqual(calls[0]['start'],4100);self.assertEqual(calls[0]['end'],4200);self.assertTrue(calls[0]['cookies'])
            self.assertEqual(first['data'][0][2],.12345678901234567)
            self.assertTrue(convert(path,replace=True)['converted']);export(folder)
            self.assertEqual(json.loads((folder/'fastest_lap.json').read_text('utf-8')),first)
            self.assertEqual(ReadPath(path).read_bytes(),original)


class UI(unittest.TestCase):
    def test_layout_counts_direct_switch_missing_map_and_context(self):
        script=r'''
import sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from unittest.mock import patch
from control_center import ControlCenter
from evo_art import catalog
from PIL import Image
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.geometry('1200x850+20+20');app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.3):
  until=time.monotonic()+s
  while time.monotonic()<until:app.root.update();time.sleep(.005)
 assets=app.data_path/'assets/evo';assets.mkdir(parents=True,exist_ok=True)
 for track in catalog()['tracks']:
  for config in track.get('configurations',[]):
   if config.get('file'):Image.new('RGB',(200,120),'yellow').save(assets/config['file'])
 app.show_page(4);pump();g=app.evo_gallery
 g.variables['query'].set('Brands');g.filter_changed();pump();ids=[str(w) for w in g.host.winfo_children()];g.filter_changed();assert ids==[str(w) for w in g.host.winfo_children()]
 g.open_track(g.visible_entries[0]);pump();assert set(g.map_buttons)=={'GP','Indy'}
 g.map_buttons['Indy'].invoke();pump(.6);assert g.map_picture.photo is not None
 original=g.map_picture;g.map_buttons['Indy'].invoke();assert g.map_picture is original
 assert g.map_picture.image.getpixel((1,1))[:3]==(255,255,0)
 g.track_select.choose(g.track_select.values.index('Suzuka'));pump();assert set(g.map_buttons)=={'GP','East','West'}
 g.map_buttons['East'].invoke();pump();assert g.map_picture is None and '尚未收录' in g.map_host.winfo_children()[0].cget('text')
 g.step_layout(1,g.map_buttons['East']);pump();assert g.selected_layout['name']=='West'
 app.set_theme('light');pump();app.toggle_language();pump();g=app.evo_gallery
 assert g.selected_track['name']=='Suzuka' and g.selected_layout['name']=='West'
 g.track_select.choose(g.track_select.values.index('Brands Hatch'));pump();assert g.selected_layout['name']=='Indy'
 g.back();pump();assert g.variables['query'].get()=='Brands'
 assert not errors,errors
 app.request_close();pump(.1)
print('Layout inventory, direct switching, missing map and browsing context OK')
'''
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            child=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=35)
            self.assertEqual(child.returncode,0,child.stdout+child.stderr)

if __name__=='__main__':unittest.main()
