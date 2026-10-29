"""Version-independent views retain provenance; EVO single-lap and raw sorting."""
import importlib.util,io,csv,json,os,sys,tempfile,subprocess,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]


def old_cache():
    # The previous envelope has a small, explicit constructor for compatibility.
    from comparison_cache import View
    class Previous(View):
        def current(self):
            from paths import app_version
            value=super().current()
            from comparison_cache import stamps
            value['assets']=stamps(self.asset_paths())
            return dict(version=1,app=app_version(),**{k:v for k,v in value.items() if k in ('selections','sources','theme','language','assets')})
    return Previous


class Data(unittest.TestCase):
    def test_renderer_fingerprints_survive_copy_times_but_detect_content_and_bound_memory(self):
        import comparison_cache as cache
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=Path(t);p=folder/'asset.js';p.write_bytes(b'original renderer');cache._asset_hashes.clear()
            first=cache.asset_fingerprints([p]);s=p.stat();os.utime(p,ns=(s.st_atime_ns,s.st_mtime_ns+1000000))
            self.assertEqual(cache.asset_fingerprints([p]),first)
            with patch.object(Path,'open',side_effect=AssertionError('Repeated unchanged resource read')):self.assertEqual(cache.asset_fingerprints([p]),first)
            p.write_bytes(b'modified renderer');self.assertNotEqual(cache.asset_fingerprints([p]),first)
            files=[]
            for i in range(70):
                path=folder/(str(i)+'.js');path.write_bytes(b'asset');files.append(path)
            cache.asset_fingerprints(files);self.assertLessEqual(len(cache._asset_hashes),64)
            self.assertTrue(all(isinstance(v[1],str) and len(v[1])==64 for v in cache._asset_hashes.values()))
            cache._asset_hashes.clear();data=p.read_bytes()
            class Changed(io.BytesIO):
                def read(self,n=-1):
                    value=super().read(n);s=p.stat();os.utime(p,ns=(s.st_atime_ns,s.st_mtime_ns+1000000));return value
            with patch.object(Path,'open',return_value=Changed(data)),self.assertRaises(OSError):cache.asset_fingerprints([p])
            self.assertFalse(cache._asset_hashes)

    def test_audited_legacy_and_new_pair_views_survive_ui_versions_but_keep_guards(self):
        import comparison_cache as cache
        from lap_comparison import export_pair
        from tests.test_selected_laps import SelectedLapTests
        from tests.test_processing325 import record
        from paths import ASSETS
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            base=Path(t)
            for game in ('lmu','ac_evo'):
                root=base/'lmu' if game=='lmu' else base/'Simulators/ac_evo'
                folder=SelectedLapTests().session(root) if game=='lmu' else record(root,'valid')
                identities=[(folder,4),(folder,1)] if game=='lmu' else [(folder,2),(folder,3)]
                template=ASSETS/('compare.html' if game=='lmu' else 'evo_compare.html')
                with patch('comparison_cache.Pair',old_cache()),patch('paths.app_version',return_value='0.3.27'):
                    result=export_pair(root,identities,ASSETS/'compare.html')
                page=Path(result['comparison']);receipt=page.with_suffix('.cache.json');previous=receipt.read_bytes()
                outputs=[page,*[Path(item[k]) for item in result['exports'] for k in ('json','csv')]];before={p:p.read_bytes() for p in outputs};stamps={p:p.stat().st_mtime_ns for p in outputs}
                with patch('lap_comparison.write_compare',side_effect=AssertionError('Legacy page was regenerated')),patch('evo_comparison.write_compare',side_effect=AssertionError('Legacy EVO page was regenerated')):
                    self.assertEqual(export_pair(root,identities,ASSETS/'compare.html'),result)
                self.assertEqual(receipt.read_bytes(),previous)
                for p,stamp in stamps.items():self.assertEqual(p.stat().st_mtime_ns,stamp)
                value=json.loads(previous);value['signature']['app']='0.3.26';receipt.write_text(json.dumps(value),'utf-8')
                view=cache.View(root,identities,template,page);self.assertIsNone(view.read())
                # LMU fresh/cached numeric spelling can differ. Compare old/new
                # rebuilds with identical cached inputs; hits above keep the
                # original fresh page and every export byte untouched.
                with patch('comparison_cache.Pair',old_cache()),patch('paths.app_version',return_value='0.3.27'):
                    self.assertEqual(export_pair(root,identities,ASSETS/'compare.html'),result)
                rebuilt={p:p.read_bytes() for p in outputs}
                value=json.loads(receipt.read_text('utf-8'));value['signature']['app']='0.3.26';receipt.write_text(json.dumps(value),'utf-8')
                self.assertEqual(export_pair(root,identities,ASSETS/'compare.html'),result)
                for p,body in rebuilt.items():self.assertEqual(p.read_bytes(),body)
                modern=receipt.read_bytes()
                with patch('paths.app_version',return_value='9.9.99'),patch('lap_comparison.write_compare',side_effect=AssertionError('UI-only release regenerated a page')),patch('evo_comparison.write_compare',side_effect=AssertionError('UI-only release regenerated an EVO page')):
                    self.assertEqual(export_pair(root,identities,ASSETS/'compare.html'),result)
                self.assertEqual(receipt.read_bytes(),modern)
                with patch('comparison_cache.VIEW_REVISION',2):self.assertIsNone(cache.View(root,identities,template,page).read())
                target='lap_cache_versions.REVISION' if game=='lmu' else 'evo_laps.VERSION'
                with patch(target,99):self.assertIsNone(cache.View(root,identities,template,page).read())
                value=json.loads(modern);value['result']['exports'][0]['number']=999;receipt.write_text(json.dumps(value),'utf-8');self.assertIsNone(cache.View(root,identities,template,page).read())
                receipt.write_bytes(modern);s=(folder/'session.json').stat();os.utime(folder/'session.json',ns=(s.st_atime_ns,s.st_mtime_ns+1000000));self.assertIsNone(cache.View(root,identities,template,page).read())

    def test_single_nonfastest_curve_packed_reuse_precision_and_source_protection(self):
        from evo_comparison import export_single
        from tests.test_processing325 import record
        from json_store import load
        from column_store import convert
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'Simulators/ac_evo';folder=record(root,'valid');source=folder/'inputs.csv';meta=folder/'session.json';original=source.read_bytes();metadata=meta.read_bytes()
            result=export_single(root,folder,3);item,=result['exports'];self.assertEqual(item['number'],3)
            value=load(item['json'])
            try:
                self.assertEqual(value['lap']['number'],3);self.assertEqual(value['simulator_id'],'ac_evo');self.assertEqual(len(value['data']),100)
                self.assertEqual(value['data'][0][2],.12345678901234567)
            finally:value['data'].close()
            with source.open(encoding='utf-8',newline='') as stream:rows=list(csv.reader(stream))
            expected=io.StringIO(newline='');writer=csv.writer(expected);writer.writerow(rows[0]);writer.writerows(rows[201:301])
            self.assertEqual(Path(item['csv']).read_bytes(),expected.getvalue().encode('utf-8'))
            paths=[Path(result['comparison']),Path(item['json']),Path(item['csv'])];bodies={p:p.read_bytes() for p in paths};stamps={p:p.stat().st_mtime_ns for p in paths}
            with patch('evo_comparison.selected',side_effect=AssertionError('Cached view reread full curve')):
                self.assertEqual(export_single(root,folder,3),result)
            for p,stamp in stamps.items():self.assertEqual(p.stat().st_mtime_ns,stamp)
            for number in (False,0,-1,'3',999):
                with self.assertRaises(ValueError):export_single(root,folder,number)
            with self.assertRaises(ValueError):export_single(Path(t),folder,3)
            from report_worker import ReportDeferred
            with patch('runtime_activity.busy',return_value=True),self.assertRaises(ReportDeferred):export_single(root,folder,3)
            self.assertEqual(source.read_bytes(),original);self.assertEqual(meta.read_bytes(),metadata)
            self.assertTrue(convert(source,replace=True)['converted']);self.assertEqual(export_single(root,folder,3),result)
            for p,body in bodies.items():self.assertEqual(p.read_bytes(),body)
            import evo_comparison
            current=evo_comparison.index
            def changed(f):
                value=current(f);meta.write_bytes(metadata+b' ');return value
            with patch('evo_comparison.index',side_effect=changed),self.assertRaises(OSError):export_single(root,folder,3)
            for p,body in bodies.items():self.assertEqual(p.read_bytes(),body)


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_raw_sort_fast_selection_single_curve_snapshot_capture_guard_and_small_layout(self):
        script=r'''
import sys,time,traceback,threading,ctypes
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
from unittest.mock import patch
from control_center import ControlCenter
from control_evo_lap_overview import show
from evo_comparison import export_single
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.3):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 pump(.4);folder=app.data_path/'Logs/evo';w=show(app,folder);w.geometry('900x700');pump(.6);c=w.lap_overview
 assert c['state']['result'] is not None
 laps=c['state']['result']['index']['laps'];times=[lap['time'] for lap in laps]
 laps[1]['time']=32.0004;laps[2]['time']=22.0003;c['populate']();c['sort']('delta',False)
 assert list(c['table'].get_children())==['2','1','0','3'],c['table'].get_children()
 c['buttons']['best-two'].invoke();pump(.1);assert set(c['table'].selection())=={'1','2'} and c['buttons']['compare'].enabled and not c['buttons']['curve'].enabled
 c['kind'].set('valid');c['populate']();assert list(c['table'].get_children())==['2','1']
 c['sort']('delta',True);assert list(c['table'].get_children())==['1','2']
 laps[1]['time']=20.0004;laps[2]['time']=20.0003;c['sort']('time',False);assert list(c['table'].get_children())==['2','1']
 for lap,v in zip(laps,times):lap['time']=v
 c['populate']();c['table'].selection_set(('2',));pump(.1);assert c['buttons']['curve'].enabled
 entered=threading.Event();gate=threading.Event()
 def held(root,f,number):entered.set();assert gate.wait(3);return export_single(root,f,number)
 with patch('evo_comparison.export_single',side_effect=held),patch('os.startfile') as opened:
  c['buttons']['curve'].invoke();pump(.15);assert entered.is_set() and app.lap_curve_jobs==1
  with patch('hud.App',side_effect=AssertionError('Capture started during curve generation')):app.start()
  assert app.hud is None and not c['buttons']['refresh'].enabled
  c['table'].selection_set(('1',));gate.set();pump(.7)
  assert app.lap_curve_jobs==0 and opened.call_count==1
  path=Path(opened.call_args.args[0]);assert path.name=='EVO_Lap_3.html' and path.is_file()
 assert c['table'].selection()==('1',) and c['buttons']['curve'].enabled
 c['query'].set('missing');c['populate']();assert not c['buttons']['best-two'].enabled
 c['query'].set('');c['populate']();c['sort']('samples',True);app.set_theme('light');app.toggle_language();pump(.5)
 assert c['table'].sort_state==('samples',True) and c['kind'].get()=='valid' and c['buttons']['curve'].cget('text')=='Open selected lap curve'
 for b in c['buttons'].values():
  from control_widgets import px
  assert b.font.measure(b.cget('text'))+px(b,36)<=b.winfo_reqwidth()
  assert b.winfo_rootx()+b.winfo_width()<=w.winfo_rootx()+w.winfo_width()+1 and b.winfo_rooty()+b.winfo_height()<=w.winfo_rooty()+w.winfo_height()+1
 c['table'].selection_set(('1',));pump(.1)
 with patch('evo_comparison.export_single',side_effect=OSError('Read failed')):c['buttons']['curve'].invoke();pump(.3)
 assert app.lap_curve_jobs==0 and not c['state']['loading'] and 'Read failed' in c['status'].get()
 import copy
 updated=copy.deepcopy(c['state']['result']);updated['index']['laps'].reverse()
 with patch('evo_lap_overview.load',return_value=updated):c['refresh']();pump(.3)
 assert [c['state']['rows'][key]['lap']['num'] for key in c['table'].selection()]==[2]
 w.destroy();assert not errors,errors;app.request_close();pump(.15)
print('EVO single curve: raw numeric sorting, filter/selection context, exact lap snapshot, capture guard, error cleanup and bilingual small window OK')
'''
        from tests.test_processing325 import record
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=record(Path(t)/'Simulators/ac_evo','valid');before={p:p.read_bytes() for p in (folder/'session.json',folder/'inputs.csv')}
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            child=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=35)
            self.assertEqual(child.returncode,0,child.stdout+child.stderr)
            for p,body in before.items():self.assertEqual(p.read_bytes(),body)


if __name__=='__main__':unittest.main()
