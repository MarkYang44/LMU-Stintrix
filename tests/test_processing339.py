"""Pure participation decisions and instant evidence-only EVO selection facts."""
import csv,math,os,struct,subprocess,sys,tempfile,unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]


class Data(unittest.TestCase):
    def test_annotation_keeps_manual_conflicts_unknown_evo_alias_and_original_fields(self):
        from race_mode import annotate,apply_annotation,mode
        cases=[({}, {}, 'unknown',False),({'race_mode':'online'}, {}, 'online',False),
            ({'race_mode':'online'},{'race_mode':'single'},'unknown',True),
            ({},{'race_mode':'online','race_mode_source':'explicit'},'online',False),
            ({'race_mode':'online'},{'race_mode':'single','race_mode_manual':True,'race_mode_source':'user'},'single',False),
            ({'simulator_id':'ac_evo','race_mode':'offline'},{},'single',False),
            ({'race_mode':'single'},{'race_mode':'online','race_mode_manual':False},'unknown',True),
            ({'race_mode':'online'},{'race_mode':'unknown','race_mode_manual':True},'online',False)]
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=Path(t)/'Logs/event';folder.mkdir(parents=True);canonical=str(folder.resolve())
            for meta,extra,expected,conflict in cases:
                meta=dict(meta,vehicle='Ferrari 296 LMGT3 Evo (No BOP)',time_s=100.12345678901235);before=deepcopy((meta,extra))
                with patch('race_mode.Path.resolve',side_effect=AssertionError('Pure annotation must not resolve paths')):value=apply_annotation(meta,extra)
                self.assertEqual(mode(value),expected);self.assertEqual(value['vehicle'],meta['vehicle']);self.assertEqual(value['time_s'],meta['time_s'])
                self.assertEqual(value,annotate(meta,folder,{canonical:extra}));self.assertEqual((meta,extra),before)
                self.assertEqual(value.get('race_mode_source')=='Conflicting evidence',conflict)

    def test_selection_stats_keep_precision_and_exclude_unusable_laps(self):
        from evo_lap_overview import selection_summary
        times=[100.12345678901235,102.34567890123457,101.00000000000001]
        rows=[dict(usable=True,lap=dict(time=t)) for t in times]+[dict(usable=False,lap=dict(time=1.)),dict(usable=False,lap=dict(time=None))]
        before=deepcopy(rows);value=selection_summary(rows);self.assertEqual((value['total'],value['valid']),(5,3))
        mean=math.fsum(times)/len(times);self.assertEqual(struct.pack('<d',value['mean']),struct.pack('<d',mean));self.assertEqual((value['fastest'],value['slowest']),(min(times),max(times)))
        self.assertAlmostEqual(value['std'],math.sqrt(math.fsum((t-mean)**2 for t in times)/len(times)),places=13);self.assertEqual(rows,before)
        self.assertEqual(selection_summary([]),dict(total=0,valid=0,mean=None,fastest=None,slowest=None,std=None))
        self.assertEqual(selection_summary(rows[3:]),dict(total=2,valid=0,mean=None,fastest=None,slowest=None,std=None))
        singleton=selection_summary(rows[:1]);self.assertEqual(singleton['mean'],times[0]);self.assertIsNone(singleton['std'])


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_selection_stats_follow_filters_reuse_values_translate_and_clear_on_failure(self):
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
 def pump(s=.2):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 w=show(app,app.data_path/'Logs/evo');w.geometry('1000x820');pump(.6);c=w.lap_overview;table=c['table'];state=c['state']
 assert state['usable_count']==5 and state['selection_summary']['total']==0
 with patch('evo_laps.index',side_effect=AssertionError('Selection must not read index')),patch('lap_scan_index.raw_rows',side_effect=AssertionError('Selection must not scan samples')):
  table.selection_set(('1','2','3','5'));pump(.15)
  s=state['selection_summary'];assert s['total']==4 and s['valid']==2 and s['mean']==(20.274+20.411)/2 and s['std'] is not None
  assert '可用 2' in c['selection_text'].get()
  with patch('evo_lap_overview.selection_summary',side_effect=AssertionError('Unchanged selection must reuse numbers')):
   table.viewport.event_generate('<<TreeviewSelect>>');pump(.1);app.set_theme('light');app.toggle_language();pump(.25)
  assert state['selection_summary'] is s and 'Selected 4 / Usable 2' in c['selection_text'].get()
  table.selection_set(('3','5'));pump(.1);assert state['selection_summary']['valid']==0 and state['selection_summary']['mean'] is None and 'Usable 0' in c['selection_text'].get()
  table.selection_set(('1',));pump(.1);assert state['selection_summary']['mean']==20.274 and state['selection_summary']['std'] is None
  c['kind'].set('valid');c['populate']();pump(.1);assert state['usable_count']==5
  c['query'].set('2');c['populate']();pump(.1);assert state['usable_count']==1 and not c['buttons']['best-two'].enabled and state['selection_summary']['valid']==1
  c['query'].set('');c['populate']();pump(.1);assert c['buttons']['best-two'].enabled
  c['buttons']['best-many'].invoke();pump(.15);assert state['selection_summary']['valid']==5
  assert max(b.winfo_rooty()+b.winfo_height() for b in c['buttons'].values())<=w.winfo_rooty()+w.winfo_height()+1
  c['kind'].set('other');c['populate']();pump(.1);assert state['usable_count']==0 and state['selection_summary']['total']==0
 with patch('evo_lap_overview.load',side_effect=OSError('Refresh failed')):c['refresh']();pump(.35)
 assert state['result'] is None and state['usable_count']==0 and state['selection_summary']['valid']==0 and 'Refresh failed' in c['status'].get()
 w.destroy();assert not errors,errors;app.request_close();pump(.2)
'''
        from tests.test_processing329 import fixture
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=fixture(Path(t)/'Simulators/ac_evo',laps=8);path=folder/'inputs.csv'
            with path.open(encoding='utf-8',newline='') as stream:r=csv.DictReader(stream);fields=r.fieldnames;rows=list(r)
            for row in rows:
                if row['lap']=='4':row['lap_invalidated']='1'
                if row['lap']=='6':row['lap_invalidated']=''
            with path.open('w',encoding='utf-8',newline='') as stream:w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();w.writerows(rows)
            before={p:p.read_bytes() for p in (path,folder/'session.json')}
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            r=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30,creationflags=0x08000000)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            for p,data in before.items():self.assertEqual(p.read_bytes(),data)
