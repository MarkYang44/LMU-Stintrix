"""One text pass must preserve every CSV field and exact seven-channel float64 row."""
import csv,io,json,math,os,struct,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT/'src'),str(ROOT)]
from tests.test_processing329 import fixture
FIELDS=('lap_distance_m','evo_lap_time_ms','throttle','brake','filtered_throttle','filtered_brake','speed_kmh')


def reference(folder,best,value):
    from telemetry_file import Path as ReadPath
    from lap_scan_index import raw_rows
    from csv_projection import projector
    with ReadPath(folder/'inputs.csv').open(encoding='utf-8-sig',newline='') as stream:columns=next(csv.reader(stream))
    out=io.StringIO(newline='');writer=csv.writer(out);writer.writerow(columns);take=projector(columns,FIELDS);binary=bytearray()
    rows=raw_rows(folder/'inputs.csv',best['first_index'],best['end_index'],value.get('cookies',()),columns=columns)
    try:
        for row in rows:
            writer.writerow(row);numbers=list(map(float,take(row)));assert all(map(math.isfinite,numbers));numbers[1]/=1000;binary.extend(struct.pack('<7d',*numbers))
    finally:rows.close()
    return out.getvalue(),bytes(binary)


class Data(unittest.TestCase):
    def test_paired_curve_and_csv_equal_reference_for_plain_complex_duplicate_and_packed(self):
        from evo_laps import index,read_curve
        from column_store import convert
        from telemetry_file import Path as ReadPath
        for kind in ('plain','complex','duplicate','packed'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
                root=Path(t)/'Simulators/ac_evo';folder=fixture(root);source=folder/'inputs.csv'
                with source.open(encoding='utf-8',newline='') as stream:rows=list(csv.reader(stream))
                if kind in ('complex','packed'):
                    rows[0].append('note')
                    for n,row in enumerate(rows[1:]):row.append('中文,"多行"\r\n'+str(n) if n%3==0 else 'raw value')
                    if kind=='complex':rows[132]=rows[132][:-1];rows[133].append('discarded extra')
                if kind=='duplicate':
                    rows[0].append('throttle')
                    for row in rows[1:]:row.append('.9182736455463728')
                rows[104][rows[0].index('throttle')]='-0.0'
                with source.open('w',encoding='utf-8-sig',newline='') as stream:
                    w=csv.writer(stream);w.writerows(rows[:135])
                    if kind!='packed':w.writerow([])
                    w.writerows(rows[135:])
                original=source.read_bytes();metadata=(folder/'session.json').read_bytes()
                if kind=='packed':self.assertTrue(convert(source,replace=True)['converted'])
                value=index(folder);best=next(l for l in value['laps'] if l['num']==2);expected,binary=reference(folder,best,value)
                output=io.StringIO(newline='');data=read_curve(folder,best,value,folder,csv_file=output)
                try:
                    data._file.seek(0);self.assertEqual(data._file.read(),binary)
                    self.assertEqual(len(data),best['samples']);self.assertEqual(output.getvalue(),expected)
                finally:data.close()
                self.assertEqual(ReadPath(source).read_bytes(),original);self.assertEqual((folder/'session.json').read_bytes(),metadata)

    def test_paired_short_invalid_and_midread_changes_close_scratch_and_reader(self):
        import analysis_spool,evo_exports
        from evo_laps import index,read_curve
        from itertools import islice
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=fixture(Path(t)/'Simulators/ac_evo');value=index(folder);best=next(l for l in value['laps'] if l['num']==2);source=folder/'inputs.csv';original=source.read_bytes()
            created=[];readers=[];base=analysis_spool.DiskTable;real=evo_exports._csv_lines
            class Observed(base):
                def __init__(self,*a,**kw):created.append(self);super().__init__(*a,**kw)
            def short(*a,**kw):
                reader=real(*a,**kw);readers.append(reader)
                try:yield from islice(reader,5)
                finally:reader.close()
            def invalid(*a,**kw):
                reader=real(*a,**kw);readers.append(reader)
                try:
                    for i,(encoded,row) in enumerate(reader):
                        if i==3:row=(*row[:2],'NaN',*row[3:])
                        yield encoded,row
                finally:reader.close()
            def changed(*a,**kw):
                reader=real(*a,**kw);readers.append(reader)
                try:
                    for i,row in enumerate(reader):
                        if i==3:s=source.stat();os.utime(source,ns=(s.st_atime_ns,s.st_mtime_ns+1000000))
                        yield row
                finally:reader.close()
            for operation,error in ((short,OSError),(invalid,ValueError),(changed,OSError)):
                with patch('analysis_spool.DiskTable',Observed),patch('evo_exports._csv_lines',side_effect=operation),self.assertRaises(error):read_curve(folder,best,value,folder,csv_file=io.StringIO(newline=''))
                self.assertIsNone(created[-1]._file);self.assertIsNone(readers[-1].gi_frame)
            self.assertEqual(source.read_bytes(),original)


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_return_double_click_exact_laps_invalid_loading_and_capture_guards(self):
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
 pump(.3);folder=app.data_path/'Logs/evo';window=show(app,folder);window.geometry('900x720');pump(.5);c=window.lap_overview;t=c['table']
 def enter(keys):
  t.selection_set(keys);t.viewport.focus_force();pump(.04);t.viewport.event_generate('<Return>');pump(.45)
 with patch('os.startfile') as opened:
  enter(('1',));assert opened.call_count==1 and Path(opened.call_args.args[0]).name=='EVO_Lap_2.html'
  with patch('control_lap_pair.show') as pair:
   enter(('1','2'));assert [n for f,n in pair.call_args.kwargs['selected']]==[2,3]
  enter(('1','2','3'));assert opened.call_count==2 and Path(opened.call_args.args[0]).name.startswith('EVO_Multi_')
  t.selection_set(('1','2'));t.scroller.move(0);pump(.05)
  c['double'](SimpleNamespace(y=t.rowheight+2));pump(.4)
  assert t.selection()==('1',) and opened.call_count==3
  c['double'](SimpleNamespace(y=2));pump(.1);assert t.selection()==('0',) and opened.call_count==3
  with patch.object(app,'active',return_value=True):enter(('1',))
  assert opened.call_count==3 and app.hud is None
  c['state']['loading']=True;c['activate']();c['double'](SimpleNamespace(y=t.rowheight+2));c['state']['loading']=False
  assert opened.call_count==3 and app.lap_curve_jobs==0
 app.set_theme('light');app.toggle_language();pump(.25)
 assert 'Enter' in str(next(w for w in t.master.winfo_children() if hasattr(w,'cget') and w.winfo_class()=='Label' and 'Enter' in str(w.cget('text'))).cget('text'))
 assert not errors,errors
 window.destroy();app.request_close();pump(.1)
"""
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=fixture(Path(t)/'Simulators/ac_evo');before={p:p.read_bytes() for p in (folder/'inputs.csv',folder/'session.json')}
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=25,creationflags=0x08000000)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for p,b in before.items():self.assertEqual(p.read_bytes(),b)
