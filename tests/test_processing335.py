"""Exact streamed matrix batches and source-contiguous EVO lap shortcuts."""
import csv,io,json,math,os,struct,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]


class Data(unittest.TestCase):
    def test_stream_batches_preserve_wire_fallback_errors_and_append_overrides(self):
        from analysis_spool import DiskTable
        from json_store import Reader
        rows=[[i/19,-0.,None,1.2345678901234567] for i in range(1800)]
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            for tail in ([],[[True,2,3,4]],[[2**70,2,3,4]],[[1,2]],[[math.inf,2,3,4]],[dict(raw='unchanged')]):
                value=dict(data=rows+tail,points=[[1.,None],[2.,3.]],tail='赛车 🏁')
                for chunk in (113,65536):
                    loaded=Reader(io.StringIO(json.dumps(value,ensure_ascii=False)),t,chunk).value()
                    self.assertEqual({k:list(v) if isinstance(v,DiskTable) else v for k,v in loaded.items()},value)
                    if not tail:
                        table=loaded['data'];table._file.seek(0)
                        self.assertEqual(table._file.read(),b''.join(struct.pack('<4d',*(math.nan if x is None else x for x in row)) for row in rows))
                        self.assertLess(math.copysign(1,table[0][1]),0)
                    for item in loaded.values():
                        if isinstance(item,DiskTable):item.close()
            table=DiskTable(rows[:100],4,t,nullable=True);table._sealed=False
            self.assertEqual(table[0],rows[0]);table.extend(rows[100:]);table.seal();self.assertEqual(list(table),rows)
            with self.assertRaises(ValueError):table.extend([[1.]*4])
            table.close()
            table=DiskTable((),2,t);table._sealed=False
            def broken():yield [1.,2.];yield [3.,4.];raise RuntimeError('broken source')
            with self.assertRaises(RuntimeError):table.extend(broken())
            self.assertEqual(list(table),[[1.,2.],[3.,4.]])
            with self.assertRaises(ValueError):table.extend([[5.,6.],[7.]])
            self.assertEqual(list(table),[[1.,2.],[3.,4.],[5.,6.]]);table.close()
            class Custom(DiskTable):
                def append(self,row):self.calls=getattr(self,'calls',0)+1;return super().append(row)
            table=Custom((),2,t);table._sealed=False;table.extend([[1.,2.]]*3);self.assertEqual(table.calls,3);table.close()
            import analysis_spool
            real=analysis_spool.tempfile.TemporaryFile;opened=[]
            def create(*a,**kw):file=real(*a,**kw);opened.append(file);return file
            with patch('analysis_spool.tempfile.TemporaryFile',side_effect=create):
                with self.assertRaises(ValueError):Reader(io.StringIO('{"data":'+json.dumps(rows)[:-1]+',]}'),t).value()
                self.assertTrue(opened and all(file.closed for file in opened))

    def test_runs_use_only_visible_eligible_adjacent_samples_and_stable_source_order(self):
        from evo_lap_overview import fastest_runs
        def row(n,time=100.):return dict(usable=True,lap=dict(num=n,time=time,first_index=n*10,end_index=(n+1)*10))
        rows={str(n):row(n,100+n/1000) for n in range(2,10)}
        rows['2']['usable']=False
        result=fastest_runs(rows);self.assertEqual(result[3]['keys'],('3','4','5'));self.assertEqual(result[5]['keys'],('3','4','5','6','7'))
        self.assertEqual(result[3]['mean_s'],math.fsum(rows[str(n)]['lap']['time'] for n in (3,4,5))/3)
        rows['6']['usable']=False;result=fastest_runs(rows);self.assertNotIn(5,result);self.assertEqual(result[3]['keys'],('3','4','5'))
        # Filtering out an intermediate lap breaks the window as well.
        self.assertFalse(fastest_runs({k:v for k,v in rows.items() if k not in ('4','8')}))
        rows={str(n):row(n) for n in range(2,9)};rows['5']['lap']['first_index']+=1
        result=fastest_runs(dict(reversed(list(rows.items()))));self.assertEqual(result[3]['keys'],('2','3','4'));self.assertNotIn(5,result)
        self.assertFalse(fastest_runs({}));self.assertFalse(fastest_runs({'x':dict(usable=False,lap={})}))


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_run_menu_selects_current_filter_preserves_context_and_blocks_stale_actions(self):
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
 w=show(app,app.data_path/'Logs/evo');w.geometry('900x740');pump(.55);c=w.lap_overview;table=c['table'];menu=c['run_menu']
 with patch('evo_laps.index',side_effect=AssertionError('Selection must not load index')),patch('lap_scan_index.raw_rows',side_effect=AssertionError('Selection must not scan samples')):
  c['buttons']['run'].invoke();pump();assert menu.popup and menu.actions[0].enabled() and menu.actions[1].enabled()
  assert '5' in menu.actions[0].hint and '7' in menu.actions[0].hint
  assert menu.footer.cget('text')==menu.actions[0].hint
  menu.invoke('3');pump();assert table.selection()==('4','5','6') and '5–7' in c['status'].get()
  c['rhythm'].button.invoke();pump();c['buttons']['run'].invoke();pump();menu.invoke('5');pump()
  assert not c['rhythm'].visible and table.selection()==('4','5','6','7','8')
  c['sort']('time',True);c['kind'].set('valid');c['populate']();pump();before=table.sort_state
  c['buttons']['run'].invoke();pump();menu.invoke('3');pump();assert set(table.selection())=={'4','5','6'} and table.sort_state==before and c['kind'].get()=='valid'
  c['query'].set('2');c['populate']();pump();assert not c['state']['runs'] and not c['buttons']['run'].enabled
  selected=table.selection();menu.invoke('3');assert table.selection()==selected
  c['query'].set('');c['populate']();pump();app.set_theme('light');app.toggle_language();pump()
  assert c['buttons']['run'].cget('text')=='Consecutive laps ▾'
  c['buttons']['run'].invoke();pump();assert menu.popup and menu.actions[0].label=='选择最快连续 3 圈'
  assert menu.popup.winfo_rootx()+menu.popup.winfo_width()<=w.winfo_rootx()+w.winfo_width()+1
  menu.close(False);c['state']['loading']=True;before=table.selection();c['select_run'](3);assert table.selection()==before;c['state']['loading']=False
 with patch('evo_lap_overview.load',side_effect=OSError('Refresh failed')):c['refresh']();pump(.35)
 assert not c['state']['runs'] and not c['buttons']['run'].enabled and not menu.popup
 w.destroy();app.request_close();pump(.1);assert not errors,errors
'''
        from tests.test_processing329 import fixture
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=fixture(Path(t)/'Simulators/ac_evo',laps=9);path=folder/'inputs.csv'
            with path.open(encoding='utf-8',newline='') as stream:r=csv.DictReader(stream);fields=r.fieldnames;rows=list(r)
            for row in rows:
                if row['lap']=='4':row['lap_invalidated']='1'
            with path.open('w',encoding='utf-8',newline='') as stream:w=csv.DictWriter(stream,fieldnames=fields);w.writeheader();w.writerows(rows)
            before={p:p.read_bytes() for p in (path,folder/'session.json')}
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            r=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=30,creationflags=0x08000000)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            for p,b in before.items():self.assertEqual(p.read_bytes(),b)
