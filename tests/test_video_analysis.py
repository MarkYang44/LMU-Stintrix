"""Known-signal video fixtures, native time maps, OCR and cancellation."""
import copy
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from video_signal import arc_points,pedal,anchor_signature,visible,clock,ocr_number
from video_alignment import sync_map,distance_readings,compare,native_lap,native_header,native_data
from video_media import frames,Cancelled
from video_analysis import analyze


def fixture(folder, duration=15):
    from PIL import Image,ImageDraw,ImageFont
    folder=Path(folder);video=folder/'known.mp4';font=ImageFont.truetype('arial.ttf',28)
    def point(cx,cy,r,a):return [cx+r*math.cos(math.radians(a)),cy+r*math.sin(math.radians(a))]
    config=dict(video=str(video),mode='time',start_s=0.,end_s=duration,sample_s=0.,hz=10,
        identity=dict(track='Test circuit',track_layout='Full',length_m=duration*100),
        throttle=dict(points=[[450,220],point(450,220,65,135),point(450,220,65,225)],clockwise=True,thickness=8),
        brake=dict(points=[[550,220],point(550,220,65,-45),point(550,220,65,45)],clockwise=True,thickness=8),
        anchor=[470,279,536,310],distance_box=[20,30,195,70],timer_box=[20,85,225,130],
        landmarks=[dict(name='entry',video_s=1.),dict(name='exit',video_s=duration-1)])
    command=['ffmpeg','-y','-v','error','-f','rawvideo','-pix_fmt','rgb24','-s','640x360','-r','10',
             '-i','pipe:0','-an','-c:v','libx264','-crf','16','-pix_fmt','yuv420p',str(video)]
    p=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    try:
        for i in range(round(duration*10)):
            t=i/10;throttle=(.25,.75,.5)[min(2,int(t/(duration/3)))];brake=(0.,.3,.6)[min(2,int(t/(duration/3)))]
            image=Image.new('RGB',(640,360),(25,25,30));draw=ImageDraw.Draw(image)
            for cx,cy,a,amount,color in [(450,220,135,throttle,'#00ed66'),(550,220,-45,brake,'#ff2545')]:
                draw.arc((cx-65,cy-65,cx+65,cy+65),a,a+90,fill='#4b4b4b',width=8)
                if amount:draw.arc((cx-65,cy-65,cx+65,cy+65),a,a+90*amount,fill=color,width=8)
            # Calibration radius follows the centre of PIL's inward arc stroke.
            draw.text((470,279),'KPH',font=font,fill='white')
            draw.text((20,30),f'{t*100:.0f}',font=font,fill='white')
            draw.text((20,85),f'0:{t:06.3f}',font=font,fill='white')
            if 6<=t<6.4:draw.rectangle((370,140,639,325),fill='black')
            p.stdin.write(image.tobytes())
        p.stdin.close();error=p.stderr.read();p.wait(timeout=20)
        if p.returncode:raise RuntimeError(error.decode())
    finally:
        if p.poll() is None:p.kill();p.wait()
        p.stderr.close()
    for name in ('throttle','brake'):
        points=config[name]['points'];center=points[0]
        for i in (1,2):points[i]=[center[j]+(points[i][j]-center[j])*61.5/65 for j in (0,1)]
    native=dict(format='inputscope.fastest-lap',version=1,session=dict(track='Test circuit',track_layout='Full',vehicle='Fixture'),
        lap=dict(validity='verified',time_s=duration,track_length_m=duration*100),
        data_columns=['lap_time_s','distance_m','filtered_throttle','filtered_brake'],
        data=[[i/10,i*10,(.25,.75,.5)[min(2,int(i/10/(duration/3)))],(0.,.3,.6)[min(2,int(i/10/(duration/3)))]] for i in range(round(duration*10)+1)])
    path=folder/'native.lap.json';path.write_text(json.dumps(native));config['telemetry']=str(path)
    config['sync']=[[0,0],[duration/2,duration/2],[duration,duration]]
    return config


class VideoTests(unittest.TestCase):
    def test_dense_display_preserves_short_releases_extrema_and_gap_boundaries(self):
        from video_report import sampled
        rows=[dict(lap_time_s=i*.05,throttle=.8,brake=.7,native_throttle=.9,native_brake=.6,status='estimated') for i in range(2000)]
        rows[12]['throttle']=0.;rows[13]['brake']=0.;rows[14]['native_throttle']=0.;rows[15]['native_brake']=0.
        rows[20]['throttle']=1.;rows[21]['brake']=1.
        for i in range(40,43):rows[i]['throttle']=None
        output=sampled(rows,limit=120);by_time={r['lap_time_s']:r for r in output}
        for i in (12,13,14,15,20,21,39,40,42,43):self.assertIn(rows[i]['lap_time_s'],by_time)
        self.assertTrue(all('_source_gap_s' not in row for row in rows))
        # Display reduction must not create fake missing-frame gaps.
        self.assertTrue(all(row['_source_gap_s']<.051 for row in output))
        rows[900]['lap_time_s']+=.4
        self.assertGreater(max(r['_source_gap_s'] for r in sampled(rows,120)),.3)

    def test_anchor_integer_variance_matches_population_stddev_threshold(self):
        import random,statistics
        from PIL import Image
        rng=random.Random(42)
        patterns=[[0,19]*256,[0,20]*256,[0,21]*256]+[[rng.randrange(256) for _ in range(512)] for _ in range(50)]
        for pixels in patterns:
            image=Image.new('L',(32,16));image.putdata(pixels);image=image.convert('RGB')
            for shift in (0,34,35):
                signature=[min(255,v+shift) for v in pixels]
                expected=statistics.pstdev(pixels)>=10 and sum(abs(a-b) for a,b in zip(pixels,signature))/512<35
                self.assertEqual(visible(image,[0,0,32,16],signature),expected)

    def test_times_and_ocr_units_are_explicit(self):
        self.assertEqual(clock('1:02.500'),62.5);self.assertEqual(ocr_number('1.234',unit='km'),1234)
        self.assertEqual(ocr_number('1:23.456',timer=True),83.456)
        for value in ('nan','1:62','-1','1:2:3:4'):
            with self.assertRaises(ValueError):clock(value)
        self.assertIsNone(ocr_number('speed 123 lap 4'));self.assertIsNone(ocr_number('unknown'))

    def test_arc_validation_and_missing_anchor(self):
        from PIL import Image,ImageDraw,ImageFont
        im=Image.new('RGB',(200,100));draw=ImageDraw.Draw(im);draw.text((10,10),'KPH',font=ImageFont.truetype('arial.ttf',30),fill='white')
        signature=anchor_signature(im,[10,10,80,50]);self.assertTrue(visible(im,[10,10,80,50],signature))
        self.assertFalse(visible(Image.new('RGB',im.size),[10,10,80,50],signature))
        with self.assertRaises(ValueError):arc_points(dict(points=[[20,20],[20,20],[40,20]]))

    def test_sync_requires_coverage_monotonicity_and_checked_residuals(self):
        result=sync_map([[10,0],[60,50],[110,100]],10,110,100)
        self.assertAlmostEqual(result['scale'],1);self.assertAlmostEqual(result['offset'],-10);self.assertTrue(result['independently_checked'])
        self.assertFalse(sync_map([[10,0],[110,100]],10,110,100)['independently_checked'])
        for points in ([[10,0]],[[10,0],[20,10]],[[10,0],[60,48],[110,100]],[[10,0],[60,70],[110,60]]):
            with self.assertRaises(ValueError):sync_map(points,10,110,100)

    def test_high_rate_native_uses_compact_reference_and_fast_headers(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as scratch:
            path=Path(scratch)/'lap.json'
            value=dict(format='inputscope.fastest-lap',session=dict(track='X',track_layout='Full'),lap=dict(validity='verified'),
                data_columns=['lap_time_s','distance_m','filtered_throttle','filtered_brake'],
                data=[[i/4000,i/40,.4,.2] for i in range(8001)])
            path.write_text(json.dumps(value));header=native_header(path)
            self.assertNotIn('data',header);self.assertEqual(header['session']['track'],'X')
            data=native_data(path)['data'];self.assertLess(len(data),125);self.assertAlmostEqual(data[-1][0],2)
            self.assertLess(data.data.buffer_info()[1]*data.data.itemsize,5000)
            value['data'][43][0]=0;path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):native_data(path)

    @unittest.skipUnless(shutil.which('ffmpeg') and os.name=='nt','local FFmpeg / Windows fixture')
    def test_missing_ocr_falls_back_and_wrong_resolution_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as scratch:
            config=fixture(scratch,3);config['mode']='distance_hud'
            with patch('video_ocr.WindowsOCR',side_effect=ValueError('OCR unavailable')):
                result=analyze(config,Path(scratch)/'output')
            self.assertFalse(result['quality']['distance_usable']);self.assertIn('OCR unavailable',result['quality']['distance_reason'])
            self.assertGreater(result['quality']['pedal_readable_ratio'],.9)
            config['frame_size']=[1280,720]
            with self.assertRaisesRegex(ValueError,'分辨率'):analyze(config,Path(scratch)/'output')

    def test_distance_rejects_timer_drift_backwards_spikes_and_freezes(self):
        values=[(i*.2,i*20,i*.2) for i in range(51)]
        good,quality=distance_readings(values,0,1000);self.assertTrue(quality['usable']);self.assertEqual(len(good),51)
        bad=copy.deepcopy(values);bad[4]=(0.8,900,.8);bad[5]=(1.,100,9.)
        _,quality=distance_readings(bad,0,1000);self.assertEqual(quality['rejected'],2)
        _,quality=distance_readings([(i*.2,0,0) for i in range(51)],0,1000);self.assertFalse(quality['usable'])

    def test_landmarks_compare_by_physical_name_and_reject_other_layout(self):
        a=dict(format='stintrix.video-curves',id='a',identity=dict(track='X',track_layout='Full',length_m=1000),start_s=10,
            landmarks=[dict(name='entry',video_s=20),dict(name='exit',video_s=30)],quality={},rows=[])
        b=copy.deepcopy(a);b['id']='b';b['landmarks'][1]['video_s']=29
        result=compare(a,b);self.assertEqual(result['segments'][0]['delta_s'],-1);self.assertEqual(result['delta'],[])
        b['identity']['track_layout']='Short'
        with self.assertRaises(ValueError):compare(a,b)

    @unittest.skipUnless(shutil.which('ffmpeg') and os.name=='nt','local FFmpeg / Windows fixture')
    def test_real_video_time_native_ocr_and_source_preservation(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as scratch:
            folder=Path(scratch);config=fixture(folder);before={p.name:(p.stat().st_size,p.stat().st_mtime_ns) for p in folder.iterdir()}
            time_result=analyze(config,folder/'output');time_data=json.loads((Path(time_result['folder'])/'curve.json').read_text(encoding='utf-8'))
            self.assertGreater(len(time_data['rows']),100);self.assertFalse(time_data['quality']['distance_usable'])
            early=[r for r in time_data['rows'] if 1<r['lap_time_s']<4]
            self.assertTrue(all(abs(r['throttle']-.25)<.045 and r['brake']==0 for r in early))
            self.assertTrue(any(r['status']=='hud_missing' and r['throttle'] is None for r in time_data['rows']))
            self.assertTrue(all(r['distance_m'] is None for r in time_data['rows']))
            config['mode']='telemetry';native_result=analyze(config,folder/'output')
            self.assertTrue(native_result['quality']['distance_usable']);self.assertLess(native_result['quality']['pedal_mae']['throttle'],.06)
            for name,stat in before.items():self.assertEqual(((folder/name).stat().st_size,(folder/name).stat().st_mtime_ns),stat)
            self.assertFalse((folder/'output'/'Logs').exists())
            self.assertFalse(list((folder/'output'/'VideoCurves').glob('pending-*')))
            for name in ('report.html','curve.csv','curve.json','calibration.json'):self.assertTrue((Path(native_result['folder'])/name).is_file())
            self.assertNotIn('steering',(Path(native_result['folder'])/'curve.csv').read_text(encoding='utf-8-sig'))
            config['identity']['track_layout']='Short'
            with self.assertRaises(ValueError):native_lap(config['telemetry'],config['identity'])

    @unittest.skipUnless(shutil.which('ffmpeg') and os.name=='nt','local FFmpeg / Windows fixture')
    def test_optional_windows_ocr_and_native_distance_comparison(self):
        from video_ocr import WindowsOCR
        try:worker=WindowsOCR()
        except ValueError as error:self.skipTest('Optional Windows OCR runtime: '+str(error))
        worker.close()
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as scratch:
            folder=Path(scratch);config=fixture(folder);config['mode']='telemetry';a=analyze(config,folder/'output')
            config['mode']='distance_hud';b=analyze(config,folder/'output')
            self.assertTrue(b['quality']['distance_usable'],b['quality'])
            native=json.loads((Path(a['folder'])/'curve.json').read_text(encoding='utf-8'))
            ocr=json.loads((Path(b['folder'])/'curve.json').read_text(encoding='utf-8'))
            comparison=compare(native,ocr);self.assertTrue(comparison['delta'])
            self.assertLess(max(abs(v) for d,v in comparison['delta'] if v is not None),.08)

    @unittest.skipUnless(shutil.which('ffmpeg') and os.name=='nt','local FFmpeg / Windows fixture')
    def test_variable_frame_rate_and_seek_keep_actual_pts(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as scratch:
            config=fixture(scratch,3);target=Path(scratch)/'vfr.mp4'
            subprocess.run(['ffmpeg','-y','-v','error','-i',config['video'],'-vf',
                "select='eq(n,0)+eq(n,1)+eq(n,4)+eq(n,9)+eq(n,10)+eq(n,18)+eq(n,27)'",'-fps_mode','vfr',str(target)],
                check=True,capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            times=[t for t,im in frames(target,0,3,30,(0,0,64,64))]
            self.assertEqual([round(t,3) for t in times],[0,.1,.4,.9,1,1.8,2.7])
            times=[t for t,im in frames(target,.35,2.9,30,(1,1,63,63))]
            self.assertEqual([round(t,3) for t in times],[.4,.9,1,1.8,2.7])

    @unittest.skipUnless(shutil.which('ffmpeg') and os.name=='nt','local FFmpeg / Windows fixture')
    def test_cancel_does_not_publish_partial_output(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as folder:
            config=fixture(folder,3);cancel=threading.Event()
            with self.assertRaises(Cancelled):analyze(config,Path(folder)/'output',cancel,lambda *_:cancel.set())
            self.assertFalse(list((Path(folder)/'output'/'VideoCurves').iterdir()))

    def test_report_escapes_injected_markup_and_preserves_missing_samples(self):
        from video_report import write_report
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as folder:
            result=dict(identity=dict(track='<script>bad</script>',track_layout='Full'),video_file='x.mp4',mode='time',start_s=0,end_s=10,
                quality=dict(pedal_readable_ratio=.2,max_frame_gap_s=.1),rows=[dict(lap_time_s=0,distance_m=None,throttle=None,brake=None)])
            path=Path(folder)/'report.html';write_report(path,result);html=path.read_text(encoding='utf-8')
            self.assertNotIn('<script>bad</script>',html);self.assertIn('\\u003cscript',html);self.assertIn('"throttle": null',html)


if __name__=='__main__':unittest.main()
