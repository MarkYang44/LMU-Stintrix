"""CSV-only EVO exports and exact full-row projection without extra analysis."""
import csv,io,json,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


class Data(unittest.TestCase):
    def test_full_row_identity_preserves_shape_duplicates_and_sparse_fallback(self):
        from csv_projection import projector
        for size in (1,2,34,128):
            fields=[str(i) for i in range(size)];project=projector(fields,fields)
            row=tuple('原值,"\r\n'+str(i) for i in range(size))
            self.assertIs(project(row),row);self.assertEqual(project(list(row)),row)
            self.assertEqual(project(row[:-1]),row[:-1]+(None,));self.assertEqual(project((*row,'extra')),row)
        for fields,columns in [(['a','b','a'],['a','b','a']),(['a','b'],['b','a']),(['a','b'],['a','missing']),(['a','b'],[])]:
            for row in ([],['x'],['x','y'],['x','y','z','extra']):
                expected=dict(zip(fields,row));expected.update({k:None for k in fields[len(row):]})
                self.assertEqual(projector(fields,columns)(row),tuple(expected.get(k,'') for k in columns))

    def test_csv_only_export_keeps_all_fields_packed_sources_and_unique_outputs(self):
        from tests.test_evo_records310 import fixture
        from evo_laps import index
        from evo_exports import fastest_csv
        from column_store import convert
        from telemetry_file import Path as ReadPath
        for packed in (False,True):
            with self.subTest(packed=packed),tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
                root=Path(t)/'Simulators/ac_evo';folder=fixture(root);source=folder/'inputs.csv'
                with source.open(encoding='utf-8',newline='') as stream:rows=list(csv.reader(stream))
                rows[0].extend(['note','note','utf8'])
                for i,row in enumerate(rows[1:]):row.extend(['first','last','中文 🏁,"多行"\r\n'+str(i)])
                with source.open('w',encoding='utf-8-sig',newline='') as stream:csv.writer(stream).writerows(rows)
                original=source.read_bytes();metadata=(folder/'session.json').read_bytes()
                parsed=list(csv.DictReader(io.StringIO(original.decode('utf-8-sig'),newline='')))
                if packed:self.assertTrue(convert(source,replace=True)['converted'])
                value=index(folder);best=value['fastest'];expected=io.StringIO(newline='');writer=csv.writer(expected);writer.writerow(rows[0])
                for row in parsed[best['first_index']:best['end_index']]:writer.writerow([row.get(k,'') for k in rows[0]])
                dest=Path(t)/'exports';dest.mkdir();keep=dest/'keep.csv';keep.write_bytes(b'preserve')
                with patch('evo_laps.scan',side_effect=AssertionError('Index should be reused')),patch('analysis_spool.DiskTable',side_effect=AssertionError('CSV does not need a curve')),patch('evo_laps.read_curve',side_effect=AssertionError('No curve read')):
                    a=fastest_csv(root,folder,dest);b=fastest_csv(root,folder,dest)
                self.assertNotEqual(a['path'],b['path']);self.assertEqual(a['samples'],100);self.assertEqual(a['number'],2)
                self.assertEqual(Path(a['path']).read_bytes(),expected.getvalue().encode('utf-8'));self.assertEqual(Path(b['path']).read_bytes(),Path(a['path']).read_bytes())
                self.assertEqual(ReadPath(source).read_bytes(),original);self.assertEqual((folder/'session.json').read_bytes(),metadata)
                self.assertEqual(keep.read_bytes(),b'preserve');self.assertFalse(list(dest.glob('*.pending')))
                self.assertFalse((folder/'SelectedLaps').exists());self.assertFalse((folder/'fastest_lap.json').exists())

    def test_export_rejects_foreign_live_missing_and_changed_sources_keeps_outputs(self):
        from tests.test_evo_records310 import fixture
        from evo_laps import index
        from evo_exports import fastest_csv
        from evo_exports import _csv_lines
        from report_worker import ReportDeferred
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'Simulators/ac_evo';folder=fixture(root);value=index(folder);dest=Path(t)/'out';dest.mkdir();keep=dest/'old.csv';keep.write_bytes(b'keep')
            before=(folder/'inputs.csv').read_bytes()
            with self.assertRaises(ValueError):fastest_csv(root,folder,folder/'inside')
            foreign=root/'Logs/foreign';shutil.copytree(folder,foreign);meta=json.loads((foreign/'session.json').read_text());meta['simulator_id']='lmu';(foreign/'session.json').write_text(json.dumps(meta))
            with self.assertRaises(ValueError):fastest_csv(root,foreign,dest)
            with self.assertRaises(ValueError):fastest_csv(root.parent,folder,dest)
            with patch('runtime_activity.busy',return_value=True),self.assertRaises(ReportDeferred):fastest_csv(root,folder,dest)
            with patch('evo_laps.index',return_value=dict(value,fastest=None)),self.assertRaises(ValueError):fastest_csv(root,folder,dest)
            with patch('pathlib.Path.is_symlink',return_value=True),self.assertRaises(ValueError):fastest_csv(root,folder,dest)
            def short(*a,**kw):yield from list(_csv_lines(*a,**kw))[:-1]
            with patch('evo_exports._csv_lines',side_effect=short),self.assertRaises(OSError):fastest_csv(root,folder,dest)
            def change(*a,**kw):
                for i,row in enumerate(_csv_lines(*a,**kw)):
                    if i==3:
                        p=folder/'inputs.csv';s=p.stat();os.utime(p,ns=(s.st_atime_ns,s.st_mtime_ns+1000000))
                    yield row
            with patch('evo_exports._csv_lines',side_effect=change),self.assertRaises(OSError):fastest_csv(root,folder,dest)
            self.assertEqual((folder/'inputs.csv').read_bytes(),before);self.assertEqual(list(dest.iterdir()),[keep]);self.assertEqual(keep.read_bytes(),b'keep')


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_evo_csv_batch_snapshot_retry_capture_guard_and_library_route(self):
        script=r'''
import sys,time,threading,traceback
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from unittest.mock import patch
from control_center import ControlCenter
from control_maintenance import busy
from control_evo_exports import fastest_csv
import evo_exports
errors=[];gate=threading.Event();entered=threading.Event();real=evo_exports.fastest_csv
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.geometry('1200x850');app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.3):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 app.show_page(1);pump(1);app.review_menu.invoke('all');pump(.05)
 chosen=[app.items[int(k)] for k in app.tree.selection()];assert len(chosen)==2
 with patch.object(app,'active',return_value=True),patch('control_evo_exports.filedialog.askdirectory') as pick:
  fastest_csv(app,chosen);pick.assert_not_called()
 def pick(**kw):app.tree.selection_set(());return str(app.data_path/'exports')
 def slow(*a,**kw):entered.set();gate.wait(4);return real(*a,**kw)
 with patch('control_evo_exports.filedialog.askdirectory',side_effect=pick),patch('evo_exports.fastest_csv',side_effect=slow),patch('evo_laps.read_curve',side_effect=AssertionError('CSV must not generate curves')):
  app.review_menu.invoke('fastest-csv');assert entered.wait(1);job=app.batch_job
  assert set(job.values)=={e['folder'] for e in chosen} and busy(app)
  with patch('hud.App') as hud:app.start();hud.assert_not_called()
  app.set_theme('light');app.toggle_language();pump(.1);gate.set();pump(.8)
  assert not job.busy and job.states==['已完成','已完成'] and not busy(app),job.errors
  files=[Path(v['path']) for v in job.results.values()];assert len(files)==2 and all(p.is_file() for p in files)
  old={p:p.read_bytes() for p in files}
  gate.clear();entered.clear();job.states[0]='失败';job.errors[0]='retry fixture';job.draw();job.retry_button.invoke();assert entered.wait(1)
  assert busy(app)
  with patch('hud.App') as hud:app.start();hud.assert_not_called()
  gate.set();pump(.8);assert not job.busy and not busy(app)
  for p,body in old.items():assert p.read_bytes()==body
 job.window.destroy();app.show_page(1);pump(.4);app.tree.selection_set(app.tree.get_children()[:1]);pump(.05)
 w=app.library();pump(.5);v=w.library
 with patch('control_evo_exports.fastest_csv') as exported:
  v.operations.menu.invoke('fastest-csv');assert exported.call_count==1
  host,items=exported.call_args.args;assert host.data_path==app.data_path and len(items)==1
 w.destroy();assert not errors,errors;app.request_close();pump(.2)
print('EVO CSV: batch snapshot, source-safe output, retry/capture exclusion and library action OK')
'''
        from tests.test_evo_records310 import fixture
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'Simulators/ac_evo';a=fixture(root);b=root/'Logs/another';shutil.copytree(a,b)
            before={p:p.read_bytes() for f in (a,b) for p in (f/'session.json',f/'inputs.csv')}
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for p,value in before.items():self.assertEqual(p.read_bytes(),value)


if __name__=='__main__':unittest.main()
