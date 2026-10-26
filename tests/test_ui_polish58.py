"""Achievement preview/export correctness, privacy and lifecycle regressions."""
import json,os,sys,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from tests import test_ui_efficiency as helpers
from tests.test_record_intelligence import entry


def picture(value):
    from PIL import Image
    return Image.new('RGB',(1920,1080),'#f5cccc' if 'driver' in value else '#eeeeee')


class Files(unittest.TestCase):
    def test_saved_preview_keeps_all_pixels_unique_names_and_existing_files(self):
        from achievement_card import save_image
        from PIL import Image
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            image=Image.new('RGB',(1920,1080));image.putpixel((1800,1000),(3,117,249));a=Path(save_image(tmp,image));old=a.read_bytes();b=Path(save_image(tmp,image));self.assertNotEqual(a,b);self.assertEqual(a.read_bytes(),old)
            with Image.open(b) as exported:self.assertEqual(exported.size,image.size);self.assertEqual(exported.tobytes(),image.tobytes())
            self.assertFalse(list(a.parent.glob('*.pending')))
    def test_failed_png_save_removes_only_its_partial_output(self):
        from achievement_card import save_image
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            folder=Path(tmp)/'PersonalRecords/AchievementCards';folder.mkdir(parents=True);keep=folder/'existing.png';keep.write_bytes(b'existing');unknown=folder/'.unknown.pending';unknown.write_bytes(b'keep')
            def fail(stream,**_):stream.write(b'partial');raise OSError('disk fixture')
            with self.assertRaises(OSError):save_image(tmp,SimpleNamespace(save=fail))
            self.assertEqual(set(folder.iterdir()),{keep,unknown});self.assertEqual(keep.read_bytes(),b'existing');self.assertEqual(unknown.read_bytes(),b'keep')
    @unittest.skipUnless(os.name=='nt','Windows fonts')
    def test_queued_card_uses_the_language_captured_in_its_payload(self):
        import i18n
        from achievement_card import payload,compose
        try:
            i18n.set_language('en');value=payload(entry(),dict(conditions={}));english=compose(value)
            i18n.set_language('zh');self.assertEqual(compose(value).tobytes(),english.tobytes());self.assertNotIn('driver',value);self.assertNotIn('date',value)
        finally:i18n.set_language('zh')


@unittest.skipUnless(os.name=='nt','Native Tk')
class UI(unittest.TestCase):
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def card(self,app,root):
        from control_achievement import show
        e=entry();e.update(folder=str(root/'Logs/one'),file=str(root/'Logs/one/fastest_lap.json'))
        for target,kwargs in [('personal_records.detail',dict(return_value=dict(conditions={}))),('achievement_card.compose',dict(side_effect=picture))]:
            guard=patch(target,**kwargs);guard.start();self.addCleanup(guard.stop)
        w=show(app,e);self.pump(app,.4);return w,w.achievement_controls,e
    def test_same_record_reuses_window_and_keeps_privacy_choices(self):
        from control_achievement import show
        app,root,errors=self.app();w,c,e=self.card(app,root);c['switches'][0].toggle();self.pump(app,.3)
        with patch('personal_records.detail') as read,patch('achievement_card.compose') as compose:
            self.assertIs(show(app,dict(e)),w);read.assert_not_called();compose.assert_not_called()
        self.assertTrue(c['name'].get());other=show(app,dict(e,folder=str(root/'Logs/two')));self.pump(app,.3);self.assertIsNot(other,w);self.assertFalse(other.achievement_controls['name'].get());self.assertEqual(len(app.achievement_windows),2)
        w.destroy();self.assertEqual(len(app.achievement_windows),1);self.assertFalse(errors)
    def test_refreshed_podium_result_opens_updated_card_instead_of_reusing_stale_values(self):
        from control_achievement import show
        app,root,errors=self.app();e=entry();e.update(folder=str(root/'OfficialResults/events/fixture'),place=2,fastest_s=100,summary=dict(grid_class_place=3))
        with patch('podium_records.detail',return_value=dict(start={},fastest_s=100,race_s=1000)),patch('achievement_card.compose',side_effect=picture):
            first=show(app,e);self.pump(app,.35)
        updated=dict(e,fastest_s=99,summary=dict(grid_class_place=4))
        with patch('podium_records.detail',return_value=dict(start={},fastest_s=99,race_s=1000)),patch('achievement_card.compose',side_effect=picture) as compose:
            second=show(app,updated);self.pump(app,.35);self.assertIsNot(first,second);self.assertEqual(compose.call_args.args[0]['time'],'1:39.000');self.assertIn('P4',compose.call_args.args[0]['result'])
        self.assertFalse(errors)
    def test_preview_keeps_image_coalesces_requests_and_blocks_stale_export(self):
        app,root,errors=self.app();w,c,_=self.card(app,root);old=c['canvas'].image;gate=threading.Event();entered=threading.Event();calls=[]
        def compose(value):
            calls.append(value)
            if len(calls)==1:entered.set();gate.wait(4)
            return picture(value)
        try:
            with patch('achievement_card.compose',side_effect=compose),patch('achievement_card.save_image') as save:
                c['switches'][0].toggle();self.pump(app,.15);self.assertTrue(entered.wait(1));self.assertIs(c['canvas'].image,old);self.assertFalse(c['buttons']['export'].enabled);c['generate']();save.assert_not_called()
                c['switches'][1].toggle();self.pump(app,.15);c['switches'][1].toggle();self.pump(app,.15);self.assertEqual(len(calls),1)
                gate.set();self.pump(app,.4);self.assertEqual(len(calls),2);self.assertIn('driver',calls[-1]);self.assertNotIn('date',calls[-1]);self.assertTrue(c['buttons']['export'].enabled);self.assertEqual(c['state']['rendered'],c['state']['revision'])
        finally:gate.set()
        self.assertFalse(errors)
    def test_failed_preview_can_retry_without_rereading_record(self):
        app,root,errors=self.app();w,c,_=self.card(app,root);old=c['canvas'].image
        with patch('achievement_card.compose',side_effect=OSError('preview fixture')):c['request']();self.pump(app,.3)
        self.assertIs(c['canvas'].image,old);self.assertFalse(c['buttons']['export'].enabled);self.assertTrue(c['buttons']['retry'].enabled);self.assertIn('preview fixture',c['status'].get())
        with patch('personal_records.detail') as read:c['buttons']['retry'].invoke();self.pump(app,.3);read.assert_not_called()
        self.assertTrue(c['buttons']['export'].enabled);self.assertFalse(c['buttons']['retry'].winfo_manager());self.assertFalse(errors)
    def test_export_saves_exact_preview_once_and_open_failure_is_recoverable(self):
        from PIL import Image
        app,root,errors=self.app();w,c,_=self.card(app,root);pixels=c['state']['image'].tobytes()
        with patch('achievement_card.compose',side_effect=AssertionError('Do not redraw approved preview')),patch('control_achievement.os.startfile',side_effect=OSError('viewer fixture')):
            c['buttons']['export'].invoke();self.pump(app,.4)
        path=Path(c['state']['result']);self.assertTrue(path.is_file());self.assertIn('viewer fixture',c['status'].get());self.assertTrue(c['buttons']['open'].enabled);self.assertEqual(c['output'].get(),str(path))
        with Image.open(path) as image:self.assertEqual(image.size,(1920,1080));self.assertEqual(image.tobytes(),pixels)
        with patch('control_achievement.os.startfile') as opened:c['buttons']['open'].invoke();opened.assert_called_once_with(str(path))
        self.assertEqual(len(list(path.parent.glob('*.png'))),1)
        with patch('control_achievement.os.startfile') as opened:c['buttons']['folder'].invoke();opened.assert_called_once_with(str(path.parent))
        path.unlink();c['buttons']['open'].invoke();self.assertIn('移动或删除',c['status'].get());self.assertFalse(errors)
    def test_export_freezes_privacy_and_duplicate_clicks_until_finished(self):
        from achievement_card import save_image
        app,root,errors=self.app();w,c,_=self.card(app,root);gate=threading.Event();entered=threading.Event()
        def save(*args):entered.set();gate.wait(4);return save_image(*args)
        try:
            with patch('achievement_card.save_image',side_effect=save) as writer,patch('control_achievement.os.startfile'):
                c['buttons']['export'].invoke();self.assertTrue(entered.wait(1));self.assertFalse(c['buttons']['export'].enabled);self.assertTrue(all(not s.enabled for s in c['switches']));c['switches'][0].toggle();self.assertFalse(c['name'].get());c['generate']();writer.assert_called_once();gate.set();self.pump(app,.4)
            self.assertTrue(c['buttons']['export'].enabled);self.assertTrue(all(s.enabled for s in c['switches']))
        finally:gate.set()
        self.assertFalse(errors)
    def test_failed_export_keeps_preview_and_prior_result_for_retry(self):
        app,root,errors=self.app();w,c,_=self.card(app,root)
        with patch('control_achievement.os.startfile'):c['generate']();self.pump(app,.4)
        old=c['state']['result'];image=c['state']['image']
        with patch('achievement_card.save_image',side_effect=OSError('save fixture')):c['generate']();self.pump(app,.3)
        self.assertEqual(c['state']['result'],old);self.assertTrue(Path(old).is_file());self.assertIs(c['state']['image'],image);self.assertTrue(c['buttons']['export'].enabled);self.assertIn('save fixture',c['status'].get());self.assertFalse(errors)
    def test_closing_export_keeps_completed_file_and_reports_its_location(self):
        from achievement_card import save_image
        app,root,errors=self.app();w,c,_=self.card(app,root);gate=threading.Event();entered=threading.Event()
        def save(*args):entered.set();gate.wait(4);return save_image(*args)
        try:
            with patch('achievement_card.save_image',side_effect=save),patch('control_achievement.os.startfile') as opened:
                c['generate']();self.assertTrue(entered.wait(1));w.destroy();gate.set();self.pump(app,.4);opened.assert_not_called()
            files=list((root/'PersonalRecords/AchievementCards').glob('*.png'));self.assertEqual(len(files),1);self.assertIn(str(files[0]),app.status.get());self.assertFalse(app.achievement_windows)
        finally:gate.set()
        self.assertFalse(errors)
    def test_read_failure_retry_and_late_close_are_safe(self):
        from control_achievement import show
        app,root,errors=self.app();e=entry();e['folder']=str(root/'Logs/one')
        with patch('personal_records.detail',side_effect=OSError('read fixture')):w=show(app,e);w.geometry('760x500');self.pump(app,.3)
        c=w.achievement_controls;self.assertTrue(c['buttons']['retry'].enabled);self.assertFalse(c['buttons']['export'].enabled)
        retry=c['buttons']['retry'];viewport=c['options'].canvas;self.assertGreaterEqual(retry.winfo_rooty(),viewport.winfo_rooty());self.assertLessEqual(retry.winfo_rooty()+retry.winfo_height(),viewport.winfo_rooty()+viewport.winfo_height()+1)
        with patch('personal_records.detail',return_value=dict(conditions={})),patch('achievement_card.compose',side_effect=picture):c['buttons']['retry'].invoke();self.pump(app,.4)
        self.assertTrue(c['buttons']['export'].enabled);w.destroy();jobs=[]
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append(done)):w=show(app,e);w.destroy();jobs.pop()(dict(conditions={}),None)
        self.assertFalse(errors)
    def test_language_change_during_export_keeps_saved_snapshot_and_reports_pending_preview(self):
        from achievement_card import save_image
        app,root,errors=self.app();w,c,_=self.card(app,root);gate=threading.Event();preview_gate=threading.Event();entered=threading.Event();preview_entered=threading.Event();original=c['state']['image'].tobytes()
        def save(*args):entered.set();gate.wait(4);return save_image(*args)
        def compose(value):preview_entered.set();preview_gate.wait(4);return picture(value)
        try:
            with patch('achievement_card.save_image',side_effect=save),patch('achievement_card.compose',side_effect=compose),patch('control_achievement.os.startfile'):
                c['generate']();self.assertTrue(entered.wait(1));app.toggle_language();self.pump(app,.15);self.assertTrue(preview_entered.wait(1));gate.set();self.pump(app,.3)
                self.assertIn('still updating',c['status'].get());self.assertFalse(c['buttons']['export'].enabled)
                from PIL import Image
                with Image.open(c['state']['result']) as image:self.assertEqual(image.tobytes(),original)
                preview_gate.set();self.pump(app,.3);self.assertTrue(c['buttons']['export'].enabled)
        finally:gate.set();preview_gate.set()
        self.assertFalse(errors)
    def test_language_theme_and_minimum_size_keep_choices_output_and_actions(self):
        from control_theme import T
        app,root,errors=self.app();w,c,_=self.card(app,root);c['switches'][0].toggle();self.pump(app,.3)
        with patch('control_achievement.os.startfile'):c['generate']();self.pump(app,.3)
        saved=c['output'].get();w.geometry('760x500');app.set_theme('light');app.toggle_language();self.pump(app,.4)
        self.assertTrue(c['name'].get());self.assertEqual(c['output'].get(),saved);self.assertEqual(c['path'].cget('readonlybackground'),T.FIELD)
        for k in ('export','open','folder'):
            b=c['buttons'][k];self.assertLessEqual(b.winfo_rooty()+b.winfo_height(),w.winfo_rooty()+w.winfo_height());self.assertGreater(b.winfo_width(),b.font.measure(__import__('i18n').tr(b.label))+15)
        self.assertGreater(c['canvas'].winfo_height(),90);self.assertFalse(errors)

if __name__=='__main__':unittest.main()
