"""The newest video extractions on the data page, each one click from its report."""
import os,time,unittest
from unittest.mock import patch
from tests import test_ui_polish69 as helpers
from tests.test_ui_polish67 import video


def wait(root,condition,seconds=3):
    deadline=time.monotonic()+seconds
    while not condition() and time.monotonic()<deadline:root.update();time.sleep(.005)
    return condition()


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.UI.app;pump=helpers.UI.pump;settle=helpers.UI.settle

    def test_three_newest_results_open_their_report_in_one_click(self):
        app,root,errors=self.app()
        for name in ('v1','v2','v3','v4'):video(root,name,reports=('raw',) if name!='v3' else ('smooth',))
        app.show_page(3);self.pump(app,.3);app.data_tasks.select('video');recent=app.recent_videos
        self.assertTrue(wait(app.root,lambda:len(recent.entries)==3))
        self.assertEqual([item['video_file'] for item,_ in recent.entries],['v4.mp4','v3.mp4','v2.mp4'])
        with patch('control_video_recent.os.startfile') as opened:
            recent.entries[0][1].invoke();recent.entries[1][1].invoke()
        self.assertEqual([os.path.basename(call.args[0]) for call in opened.call_args_list],['report.html','report_120hz.html']);self.assertFalse(errors)

    def test_no_results_point_to_the_first_extraction(self):
        app,root,errors=self.app();app.show_page(3);self.pump(app,.3);app.data_tasks.select('video');recent=app.recent_videos
        self.assertTrue(wait(app.root,lambda:recent.note.winfo_exists() and recent.note.cget('text').startswith('还没有提取结果')));self.assertFalse(errors)
