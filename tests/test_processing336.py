"""Bounded vehicle encoding and EVO cross-session bests use shared backends."""
import csv,json,os,shutil,struct,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]


class Data(unittest.TestCase):
    def test_vehicle_batch_bound_cancel_and_invalid_clock_preserve_old_page(self):
        import reporting
        from reporting import VehicleJSON,json_chunks,write_page
        from vehiclelab import COLUMNS
        from vehiclelab import number
        tokens=['',' ',None,'-0.0','1.2345678901234567','1e-300','1e300','NaN','inf','-inf','invalid','\u0661.\u0665',0,False]
        for row in (tokens,['-0.0','2.1234567890123457','3.4'],['','1.25',None,'NaN']):
            actual=reporting._vehicle_values(row);expected=list(map(number,row));self.assertEqual(actual,expected)
            for a,b in zip(actual,expected):
                if a is not None:self.assertEqual(struct.pack('<d',a),struct.pack('<d',b))
        columns=[k for k in COLUMNS if k not in ('time_s','session_time_s')]
        read=[];closed=[];invalid=[False]
        def rows(*a,**kw):
            try:
                for i in range(200):
                    read.append(i);yield [str(5+i*.1 if not invalid[0] or i!=70 else 5.),str(i*.1),*['-0.0' if j==0 else '.12345678901234567' if j%3 else '' for j in range(len(columns))]]
            finally:closed.append(True)
        encoder=reporting._encoder;batch_sizes=[]
        class Bounded:
            def encode(self,value):
                if isinstance(value,list) and value and isinstance(value[0],list):
                    batch_sizes.append(len(value));self_test.assertLessEqual(len(value),64);self_test.assertLessEqual(sum(map(len,value)),8192)
                return encoder.encode(value)
            def iterencode(self,value):return encoder.iterencode(value)
        self_test=self
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t,patch('lap_scan_index.raw_rows',rows),patch.object(reporting,'_encoder',Bounded()):
            stream=json_chunks(VehicleJSON(t,{}))
            while len(read)<2:next(stream)
            self.assertLessEqual(len(read),64);stream.close();self.assertEqual(closed,[True]);self.assertTrue(batch_sizes)
            read.clear();closed.clear();invalid[0]=True;path=Path(t)/'review.html';path.write_bytes(b'previous approved report')
            with self.assertRaisesRegex(ValueError,'时间戳'):
                write_page(path,'<html>/*STINTRIX_BLOCKS*/</html>',[('vehicle',json_chunks(VehicleJSON(t,{})))])
            self.assertEqual(path.read_bytes(),b'previous approved report');self.assertEqual(closed,[True]);self.assertFalse(list(Path(t).glob('*.pending')))


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_six_session_snapshot_capture_guard_manager_close_failure_and_context(self):
        script=r'''
import sys,time,traceback
from pathlib import Path
from copy import deepcopy
sys.path[:0]=[str(Path.cwd()/'src'),str(Path.cwd())]
from unittest.mock import patch
from control_center import ControlCenter
from control_maintenance import offline_ready
from control_evo_compare import fastest
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.withdraw();app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.3):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 app.show_page(1);pump(.8);app.review_menu.invoke('all');pump(.1)
 keys=app.tree.selection();assert len(keys)==6
 assert app.review_actions['compare'].label=='跨场最快圈对比' and app.review_actions['compare'].enabled
 selected=[dict(app.items[int(key)]) for key in keys];root=app.data_path
 app.lap_pair_context={str(root.resolve()):dict(query='Ferrari',result='previous-pair.html')};context=deepcopy(app.lap_pair_context)
 action=next(a for a in app.review_menu.actions if a.key=='compare-best');assert action.enabled() and action.visible()
 jobs=[]
 with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append((work,done))),patch('control_evo_compare.os.startfile') as opened:
  app.review_actions['compare'].invoke();assert len(jobs)==1 and app.lap_curve_jobs==1 and not offline_ready(app)
  app.tree.selection_set(keys[:2]);assert not action.enabled()
  result=jobs[0][0]();assert len(result['exports'])==6 and Path(result['comparison']).name.startswith('EVO_Multi_')
  jobs[0][1](result,None);assert app.lap_curve_jobs==0 and opened.call_count==1 and app.lap_pair_context==context
  jobs[0][1](result,None);assert opened.call_count==1
  assert app.tree.selection()==keys[:2]
  app.update_selection_count();assert app.review_actions['compare'].label=='圈 A / 圈 B'
  assert not fastest(app,selected+[selected[0]]) and len(jobs)==1
  missing=[dict(v) for v in selected[:3]];missing[0]['fastest_file']=None
  assert not fastest(app,missing) and len(jobs)==1
  assert fastest(app,selected[:3]);assert len(jobs)==2 and app.lap_curve_jobs==1
  with patch('evo_comparison.export_many',side_effect=ValueError('layout mismatch')):
   try:jobs[-1][0]()
   except ValueError as issue:jobs[-1][1](None,str(issue))
  assert app.lap_curve_jobs==0 and 'layout mismatch' in app.status.get() and opened.call_count==1
 # Actual manager uses the same action and can close while its accepted work completes.
 window=app.library([v['folder'] for v in selected]);pump(.7);view=window.library;ops=view.operations
 action=next(a for a in ops.menu.actions if a.key=='compare-best');assert action.visible() and action.enabled() and len(view.selected_items())==6
 app.set_theme('light');app.toggle_language();pump(.2);assert len(view.selected_items())==6
 jobs=[]
 with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append((work,done))),patch('control_evo_compare.os.startfile') as opened:
  ops.menu.invoke('compare-best');assert view.working and app.lap_curve_jobs==1 and len(jobs)==1
  window.destroy();value=jobs[0][0]();jobs[0][1](value,None)
  assert not view.working and app.lap_curve_jobs==0 and opened.call_count==1 and app.lap_pair_context==context
 assert not errors,errors;app.request_close();pump(.1)
'''
        from tests.test_processing329 import fixture
        from evo_laps import export
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            game=Path(t)/'Simulators/ac_evo';a=fixture(game,laps=3);folders=[a]
            for i in range(1,6):
                folder=game/'Logs'/('session-'+str(i));shutil.copytree(a,folder);folders.append(folder)
            for folder in folders:export(folder)
            before={p:p.read_bytes() for f in folders for p in (f/'session.json',f/'inputs.csv')}
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            r=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=35,creationflags=0x08000000)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            for p,b in before.items():self.assertEqual(p.read_bytes(),b)
