"""Reuse canonical record identities and prefill EVO comparison with session best."""
import json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]


class Data(unittest.TestCase):
    def test_record_entries_preserve_overlay_hidden_foreign_missing_and_source_boundaries(self):
        from personal_records import entries
        from evo_laps import stamp
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            outside=Path(t)/'outside.json';outside.write_bytes(b'outside the selected simulator root')
            for game in ('lmu','ac_evo'):
                root=Path(t)/'lmu' if game=='lmu' else Path(t)/'Simulators/ac_evo';folders={}
                for i,(name,category) in enumerate([('hidden','Logs'),('valid, 圈','ImportedLogs'),('foreign','RecoveredLogs'),('missing','Logs'),('escape','Logs')]):
                    f=root/category/name;f.mkdir(parents=True);folders[name]=f
                    meta=dict(status='complete',simulator_id=('ac_evo' if game=='lmu' else 'lmu') if name=='foreign' else game,source='Fixture',track='Monza',track_layout='GP',vehicle='Ferrari 296 LMGT3 Evo (No BOP)' if game=='lmu' else 'Ferrari 296 GTB',vehicle_variant='no_bop' if game=='lmu' else '',vehicle_class='GT3',race_mode='unknown',driver='Fixture Driver')
                    (f/'session.json').write_text(json.dumps(meta),'utf-8');(f/'inputs.csv').write_bytes(b'raw, never read');(f/'lap.json').write_bytes(b'complete curve, never read')
                    value=dict(status='saved',session=meta,file=str(outside) if name=='escape' else 'lap.json',lap=dict(number=3,time_s=100.12345678901235,track_length_m=5781.123456789012,validity='verified'),conditions=dict(raw_value=-0.0))
                    if game=='ac_evo':value['signature']=stamp(f)
                    (f/'fastest_lap_summary.json').write_text(json.dumps(value),'utf-8')
                    if name=='missing':(f/'lap.json').unlink()
                before={p:p.read_bytes() for p in root.rglob('*') if p.is_file()};valid=folders['valid, 圈'];hidden=folders['hidden'].resolve()
                overlay={str(valid.resolve()):dict(race_mode='single',race_mode_manual=True,race_mode_source='user')}
                with patch('race_mode.overlay',return_value=overlay),patch('session_groups.superseded',return_value={hidden}),patch('race_mode.annotate',side_effect=AssertionError('Canonical record paths must use the shared pure decision')),patch('lap_scan_index.raw_rows',side_effect=AssertionError('No raw scan')):
                    values=entries(root)
                self.assertEqual(len(values),1);e=values[0];self.assertEqual(e['folder'],str(valid));self.assertEqual(e['file'],str((valid/'lap.json').resolve()));self.assertEqual(e['time_s'],100.12345678901235);self.assertEqual(e['length_m'],5781.123456789012)
                self.assertEqual(e['race_mode'],'single');self.assertTrue(e['session']['race_mode_manual']);self.assertEqual(e['session']['vehicle'],'Ferrari 296 LMGT3 Evo (No BOP)' if game=='lmu' else 'Ferrari 296 GTB')
                self.assertEqual(e['identity'][-3:] if game=='lmu' else e['identity'][-2:],('variant','no_bop','ferrari 296 lmgt3 evo (no bop)') if game=='lmu' else ('ac_evo','ferrari 296 gtb'))
                for p,b in before.items():self.assertEqual(p.read_bytes(),b)
            self.assertEqual(outside.read_bytes(),b'outside the selected simulator root')


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_single_lap_compare_prefills_global_eligible_best_and_keeps_selection_context(self):
        script=r'''
import sys,time,traceback
from pathlib import Path
sys.path[:0]=[str(Path.cwd()/'src'),str(Path.cwd())]
from unittest.mock import patch
from control_center import ControlCenter
from control_evo_lap_overview import show
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.withdraw();app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.15):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 folder=app.data_path/'Logs/evo';w=show(app,folder);w.geometry('1000x820');pump(.7);c=w.lap_overview;table=c['table'];state=c['state'];button=c['buttons']['compare']
 assert state['best_lap']['num']==2
 # Even when the fastest lap is filtered out, A is the session best and B is the selected lap.
 c['query'].set('3');c['populate']();table.selection_set(('2',));pump();c['sort']('time',True);before=(table.selection(),tuple(table.order),table.offset,c['query'].get())
 with patch('evo_laps.index',side_effect=AssertionError('Selection must not scan index')),patch('lap_scan_index.raw_rows',side_effect=AssertionError('No raw read')),patch('control_lap_pair.show') as pair:
  assert button.enabled and button.label=='与本场最快圈对比';button.invoke();assert pair.call_args.kwargs['selected']==[(folder,2),(folder,3)]
  assert (table.selection(),tuple(table.order),table.offset,c['query'].get())==before
  with patch('control_evo_lap_overview.offline_ready',return_value=False):button.invoke();assert pair.call_count==1
  state['loading']=True;table.viewport.event_generate('<<TreeviewSelect>>');pump();button.action();assert pair.call_count==1 and not button.enabled
  state['loading']=False;table.viewport.event_generate('<<TreeviewSelect>>');pump()
  app.set_theme('light');app.toggle_language();w.geometry('800x600');pump(.3)
  assert button.cget('text')=='Compare with session best' and button.enabled
  assert button.winfo_reqwidth()>=button.font.measure(button.cget('text'))
  assert max(b.winfo_rooty()+b.winfo_height() for b in c['buttons'].values() if b.winfo_ismapped())<=w.winfo_rooty()+w.winfo_height()+1
  c['query'].set('');c['populate']();table.selection_set(('1',));pump();assert not button.enabled
  table.selection_set(('0',));pump();assert not button.enabled
  table.selection_set(('1','2'));pump();assert button.enabled and button.cget('text')=='Compare selected laps';button.invoke();assert pair.call_args.kwargs['selected']==[(folder,int(k)+1) for k in table.selection()]
 # The real selector rechecks availability and accepts these exact identities.
 c['query'].set('3');c['populate']();table.selection_set(('2',));pump();button.invoke();pump(.6)
 p=app.lap_pair_window;pc=p.pair_controls
 assert [pc['state']['laps'][side].get(pc['numbers'][side].get()) for side in ('A','B')]==[2,3]
 assert pc['compare'].enabled and table.selection()==('2',);p.destroy()
 with patch('evo_lap_overview.load',side_effect=OSError('Refresh failed')):c['refresh']();pump(.35)
 assert state['best_lap'] is None and not button.enabled and 'Refresh failed' in c['status'].get()
 w.destroy();assert not errors,errors;app.request_close();pump(.15)
'''
        from tests.test_processing329 import fixture
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=fixture(Path(t)/'Simulators/ac_evo',laps=8);before={p:p.read_bytes() for p in (folder/'inputs.csv',folder/'session.json')}
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=35,creationflags=0x08000000)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for p,b in before.items():self.assertEqual(p.read_bytes(),b)
