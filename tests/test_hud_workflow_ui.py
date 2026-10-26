"""Native layout editing, continued demo recording and post-session actions."""
import json,os,time,unittest
from pathlib import Path
from unittest.mock import patch
import tests.test_ui_efficiency as efficiency


@unittest.skipUnless(os.name=='nt','Windows Tk')
class WorkflowUITests(unittest.TestCase):
    app=efficiency.EfficiencyTests.app
    pump=efficiency.EfficiencyTests.pump
    def test_editor_save_copy_restore_and_shortcut_validation(self):
        from control_layouts import show
        from control_shortcuts import show as shortcuts
        from hud_layouts import LayoutStore
        app,root,errors=self.app();window=show(app);self.pump(app)
        window.layout_name.set('Practice');window.layout_fields['x'].set('123');window.layout_save()
        store=LayoutStore(root);self.assertEqual(store.current()['panels']['main']['x'],123)
        window.layout_fields['x'].set('456');window.layout_save();window.layout_restore()
        self.assertEqual(store.current()['panels']['main']['x'],123)
        window.destroy();window=shortcuts(app);self.pump(app)
        window.shortcut_fields['visibility'].set('Ctrl+A');window.shortcut_fields['lock'].set('Ctrl+A');window.shortcut_save()
        self.assertFalse((root/'hotkey_settings.json').exists())
        self.assertIn('相同快捷键',window.shortcut_status.get());self.assertFalse(errors)
    def test_layout_and_visibility_keep_same_engine_recorder_and_continuous_file(self):
        from hud_layouts import defaults,LayoutStore
        from layout_actions import save,select
        from hud_presentation import capture
        app,root,errors=self.app()
        with patch('hud.ROOT',root),patch('engine.ROOT',root),patch('recorder.make_report'):
            app.start(True);hud=app.hud;engine=hud.engine;recorder=engine.recorder
            deadline=time.monotonic()+5
            while recorder.samples<=10 and time.monotonic()<deadline:self.pump(app,.1)
            self.assertGreater(recorder.samples,10);before=recorder.samples;folder=recorder.folder
            snapshot=capture(hud);snapshot['panels']['main'].update(x=150,width=700,opacity=.7)
            snapshot['panels']['weather']['visible']=True
            save(root,hud,'Race',snapshot);self.pump(app,.2)
            self.assertEqual(hud.endurance_panels.windows['weather'].state(),'normal')
            self.assertFalse(hud.weather_on.get());self.assertFalse(hud.endurance_settings['weather_enabled'])
            app.shortcuts.invoke('visibility');self.assertEqual(hud.root.state(),'withdrawn')
            self.pump(app,.15);app.shortcuts.invoke('visibility');self.assertEqual(hud.root.state(),'normal')
            select(root,hud,'Race');self.pump(app,.15)
            self.assertIs(hud.engine,engine);self.assertIs(engine.recorder,recorder);self.assertEqual(recorder.folder,folder)
            self.assertGreater(recorder.samples,before);self.assertEqual(len(list((root/'DemoLogs').iterdir())),1)
            self.assertAlmostEqual(float(hud.root.attributes('-alpha')),.7,delta=.01)
            self.assertFalse((root/'vehicle_settings.json').exists());self.assertFalse((root/'endurance_settings.json').exists());self.assertFalse(errors)
    def test_post_session_toolbar_opens_exact_ready_report_and_stays_disabled_while_building(self):
        from report_state import remember
        from control_recent_session import update
        app,root,errors=self.app();folder=root/'Logs'/'done';folder.mkdir(parents=True)
        meta=dict(status='complete',source='LMU',track='Monza',vehicle='720S');(folder/'session.json').write_text(json.dumps(meta))
        original=(folder/'session.json').read_bytes();app.recent.folder=folder;app.recent.meta=meta
        remember(folder,dict(state='building',steps={},updated_utc='one'));update(app);self.pump(app,.1)
        label,buttons=app.recent_widgets;self.assertFalse(buttons['review'].enabled);self.assertFalse(buttons['laps'].enabled);self.assertTrue(buttons['note'].enabled)
        (folder/'review.html').write_text('fixture');remember(folder,dict(state='building',steps=dict(review=dict(state='ready')),updated_utc='two'));update(app)
        with patch('control_recent_session.os.startfile') as opened:
            buttons['review'].invoke();opened.assert_called_once_with(folder/'review.html')
        self.assertEqual((folder/'session.json').read_bytes(),original);self.assertFalse(errors)
    def test_saved_layout_restores_on_next_hud_start_without_resetting_base_preferences(self):
        from hud_layouts import defaults,LayoutStore
        app,root,errors=self.app();snapshot=defaults();snapshot.update(mode='curves');snapshot['panels']['main']['opacity']=.6
        snapshot['panels']['weather']['visible']=True;LayoutStore(root).save('Recording',snapshot,defaults())
        with patch('hud.ROOT',root),patch('engine.ROOT',root),patch('recorder.make_report'):
            app.start(True);self.pump(app,.2);hud=app.hud
            self.assertEqual(hud.hud_mode.get(),'curves');self.assertAlmostEqual(float(hud.root.attributes('-alpha')),.6,delta=.01)
            self.assertEqual(hud.endurance_panels.windows['weather'].state(),'normal');self.assertFalse(hud.endurance_settings['weather_enabled'])
            self.assertFalse(errors)
