"""Full EVO multi-lap output and current-source snapshots without data reduction."""
import csv,json,math,os,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]


def fixture(root,laps=7):
    from tests.test_processing325 import record
    folder=record(root,'valid');path=folder/'inputs.csv'
    with path.open(encoding='utf-8',newline='') as stream:r=csv.DictReader(stream);fields=r.fieldnames;base=next(r)
    with path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for i in range(laps*100+1):
            count=i//100+1;offset=i%100;phase=offset*math.tau/100;duration=20000+count*137;row=dict(base)
            row.update(time_s=i*.2,lap=count,lap_distance_m=offset*50,lap_invalidated=0,in_pits=0,evo_graphics_packet=i,
                evo_lap_time_ms=offset*duration//100,evo_last_lap_time_ms=20000+(count-1)*137 if count>1 else 0,
                throttle=.5+.45*math.sin(phase+count*.35),brake=.3*(1+math.cos(2*phase+count*.2)),
                filtered_throttle=.5+.4*math.sin(phase+count*.3),filtered_brake=.25*(1+math.cos(2*phase+count*.15)),
                steering=-0.0 if not offset else .3*math.sin(phase),speed_kmh=120+70*math.cos(phase*.7)**2+count*2)
            writer.writerow(row)
    meta=json.loads((folder/'session.json').read_text('utf-8'));meta.update(samples=laps*100+1,duration_s=laps*20.);(folder/'session.json').write_text(json.dumps(meta),'utf-8')
    return folder


class Data(unittest.TestCase):
    def test_six_full_laps_packed_reuse_and_all_pair_layout_validation(self):
        from evo_comparison import export_many,export_pair
        from column_store import convert
        from paths import ASSETS
        from json_store import load
        import evo_comparison
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'Simulators/ac_evo';folder=fixture(root);identities=[(folder,n) for n in range(2,8)];raw=(folder/'inputs.csv').read_bytes();meta=(folder/'session.json').read_bytes()
            with patch('evo_comparison.index',wraps=evo_comparison.index) as indexed:result=export_many(root,identities);self.assertEqual(indexed.call_count,1)
            self.assertEqual([v['number'] for v in result['exports']],list(range(2,8)))
            for item in result['exports']:
                value=load(item['json'])
                try:self.assertEqual(value['lap']['number'],item['number']);self.assertEqual(len(value['data']),100);self.assertFalse(value['lap']['boundary_interpolation'])
                finally:value['data'].close()
            paths=[Path(result['comparison']),*[Path(v[k]) for v in result['exports'] for k in ('json','csv')]];before={p:p.read_bytes() for p in paths}
            with patch('evo_comparison.selected',side_effect=AssertionError('Repeated full lap read')),patch('evo_comparison.index',side_effect=AssertionError('Cached page must only check provenance')):self.assertEqual(export_many(root,identities),result)
            self.assertEqual(export_pair(root,identities[:2]),export_many(root,identities[:2]))
            for values in (identities[:1],identities+[(folder,8)],[identities[0]]*3,[(folder,True),*identities[1:3]],[(folder,1),*identities[1:3]]):
                with self.assertRaises(ValueError):export_many(root,values)
            with self.assertRaises(ValueError):export_pair(root,identities)
            self.assertEqual((folder/'inputs.csv').read_bytes(),raw);self.assertEqual((folder/'session.json').read_bytes(),meta)
            self.assertTrue(convert(folder/'inputs.csv',replace=True)['converted']);self.assertEqual(export_many(root,identities),result)
            for p,body in before.items():self.assertEqual(p.read_bytes(),body)
            b=fixture(root/'b',laps=3);c=fixture(root/'c',laps=3)
            for f,layout in ((folder,''),(b,'GP'),(c,'Indy')):
                value=json.loads((f/'session.json').read_text('utf-8'));value['track_layout']=layout;(f/'session.json').write_text(json.dumps(value),'utf-8')
            with self.assertRaises(ValueError):export_many(root,[(folder,2),(b,2),(c,2)])
            for p,body in before.items():self.assertEqual(p.read_bytes(),body)

    def test_shared_source_snapshot_keeps_envelope_and_rejects_midread_changes(self):
        import comparison_cache as cache
        from evo_comparison import export_many
        import evo_comparison
        from paths import ASSETS
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'Simulators/ac_evo';folder=fixture(root);ids=[(folder,n) for n in range(2,8)]
            expected=[cache.source(f) for f,_ in ids]
            with patch('comparison_cache.source',wraps=cache.source) as source:
                view=cache.View(root,ids,ASSETS/'evo_compare.html',root/'page.html');self.assertEqual(source.call_count,1)
            self.assertEqual(view.signature['sources'],expected)
            current=evo_comparison.index
            def changed(f):
                value=current(f);p=folder/'session.json';p.write_bytes(p.read_bytes()+b' ');return value
            with patch('evo_comparison.index',side_effect=changed),self.assertRaises(OSError):export_many(root,ids)
            self.assertFalse((root/'LapComparisons').exists())


class Renderer(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'),'Node renderer checks')
    def test_original_values_validation_six_laps_and_constant_speed_lookup(self):
        from tests.evo_renderer329 import SCRIPT
        result=subprocess.run([shutil.which('node'),'-'],input=SCRIPT,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_multi_selection_exact_snapshot_capture_guard_and_bilingual_layout(self):
        script=r'''
import sys,time,traceback,threading,ctypes
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
from unittest.mock import patch
from control_center import ControlCenter
from control_evo_lap_overview import show
from evo_comparison import export_many
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.3):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 pump(.4);folder=app.data_path/'Logs/evo';w=show(app,folder);w.geometry('900x720');pump(.7);c=w.lap_overview
 c['kind'].set('valid');c['populate']();c['table'].selection_set(c['table'].get_children());pump(.1)
 assert len(c['table'].selection())==7 and not c['buttons']['compare'].enabled and not c['buttons']['csv'].enabled
 c['buttons']['best-many'].invoke();pump(.1);assert len(c['table'].selection())==6 and c['buttons']['compare'].enabled and c['buttons']['csv'].enabled
 selected=[c['state']['rows'][k]['lap']['num'] for k in c['table'].selection()];assert selected==list(range(2,8)),selected
 entered=threading.Event();gate=threading.Event()
 def held(root,ids):entered.set();assert gate.wait(3);return export_many(root,ids)
 with patch('evo_comparison.export_many',side_effect=held),patch('os.startfile') as opened:
  c['buttons']['compare'].invoke();pump(.1);assert entered.is_set() and app.lap_curve_jobs==1
  with patch('hud.App',side_effect=AssertionError('Capture overlapped multi-lap export')):app.start()
  assert app.hud is None;c['table'].selection_set(('7',));gate.set();pump(.8)
  assert app.lap_curve_jobs==0 and opened.call_count==1
  page=Path(opened.call_args.args[0]);assert page.name.startswith('EVO_Multi_') and page.is_file()
  receipt=__import__('json').loads(page.with_suffix('.cache.json').read_text('utf-8'));assert [v['number'] for v in receipt['result']['exports']]==selected
 assert c['table'].selection()==('7',)
 c['buttons']['best-two'].invoke();pump(.1);assert c['buttons']['compare'].enabled and c['buttons']['csv'].enabled
 c['buttons']['compare'].invoke();pump(.6);p=app.lap_pair_window.pair_controls
 assert [p['state']['laps'][k][p['numbers'][k].get()] for k in ('A','B')]==[2,3];app.lap_pair_window.destroy()
 c['buttons']['best-many'].invoke();pump(.1);app.set_theme('light');app.toggle_language();pump(.5)
 assert len(c['table'].selection())==6 and c['buttons']['compare'].cget('text')=='Compare selected laps'
 for b in c['buttons'].values():assert b.winfo_rootx()+b.winfo_width()<=w.winfo_rootx()+w.winfo_width()+1 and b.winfo_rooty()+b.winfo_height()<=w.winfo_rooty()+w.winfo_height()+1
 with patch('evo_comparison.export_many',side_effect=OSError('Export failed')):c['buttons']['compare'].invoke();pump(.3)
 assert app.lap_curve_jobs==0 and not c['state']['loading'] and 'Export failed' in c['status'].get()
 w.destroy();assert not errors,errors;app.request_close();pump(.15)
print('EVO multi-lap: up to six eligible laps, exact snapshot, existing A/B, capture/error cleanup and bilingual small layout OK')
'''
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=fixture(Path(t)/'Simulators/ac_evo',laps=8);before={p:p.read_bytes() for p in (folder/'session.json',folder/'inputs.csv')}
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=35)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for p,body in before.items():self.assertEqual(p.read_bytes(),body)


if __name__=='__main__':unittest.main()
