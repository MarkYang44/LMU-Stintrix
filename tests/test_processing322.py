"""Exact bounded matrix output and report navigation without repeated selection."""
import json,math,os,shutil,subprocess,sys,tempfile,tracemalloc,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


class Data(unittest.TestCase):
    def test_batched_tables_match_standard_json_bytes_at_row_and_cell_limits(self):
        from reporting import json_chunks
        from analysis_spool import DiskTable
        from buffers import NumericTable,NullableTable
        scalars=[-0.0,1.2345678901234567,1e-250,1e250,None,0.0,9007199254740992.0]
        cases=[(0,7),(1,7),(63,7),(64,7),(65,7),(129,7),(65,128),(65,129),(34,255),(34,256),(3,257)]
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            for rows,width in cases:
                values=[[scalars[(i+j)%len(scalars)] for j in range(width)] for i in range(rows)]
                for kind in ('disk','numeric','nullable'):
                    source=[[0.0 if v is None else v for v in row] for row in values] if kind=='numeric' else values
                    table=DiskTable(source,width,t,nullable=True) if kind=='disk' else NumericTable(source,width) if kind=='numeric' else NullableTable(source,width)
                    try:
                        expected=json.dumps(dict(text='赛车 🏁 <&>\n',data=[list(row) for row in table],tail=True),ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
                        self.assertEqual(b''.join(json_chunks(dict(text='赛车 🏁 <&>\n',data=table,tail=True))),expected,(rows,width,kind))
                    finally:
                        if kind=='disk':table.close()

    def test_writer_keeps_a_small_batch_and_does_not_retain_the_matrix(self):
        from unittest.mock import patch
        import reporting
        from analysis_spool import DiskTable
        from reporting import json_chunks
        class Counted(DiskTable):
            read_rows=0
            def __iter__(self):
                for row in super().__iter__():self.read_rows+=1;yield row
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            table=Counted(([i*.12345678901234567]*32 for i in range(4096)),32,t)
            try:
                iterator=json_chunks(table);self.assertEqual(next(iterator),b'[');self.assertEqual(table.read_rows,0)
                chunk=next(iterator);self.assertLessEqual(table.read_rows,64);self.assertTrue(chunk.startswith(b'['))
                iterator.close();tracemalloc.start()
                try:
                    size=sum(map(len,json_chunks(table)));peak=tracemalloc.get_traced_memory()[1]
                finally:tracemalloc.stop()
                self.assertGreater(size,2_000_000);self.assertLess(peak,2_000_000)
            finally:table.close()
            table=DiskTable(([float(i)]*255 for i in range(70)),255,t)
            encoder=reporting._encoder
            class Bounded:
                def encode(self,rows):
                    self_test.assertLessEqual(len(rows),64);self_test.assertLessEqual(sum(map(len,rows)),8192)
                    return encoder.encode(rows)
            self_test=self
            try:
                with patch.object(reporting,'_encoder',Bounded()):self.assertGreater(sum(map(len,json_chunks(table))),0)
            finally:table.close()

    def test_nonfinite_values_keep_atomic_json_and_page_outputs(self):
        from analysis_spool import DiskTable
        from laps import write_json
        from reporting import json_chunks,write_page
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=Path(t);target=folder/'report.json';page=folder/'report.html';target.write_bytes(b'original-json');page.write_bytes(b'original-page')
            for invalid in (math.nan,math.inf,-math.inf):
                table=DiskTable(([i*.1,invalid if i==65 else -0.0] for i in range(66)),2,t)
                try:
                    with self.assertRaises(ValueError):write_json(target,dict(data=table))
                    with self.assertRaises(ValueError):write_page(page,'head/*STINTRIX_BLOCKS*/tail',[('data',json_chunks(table))])
                finally:table.close()
                self.assertEqual(target.read_bytes(),b'original-json');self.assertEqual(page.read_bytes(),b'original-page')
                self.assertFalse(list(folder.glob('*.pending')))


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    def test_evo_selected_reports_reuse_window_retry_only_missing_and_restore_filters(self):
        script=r'''
import sys,time,json,traceback
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'src'))
from unittest.mock import patch
from control_center import ControlCenter
from control_maintenance import reports
from session_reports import make_report
errors=[];calls=[]
with patch.object(ControlCenter,'repair_windows_entry'):
 app=ControlCenter();app.root.geometry('1200x850');app.root.report_callback_exception=lambda *a:errors.append(''.join(traceback.format_exception(*a)))
 def pump(seconds=.4):
  end=time.monotonic()+seconds
  while time.monotonic()<end:app.root.update();time.sleep(.005)
 app.show_page(1);pump(1);root=app.data_path;a=root/'Logs/evo';b=root/'Logs/ready'
 w=reports(app);pump(.5);v=w.worklist;assert len(v.items)==2
 v.table.selection_set((str(a),));pump(.04);v.query.set('no matching report');v.search.flush();assert not v.table.rows
 app.tree.selection_set(next(k for k in app.tree.get_children() if app.items[int(k)]['folder']==str(b)));app.update_selection_count()
 app.review_menu.invoke('reports');pump(.2)
 assert app.report_tasks_window is w and v.query.get()=='no matching report' and v.view.get()=='pending'
 assert v.table.selection()==(str(b),) and not v.buttons['retry'].enabled
 assert w.report_focus.strip.winfo_manager();assert str(root/'Logs/foreign') not in v.items
 app.set_theme('light');app.toggle_language();pump(.2);assert v.query.get()=='no matching report' and v.table.selection()==(str(b),)
 w.report_focus.restore();assert not v.table.rows and v.remembered==(str(a),)
 v.search.clear();pump(.1);assert v.table.selection()==(str(a),)
 v.query.set('still hidden');v.search.flush();reports(app,[a,Path(root).parent/'foreign']);pump(.1)
 assert w.report_focus.targets==(str(a),) and v.table.selection()==(str(a),) and v.buttons['retry'].enabled
 def unused():raise AssertionError('A successful report step ran again')
 with patch('evo_reports.operations',return_value=dict(fastest=unused,review=unused,images=lambda:calls.append('images'),compression=unused)),patch('report_worker.run',side_effect=lambda folder,root:make_report(folder,isolated=False)):
  v.buttons['retry'].invoke();pump(1.2)
 assert calls==['images'];assert v.table.selection()==(str(a),) and v.items[str(a)]['receipt']['state']=='ready' and not v.buttons['retry'].enabled
 app.report_retry_job.window.destroy();w.report_focus.restore();assert not v.table.rows
 reports(app,[a]);pump(.1);v.query.set('Nurburgring');v.search.flush();assert not w.report_focus.targets and not w.report_focus.strip.winfo_manager()
 app.tree.selection_set(next(k for k in app.tree.get_children() if app.items[int(k)]['folder']==str(a)))
 app.review_menu.invoke('library');pump(.5);library=app.library().library;library.operations.menu.invoke('reports');pump(.1)
 assert app.report_tasks_window is w and v.table.selection()==(str(a),)
 library.window.destroy();w.destroy();app.show_page(3);pump(.6);browser=app.data_browser
 browser.table.selection_set(next(k for k in browser.table.get_children() if app.items[int(k)]['folder']==str(b)))
 browser.menu.invoke('reports');pump(.6);w=app.report_tasks_window
 assert w.worklist.table.selection()==(str(b),);w.destroy();assert not errors,errors;app.request_close();pump(.2)
print('Selected EVO reports: current game, preserved filters, focused retry, library and storage routing OK')
'''
        from tests.test_processing316 import fixture
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t)/'Simulators/ac_evo';a=fixture(root);b=root/'Logs/ready';shutil.copytree(a,b)
            status=json.loads((b/'report_status.json').read_text('utf-8'));status['state']='ready'
            for step in status['steps'].values():step['state']='ready'
            (b/'report_status.json').write_text(json.dumps(status),'utf-8')
            foreign=root/'Logs/foreign';shutil.copytree(a,foreign);(foreign/'session.json').write_text('{"simulator_id":"lmu","status":"complete"}','utf-8')
            before={p:p.read_bytes() for folder in (a,b,foreign) for p in folder.iterdir() if p.name in ('session.json','inputs.csv')}
            env=dict(os.environ,LMU_STINTRIX_DATA_DIR=t,STINTRIX_SIMULATOR='ac_evo',LMU_STINTRIX_HOTKEYS='0',PYTHONIOENCODING='utf-8')
            result=subprocess.run([sys.executable,'-c',script],cwd=ROOT,env=env,capture_output=True,text=True,encoding='utf-8',timeout=35)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            for path,value in before.items():self.assertEqual(path.read_bytes(),value)


if __name__=='__main__':unittest.main()
