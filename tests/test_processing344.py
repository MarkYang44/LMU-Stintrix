"""Bounded exact CSV writes and target-based selection using observed lap facts."""
import csv,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]


class Data(unittest.TestCase):
    def test_serialized_writes_preserve_text_count_bound_and_direct_large_records(self):
        from evo_exports import _write_lines
        class Sink:
            def __init__(self):self.blocks=[]
            def write(self,text):self.blocks.append(text)
        huge='汉'*3000+'\r\n';rows=['-0.0,0.12345678901234567,1e-300,中文\r\n']*100+[huge,'','','"a\r\nb","quote""x"\r\n']*3
        sink=Sink();self.assertEqual(_write_lines(iter(rows),sink,limit=1024),len(rows));self.assertEqual(''.join(sink.blocks),''.join(rows))
        self.assertTrue(all(len(s)<2048 or s is huge for s in sink.blocks));self.assertTrue(any(s is huge for s in sink.blocks));self.assertLess(len(sink.blocks),len(rows)//2)
        sink=Sink();self.assertEqual(_write_lines(iter(()),sink),0);self.assertFalse(sink.blocks)
        def broken():yield 'unpublished,precision\r\n';raise OSError('source failed')
        with self.assertRaises(OSError):_write_lines(broken(),Sink())

    def test_failed_chunk_write_closes_batch_source_preserves_old_export_and_retries(self):
        import evo_exports
        from evo_exports import lap_csv,Inventory
        from tests.test_processing329 import fixture
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'Simulators/ac_evo';folder=fixture(root,laps=3);dest=Path(t)/'exports';original={p:p.read_bytes() for p in (folder/'inputs.csv',folder/'session.json')}
            previous=Path(lap_csv(root,folder,dest,2)['path']);expected=previous.read_bytes();cache=Inventory();closed=[];real_rows=evo_exports._csv_lines;real_open=evo_exports.os.fdopen
            def rows(*a,**kw):
                try:yield from real_rows(*a,**kw)
                finally:closed.append(True)
            class Failing:
                def __init__(self,*a,**kw):self.file=real_open(*a,**kw);self.calls=0
                def __enter__(self):return self
                def __exit__(self,*a):self.file.close()
                def write(self,text):
                    self.calls+=1
                    if self.calls>1:raise OSError('chunk write failed')
                    return self.file.write(text)
            with patch('evo_exports._csv_lines',rows):
                with patch('evo_exports.os.fdopen',Failing),self.assertRaisesRegex(OSError,'chunk write failed'):lap_csv(root,folder,dest,2,_inventory=cache)
                self.assertIsNone(cache.reader);self.assertEqual(closed,[True]);self.assertEqual(previous.read_bytes(),expected);self.assertFalse(list(dest.glob('*.pending')))
                retried=Path(lap_csv(root,folder,dest,2,_inventory=cache)['path']);cache.clear();self.assertEqual(retried.read_bytes(),expected);self.assertEqual(len(closed),2)
            for p,b in original.items():self.assertEqual(p.read_bytes(),b)


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_goal_selection_respects_visible_order_evidence_limits_and_csv_handoff(self):
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
 folder=app.data_path/'Logs/evo';w=show(app,folder);w.geometry('1000x820');pump(.7);c=w.lap_overview;state=c['state'];table=c['table'];menu=c['run_menu']
 assert state['goal_counts'] is None
 with patch('evo_laps.index',side_effect=AssertionError('Goal selection must not load index')),patch('lap_scan_index.raw_rows',side_effect=AssertionError('No raw read')),patch.object(app,'run_background',side_effect=AssertionError('No background selection task')):
  c['set_goal']('0:20.411');assert state['goal_counts']==dict(valid=9,met=2)
  c['sort']('time',True);before=(tuple(table.order),table.sort_state,c['query'].get(),c['kind'].get())
  menu.invoke('goal-met');pump();assert table.selection()==('2','1') and state['selection_goal']==dict(valid=2,met=2) and c['buttons']['csv'].enabled
  assert before==(tuple(table.order),table.sort_state,c['query'].get(),c['kind'].get())
  menu.invoke('goal-above');pump();assert len(table.selection())==7 and not c['buttons']['compare'].enabled and not c['buttons']['csv'].enabled
  assert all(state['rows'][key]['usable'] and state['rows'][key]['lap']['time']>20.411 for key in table.selection())
  c['rhythm'].toggle();pump();assert c['rhythm'].visible;menu.invoke('goal-met');pump();assert not c['rhythm'].visible and table.selection()==('2','1')
  c['query'].set('7');c['populate']();menu.invoke('goal-above');pump();assert table.selection()==('6',)
  before=table.selection();menu.invoke('goal-met');c['select_goal'](True);assert table.selection()==before
  c['buttons']['run'].invoke();pump();assert menu.popup and menu.footer.cget('text');menu.close(False)
  state['loading']=True;c['select_goal'](False);assert table.selection()==before;state['loading']=False
  c['query'].set('');c['populate']();app.set_theme('light');app.toggle_language();w.geometry('800x600');pump(.3)
  c['buttons']['run'].invoke();pump();action=next(a for a in menu.actions if a.key=='goal-met');menu.hover('goal-met');assert 'current filter' in menu.footer.cget('text')
  assert menu.popup.winfo_rootx()+menu.popup.winfo_width()<=w.winfo_rootx()+w.winfo_width()+1
  menu.invoke('goal-met');pump();assert table.selection()==('2','1') and 'Selected 2 filtered laps' in c['status'].get()
 # The existing CSV action receives the chosen laps in displayed order.
 with patch('control_evo_exports.filedialog.askdirectory',return_value=str(app.data_path/'exports')):c['buttons']['csv'].invoke();pump(.8)
 job=app.batch_job;assert not job.busy and job.states==['已完成','已完成'],job.errors
 assert [v['number'] for _,v in sorted(job.results.items())]==[3,2]
 assert all(v['samples']==100 for v in job.results.values());job.window.destroy()
 menu.invoke('goal-clear');pump();before=table.selection();menu.invoke('goal-above');assert table.selection()==before
 with patch('evo_lap_overview.load',side_effect=OSError('Refresh failed')):c['refresh']();pump(.35)
 assert not next(a for a in menu.actions if a.key=='goal-met').enabled() and not next(a for a in menu.actions if a.key=='goal-above').enabled()
 w.destroy();assert not errors,errors;app.request_close();pump(.15)
'''
        from tests.test_processing329 import fixture
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=fixture(Path(t)/'Simulators/ac_evo',laps=12);path=folder/'inputs.csv'
            with path.open(encoding='utf-8',newline='') as f:r=csv.DictReader(f);fields=r.fieldnames;rows=list(r)
            for row in rows:
                if row['lap']=='4':row['lap_invalidated']='1'
                if row['lap']=='6':row['lap_invalidated']=''
            with path.open('w',encoding='utf-8',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
            before={p:p.read_bytes() for p in (path,folder/'session.json')};env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=35,creationflags=0x08000000)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for p,b in before.items():self.assertEqual(p.read_bytes(),b)
