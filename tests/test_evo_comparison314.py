"""Selected EVO lap evidence, exact exports, bounded reuse and UI entry points."""
import csv,json,os,sys,tempfile,unittest,subprocess,shutil,time,struct,math
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from tests.test_evo_records310 import fixture
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


def pair(root):
    a=fixture(root);b=root/'Logs/other';shutil.copytree(a,b)
    path=b/'session.json';meta=json.loads(path.read_text());meta['started_utc']='2026-10-27T11:00:00Z';path.write_text(json.dumps(meta))
    return a,b


class Data(unittest.TestCase):
    def test_full_precision_selected_exports_packed_roundtrip_and_reuse(self):
        from lap_comparison import valid_laps,export_pair
        from column_store import convert
        from telemetry_file import Path as ReadPath
        from paths import ASSETS
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'Simulators/ac_evo';a,b=pair(root)
            for f in (a,b):
                with (f/'inputs.csv').open(newline='',encoding='utf-8') as s:r=csv.DictReader(s);fields=r.fieldnames;rows=list(r)
                for i,row in enumerate(rows):row['evo_lap_time_ms']=str((i%100//2)*400)
                rows[130]['utc']='quoted, "UTC"\r\nnext line'
                with (f/'inputs.csv').open('w',newline='',encoding='utf-8') as s:w=csv.DictWriter(s,fieldnames=fields);w.writeheader();w.writerows(rows)
            original={f:(f/'inputs.csv').read_bytes() for f in (a,b)}
            self.assertEqual([v['number'] for v in valid_laps(a)],[2])
            result=export_pair(root,[(a,2),(b,2)],ASSETS/'compare.html')
            records=[json.loads(Path(e['json']).read_text('utf-8')) for e in result['exports']]
            self.assertEqual(records[0]['data'][0][1],records[0]['data'][1][1]);self.assertEqual(len(records[0]['data']),100)
            self.assertEqual(records[0]['data'][0][2],.12345678901234567);self.assertEqual(records[0]['data'][0][4],.7777777777777778)
            self.assertFalse(records[0]['lap']['boundary_interpolation']);self.assertIsNone(records[0]['lap']['start_session_time_s'])
            with Path(result['exports'][0]['csv']).open(newline='',encoding='utf-8') as s:exported=list(csv.DictReader(s))
            with (a/'inputs.csv').open(newline='',encoding='utf-8') as s:expected=list(csv.DictReader(s))[100:200]
            self.assertEqual(exported,expected)
            page=Path(result['comparison']);before=page.stat().st_mtime_ns
            with patch('evo_comparison.read_curve',side_effect=AssertionError('Repeated extraction')):
                self.assertEqual(export_pair(root,[(a,2),(b,2)],ASSETS/'compare.html'),result)
                self.assertEqual(page.stat().st_mtime_ns,before)
                swapped=export_pair(root,[(b,2),(a,2)],ASSETS/'compare.html');self.assertNotEqual(swapped['comparison'],str(page))
            for f in (a,b):self.assertTrue(convert(f/'inputs.csv',replace=True)['converted'])
            result=export_pair(root,[(a,2),(b,2)],ASSETS/'compare.html')
            self.assertEqual([json.loads(Path(e['json']).read_text('utf-8')) for e in result['exports']],records)
            for f in (a,b):self.assertEqual(ReadPath(f/'inputs.csv').read_bytes(),original[f])

    def test_foreign_layout_invalid_and_ambiguous_laps_are_rejected(self):
        from lap_comparison import export_pair,valid_laps
        from evo_comparison import available
        from evo_laps import index
        from paths import ASSETS
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'Simulators/ac_evo';a,b=pair(root)
            for selection in ([(a,2),(a,2)],[(a,1),(b,2)],[(a,True),(b,2)],[(a,3),(b,2)]):
                with self.assertRaises(ValueError):export_pair(root,selection,ASSETS/'compare.html')
            path=b/'session.json';meta=json.loads(path.read_text());meta['track_layout']='Sprint';path.write_text(json.dumps(meta))
            with self.assertRaises(ValueError):export_pair(root,[(a,2),(b,2)],ASSETS/'compare.html')
            meta['track_layout']='GP';meta.pop('simulator_id');path.write_text(json.dumps(meta))
            with self.assertRaises(ValueError):export_pair(root,[(a,2),(b,2)],ASSETS/'compare.html')
            value=index(a);value['laps'].append(dict(value['laps'][1]));self.assertNotIn(2,available(value))
            self.assertEqual(len(valid_laps(a)),1)

    def test_index_coalesces_isolated_results_and_invalidates_physical_changes(self):
        import evo_laps
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            f=fixture(t);read=evo_laps._index
            def slow():time.sleep(.05);return read(f)
            with patch('evo_laps._index',side_effect=lambda _:slow()) as calls:
                with ThreadPoolExecutor(4) as pool:values=list(pool.map(lambda _:evo_laps.index(f),range(4)))
                self.assertEqual(calls.call_count,1)
            values[0]['laps'][1]['time']=-1;self.assertEqual(evo_laps.index(f)['laps'][1]['time'],20)
            path=f/'evo_laps_index.json';path.write_text('{}')
            with patch('evo_laps.scan',wraps=evo_laps.scan) as calls:self.assertEqual(evo_laps.index(f)['fastest']['num'],2);self.assertEqual(calls.call_count,1)
            path=f/'inputs.csv';s=path.stat();os.utime(path,ns=(s.st_atime_ns,s.st_mtime_ns+1000000))
            with patch('evo_laps.scan',wraps=evo_laps.scan) as calls:evo_laps.index(f);self.assertEqual(calls.call_count,1)
            path=f/'evo_laps_index.json';value=json.loads(path.read_text());value['padding']='x'*524289;path.write_text(json.dumps(value))
            with patch('evo_laps._index',wraps=evo_laps._index) as calls:
                evo_laps.index(f);evo_laps.index(f);self.assertEqual(calls.call_count,2)

    def test_metadata_fast_read_and_numeric_spill_keep_original_semantics(self):
        from json_store import load
        from analysis_spool import DiskTable
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            p=Path(t)/'meta.json';value=dict(name='布局 🏁',lap=dict(time_s=123.12345678901234,unknown=None,negative=-0.0),valid=True)
            p.write_text(json.dumps(value,ensure_ascii=False),'utf-8')
            with patch('paths.data_directory',side_effect=AssertionError('Unexpected preference lookup')):
                self.assertEqual(load(p),value);self.assertEqual(load(p,fields=('lap',)),{'lap':value['lap']})
            table=DiskTable((),4,t,nullable=True);table._sealed=False
            rows=[[1.1234567890123457,-0.0,2**40,True],[None,1e-300,1e300,False]]
            for row in rows:table.append(row)
            table.seal();table._file.seek(0)
            self.assertEqual(table._file.read(),b''.join(struct.pack('<4d',*(math.nan if x is None else x for x in row)) for row in rows))
            self.assertEqual(list(table),rows);self.assertEqual(math.copysign(1,table[0][1]),-1);table.close()


class UI(unittest.TestCase):
    def test_evo_pair_selector_toolbar_and_personal_record_shortcut(self):
        script=r'''
import sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from unittest.mock import patch
from control_center import ControlCenter
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.geometry('1200x850+20+20');app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.3):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 app.show_page(1);pump(1)
 assert {'compare','delete','laps','journal'}<=set(app.review_actions)
 assert {'note','copy-rows','export','import','refresh'}<={a.key for a in app.review_menu.actions}
 app.tree.selection_set(app.tree.get_children()[0]);app.selected_laps();pump(1)
 window=app.lap_pair_window;c=window.pair_controls;assert c['track'].get() and c['state']['rows']['A']
 c['quick']['same'].invoke();pump();assert c['state']['rows']['B'] and not c['compare'].enabled
 labels=list(c['state']['events']);c['events']['B'].set(next(k for k in labels if k!=c['events']['A'].get()));c['scan']('B');pump(.6);assert c['compare'].enabled
 with patch('control_lap_pair.os.startfile') as opened:
  c['compare'].invoke();pump(1.3);assert opened.call_count==1 and 'EVO_Compare_' in opened.call_args.args[0]
 window.destroy();app.show_page(6);pump(1.3);page=app.record_loaders['best'].page;page.menu.invoke('lap-pair');pump(.7);assert app.lap_pair_window.winfo_exists()
 app.lap_pair_window.destroy();app.set_theme('light');pump();app.toggle_language();pump();app.show_page(1);pump(.5)
 assert not errors,errors
 app.request_close();pump(.2)
print('EVO pair, compact actions, bilingual/theme rebuild and record shortcut OK')
'''
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t);pair(root/'Simulators/ac_evo')
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=35)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)

if __name__=='__main__':unittest.main()
