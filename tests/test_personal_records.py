"""Cross-session selection, class/layout isolation, and practice persistence."""
import base64,csv,gzip,json,os,re,shutil,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from tests import test_selected_laps as selected_tests
from laps import export_fastest
from lap_comparison import export_pair,valid_laps
from personal_records import records,detail
from lap_identity import same_layout,vehicle_class
import recording_policy
TEMPLATE=ROOT/'src/compare.html'


class FeatureTests(unittest.TestCase):
    def session(self,root,name,**metadata):
        target=Path(root)/'Logs'/name;target.parent.mkdir(parents=True,exist_ok=True)
        temp=Path(root)/('fixture-'+name);temp.mkdir()
        source=selected_tests.SelectedLapTests().session(temp);shutil.move(source,target)
        meta=json.loads((target/'session.json').read_text());meta.update(metadata)
        (target/'session.json').write_text(json.dumps(meta),encoding='utf-8')
        return target

    def test_cross_event_arbitrary_laps_and_unique_ids_preserve_originals(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            a=self.session(t,'a');b=self.session(t,'b',vehicle='Toyota GR010 Hybrid')
            imported=Path(t)/'ImportedLogs';imported.mkdir();shutil.move(b,imported/'a');b=imported/'a'
            snapshots={p:p.read_bytes() for folder in (a,b) for p in folder.iterdir() if p.is_file()}
            self.assertEqual([v['number'] for v in valid_laps(a)],[1,4])
            result=export_pair(t,[(a,1),(b,1)],TEMPLATE)
            html=Path(result['comparison']).read_text(encoding='utf-8')
            block=re.search(r'id="stintrix-laps" data-bytes="\d+">([^<]+)</script>',html).group(1)
            laps=json.loads(gzip.decompress(base64.b64decode(block)))['laps']
            self.assertEqual([v['lap']['number'] for v in laps],[1,1]);self.assertNotEqual(laps[0]['id'],laps[1]['id'])
            self.assertEqual(len(laps[0]['data']),121)
            self.assertEqual({p:p.read_bytes() for p in snapshots},snapshots)
            same=export_pair(t,[(a,1),(a,4)],TEMPLATE)
            self.assertTrue(Path(same['comparison']).exists())

    def test_pair_rejects_other_layout_invalid_pit_and_duplicate_before_writes(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            a=self.session(t,'a',track_layout='GP');b=self.session(t,'b',track_layout='Short')
            for selection in ([(a,1),(b,4)],[(a,1),(a,2)],[(a,1),(a,3)],[(a,1),(a,1)]):
                with self.assertRaises(ValueError):export_pair(t,selection,TEMPLATE)
            self.assertFalse((a/'SelectedLaps').exists());self.assertFalse((Path(t)/'LapComparisons').exists())
            with self.assertRaises(ValueError):export_pair(t,[],TEMPLATE)
            legacy_root=Path(t)/'legacy-fixture';legacy_root.mkdir()
            legacy=selected_tests.SelectedLapTests().session(legacy_root,legacy=True)
            self.assertFalse(valid_laps(legacy))
            h=lambda length:dict(session=dict(track='X'),lap=dict(track_length_m=length))
            self.assertFalse(same_layout(h(5000),h(5020)));self.assertTrue(same_layout(h(5000),h(5000.3)))

    def test_record_winners_separate_layout_class_and_skip_demo_and_invalid(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            for name,layout,group,car in [('a','GP','LMGT3','BMW M4 LMGT3'),('b','GP','LMGT3','Porsche 911 GT3 R LMGT3'),('c','GP','Hypercar','Toyota GR010 Hybrid'),('d','Short','LMGT3','BMW M4 LMGT3')]:
                folder=self.session(t,name,track_layout=layout,vehicle_class=group,vehicle=car);export_fastest(folder,TEMPLATE)
            result=records(t);self.assertEqual(len(result),3)
            self.assertEqual({(v['layout'],v['vehicle_class']) for v in result},{('GP','LMGT3'),('GP','Hypercar'),('Short','LMGT3')})
            self.assertTrue(detail(result[0])['curve'])
            meta=Path(t)/'Logs/c/session.json';v=json.loads(meta.read_text());v['status']='recording';meta.write_text(json.dumps(v))
            self.assertEqual(len(records(t)),2)
            summary=Path(t)/'Logs/a/fastest_lap_summary.json';v=json.loads(summary.read_text());v['lap']['lap_invalidated']=True;summary.write_text(json.dumps(v))
            self.assertEqual(len(records(t)),2)  # Other GT3 session still supplies its best.
            demo=Path(t)/'DemoLogs';demo.mkdir();shutil.copytree(Path(t)/'Logs/d',demo/'fake')
            self.assertEqual(len(records(t)),2)
            imported=self.session(t,'imported-demo',source='Synthetic demo',track='Demo Track');export_fastest(imported,TEMPLATE)
            self.assertEqual(len(records(t)),2)
            self.assertEqual(vehicle_class(dict(vehicle='Toyota GR010 Hybrid')),'Hypercar')
            self.assertTrue(vehicle_class(dict(vehicle='Unidentified')).startswith('Unknown'))

    def test_practice_default_opt_in_persistence_and_phase_boundaries(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            self.assertFalse(recording_policy.load(t));recording_policy.save(t,True)
            self.assertTrue(recording_policy.load(t))
            self.assertEqual([i for i in range(15) if recording_policy.should_record(i,practice_enabled=True)],list(range(9))+list(range(10,14)))
            self.assertFalse(recording_policy.should_record(True,practice_enabled=True))
            self.assertFalse(recording_policy.should_record(9,practice_enabled=True))
            recording_policy.save(t,False);self.assertFalse(recording_policy.load(t))

    def test_new_conditions_keep_tire_names_and_numeric_storage(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=self.session(t,'a',vehicle_class='LMGT3',track_layout='GP')
            csv_path=folder/'inputs.csv'
            with csv_path.open(newline='',encoding='utf-8') as stream:
                reader=csv.DictReader(stream);fields=list(reader.fieldnames);rows=list(reader)
            extra=dict(tyre_front_name='Medium',tyre_rear_name='Medium',tyre_rear_compound='1',ambient_temp_c='20',rain='.2',track_grip='4')
            with csv_path.open('w',newline='',encoding='utf-8') as stream:
                writer=csv.DictWriter(stream,fieldnames=list(dict.fromkeys([*fields,*extra])));writer.writeheader()
                writer.writerows({**row,**extra} for row in rows)
            record,_=export_fastest(folder,TEMPLATE)
            self.assertEqual(record['conditions']['tyre_front_name'],'Medium')
            self.assertEqual(record['conditions']['ambient_temp_c'],20)
            self.assertEqual(record['session']['vehicle_class'],'LMGT3')
            with (folder/'fastest_lap.csv').open(newline='',encoding='utf-8') as stream:
                self.assertEqual(next(csv.DictReader(stream))['tyre_front_name'],'Medium')

    def test_missing_report_is_indexed_in_private_cache_without_changing_source(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=self.session(t,'a');before={p:p.read_bytes() for p in folder.iterdir() if p.is_file()}
            first=records(t);self.assertEqual(len(first),1)
            self.assertTrue(Path(first[0]['file']).is_relative_to(Path(t)/'PersonalRecords'))
            self.assertTrue(detail(first[0])['curve']);self.assertEqual(records(t),first)
            self.assertEqual({p:p.read_bytes() for p in before},before)
            self.assertEqual(set(folder.iterdir()),set(before))

    @unittest.skipUnless(os.name=='nt','Windows Tk')
    def test_new_pages_selector_and_bottom_actions_with_no_callback_errors(self):
        import tkinter as tk
        import control_center,control_records,i18n
        from control_widgets import Pill
        from control_fields import Select
        errors=[]
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t,patch('control_center.ROOT',Path(t)):
            a=self.session(t,'a');b=self.session(t,'b');export_fastest(a,TEMPLATE);export_fastest(b,TEMPLATE)
            center=control_center.ControlCenter();center.root.report_callback_exception=lambda *args:errors.append(str(args))
            def pump(condition):
                deadline=time.monotonic()+6
                while time.monotonic()<deadline:
                    center.root.update();time.sleep(.01)
                    if condition():return
                self.fail('UI did not finish')
            def descendants(w):
                for child in w.winfo_children():yield child;yield from descendants(child)
            try:
                center.show_page(1);center.root.update_idletasks()
                body=center.content.winfo_children()[0].body
                actions=[w.label for w in body.winfo_children()[-1].winfo_children() if isinstance(w,Pill)]
                self.assertEqual(actions,['全选当前列表','清除选择'])
                center.show_page(6);pump(lambda:'条个人赛道纪录' in center.status.get())
                pump(lambda:bool([w for w in descendants(center.content) if isinstance(w,tk.Canvas) and w.find_all()]))
                center.set_theme('light');center.toggle_language();center.root.update()
                self.assertEqual(center.title.cget('text'),'Personal track records')
                center.show_page(1);center.selected_laps();window=center.lap_pair_window
                boxes=[w for w in descendants(window) if isinstance(w,Select)]
                pump(lambda:len(boxes)==4 and all(w.cget('state')=='readonly' for w in boxes))
                self.assertEqual(len(boxes[1].cget('values')),2)
                window.destroy();self.assertFalse(errors,errors)
            finally:center.close();i18n.set_language('zh')

    def test_practice_engine_starts_stops_saves_and_resumes_without_restart(self):
        from engine import Engine
        from telemetry import extract
        from tests.test_core import fixture
        base=extract(fixture());phase=[0];clock=[0.0]
        class Feed:
            def read(self):
                clock[0]+=.01
                return dict(base,session=phase[0],et=clock[0],finish=0)
            def close(self):pass
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t,patch('engine.ROOT',Path(t)),patch('recorder.make_report'):
            recording_policy.save(t,True)
            engine=Engine(output=Path(t)/'Logs',reader_factory=Feed,settings={'fixed_hz':200})
            def wait(condition):
                deadline=time.monotonic()+3
                while not condition():
                    if time.monotonic()>deadline:self.fail('Recording transition failed')
                    time.sleep(.01)
            try:
                wait(lambda:engine.recorder.samples>=3)
                first=engine.recorder.folder;engine.practice_enabled=False
                wait(lambda:engine.recorder.file is None)
                engine.practice_enabled=True
                wait(lambda:engine.recorder.file is not None and engine.recorder.folder!=first)
                phase[0]=5
                wait(lambda:engine.recorder.meta.get('session')==5 and engine.recorder.samples>=1)
            finally:
                engine.stop.set();engine.wake.set();engine.thread.join(4)
                for thread in engine.recorder.pending_reports:thread.join(4)
            meta=json.loads((first/'session.json').read_text())
            self.assertEqual(meta['status'],'complete');self.assertEqual(meta['end_reason'],'practice recording disabled')
            self.assertGreaterEqual(meta['written_samples'],3)


if __name__=='__main__':unittest.main()
