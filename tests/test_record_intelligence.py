"""Analytical validity, read-only history, privacy, and native feature integration."""
import json,shutil,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from record_history import history
from training_report import aggregate,conditions,report
from achievement_card import payload,render
from tests import test_personal_records as record_tests
TEMPLATE=record_tests.TEMPLATE
from laps import export_fastest
from personal_records import records


def entry(duration=100,date='2026-10-01T10:00:00Z',layout='GP',group='LMGT3'):
    return dict(identity=('track',layout,5000,group),session=dict(started_utc=date,driver='Private Driver',vehicle='BMW M4 LMGT3',track='Track',track_layout=layout),
        track='Track',layout=layout,vehicle_class=group,lap=dict(number=1,track_length_m=5000),length_m=5000,time_s=duration,file='private',folder='private')


class IntelligenceTests(unittest.TestCase):
    def test_history_only_real_improvements_separates_layout_class_and_dates(self):
        values=[entry(100),entry(101,'2026-10-02T10:00:00Z'),entry(99,'2026-10-03T10:00:00Z'),entry(99,'2026-10-04T10:00:00Z'),entry(98,'2026-10-05T10:00:00Z'),entry(90,layout='Short'),entry(80,group='Hypercar'),entry(75,date='bad')]
        with patch('record_history.entries',return_value=values):result=history('unused')
        gp=[v for v in result['entries'] if v['layout']=='GP' and v['vehicle_class']=='LMGT3']
        self.assertEqual([v['time_s'] for v in gp],[100,99,98]);self.assertEqual([v['improvement_s'] for v in gp],[None,1,1])
        self.assertEqual(result['missing_dates'],1);self.assertEqual(len(result['entries']),5)

    def test_history_import_copy_dedup_conflict_and_same_timestamp(self):
        a=entry();b=dict(a,folder='copy');c=entry(98,'2026-10-02T10:00:00Z');d=dict(c,time_s=97)
        with patch('record_history.entries',return_value=[a,b,c,d]):result=history('unused')
        self.assertEqual(len(result['entries']),1);self.assertEqual(result['conflicts'],1)
        e=entry(95);e['session']=dict(e['session'],vehicle='Porsche 911 GT3 R LMGT3')
        with patch('record_history.entries',return_value=[a,e]):result=history('unused')
        self.assertEqual(len(result['entries']),1);self.assertEqual(result['entries'][0]['time_s'],95)

    def test_extended_conditions_do_not_hide_unknown_or_allow_different_rear_tires(self):
        self.assertIn('fuel_l',conditions({}, {})['unknown'])
        self.assertFalse(conditions({'tyre_rear_compound':1},{'tyre_rear_compound':2})['allowed'])
        self.assertFalse(conditions({'tyre_front_name':'Medium'},{'tyre_front_name':'Wet'})['allowed'])
        self.assertFalse(conditions({'rain':0},{'rain':.2})['allowed'])

    def test_priority_ranks_repeat_loss_and_preserves_negative_segment_delta(self):
        def lap(delta=0):
            rows=[]
            for i in range(101):
                d=i*10;t=i/10+delta*min(1,d/500)
                rows.append([d,t,1,1 if 100<=d<=150 or 650<=d<=700 else 0,1,0,100])
            return dict(data=rows,length_m=1000,time_s=rows[-1][1])
        ref=lap();values=[ref,lap(.5),lap(.6),lap(.7)]
        result=aggregate(values,ref)
        self.assertGreater(result[0]['median_loss_s'],.4);self.assertEqual(result[0]['count'],3)
        self.assertGreater(result[0]['score'],result[1]['score']);self.assertEqual(sum(v['target']['time_s'] for v in result),10)
        self.assertEqual(aggregate([ref],ref),[])

    def test_report_uses_verified_laps_preserves_originals_skips_demo_and_import_duplicates(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            for i in range(3):
                folder=record_tests.FeatureTests().session(temp,str(i),started_utc=f'2026-10-0{i+1}T10:00:00Z',track_layout='GP',vehicle='BMW M4 LMGT3')
                export_fastest(folder,TEMPLATE)
            source=Path(temp)/'Logs/0';imported=Path(temp)/'ImportedLogs/copy';shutil.copytree(source,imported)
            demo=record_tests.FeatureTests().session(temp,'demo',source='Synthetic demo',track_layout='GP',vehicle='BMW M4 LMGT3')
            snapshots={p:p.read_bytes() for category in ('Logs','ImportedLogs') for p in (Path(temp)/category).rglob('*') if p.is_file()}
            selected=records(temp)[0];value=report(temp,selected,dict(include_unknown=True))
            self.assertEqual(value['count'],6);self.assertGreater(value['excluded'],0);self.assertTrue(value['unknown'])
            self.assertEqual({p:p.read_bytes() for p in snapshots},snapshots)
            self.assertTrue((Path(temp)/'PersonalRecords/TrainingCache').is_dir())
            from training_presentation import content
            value['entry']['track']='<script>alert(1)</script>'
            self.assertNotIn('<script>',content(value));self.assertIn('&lt;script&gt;',content(value))

    def test_insufficient_data_explains_no_generated_claim(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            folder=record_tests.FeatureTests().session(temp,'one');export_fastest(folder,TEMPLATE)
            with self.assertRaisesRegex(ValueError,'4'):report(temp,records(temp)[0])

    def test_card_privacy_and_unique_png_exports(self):
        e=entry();details=dict(conditions=dict(fuel_l=34,tyre_front_name='Medium',wetness=0,track_temp_c=25))
        hidden=payload(e,details);visible=payload(e,details,True,True)
        self.assertNotIn('Private Driver',json.dumps(hidden));self.assertNotIn('2026-10-01',json.dumps(hidden));self.assertNotIn('private',json.dumps(hidden))
        self.assertEqual(visible['driver'],'Private Driver');self.assertIn('2026-10-01',visible['date'])
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            from PIL import Image
            a=render(temp,hidden);b=render(temp,hidden);self.assertNotEqual(a,b)
            with Image.open(a) as image:self.assertEqual(image.size,(1920,1080));self.assertEqual(image.format,'PNG');self.assertNotIn('exif',image.info)

    def test_native_report_exports_visible_and_card_privacy_defaults(self):
        import time,tkinter as tk
        import control_center,control_training,control_achievement,i18n
        from control_list import SessionList
        from control_widgets import Pill,Switch
        fake=entry();reference=dict(number=1,time_s=100)
        training=dict(reference=reference,count=4,unknown=[],priorities=[dict(name='制动区 1',start=0,end=500,median_loss_s=.4,std_s=.1,count=3,differences=dict(brake_m=3,minimum_kmh=-2,full_m=5))])
        def walk(widget):
            for child in widget.winfo_children():yield child;yield from walk(child)
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp,patch('control_center.ROOT',Path(temp)),patch('control_center.ControlCenter.repair_windows_entry'),patch('training_report.report',return_value=training):
            center=control_center.ControlCenter();errors=[];center.root.report_callback_exception=lambda *args:errors.append(str(args))
            try:
                control_training.show(center,fake)
                window=next(w for w in center.root.winfo_children() if w.winfo_class()=='Toplevel')
                deadline=time.monotonic()+5
                while time.monotonic()<deadline:
                    center.root.update();time.sleep(.01)
                    tables=[w for w in walk(window) if isinstance(w,SessionList)]
                    if tables and tables[0].rows:break
                self.assertTrue(tables[0].rows)
                export=next(w for w in walk(window) if isinstance(w,Pill) and w.label=='导出完整训练报告')
                self.assertLessEqual(export.winfo_rooty()+export.winfo_height(),window.winfo_rooty()+window.winfo_height())
                window.destroy();control_achievement.show(center,fake);center.root.update()
                window=next(w for w in center.root.winfo_children() if w.winfo_class()=='Toplevel')
                checks=[w for w in walk(window) if isinstance(w,Switch)]
                self.assertEqual(len(checks),2)
                self.assertTrue(all(not w.variable.get() for w in checks))
                button=next(w for w in walk(window) if isinstance(w,Pill) and w.label=='生成并打开图片')
                self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),window.winfo_rooty()+window.winfo_height())
                window.destroy();self.assertFalse(errors,errors)
            finally:center.close();i18n.set_language('zh')

    def test_vehicle_history_includes_improvements_hidden_by_other_car_class_pb(self):
        a=entry(90);b=entry(100,'2026-10-02T10:00:00Z');b['session']=dict(b['session'],vehicle='Porsche 911 GT3 R LMGT3')
        c=dict(b,time_s=99,session=dict(b['session'],started_utc='2026-10-03T10:00:00Z'))
        with patch('record_history.entries',return_value=[a,b,c]):
            self.assertEqual(len(history('unused')['entries']),1)
            values=history('unused',per_vehicle=True)['entries'];self.assertEqual(len(values),3);self.assertEqual(values[-1]['improvement_s'],1)

    def test_history_filter_sort_and_chart_keep_layout_class_car_isolated(self):
        from history_view import filtered,series
        values=[]
        for e in (entry(100),entry(99,'2026-10-02T10:00:00Z'),entry(90,layout='Short'),entry(80,group='Hypercar')):
            values.append(dict(e,observed_utc=e['session']['started_utc']))
        other=entry(95);other['session']=dict(other['session'],vehicle='Porsche');values.append(dict(other,observed_utc=other['session']['started_utc']))
        self.assertEqual(filtered(values)[0][1]['time_s'],99)
        self.assertEqual(len(filtered(values,car='Porsche')),1)
        self.assertEqual(len(filtered(values,layout_key=values[0]['identity'])),3)
        self.assertEqual([e['time_s'] for e in series(values,values[0])],[100,99])
        self.assertEqual(filtered(values,query='not-found'),[])
        self.assertEqual(filtered(values,sort=1)[-1][1]['time_s'],99)


if __name__=='__main__':unittest.main()
