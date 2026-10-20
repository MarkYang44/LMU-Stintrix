import copy,json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from video_resample import resample,export

class ResampleTests(unittest.TestCase):
    def result(self,points):
        return dict(rows=[dict(lap_time_s=t,throttle=v,brake=v,status='estimated') for t,v in points],quality=dict(frame_gap_limit_s=.3))
    def test_uniform_and_preserves_knots(self):
        r=self.result([(0,0),(.1,.7),(.2,.3),(.3,1)]);before=copy.deepcopy(r);out=resample(r)['rows']
        self.assertEqual(r,before);self.assertEqual(len(out),37)
        for i,row in enumerate(out):self.assertEqual(row['lap_time_s'],i/120)
        for t,v in [(0,0),(.1,.7),(.2,.3),(.3,1)]:self.assertAlmostEqual(out[round(t*120)]['throttle'],v)
    def test_monotone_no_overshoot(self):
        out=resample(self.result([(0,0),(.08,.01),(.2,.9),(.4,1)]))['rows']
        values=[r['throttle'] for r in out];self.assertTrue(all(0<=v<=1 for v in values));self.assertTrue(all(a<=b for a,b in zip(values,values[1:])))
    def test_missing_channels_and_hud(self):
        r=self.result([(0,0),(.1,.5),(.2,.6),(.3,1),(.4,0)]);r['rows'][2]['brake']=None
        out=resample(r)['rows'];self.assertIsNone(out[24]['brake']);self.assertIsNotNone(out[24]['throttle']);self.assertIsNone(out[20]['brake'])
        r['rows'][2]['status']='hud_missing';self.assertIsNone(resample(r)['rows'][24]['throttle'])
    def test_gap_and_no_extrapolation(self):
        out=resample(self.result([(.02,.1),(.12,.4),(.8,.7),(.9,1)]))['rows']
        self.assertIsNone(out[0]['throttle']);self.assertIsNone(out[60]['throttle']);self.assertEqual(len(out),109)
    def test_irregular_low_fps(self):
        out=resample(self.result([(0,0),(.19,.2),(.39,.8),(.581,1)]))['rows']
        self.assertEqual(len(out),70);self.assertTrue(all(r['throttle'] is not None for r in out));self.assertLessEqual(out[-1]['lap_time_s'],.581)
    def test_reject_duplicate_time(self):
        with self.assertRaises(ValueError):resample(self.result([(0,0),(0,1)]))
    def test_export_raw_untouched(self):
        r=self.result([(0,0),(.1,1)]);r.update(identity=dict(track='Monza',track_layout='Monza'),mode='time',video_file='clip.mp4',start_s=0,end_s=.1)
        r['quality'].update(pedal_readable_ratio=1,missing_samples=0,max_frame_gap_s=.1)
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);raw=folder/'curve.json';raw.write_text(json.dumps(r));before=raw.read_bytes();receipt=export(folder,r)
            self.assertEqual(raw.read_bytes(),before);self.assertEqual(receipt['samples'],13)
            html=(folder/'report_120hz.html').read_text(encoding='utf-8');self.assertIn('aria-pressed="false"',html);self.assertIn('120 Hz 插值估算',html)
