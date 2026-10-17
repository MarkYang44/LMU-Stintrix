"""Real native-lap schema bridge, layout isolation and time-axis honesty."""
import copy,json,os
from pathlib import Path
import sys,tempfile,threading,time,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from video_history import reference_curve,compare_history,export_comparison,history_laps,circuit_key
from video_media import Cancelled


def fixture(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    ident=dict(track='Test Track',track_layout='Grand Prix',length_m=1000)
    native=dict(format='inputscope.fastest-lap',session=dict(track='Test Track',track_layout='Grand Prix',vehicle='Test car',started_utc='2026-10-16T12:00:00Z'),
        lap=dict(number=2,validity='verified',time_s=10,track_length_m=1000,in_pits=False,lap_invalidated=False),
        data_columns=['distance_m','lap_time_s','throttle','brake','filtered_throttle','filtered_brake','speed_kmh'],
        data=[[i, i/100,.7,.2,.6,.1,180] for i in range(1001)])
    path=folder/'native.lap.json';path.write_text(json.dumps(native),encoding='utf8')
    video=dict(format='stintrix.video-curves',version=1,id='test-video',identity=ident,mode='time',start_s=2,end_s=11,video_file='fixture.mp4',landmarks=[],
        quality=dict(distance_usable=False,pedal_readable_ratio=1,missing_samples=0),
        rows=[dict(lap_time_s=i*.05,video_pts_s=2+i*.05,distance_m=None,throttle=.5,brake=.3,status='estimated') for i in range(181)])
    video_path=folder/'curve.json';video_path.write_text(json.dumps(video),encoding='utf8')
    return video,path,video_path


class VideoHistoryTests(unittest.TestCase):
    def test_channels_and_native_rows_are_preserved(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            _,p,_=fixture(t)
            self.assertEqual(reference_curve(p,'raw')['rows'][10]['throttle'],.7)
            ref=reference_curve(p,'filtered');self.assertEqual(ref['rows'][10]['throttle'],.6)
            self.assertTrue(ref['quality']['distance_usable']);self.assertLessEqual(len(ref['rows']),602)
            with self.assertRaises(ValueError):reference_curve(p,'steering')

    def test_plain_video_compares_without_fabricated_distance(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            video,p,_=fixture(t);result=compare_history(video,reference_curve(p))
            self.assertEqual(result['delta'],[]);self.assertEqual(result['segments'],[])
            self.assertEqual(result['reference_duration_s']-result['video_duration_s'],1)
            self.assertFalse(result['layout_bound'])

    def test_layout_binding_requires_confirmation_and_does_not_edit_source(self):
        self.assertEqual(circuit_key('Fuji Speedway'),circuit_key('富士赛车场'))
        self.assertNotEqual(circuit_key('未知甲赛道'),circuit_key('未知乙赛道'))
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            video,p,_=fixture(t);video['identity']['track_layout']='Short';ref=reference_curve(p);before=copy.deepcopy(video)
            with self.assertRaisesRegex(ValueError,'关联布局'):compare_history(video,ref)
            self.assertTrue(compare_history(video,ref,True)['layout_bound']);self.assertEqual(video,before)
            video['quality']['distance_usable']=True
            with self.assertRaisesRegex(ValueError,'不能重绑定'):compare_history(video,ref,True)
            video['identity']['track']='Different Track'
            with self.assertRaisesRegex(ValueError,'同一赛道'):compare_history(video,ref,True)

    def test_distance_delta_uses_actual_progress_and_keeps_holes(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            video,p,_=fixture(t);video['quality']['distance_usable']=True
            for r in video['rows']:r['distance_m']=r['lap_time_s']/9*1000
            result=compare_history(video,reference_curve(p));self.assertAlmostEqual(result['delta'][50][1],.5)
            video['rows']=[r for r in video['rows'] if not 3<r['lap_time_s']<6]
            result=compare_history(video,reference_curve(p));self.assertIsNone(result['delta'][50][1])

    def test_fixed_landmarks_validate_names_and_order(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            video,p,_=fixture(t);ref=reference_curve(p)
            video['landmarks']=[dict(name='entry',video_s=3),dict(name='exit',video_s=9)]
            marks=[dict(name='entry',lap_time_s=1),dict(name='exit',lap_time_s=8)]
            self.assertEqual(compare_history(video,ref,landmarks=marks)['segments'][0]['delta_s'],1)
            marks[1]['lap_time_s']=.5
            with self.assertRaisesRegex(ValueError,'顺序'):compare_history(video,ref,landmarks=marks)

    def test_export_read_only_atomic_and_invalid_laps_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            video,p,v=fixture(t);before=p.read_bytes(),v.read_bytes()
            result=export_comparison(v,p,Path(t)/'output')
            html=Path(result['report']).read_text(encoding='utf8')
            self.assertIn('stintrix.video-history-comparison',html);self.assertIn('虚线蓝 / 紫',html)
            self.assertEqual((p.read_bytes(),v.read_bytes()),before)
            event=threading.Event();event.set()
            with self.assertRaises(Cancelled):export_comparison(v,p,Path(t)/'cancelled',cancel=event)
            native=json.loads(p.read_text());native['lap']['in_pits']=True;p.write_text(json.dumps(native))
            with self.assertRaisesRegex(ValueError,'有效完整圈'):reference_curve(p)

    def test_picker_indexes_headers_only_and_separates_layouts(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=Path(t)/'Logs'/'example';video,p,_=fixture(folder)
            event=dict(folder=str(folder),source='Logs',status='complete',track='Test Track',date='2026',vehicle='Test',fastest_file=p.name)
            with patch('library.inventory',return_value=[event]),patch('video_history.native_data',side_effect=AssertionError('loaded entire curve')):
                items=history_laps(t,video)
            self.assertEqual(len(items),1);self.assertTrue(items[0]['exact'])

    @unittest.skipUnless(os.name=='nt','Windows Tk')
    def test_native_picker_runs_comparison_and_minimum_width_fits(self):
        from control_center import ControlCenter
        from control_video_history import show
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t,patch('control_center.ROOT',Path(t)):
            _,p,v=fixture(t);app=ControlCenter();app.root.withdraw();errors=[];app.root.report_callback_exception=lambda *e:errors.append(str(e))
            try:
                with patch('video_history.history_laps',return_value=[dict(file=str(p),identity=dict(track='Test Track',track_layout='Grand Prix',length_m=1000),date='2026',vehicle='Test',number=2,time_s=10,exact=True)]):
                    window=show(app,t,v);window.geometry('940x700');state=window.history_state;controls=window.history_controls
                    def wait():
                        until=time.monotonic()+15
                        while time.monotonic()<until:
                            app.root.update();time.sleep(.01)
                            if not state['busy']:return
                        self.fail('history picker stuck')
                    wait();self.assertTrue(state['items']);controls['start'].invoke();wait()
                    self.assertIsNotNone(state['result']);self.assertTrue(Path(state['result']['report']).exists())
                    app.root.update_idletasks();self.assertLessEqual(controls['start'].winfo_rooty()+controls['start'].winfo_height(),window.winfo_rooty()+window.winfo_height())
                    self.assertFalse(errors,errors)
            finally:app.close()
            self.assertTrue(state['cancel'].is_set())


if __name__=='__main__':unittest.main()
