"""Fewer manual steps without guessing geometry, lap identity or session types."""
import copy,json,os,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from video_preferences import infer_identity,remember,load,match
from record_presentation import session_type
from tests.test_record_intelligence import entry


class AssistTests(unittest.TestCase):
    def test_types_share_lmu_ranges_text_aliases_and_unknowns(self):
        import i18n
        with patch.object(i18n,'language','zh'):
            for n in range(14):self.assertEqual(session_type(n),'练习' if n<5 else '排位' if n<9 else '暖胎' if n==9 else '正赛')
            for value,label in [('race','正赛'),('Qualifying','排位'),('practice','练习'),('10','正赛'),(True,'赛事类型未知'),(None,'赛事类型未知')]:
                self.assertEqual(session_type(value),label)
        with patch.object(i18n,'language','en'):self.assertEqual(session_type(10),'Race')

    def test_card_types_are_present_for_fastest_and_podium_without_leaking_privacy(self):
        from achievement_card import payload
        e=entry();e['session']['session']=5
        details=dict(conditions={})
        self.assertTrue(payload(e,details)['context'].endswith(' · 排位'))
        e.update(place=1,summary={});e['session']['session']=10
        value=payload(e,dict(start={},race_s=300,fastest_s=99))
        self.assertTrue(value['context'].endswith(' · 正赛'));self.assertNotIn('driver',value);self.assertNotIn('date',value)
        e['session'].pop('session');self.assertTrue(payload(e,details)['context'].endswith('赛事类型未知'))

    def test_filename_inference_requires_a_unique_recorded_layout(self):
        choices={'Fuji full':('Fuji Speedway','Fuji Speedway',4535.8),'Monza':('Monza','Grand Prix',5793)}
        self.assertEqual(infer_identity('【LMU】富士911GT3 fixed.mp4',choices),'Fuji full')
        self.assertIsNone(infer_identity('unknown.mp4',choices))
        choices['Fuji short']=('Fuji Speedway','Short',3000)
        self.assertIsNone(infer_identity('Fuji Speedway.mp4',choices))

    def test_hud_drafts_are_small_bounded_and_require_visible_anchor_and_resolution(self):
        from PIL import Image,ImageDraw,ImageFont
        image=Image.new('RGB',(640,360));ImageDraw.Draw(image).text((470,279),'KPH',font=ImageFont.truetype('arial.ttf',28),fill='white')
        config=dict(frame_size=[640,360],throttle=dict(points=[[450,220],[410,260],[410,180]],thickness=6),
                    brake=dict(points=[[550,220],[590,180],[590,260]],thickness=6),anchor=[470,279,536,310])
        media=dict(width=640,height=360)
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as scratch:
            for i in range(8):
                value=copy.deepcopy(config);value['anchor'][0]-=i;remember(scratch,value,image,media)
            profiles=load(scratch);self.assertTrue(2<=len(profiles)<=6)
            self.assertLess((Path(scratch)/'video_preferences.json').stat().st_size,32768)
            found=match(profiles,image,media);self.assertIsNotNone(found)
            found['throttle']['points'][0][0]=0;self.assertNotEqual(found,profiles[0])
            self.assertIsNone(match(profiles,Image.new('RGB',image.size),media))
            self.assertIsNone(match(profiles,image,dict(width=1920,height=1080)))
            (Path(scratch)/'video_preferences.json').write_text('{"profiles":false}')
            self.assertEqual(load(scratch),[])


@unittest.skipUnless(os.name=='nt','Windows Tk')
class AssistUITests(unittest.TestCase):
    def pump(self,center,condition,seconds=12):
        limit=time.monotonic()+seconds
        while time.monotonic()<limit:
            center.root.update();time.sleep(.01)
            if condition():return
        self.fail('Wizard did not settle')

    def test_select_auto_preview_range_identity_undo_and_reuse(self):
        from PIL import Image,ImageDraw,ImageFont
        from control_center import ControlCenter
        from control_video import show
        image=Image.new('RGB',(640,360));ImageDraw.Draw(image).text((470,279),'KPH',font=ImageFont.truetype('arial.ttf',28),fill='white')
        event=dict(track='Fuji Speedway',track_layout='Fuji Speedway',track_length_m=4535.8)
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as scratch,patch('control_center.ROOT',Path(scratch)),patch('library.inventory',return_value=[event]),patch('video_media.probe',return_value=dict(path=str(Path(scratch)/'富士.mp4'),width=640,height=360,duration=105)),patch('video_media.preview',return_value=image):
            center=ControlCenter();errors=[];center.root.report_callback_exception=lambda *args:errors.append(args)
            try:
                w=show(center,Path(scratch)).video_wizard
                self.pump(center,lambda:bool(w.identities))
                with patch('control_video.filedialog.askopenfilename',return_value=str(Path(scratch)/'富士.mp4')):w.choose('video','video')
                self.pump(center,lambda:not w.busy)
                self.assertEqual(w.fields['end'].get(),'105.000000');self.assertEqual(w.fields['layout'].get(),'Fuji Speedway')
                self.assertFalse(w.manual_body.winfo_manager());self.assertFalse(w.tools_body.winfo_manager())
                w.loaded_sample=3.2;w.mark_range('start');self.assertEqual(w.fields['start'].get(),'3.200000')
                w.loaded_sample=104.166667;w.mark_range('end');self.pump(center,lambda:not w.busy)
                self.assertLess(float(w.fields['sample'].get()),float(w.fields['end'].get()))
                w.geometry={'throttle':dict(points=[[450,220],[410,260],[410,180]])};w.clicks=[[5,6]];w.target.set('brake');w.save_undo()
                w.geometry['brake']=dict(points=[[550,220],[590,180],[590,260]]);w.advance_target();self.assertEqual(w.target.get(),'anchor')
                w.undo_calibration();self.assertEqual(w.target.get(),'brake');self.assertNotIn('brake',w.geometry)
                w.request_frame(5);self.pump(center,lambda:not w.busy);self.assertEqual(w.clicks,[[5,6]])
                w.fields['sample'].set('invalid');w.next_preview();self.assertFalse(errors)
                w.fields['sample'].set('5');w.geometry.update(brake=dict(points=[[550,220],[590,180],[590,260]]),anchor=[470,279,536,310])
                remember(scratch,w.config(),image,w.media)
                w.selected_video();self.pump(center,lambda:not w.busy)
                self.assertEqual(set(w.geometry),{'throttle','brake','anchor'});self.assertIn('复用',w.status.get())
                self.assertFalse(errors,errors)
            finally:center.close()
