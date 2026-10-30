"""Skip unused filter work, exact selected targets and a shared LMU delete entry."""
import csv,json,os,subprocess,sys,tempfile,unittest
from copy import deepcopy
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]


class Data(unittest.TestCase):
    def test_static_track_prefixes_keep_exact_priority_suffixes_and_live_language(self):
        import i18n,track_names as t
        from unittest.mock import patch
        self.assertEqual(t.display('Silverstone International Circuit'),'银石国际布局')
        self.assertEqual(t.display('Silverstone Grand Prix GP 2026'),'银石赛道')
        self.assertEqual(t.display('  Autódromo Internacional do Algarve - GP  ','zh'),'波尔蒂芒赛道')
        for value in ('Nurburgring','GP','赛道未登记','',None):
            with patch.object(t,'key',wraps=t.key) as normalize:self.assertEqual(t.display(value,'zh'),str(value or '').strip());self.assertEqual(normalize.call_count,1)
        with patch.object(i18n,'language','en'):self.assertEqual(t.display('  Monza GP  '),'Monza GP')
        with patch.object(i18n,'language','zh'):self.assertEqual(t.display('Monza GP'),'蒙扎国家赛车场')
        with patch.dict(t.LOOKUP,{t.key('Custom'): '自定义赛道'}):self.assertEqual(t.display('Custom','zh'),'自定义赛道')
        self.assertIn('蒙扎',t.search_text('Monza'));self.assertEqual(t.layout_label('Monza','GP'),i18n.tr('大奖赛布局（减速弯）'))

    def test_empty_search_skips_text_and_reuses_utc_dates_without_mutating_records(self):
        import event_filters as f
        values=[dict(folder=str(i),track='Monza',vehicle='Ferrari 296 LMGT3 Evo (No BOP)',vehicle_class='LMGT3',date=d,time_s=t) for i,(d,t) in enumerate((('2026-10-29T10:00:00Z',90.12345678901234),('2026-10-29T12:00:00+02:00',None),('invalid',-0.),(None,None),('2026-10-28T10:00:00',92.)))];before=deepcopy(values)
        with patch.object(f,'stamp',wraps=f.stamp) as dates,patch.object(f,'search_text',side_effect=AssertionError('No empty search text')),patch.object(f,'layout',side_effect=AssertionError('No unused layout text')):
            self.assertEqual([i for i,_ in f.filtered(values,dict(sort=1),query='  ')],[4,1,0,3,2]);self.assertEqual(dates.call_count,len(values))
        self.assertEqual([i for i,_ in f.filtered(values,dict(sort=10))],[2,0,4,1,3])
        self.assertEqual([i for i,_ in f.filtered(values,dict(period=1),now=datetime(2026,10,29,13,tzinfo=timezone.utc))],[1,0])
        self.assertEqual(len(f.filtered(values,{},query='No BOP')),5);self.assertEqual(len(f.filtered(values,{},query='蒙扎')),5);self.assertEqual(f.filtered(values,{},query='McLaren'),[])
        self.assertEqual(values,before)


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_selected_lap_target_preserves_exact_time_context_and_evidence_guards(self):
        script=r'''
import struct,sys,time,traceback
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
 w=show(app,app.data_path/'Logs/evo');w.geometry('1000x820');pump(.7);c=w.lap_overview;table=c['table'];state=c['state'];menu=c['run_menu'];action=next(a for a in menu.actions if a.key=='goal-from-selection')
 assert not action.enabled()
 # More precision than the displayed milliseconds must survive the shortcut.
 state['result']['index']['laps'][1]['time']=20.274123456789013;c['populate']();original=deepcopy(state['result']['index'])
 with patch('evo_laps.index',side_effect=AssertionError('No index read')),patch('lap_scan_index.raw_rows',side_effect=AssertionError('No raw read')),patch.object(app,'run_background',side_effect=AssertionError('No goal background task')):
  c['sort']('time',True);table.selection_set(('1',));pump();assert action.enabled()
  before=(table.selection(),tuple(table.order),table.offset,c['query'].get(),c['kind'].get());menu.invoke('goal-from-selection');pump()
  assert struct.pack('<d',state['goal'])==struct.pack('<d',20.274123456789013)
  assert before==(table.selection(),tuple(table.order),table.offset,c['query'].get(),c['kind'].get()) and state['selection_goal']==dict(valid=1,met=1)
  assert '第 2 圈' in c['status'].get() and state['result']['index']==original
  for keys in (('3',),('5',),('1','2'),()):
   table.selection_set(keys);pump();assert not action.enabled();menu.invoke('goal-from-selection');assert state['goal']==20.274123456789013
  table.selection_set(('1',));pump();state['loading']=True;assert not action.enabled();menu.invoke('goal-from-selection');assert state['goal']==20.274123456789013;state['loading']=False
  menu.invoke('goal');pump();editor=w.goal_window;assert editor.goal_controls['text'].get()==str(state['goal']);editor.destroy()
  app.set_theme('light');app.toggle_language();w.geometry('800x600');pump(.3);c['buttons']['run'].invoke();pump();menu.hover('goal-from-selection')
  assert 'without typing' in menu.footer.cget('text') and menu.popup.winfo_rootx()+menu.popup.winfo_width()<=w.winfo_rootx()+w.winfo_width()+1
  menu.close(False);menu.invoke('goal-clear');assert state['goal'] is None
  menu.invoke('goal-from-selection');assert state['goal']==20.274123456789013
 with patch('evo_lap_overview.load',side_effect=OSError('Refresh failed')):c['refresh']();pump(.4)
 assert not action.enabled() and state['result'] is None
 w.destroy();assert not errors,errors;app.request_close();pump(.1)
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

    def test_lmu_red_delete_button_cancel_frozen_targets_and_narrow_bilingual_toolbar(self):
        script=r'''
import sys,time,traceback
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path.cwd()/'src'))
from unittest.mock import patch
from control_center import ControlCenter
from control_danger import Danger
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.geometry('1350x950');app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.2):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 app.show_page(1);pump(.7);button=app.review_actions['delete'];assert isinstance(button,Danger) and button.label=='删除选中记录' and not button.enabled
 with patch('control_danger.confirm',side_effect=AssertionError('No empty confirmation')):button.invoke()
 targets=tuple(str(i) for i,e in enumerate(app.items) if e['track']!='Keep');app.tree.selection_set(targets);app.update_toolbar();pump(.1);assert len(targets)==2 and button.enabled
 with patch('control_danger.confirm',return_value=False) as ask:
  button.invoke();assert ask.call_count==1 and '(2)' in ask.call_args.args[2]
 assert all((app.data_path/'Logs'/name/'inputs.csv').read_bytes()==b'keep full samples' for name in ('one','two','keep'))
 # Existing background protection must also guard this new entry.
 with patch('control_delete.busy',return_value=True),patch('control_danger.confirm',side_effect=AssertionError('Busy')):button.invoke()
 accepted=[]
 def accept(work,done):accepted.append((work,done))
 with patch('control_danger.confirm',return_value=True),patch.object(app,'work',side_effect=accept):button.invoke()
 app.tree.selection_set(());app.update_toolbar();assert not button.enabled and len(accepted)==1
 result=accepted[0][0]();assert len(result['deleted'])==2 and not result['failed'];assert not (app.data_path/'Logs/one').exists() and not (app.data_path/'Logs/two').exists()
 assert (app.data_path/'Logs/keep/inputs.csv').read_bytes()==b'keep full samples' and (app.data_path/'Simulators/ac_evo/Logs/foreign/inputs.csv').read_bytes()==b'foreign samples'
 accepted[0][1](result);pump(.5);assert len(app.tree.get_children())==1 and not app.review_actions['delete'].enabled
 app.tree.selection_set(app.tree.get_children());app.update_toolbar();app.set_theme('light');app.toggle_language();app.root.minsize(800,650);app.root.geometry('900x760');pump(.4);button=app.review_actions['delete']
 assert button.enabled and button.cget('text')=='Delete selected records' and button.font.measure(button.cget('text'))<button.winfo_width()
 host=app.shell.action_host;assert all(w.winfo_rootx()+w.winfo_width()<=host.winfo_rootx()+host.winfo_width()+1 for w in app.review_actions.values())
 labels=[w for w in host.winfo_children() if w.winfo_class()=='Label'];assert len(labels)==1 and labels[0].winfo_rooty()+labels[0].winfo_height()<=host.winfo_rooty()+host.winfo_height()+1
 app.show_page(0);pump(.1);app.show_page(1);pump(.4);assert isinstance(app.review_actions['delete'],Danger) and app.review_actions['delete'].enabled
 assert not errors,errors;app.request_close();pump(.1)
'''
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)
            for name,track in (('one','Monza'),('two','Fuji'),('keep','Keep')):
                folder=root/'Logs'/name;folder.mkdir(parents=True);(folder/'session.json').write_text(json.dumps(dict(simulator_id='lmu',status='complete',track=track,vehicle='Ferrari 296 LMGT3 Evo',session=10,started_utc='2026-10-29T12:00:00Z')),encoding='utf-8');(folder/'inputs.csv').write_bytes(b'keep full samples')
            foreign=root/'Simulators/ac_evo/Logs/foreign';foreign.mkdir(parents=True);(foreign/'session.json').write_text('{"simulator_id":"ac_evo","status":"complete"}',encoding='utf-8');(foreign/'inputs.csv').write_bytes(b'foreign samples')
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='lmu',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=35,creationflags=0x08000000)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
