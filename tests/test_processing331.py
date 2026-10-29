"""One-to-six EVO CSV snapshots, bounded preparation and exact source guards."""
import csv,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from tests.test_processing329 import fixture


class Data(unittest.TestCase):
    def test_csv_text_matches_parser_for_sparse_complex_cookies_and_field_limit(self):
        import io
        from evo_exports import _csv_lines
        from lap_scan_index import raw_rows
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            path=Path(t)/'inputs.csv';columns=['a','b','c']
            text='a,b,c\r\n0.12345678901234567,-0.0,1e-300\r\n\n"a\r\nb",中文,"q""x"\nshort,last\r\nextra,tail,value,discarded\rspace, ,\n"",,\r\n'
            path.write_bytes(('\ufeff'+text).encode('utf-8'));cookies=[];rows=list(raw_rows(path,capture=cookies,columns=columns))
            expected=io.StringIO(newline='');csv.writer(expected).writerows(rows)
            self.assertEqual(''.join(_csv_lines(path,0,None,cookies,columns)),expected.getvalue())
            for first,last in ((1,4),(2,6),(5,None)):
                out=io.StringIO(newline='');csv.writer(out).writerows(rows[first:last])
                self.assertEqual(''.join(_csv_lines(path,first,last,cookies,columns)),out.getvalue())
            old_limit=csv.field_size_limit()
            try:
                csv.field_size_limit(12)
                with self.assertRaises(csv.Error):list(_csv_lines(path,0,None,(),columns))
            finally:csv.field_size_limit(old_limit)

    def test_six_laps_one_inventory_same_bytes_plain_and_packed(self):
        import evo_laps,laps
        from evo_exports import Inventory,lap_csv
        from column_store import convert
        for packed in (False,True):
            with self.subTest(packed=packed),tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
                root=Path(t)/'Simulators/ac_evo';folder=fixture(root);source=folder/'inputs.csv';original=source.read_bytes();meta=(folder/'session.json').read_bytes()
                if packed:self.assertTrue(convert(source,replace=True)['converted'])
                expected=[Path(lap_csv(root,folder,Path(t)/'old',n)['path']).read_bytes() for n in range(2,8)]
                cache=Inventory()
                with patch('evo_laps.index',wraps=evo_laps.index) as indexed,patch('laps.finished_metadata',wraps=laps.finished_metadata) as metadata,patch('evo_laps.read_curve',side_effect=AssertionError('No unused curve')):
                    results=[lap_csv(root,folder,Path(t)/'new',n,_inventory=cache) for n in range(2,8)]
                self.assertEqual(indexed.call_count,1);self.assertEqual(metadata.call_count,1)
                self.assertEqual([Path(v['path']).read_bytes() for v in results],expected)
                self.assertEqual([v['number'] for v in results],list(range(2,8)))
                self.assertTrue(all(v['samples']==100 for v in results));self.assertIsNotNone(cache.value)
                self.assertEqual(cache.value[1]['signature'],evo_laps.stamp(folder));self.assertIsNotNone(cache.reader);cache.clear();self.assertIsNone(cache.value);self.assertIsNone(cache.reader)
                self.assertEqual((folder/'session.json').read_bytes(),meta)
                from telemetry_file import Path as ReadPath
                self.assertEqual(ReadPath(source).read_bytes(),original)
                self.assertFalse((folder/'SelectedLaps').exists());self.assertFalse((root/'LapComparisons').exists())
                self.assertFalse(list((Path(t)/'new').glob('*.pending')))

    def test_changed_source_foreign_and_memory_limit_force_fresh_preparation(self):
        import evo_laps
        from evo_exports import Inventory,lap_csv
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'Simulators/ac_evo';folder=fixture(root);dest=Path(t)/'out';cache=Inventory()
            first=lap_csv(root,folder,dest,2,_inventory=cache);preserved=Path(first['path']).read_bytes()
            path=folder/'inputs.csv'
            with path.open(encoding='utf-8',newline='') as stream:r=csv.DictReader(stream);fields=r.fieldnames;rows=list(r)
            for row in rows:
                if row['lap']=='3':row['lap_invalidated']='1'
            with path.open('w',encoding='utf-8',newline='') as stream:w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();w.writerows(rows)
            with patch('evo_laps.index',wraps=evo_laps.index) as read,self.assertRaises(ValueError):lap_csv(root,folder,dest,3,_inventory=cache)
            self.assertEqual(read.call_count,1);self.assertEqual(Path(first['path']).read_bytes(),preserved)
            cache.clear()
            with patch.object(Inventory,'INDEX_BYTES',0),patch('evo_laps.index',wraps=evo_laps.index) as read:
                a=lap_csv(root,folder,dest,4,_inventory=cache);b=lap_csv(root,folder,dest,5,_inventory=cache)
            self.assertEqual(read.call_count,2);self.assertIsNone(cache.value)
            meta=json.loads((folder/'session.json').read_text('utf-8'));meta['simulator_id']='lmu';(folder/'session.json').write_text(json.dumps(meta),'utf-8')
            with patch('evo_laps.index',side_effect=AssertionError('Foreign game must fail before scan')),self.assertRaises(ValueError):lap_csv(root,folder,dest,4,_inventory=cache)
            self.assertTrue(Path(a['path']).is_file() and Path(b['path']).is_file());self.assertFalse(list(dest.glob('*.pending')))


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_six_snapshot_cancel_resume_retry_capture_guard_and_release(self):
        script=r"""
import sys,time,threading,traceback
from pathlib import Path
sys.path[:0]=[str(Path.cwd()/'src'),str(Path.cwd())]
from unittest.mock import patch
from control_center import ControlCenter
from control_evo_lap_overview import show
from control_evo_exports import selected_csv
from control_maintenance import busy
import evo_exports
errors=[];entered=threading.Event();gate=threading.Event();caches=[];real=evo_exports.lap_csv;fail={4}
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.3):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 pump(.3);folder=app.data_path/'Logs/evo';w=show(app,folder);w.geometry('900x720');pump(.5);c=w.lap_overview
 c['kind'].set('valid');c['populate']();c['table'].selection_set(c['table'].get_children());pump(.1)
 assert len(c['table'].selection())==7 and not c['buttons']['csv'].enabled
 c['buttons']['best-many'].invoke();pump(.1);assert c['buttons']['csv'].enabled
 def pick(**kw):c['table'].selection_set(('1',));return str(app.data_path/'exports')
 def held(*a,**kw):
  caches.append(kw['_inventory']);n=kw.get('number')
  if n==2:entered.set();assert gate.wait(4)
  if n in fail:fail.remove(n);raise OSError('One export failed')
  return real(*a,**kw)
 with patch('control_evo_exports.filedialog.askdirectory',side_effect=pick),patch('evo_exports.lap_csv',side_effect=held),patch('evo_laps.read_curve',side_effect=AssertionError('CSV must not build curves')):
  c['buttons']['best-many'].invoke();c['buttons']['csv'].invoke();assert entered.wait(1);job=app.batch_job
  assert [n for _,n in job.values]==list(range(2,8)) and busy(app)
  assert [v.split(' · ')[0] for v in job.names]==list('ABCDEF')
  with patch('hud.App',side_effect=AssertionError('Capture overlapped CSV export')):app.start()
  assert app.hud is None
  app.set_theme('light');app.toggle_language();pump(.1);job.stop_after();gate.set();pump(.5)
  assert job.states==['已完成']+['等待处理']*5 and not busy(app),job.states
  assert all(v.value is None and v.reader is None for v in caches)
  job.resume_button.invoke();pump(.6)
  assert job.states.count('失败')==1 and job.states.count('已完成')==5 and not busy(app),job.errors
  before={Path(v['path']):Path(v['path']).read_bytes() for v in job.results.values()}
  job.retry_button.invoke();pump(.5)
  assert job.states==['已完成']*6 and not busy(app) and all(v.value is None and v.reader is None for v in caches),job.errors
  assert [v['number'] for _,v in sorted(job.results.items())]==list(range(2,8))
  assert all(p.read_bytes()==b for p,b in before.items())
  assert not (folder/'SelectedLaps').exists() and not (app.data_path/'LapComparisons').exists()
 for values in ([(folder,n) for n in range(2,9)],[(folder,2),(folder,2)]):
  with patch('control_evo_exports.filedialog.askdirectory') as picker:
   try:selected_csv(app,app.data_path,values)
   except ValueError:pass
   else:raise AssertionError('Invalid selection accepted')
   picker.assert_not_called()
 assert not errors,errors
 job.window.destroy();w.destroy();app.request_close();pump(.1)
"""
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=fixture(Path(t)/'Simulators/ac_evo',laps=8);before={p:p.read_bytes() for p in (folder/'session.json',folder/'inputs.csv')}
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=25,creationflags=0x08000000)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for p,b in before.items():self.assertEqual(p.read_bytes(),b)
