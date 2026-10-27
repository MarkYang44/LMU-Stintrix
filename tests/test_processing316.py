"""Lexical column fast path and game-scoped recovery/storage workflow."""
import csv,io,json,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


def fixture(root):
    from tests.test_evo_records310 import fixture as create
    folder=create(root)
    status=dict(version=2,state='partial',steps={k:dict(state='error' if k=='images' else 'ready',attempts=1) for k in ('fastest','review','images','compression')})
    (folder/'report_status.json').write_text(json.dumps(status),'utf-8')
    return folder


class Data(unittest.TestCase):
    def test_equivalent_legacy_lap_caches_survive_ui_release_but_reject_unknown_and_changed_sources(self):
        from tests.test_selected_laps import SelectedLapTests
        from lap_comparison import export_pair,valid_laps
        from lap_scan_index import load,encode,signature
        from lap_exports import cached
        from paths import ASSETS
        import hashlib
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t);folder=SelectedLapTests().session(root);raw=(folder/'inputs.csv').read_bytes()
            result=export_pair(root,[(folder,1),(folder,4)],ASSETS/'compare.html')
            path=folder/'_lap_scan.json';envelope=json.loads(path.read_text());envelope['value']['signature']=dict(version=2,app='0.3.15',source=envelope['value']['signature']['source']);envelope['sha256']=hashlib.sha256(encode(envelope['value'])).hexdigest();path.write_text(json.dumps(envelope));index_bytes=path.read_bytes()
            receipt=folder/'SelectedLaps/_exports.json';value=json.loads(receipt.read_text())
            for key,item in value.items():
                item['signature']=dict(version=2,app='0.3.15',source=item['signature']['source'])
                if key.startswith('lap:'):item['template']=[['old-version-file',1,2]]
            receipt.write_text(json.dumps(value));stamps={p:Path(p).stat().st_mtime_ns for item in result['exports'] for p in (item['json'],item['csv'])}
            with patch('paths.app_version',return_value='future-ui-only'),patch('laps.extract_best',side_effect=AssertionError('Unnecessary rescan')):
                self.assertTrue(valid_laps(folder));self.assertEqual(load(folder)['signature'],signature(folder))
                export_pair(root,[(folder,4),(folder,1)],ASSETS/'compare.html')
            self.assertEqual(path.read_bytes(),index_bytes);self.assertEqual({p:Path(p).stat().st_mtime_ns for p in stamps},stamps)
            envelope['value']['signature']['app']='0.3.14';envelope['sha256']=hashlib.sha256(encode(envelope['value'])).hexdigest();path.write_text(json.dumps(envelope));self.assertIsNone(load(folder))
            envelope['value']['signature']['app']='0.3.15';envelope['sha256']='broken';path.write_text(json.dumps(envelope));self.assertIsNone(load(folder))
            source=folder/'inputs.csv';s=source.stat();os.utime(source,ns=(s.st_atime_ns,s.st_mtime_ns+1000000));self.assertIsNone(cached(folder,[1],None,individual=True));self.assertEqual(source.read_bytes(),raw)

    def test_cache_inventory_counts_files_and_protects_curve_and_comparison_exports(self):
        from cache_management import inventory,target
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)
            for folder in ('PersonalRecords/History','LapComparisons','Logs/session'):
                path=root/folder;path.mkdir(parents=True)
                for n in range(12):(path/str(n)).write_bytes(b'x'*(n+1))
            before={p:p.read_bytes() for p in root.rglob('*') if p.is_file()};items={item['key']:item for item in inventory(root)}
            for key in ('curves','comparisons','races'):
                self.assertFalse(items[key]['clearable']);self.assertEqual((items[key]['files'],items[key]['bytes']),(12,78))
                with self.assertRaises(ValueError):target(root,key)
            self.assertEqual({p:p.read_bytes() for p in before},before)

    def test_column_values_match_csv_parser_for_simple_complex_and_sparse_ranges(self):
        from column_store import convert,Reader,packed,values
        from csv_projection import projector
        from telemetry_file import Path as ReadPath
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=Path(t);(folder/'session.json').write_text('{"status":"complete"}');path=folder/'inputs.csv';stream=io.StringIO(newline='')
            stream.write('\ufeff');w=csv.writer(stream);w.writerow(['t','n','text','dup','dup','last'])
            for i in range(5001):
                text='repeat-🏁-'*8
                if i==2049:text='quoted, "UTF8"\r\nnext line'
                if i==4100:text='null\0inside'
                w.writerow([repr(i*.12345678901234567),'-0.0' if i%2 else '',text,'first','last',str(i%3) if i%4 else ''])
            original=stream.getvalue().encode('utf-8');path.write_bytes(original);self.assertTrue(convert(path,replace=True)['converted'])
            def expected(columns,start,end):
                project=projector(columns,columns)
                for block in Reader(packed(path)).chunks(columns,start,end):
                    for row in csv.reader(io.StringIO(block.decode('utf-8'),newline='')):
                        if row:yield project(row)
            for cols in [('t','n','text','last'),('dup','dup','missing'),('last',),('missing',),(),('t','n')]:
                for start,end in [(0,None),(2041,2060),(4094,4110),(5000,5100)]:
                    self.assertEqual(list(values(path,cols,start,end)),list(expected(cols,start,end)),(cols,start,end))
            self.assertEqual(ReadPath(path).read_bytes(),original)

    def test_report_receipts_use_game_steps_exclude_foreign_data_and_do_not_scan_samples(self):
        from control_report_tasks import entries,readable,details
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'Simulators/ac_evo';folder=fixture(root);foreign=root/'Logs/foreign';shutil.copytree(folder,foreign)
            meta=json.loads((foreign/'session.json').read_text());meta.pop('simulator_id');(foreign/'session.json').write_text(json.dumps(meta))
            before={p:p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with patch('evo_laps.index',side_effect=AssertionError('Unexpected telemetry scan')):items=entries(root)
            self.assertEqual(len(items),1);item=items[0];self.assertFalse(item['read_error']);self.assertTrue(readable(item['receipt'],'ac_evo'));self.assertFalse(readable(item['receipt'],'lmu'))
            text=details(item);self.assertIn('比赛图片',text);self.assertNotIn('耐力分析',text);self.assertNotIn('圈分析',text)
            malformed=dict(item['receipt'],steps=dict(fastest='broken'));self.assertFalse(readable(malformed,'ac_evo'))
            self.assertEqual({p:p.read_bytes() for p in before},before)


class UI(unittest.TestCase):
    def test_evo_shared_selection_recovery_only_failed_stage_and_cache_view(self):
        script=r'''
import sys,time,traceback
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from unittest.mock import patch
from control_center import ControlCenter
from control_report_tasks import show
from session_reports import make_report
errors=[];calls=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.geometry('1250x900+20+20');app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.3):
  until=time.monotonic()+s
  while time.monotonic()<until:app.root.update();time.sleep(.005)
 app.show_page(3);pump(1);browser=app.data_browser;assert set(app.data_tasks.frames)=={'packages','storage','renderer'};assert 'native' not in browser.toolbar
 browser.table.selection_set(browser.table.get_children()[0]);browser.filters.state['query']='Nurburgring';app.search.set('Nurburgring');app.populate();pump()
 selected=[i['folder'] for i in browser.selected()];table=browser.table
 app.data_tasks.select('storage');pump();assert browser.table is table and selected==[i['folder'] for i in browser.selected()];assert 'html' not in browser.toolbar and browser.toolbar['csv'].enabled
 app.data_tasks.select('packages');pump();assert browser.table is table and selected==[i['folder'] for i in browser.selected()]
 browser.menu.invoke('reports');window=app.report_tasks_window;pump(.7);view=window.worklist;assert len(view.items)==1
 key=next(iter(view.items));view.table.selection_set((key,));view.selected();pump();assert view.buttons['retry'].enabled
 def unused():raise AssertionError('Successful report stage reran')
 def image():calls.append('images')
 with patch('evo_reports.operations',return_value=dict(fastest=unused,review=unused,images=image,compression=unused)),patch('report_worker.run',side_effect=lambda folder,root:make_report(folder,isolated=False)):
  view.buttons['retry'].invoke();pump(1.5)
 assert calls==['images'],calls
 assert next(iter(view.items.values()))['receipt']['state']=='ready'
 if getattr(app,'report_retry_job',None) and app.report_retry_job.window.winfo_exists():app.report_retry_job.window.destroy()
 window.destroy()
 browser.menu.invoke('caches');cache=app.cache_panel_window;pump(.6);assert cache.worklist.items
 assert all(not v['clearable'] for v in cache.worklist.items.values() if 'History' in v['path'] or 'Logs' in v['path'])
 cache.destroy();app.data_tasks.select('storage');pump();app.set_theme('light');pump(.6);app.toggle_language();pump(.6)
 assert app.data_tasks.current=='storage' and len(app.data_browser.selected())==1
 assert not errors,errors
 app.request_close();pump(.2)
print('EVO shared storage selection, four-step recovery, protected cache view and context OK')
'''
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t);folder=fixture(root/'Simulators/ac_evo');original=(folder/'inputs.csv').read_bytes()
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=40)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr);self.assertEqual((folder/'inputs.csv').read_bytes(),original)

if __name__=='__main__':unittest.main()
