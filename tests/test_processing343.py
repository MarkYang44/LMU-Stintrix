"""Observed session targets and bounded, file-independent artwork name caching."""
import csv,json,math,os,re,struct,subprocess,sys,tempfile,unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]


class Data(unittest.TestCase):
    def test_goal_decimal_boundary_precision_invalid_inputs_and_usable_counts(self):
        from evo_lap_overview import parse_goal,goal_counts
        self.assertEqual(struct.pack('<d',parse_goal('1:40.123')),struct.pack('<d',100123/1000))
        self.assertEqual(parse_goal('100.123'),parse_goal('1:40.123'));self.assertEqual(parse_goal(' 0:20.411 '),20.411)
        self.assertEqual(parse_goal('0.12345678901234567'),.12345678901234567)
        for bad in ('','0','0:00.0','-1','NaN','inf','1e2','1:60','1:2:03','3.2:10','.'*33,'1'*33):
            with self.assertRaises(ValueError,msg=bad):parse_goal(bad)
        rows=[dict(usable=True,lap=dict(time=t)) for t in (100.123,100.122,100.124)]+[dict(usable=False,lap=dict(time=None)),dict(usable=False,lap=dict(time=1.))];before=deepcopy(rows)
        self.assertEqual(goal_counts(rows,parse_goal('1:40.123')),dict(valid=3,met=2));self.assertEqual(goal_counts([],10),dict(valid=0,met=0));self.assertIsNone(goal_counts(rows,None));self.assertEqual(rows,before)

    def test_name_cache_preserves_matching_bounds_mutations_and_live_asset_checks(self):
        import race_art,evo_art
        reference=lambda v:re.sub(r'[^a-z0-9\u4e00-\u9fff]','',str(v).casefold())
        catalog=evo_art.catalog();values=[None,False,17,[],{'car':1},'Éß中文 🏁 Full-width Ａ','-0.0','X'*400]
        values.extend(n for kind in ('cars','tracks') for e in catalog[kind] for n in [e['name'],*e.get('aliases',[]),*e.get('layouts',[])])
        for value in values:self.assertEqual(race_art.normalized(value),reference(value))
        class Mutable:
            value='first'
            def __str__(self):return self.value
        mutable=Mutable();self.assertEqual(race_art.normalized(mutable),'first');mutable.value='second';self.assertEqual(race_art.normalized(mutable),'second')
        race_art._short_normalized.cache_clear()
        for i in range(700):race_art.normalized('bounded model '+str(i))
        self.assertLessEqual(race_art._short_normalized.cache_info().currsize,512);before=race_art._short_normalized.cache_info().currsize;race_art.normalized('X'*257);self.assertEqual(race_art._short_normalized.cache_info().currsize,before)
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'one';other=Path(t)/'two';base=root/'assets/evo';base.mkdir(parents=True);entry=dict(name='Car One',aliases=['Car 1'],file='one.png');value=dict(cars=[entry],tracks=[])
            with patch('evo_art.catalog',return_value=value):
                self.assertIsNone(evo_art.item('cars','Car 1',root=root));path=base/'one.png';path.write_bytes(b'local image')
                self.assertEqual(evo_art.item('cars','Car 1',root=root)['local_image'],str(path.resolve()));self.assertIsNone(evo_art.item('cars','Car 1',root=other))
                entry['aliases']=['Car X'];self.assertIsNone(evo_art.item('cars','Car 1',root=root));self.assertIsNotNone(evo_art.item('cars','Car X',root=root))
                path.unlink();self.assertIsNone(evo_art.item('cars','Car X',root=root));(base.parent/'escape.png').write_bytes(b'outside resource directory');entry['file']='../escape.png';self.assertIsNone(evo_art.item('cars','Car X',root=root))


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_session_target_editor_filter_selection_clear_refresh_and_theme_keep_sources(self):
        script=r'''
import sys,time,traceback
from copy import deepcopy
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
 w=show(app,app.data_path/'Logs/evo');w.geometry('1000x820');pump(.7);c=w.lap_overview;state=c['state'];table=c['table'];menu=c['run_menu'];original=deepcopy(state['result']['index'])
 assert state['goal'] is None and state['goal_counts'] is None
 with patch('evo_laps.index',side_effect=AssertionError('No index read')),patch('lap_scan_index.raw_rows',side_effect=AssertionError('No raw read')),patch.object(app,'run_background',side_effect=AssertionError('No background goal task')):
  menu.invoke('goal');pump();editor=w.goal_window;fields=editor.goal_controls;fields['text'].set('1:60');assert not fields['save']() and state['goal'] is None and fields['message'].get()
  fields['text'].set('0:20.411');assert fields['save']();pump();assert state['goal']==20.411 and state['goal_counts']==dict(valid=5,met=2)
  assert '当前筛选达标 2/5' in c['facts'].get()
  table.selection_set(('1','2','3','5'));pump();assert state['selection_goal']==dict(valid=2,met=2) and '达标 2/2' in c['selection_text'].get()
  before=(table.selection(),tuple(table.order),table.offset)
  try:c['set_goal']('bad')
  except ValueError:pass
  else:raise AssertionError('Invalid target accepted')
  assert state['goal']==20.411 and before==(table.selection(),tuple(table.order),table.offset)
  c['query'].set('7');c['populate']();pump();assert state['goal_counts']==dict(valid=1,met=0)
  before=(table.selection(),tuple(table.order),table.offset);c['set_goal']('0:21.000');pump();assert state['goal_counts']==dict(valid=1,met=1) and before==(table.selection(),tuple(table.order),table.offset)
  app.set_theme('light');app.toggle_language();w.geometry('800x600');pump(.3);assert 'Target 0:21.000' in c['facts'].get() and 'Filtered laps meeting target 1/1' in c['facts'].get()
  assert max(b.winfo_rooty()+b.winfo_height() for b in c['buttons'].values() if b.winfo_ismapped())<=w.winfo_rooty()+w.winfo_height()+1
  menu.invoke('goal');pump();editor=w.goal_window;editor.goal_controls['text'].set('changed but cancelled');editor.destroy();assert state['goal']==21.
  state['loading']=True
  try:c['set_goal']('0:19')
  except ValueError:pass
  else:raise AssertionError('Loading target changed')
  state['loading']=False;menu.invoke('goal-clear');pump();assert state['goal'] is None and state['goal_counts'] is None and 'Target ' not in c['facts'].get()
  assert state['result']['index']==original
 c['set_goal']('0:20.411')
 with patch('evo_lap_overview.load',side_effect=OSError('Refresh failed')):c['refresh']();pump(.35)
 assert state['goal']==20.411 and state['goal_counts']==dict(valid=0,met=0) and not c['facts'].get() and not c['buttons']['run'].enabled
 w.destroy();assert not errors,errors;app.request_close();pump(.15)
'''
        from tests.test_processing329 import fixture
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=fixture(Path(t)/'Simulators/ac_evo',laps=8);path=folder/'inputs.csv'
            with path.open(encoding='utf-8',newline='') as stream:r=csv.DictReader(stream);fields=r.fieldnames;rows=list(r)
            for row in rows:
                if row['lap']=='4':row['lap_invalidated']='1'
                if row['lap']=='6':row['lap_invalidated']=''
            with path.open('w',encoding='utf-8',newline='') as stream:w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();w.writerows(rows)
            before={p:p.read_bytes() for p in (path,folder/'session.json')};env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=35,creationflags=0x08000000)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for p,b in before.items():self.assertEqual(p.read_bytes(),b)
