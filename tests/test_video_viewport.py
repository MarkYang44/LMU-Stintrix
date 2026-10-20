"""Native canvas navigation must retain original calibration coordinates."""
import copy,os,sys,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from tests import test_video_motion as fixtures


@unittest.skipUnless(os.name=='nt','Windows Tk')
class ViewportTests(unittest.TestCase):
    window=fixtures.VideoMotionTests.window
    pump=fixtures.VideoMotionTests.pump

    def ready(self):
        from PIL import Image
        app,window,w,errors=self.window();w.tabs.select(1);self.pump(app)
        w.media=dict(width=1920,height=1080,duration=120)
        w.seek_scale.configure(to=119.999)
        w.image=Image.new('RGB',(1120,630),'#456789');w.fit_preview();self.pump(app)
        w.geometry={'anchor':[1500,820,1540,842]};w.redraw()
        return app,window,w,errors

    def test_wheel_keeps_pointer_source_coordinate_and_shift_moves_horizontally(self):
        app,window,w,errors=self.ready();w.set_preview_zoom(3)
        w.scroll_preview('x','moveto',.25);w.scroll_preview('y','moveto',.2)
        e=SimpleNamespace(widget=w.canvas,x=350,y=120,delta=120,state=0)
        before=w.point(e);old=copy.deepcopy(w.geometry)
        w.preview_wheel(e);self.pump(app,.03);after=w.point(e)
        self.assertLess(max(abs(a-b) for a,b in zip(before,after)),2)
        origin=w.canvas.canvasx(0);zoom=w.zoom.get();e.state=1
        w.preview_wheel(e);self.assertEqual(w.zoom.get(),zoom);self.assertLess(w.canvas.canvasx(0),origin)
        self.assertEqual(w.geometry,old);self.assertEqual(w.clicks,[]);self.assertFalse(errors)

    def test_right_and_space_drag_do_not_calibrate_or_change_undo(self):
        app,window,w,errors=self.ready();w.set_preview_zoom(3)
        w.scroll_preview('x','moveto',.25);w.scroll_preview('y','moveto',.2)
        original=copy.deepcopy(w.geometry);origin=w.canvas.canvasx(0)
        w.canvas.event_generate('<ButtonPress-3>',x=400,y=100)
        w.canvas.event_generate('<B3-Motion>',x=250,y=75)
        w.canvas.event_generate('<ButtonRelease-3>',x=250,y=75);self.pump(app,.03)
        self.assertGreater(w.canvas.canvasx(0),origin)
        w.space_down(None);w.press(SimpleNamespace(x=300,y=110));w.dragging(SimpleNamespace(x=200,y=80));w.release(SimpleNamespace(x=200,y=80));w.space_up(None)
        self.assertFalse(w.pan_active);self.assertEqual(w.geometry,original);self.assertEqual(w.clicks,[]);self.assertEqual(w.undo_stack,[])
        self.assertFalse(errors)

    def test_high_zoom_bitmap_is_viewport_bounded_and_scrollbar_refreshes_it(self):
        app,window,w,errors=self.ready();w.set_preview_zoom(12)
        self.assertLessEqual(w.photo.width(),w.canvas.winfo_width()+90)
        self.assertLessEqual(w.photo.height(),w.canvas.winfo_height()+90)
        first=w.photo;w.scroll_preview('x','moveto',.7);self.assertIsNot(w.photo,first)
        self.assertGreater(w.canvas.coords('bitmap')[0],0)
        w.fit_preview();self.assertLessEqual(w.photo.width(),w.canvas.winfo_width());self.assertLessEqual(w.photo.height(),w.canvas.winfo_height())
        self.assertLessEqual(abs(w.canvas.canvasx(0)),1);self.assertFalse(errors)

    def test_time_nudges_accumulate_while_preview_pending_and_clamp_at_edges(self):
        app,window,w,errors=self.ready();w.seek.set(1)
        with patch.object(w,'request_frame') as request:
            w.nudge_preview(.02);w.nudge_preview(.02);self.assertAlmostEqual(w.seek.get(),1.04)
            self.assertAlmostEqual(request.call_args.args[0],1.04)
            w.seek.set(0);w.nudge_preview(-1);self.assertEqual(w.seek.get(),0)
            w.seek.set(119.99);w.nudge_preview(1);self.assertEqual(w.seek.get(),119.999)
        self.assertFalse(errors)

    def test_native_preview_does_not_discard_pixels_before_zooming(self):
        import shutil,subprocess,tempfile
        from video_media import preview
        ff=shutil.which('ffmpeg')
        if not ff:self.skipTest('FFmpeg unavailable')
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as d:
            p=Path(d)/'preview.mp4'
            subprocess.run([ff,'-v','error','-y','-f','lavfi','-i','color=c=blue:s=1600x900:r=1','-frames:v','1','-c:v','libx264','-pix_fmt','yuv420p',str(p)],check=True)
            self.assertEqual(preview(p,0).size,(1600,900))
