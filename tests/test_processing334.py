"""Bounded scratch construction and an evidence-only EVO lap rhythm view."""
import csv,math,os,struct,subprocess,sys,tempfile,unittest,weakref
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]


class Data(unittest.TestCase):
    def test_block_construction_keeps_bytes_nulls_bounds_reads_and_append_contract(self):
        import analysis_spool
        from analysis_spool import DiskTable
        rows=[[1.1234567890123457,-0.,None,1e-300,math.inf,math.nan,True],[None,2.,3.,4.,5.,6.,7.],[1.,2.,3.,4.,5.,6.,7.]]*5000
        expected=b''.join(struct.pack('<7d',*(math.nan if x is None else x for x in row)) for row in rows)
        real=analysis_spool.tempfile.TemporaryFile;files=[]
        class Spy:
            def __init__(self,*a,**kw):self.file=real(*a,**kw);self.sizes=[];files.append(self)
            def __getattr__(self,name):return getattr(self.file,name)
            def write(self,block):self.sizes.append(len(block));return self.file.write(block)
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t,patch('analysis_spool.tempfile.TemporaryFile',Spy):
            table=DiskTable(rows,7,t,nullable=True);table._file.seek(0);self.assertEqual(table._file.read(),expected)
            self.assertEqual(len(table),len(rows));self.assertLess(math.copysign(1,table[0][1]),0);self.assertIsNone(table[0][2])
            self.assertLess(len(files[0].sizes),20);self.assertLessEqual(max(files[0].sizes),65536+56)
            self.assertEqual(table[-1],[1.,2.,3.,4.,5.,6.,7.]);self.assertEqual(list(table[-3:])[-1],table[-1])
            table._sealed=False;table.append([7.]*7);table.seal();self.assertEqual(table[-1],[7.]*7)
            with self.assertRaises(ValueError):table.append([1.]*7)
            ref=weakref.ref(table);file=files[0];del table;self.assertIsNone(ref());self.assertTrue(file.closed)

    def test_constructor_failures_close_and_append_overrides_remain_active(self):
        import analysis_spool
        from analysis_spool import DiskTable
        real=analysis_spool.tempfile.TemporaryFile;files=[]
        def create(*a,**kw):value=real(*a,**kw);files.append(value);return value
        def failing():
            for _ in range(2000):yield [1.]*7
            raise RuntimeError('fixture stream failed')
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t,patch('analysis_spool.tempfile.TemporaryFile',side_effect=create):
            for rows,error in (([[1.]*7,[1.]],ValueError),([[1.]*7,['bad',None,1,2,3,4,5]],(TypeError,struct.error)),(failing(),RuntimeError)):
                with self.assertRaises(error):DiskTable(rows,7,t)
                self.assertTrue(files[-1].closed)
            class Customized(DiskTable):
                def __init__(self,*a,**kw):self.calls=0;super().__init__(*a,**kw)
                def append(self,row):self.calls+=1;return super().append(row)
            value=Customized([[1.]*7]*5,7,t);self.assertEqual(value.calls,5);self.assertEqual(len(value),5);value.close()
            value=DiskTable([[1.]*8192]*2,8192,t);self.assertEqual(len(value),2);self.assertEqual(value.record.size,65536);value.close()


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_lazy_rhythm_filters_gaps_click_context_theme_and_failure_cleanup(self):
        script=r"""
import sys,time,traceback
from pathlib import Path
from types import SimpleNamespace
sys.path[:0]=[str(Path.cwd()/'src'),str(Path.cwd())]
from unittest.mock import patch
from control_center import ControlCenter
from control_evo_lap_overview import show
errors=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(s=.25):
  end=time.monotonic()+s
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 pump(.3);w=show(app,app.data_path/'Logs/evo');w.geometry('900x720');pump(.5);c=w.lap_overview;rhythm=c['rhythm'];table=c['table']
 assert rhythm.chart is None and not rhythm.visible and table.winfo_manager()=='pack'
 with patch('evo_laps.index',side_effect=AssertionError('Graph must not read lap index')),patch('lap_scan_index.raw_rows',side_effect=AssertionError('Graph must not scan telemetry')):
  rhythm.button.invoke();pump(.15);chart=rhythm.chart
  assert rhythm.visible and not table.winfo_manager() and chart.axis=='lap'
  assert [e['number'] for e in chart.entries]==[2,3,5,6,7,8]
  assert len(chart.find_withtag('series'))==2
  assert all('observed_utc' not in e for e in chart.entries)
  chart.inspect(SimpleNamespace(x=chart.points[2][0]));assert '5' in chart.itemcget(chart.tooltip,'text') and 'UTC' not in chart.itemcget(chart.tooltip,'text')
  c['query'].set('2');c['populate']();pump(.1);assert len(chart.entries)==1
  point=chart.points[0];chart.select(SimpleNamespace(x=point[0]));pump(.15)
  assert not rhythm.visible and table.winfo_manager()=='pack' and table.selection()==('1',) and c['query'].get()=='2'
  rhythm.button.invoke();pump(.1);assert rhythm.chart is chart and len(chart.entries)==1
  c['query'].set('');c['kind'].set('other');c['populate']();pump(.1);assert not chart.entries and not chart.points
  app.set_theme('light');app.toggle_language();pump(.2);assert rhythm.button.cget('text')=='Back to lap table'
  assert rhythm.button.winfo_rootx()+rhythm.button.winfo_width()<=w.winfo_rootx()+w.winfo_width()+1
  c['kind'].set('valid');c['populate']();pump(.1);assert len(chart.entries)==6
 with patch('evo_lap_overview.load',side_effect=OSError('Refresh failed')):c['refresh']();pump(.3)
 assert c['state']['result'] is None and not chart.entries and 'Refresh failed' in c['status'].get()
 rhythm.button.invoke();pump(.1);assert not rhythm.visible and not errors,errors
 w.destroy();app.request_close();pump(.1)
"""
        from tests.test_processing329 import fixture
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=fixture(Path(t)/'Simulators/ac_evo',laps=8);path=folder/'inputs.csv'
            with path.open(encoding='utf-8',newline='') as stream:r=csv.DictReader(stream);fields=r.fieldnames;rows=list(r)
            for row in rows:
                if row['lap']=='4':row['lap_invalidated']='1'
            with path.open('w',encoding='utf-8',newline='') as stream:writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
            before={p:p.read_bytes() for p in (path,folder/'session.json')}
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=25,creationflags=0x08000000)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for p,b in before.items():self.assertEqual(p.read_bytes(),b)
