"""Shared event discovery and factual EVO lap-list CSVs preserve source evidence."""
import csv,json,os,struct,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]


class Data(unittest.TestCase):
    def test_inventory_shares_discovery_keeps_hidden_official_notes_and_packed_size(self):
        from library import inventory
        from event_catalog import snapshot
        from column_store import convert
        import session_groups
        def event(root,category,name,**extra):
            folder=root/category/name;folder.mkdir(parents=True)
            meta=dict(status='complete',simulator_id='lmu',track='Monza',track_layout='GP',track_length=5781,vehicle='BMW M4 LMGT3',vehicle_class='LMGT3',driver='Fixture',session=10,started_utc='2026-10-20T10:00:00Z',race_mode='online');meta.update(extra)
            (folder/'session.json').write_text(json.dumps(meta),'utf-8')
            (folder/'inputs.csv').write_bytes(b'utc,throttle\r\n'+b'2026-10-20T10:00:00Z,.12345678901234567\r\n'*3000)
            (folder/'fastest_lap_summary.json').write_text(json.dumps(dict(status='saved',file='lap.json',lap=dict(number=2,time_s=100.12345678901235,validity='verified',track_length_m=5781),conditions={})), 'utf-8')
            return folder
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t);a=event(root,'Logs','a');b=event(root,'ImportedLogs','b');original=event(root,'Logs','original')
            merged=event(root,'RecoveredLogs','merged',recovery_sources=[str(original.resolve())]);demo=event(root,'DemoLogs','demo');foreign=event(root,'Logs','foreign',simulator_id='ac_evo')
            (root/'SessionGroups').mkdir();(root/'SessionGroups/index.json').write_text(json.dumps(dict(links={'Logs/original':'RecoveredLogs/merged'})),'utf-8')
            (root/'OfficialResults').mkdir();(root/'OfficialResults/index.json').write_text(json.dumps(dict(entries=[dict(linked_folder=str(a.resolve()),link_status='matched',finish_status='Finished',finished=True,grid_place=5,finish_place=2,grid_class_place=3,finish_class_place=1)])),'utf-8')
            (root/'library_notes.json').write_text(json.dumps({'ImportedLogs/b':dict(favorite=True,tags=['keep'],text='原始备注',traffic=True)}),'utf-8')
            logical=(b/'inputs.csv').stat().st_size;self.assertTrue(convert(b/'inputs.csv',replace=True)['converted'])
            source={p:p.read_bytes() for f in (a,b,original,merged,demo,foreign) for p in f.iterdir() if p.is_file()}
            baseline=inventory(root);index=root/'EventCatalog/index.json';receipt=(index.read_bytes(),index.stat().st_mtime_ns)
            native_open=Path.open
            def guarded(p,*args,**kw):
                if p.suffix=='.csv':raise AssertionError('Inventory must not open telemetry')
                return native_open(p,*args,**kw)
            with patch.object(Path,'open',guarded),patch('event_catalog.build',side_effect=AssertionError('Warm inventory must reuse facets')),patch('session_groups.folders',wraps=session_groups.folders) as discover,patch('session_groups.superseded',wraps=session_groups.superseded) as hidden:
                result=inventory(root);self.assertEqual(discover.call_count,1);self.assertEqual(hidden.call_count,1)
            self.assertEqual(result,baseline);self.assertEqual((index.read_bytes(),index.stat().st_mtime_ns),receipt)
            self.assertEqual({r['folder'] for r in result},{str(p.resolve()) for p in (a,b,merged,demo)})
            row=next(r for r in result if r['folder']==str(b.resolve()));self.assertEqual(row['size_mb'],logical/1048576);self.assertEqual((row['favorite'],row['tags'],row['note'],row['traffic']),(True,['keep'],'原始备注',True));self.assertEqual(row['time_s'],100.12345678901235)
            facets=next(r for r in result if r['folder']==str(a.resolve()))['_facets'];self.assertEqual((facets['trust'],facets['finish'],facets['gain']),('official',2,3))
            with patch('event_catalog.build',side_effect=AssertionError('Do not read outside root')):self.assertEqual(snapshot(root,_folders=[('Logs',root.parent/'outside')]),{})
            for p,data in source.items():self.assertEqual(p.read_bytes(),data)

    def test_timing_csv_keeps_order_precision_missing_flags_and_source_guards(self):
        from evo_lap_overview import load,timing_csv
        from tests.test_processing329 import fixture
        from column_store import convert
        from report_worker import ReportDeferred
        for packed in (False,True):
            with self.subTest(packed=packed),tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
                root=Path(t)/'Simulators/ac_evo';folder=fixture(root,laps=7);path=folder/'inputs.csv'
                with path.open(encoding='utf-8',newline='') as stream:r=csv.DictReader(stream);fields=r.fieldnames;rows=list(r)
                for row in rows:
                    if row['lap']=='4':row['lap_invalidated']='1'
                    if row['lap']=='6':row['lap_invalidated']=''
                with path.open('w',encoding='utf-8',newline='') as stream:w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();w.writerows(rows)
                meta=json.loads((folder/'session.json').read_text('utf-8'));meta.update(track='Race, "North"',track_layout='GP\nEast');(folder/'session.json').write_text(json.dumps(meta),'utf-8')
                if packed:self.assertTrue(convert(path,replace=True)['converted']);path=Path(str(path)+'.stc')
                result=load(root,folder);result['index']['laps'][1]['time']=20.274123456789013
                sources={p:p.read_bytes() for p in (path,folder/'session.json')};destination=Path(t)/'exports';indices=[6,1,3,5,7,0]
                with patch('evo_laps.index',side_effect=AssertionError('Do not rebuild lap index')),patch('lap_scan_index.raw_rows',side_effect=AssertionError('Do not read raw samples')),patch('evo_laps.read_curve',side_effect=AssertionError('Do not build curves')):
                    first=timing_csv(root,folder,destination,result,indices);second=timing_csv(root,folder,destination,result,list(range(8)))
                self.assertNotEqual(first['path'],second['path']);self.assertEqual((first['rows'],second['rows']),(6,8))
                with Path(first['path']).open(encoding='utf-8-sig',newline='') as stream:exported=list(csv.DictReader(stream))
                self.assertEqual([int(r['lap']) for r in exported],[7,2,4,6,8,1]);self.assertEqual(exported[0]['track'],meta['track']);self.assertEqual(exported[0]['layout'],meta['track_layout'])
                self.assertEqual(struct.pack('<d',float(exported[1]['time_s'])),struct.pack('<d',result['index']['laps'][1]['time']))
                self.assertEqual(exported[2]['valid'],'False');self.assertEqual(exported[2]['eligible_for_export'],'False');self.assertEqual(exported[2]['delta_to_session_best_s'],'')
                self.assertEqual(exported[3]['valid'],'');self.assertEqual(exported[3]['eligible_for_export'],'False')
                for row,i in zip(exported,indices):self.assertEqual(row['time_s'],'' if result['index']['laps'][i]['time'] is None else str(result['index']['laps'][i]['time']))
                old={p:p.read_bytes() for p in destination.iterdir()}
                for bad in ([],[True],[1,1],[99]):
                    with self.assertRaises(ValueError):timing_csv(root,folder,destination,result,bad)
                with patch('runtime_activity.busy',return_value=True):
                    with self.assertRaises(ReportDeferred):timing_csv(root,folder,destination,result,indices)
                signature=result['index']['signature']
                with patch('evo_laps.stamp',side_effect=[signature,{'changed':True}]):
                    with self.assertRaises(OSError):timing_csv(root,folder,destination,result,indices)
                with self.assertRaises(ValueError):timing_csv(Path(t)/'lmu',folder,destination,result,indices)
                self.assertEqual({p:p.read_bytes() for p in destination.iterdir()},old);self.assertFalse(list(destination.glob('*.pending')))
                for p,data in sources.items():self.assertEqual(p.read_bytes(),data)


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_timing_export_snapshots_filter_order_and_releases_after_failure_and_close(self):
        script=r'''
import csv,sys,time,traceback
from pathlib import Path
sys.path[:0]=[str(Path.cwd()/'src'),str(Path.cwd())]
from unittest.mock import patch
from control_center import ControlCenter
from control_evo_lap_overview import show
from control_maintenance import offline_ready
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.withdraw();app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.25):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 w=show(app,app.data_path/'Logs/evo');w.geometry('1000x780');pump(.65);c=w.lap_overview;table=c['table'];button=c['buttons']['timing'];destination=app.data_path/'timing-export'
 c['kind'].set('valid');c['populate']();c['sort']('time',True);table.selection_set(('1',));pump(.1)
 expected=[int(table.rows[k][0]) for k in table.order];assert expected==[7,6,5,3,2] and button.enabled
 with patch('tkinter.filedialog.askdirectory',return_value=''),patch.object(app,'run_background',side_effect=AssertionError('Cancel must not start work')):button.invoke()
 assert not c['state']['loading'] and getattr(app,'lap_curve_jobs',0)==0
 jobs=[]
 with patch('tkinter.filedialog.askdirectory',return_value=str(destination)),patch.object(app,'run_background',side_effect=lambda work,done:jobs.append((work,done))):
  button.invoke();assert len(jobs)==1 and app.lap_curve_jobs==1 and not offline_ready(app) and not button.enabled
 c['query'].set('2');c['populate']();pump(.1);assert table.selection()==('1',)
 with patch('evo_laps.index',side_effect=AssertionError('Do not rebuild')),patch('lap_scan_index.raw_rows',side_effect=AssertionError('Do not scan')):result=jobs[0][0]()
 with Path(result['path']).open(encoding='utf-8-sig',newline='') as stream:assert [int(row['lap']) for row in csv.DictReader(stream)]==expected
 jobs[0][1](result,None);assert app.lap_curve_jobs==0 and not c['state']['loading'] and c['query'].get()=='2' and table.selection()==('1',)
 app.set_theme('light');app.toggle_language();pump(.2);assert button.cget('text')=='Export lap times'
 assert button.winfo_rootx()+button.winfo_width()<=w.winfo_rootx()+w.winfo_width()+1
 with patch('tkinter.filedialog.askdirectory',return_value=str(destination)),patch.object(app,'run_background',side_effect=RuntimeError('dispatch failed')):button.invoke()
 assert app.lap_curve_jobs==0 and not c['state']['loading'] and 'dispatch failed' in c['status'].get()
 jobs=[]
 with patch('tkinter.filedialog.askdirectory',return_value=str(destination)),patch.object(app,'run_background',side_effect=lambda work,done:jobs.append((work,done))):button.invoke()
 assert app.lap_curve_jobs==1;w.destroy();result=jobs[0][0]();jobs[0][1](result,None);jobs[0][1](result,None);assert app.lap_curve_jobs==0
 assert not errors,errors;app.request_close();pump(.2)
'''
        from tests.test_processing329 import fixture
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=fixture(Path(t)/'Simulators/ac_evo',laps=7);path=folder/'inputs.csv'
            with path.open(encoding='utf-8',newline='') as stream:r=csv.DictReader(stream);fields=r.fieldnames;rows=list(r)
            for row in rows:
                if row['lap']=='4':row['lap_invalidated']='1'
            with path.open('w',encoding='utf-8',newline='') as stream:w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();w.writerows(rows)
            before={p:p.read_bytes() for p in (path,folder/'session.json')}
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            r=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30,creationflags=0x08000000)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            for p,data in before.items():self.assertEqual(p.read_bytes(),data)
