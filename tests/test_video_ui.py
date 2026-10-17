"""Exercise the in-app entry, preview, extraction, layout and shutdown."""
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


@unittest.skipUnless(os.name=='nt','Windows Tk UI')
class VideoUITests(unittest.TestCase):
    def pump(self,app,condition=lambda:True,seconds=15):
        until=time.monotonic()+seconds
        while time.monotonic()<until:
            app.root.update();time.sleep(.01)
            if condition():return
        self.fail('Video workflow did not settle')

    @unittest.skipUnless(shutil.which('ffmpeg'),'local FFmpeg fixture')
    def test_entry_preview_extract_and_minimum_window_controls(self):
        from control_center import ControlCenter
        from control_video import show
        from tests.test_video_analysis import fixture
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as scratch,patch('control_center.ROOT',Path(scratch)):
            config=fixture(scratch,3);center=ControlCenter();errors=[]
            center.root.report_callback_exception=lambda *args:errors.append(args)
            try:
                center.show_page(3);center.root.update();window=show(center,Path(scratch));wizard=window.video_wizard
                self.assertIs(show(center,Path(scratch)),window)
                for key,value in dict(video=config['video'],start='0',end='3',sample='0',track='Test circuit',layout='Full',length='300').items():wizard.fields[key].set(value)
                wizard.geometry={k:copy.deepcopy(config[k]) for k in ('throttle','brake','anchor')}
                wizard.thickness.set('8');wizard.load_preview();self.pump(center,lambda:not wizard.busy)
                self.assertIsNotNone(wizard.image,wizard.status.get());self.assertEqual(wizard.media['width'],640)
                for size in ('1180x900','940x720'):
                    window.geometry(size);self.pump(center,seconds=2);center.root.update_idletasks()
                    for widget in (wizard.start,wizard.stop,wizard.open,wizard.history_button,wizard.tabs):
                        self.assertGreater(widget.winfo_height(),5)
                        self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),window.winfo_rooty()+window.winfo_height(),
                            (size,str(widget),window.winfo_geometry(),widget.winfo_geometry(),widget.winfo_y()))
                window.geometry('1180x900');wizard.run();self.pump(center,lambda:not wizard.busy)
                self.assertIsNotNone(wizard.result,wizard.status.get());self.assertTrue(Path(wizard.result['report']).is_file())
                self.assertFalse((Path(scratch)/'Logs').exists());self.assertFalse(errors,errors)
            finally:center.close()

    def test_close_cancels_video_and_idle_start_does_not_load_decoder(self):
        from control_center import ControlCenter
        from control_video import show
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as scratch,patch('control_center.ROOT',Path(scratch)):
            center=ControlCenter();window=show(center,Path(scratch));cancel=window.video_wizard.cancel
            center.close();self.assertTrue(cancel.is_set())
        import subprocess
        result=subprocess.run([sys.executable,'-c',"import sys;sys.path.insert(0,'src');import control_center;assert not any(k in sys.modules for k in ('video_media','video_ocr','video_analysis'))"],cwd=ROOT,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr.decode('utf-8','replace'))
