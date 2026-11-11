"""Offline policy, exact Windows-data compatibility and the shared desktop."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch,Mock
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


class Data(unittest.TestCase):
    def test_frozen_mac_switch_uses_launch_services_with_scoped_data(self):
        from simulators import launch
        # Built with the host's path flavour, so the Windows compatibility job runs it too.
        executable=str(Path('/Applications/LMU-Stintrix.app/Contents/MacOS/LMU-Stintrix'))
        with tempfile.TemporaryDirectory(dir=ROOT) as work,patch('sys.frozen',True,create=True),patch('sys.executable',executable):
            with patch('sys.platform','darwin'),patch('subprocess.Popen') as child:
                child.return_value.wait.return_value=0
                launch(work,'ac_evo')
                command=child.call_args.args[0]
                self.assertEqual(command[:4],['/usr/bin/open','-n','-a',str(Path(executable).parents[2])])
                self.assertIn('STINTRIX_SIMULATOR=ac_evo',command)
                self.assertIn('LMU_STINTRIX_DATA_DIR='+str(Path(work).resolve()),command)
                self.assertIn('PYINSTALLER_RESET_ENVIRONMENT=1',command)
            with patch('sys.platform','win32'),patch('subprocess.Popen') as child:
                launch(work,'lmu')
                self.assertEqual(child.call_args.args[0],[sys.executable])

    def test_failed_mac_launch_services_restores_selection(self):
        from simulators import launch
        with tempfile.TemporaryDirectory(dir=ROOT) as work,patch('sys.frozen',True,create=True),patch('sys.executable','/Applications/LMU-Stintrix.app/Contents/MacOS/LMU-Stintrix'),patch('sys.platform','darwin'),patch('subprocess.Popen') as child:
            path=Path(work)/'simulator_settings.json';before=b'{"simulator":"lmu"}';path.write_bytes(before)
            child.return_value.wait.return_value=1
            with self.assertRaises(OSError):launch(work,'ac_evo')
            self.assertEqual(path.read_bytes(),before)

    def test_frozen_mac_app_keeps_its_bundle_dock_icon(self):
        import branding
        root=Mock()
        with patch('sys.platform','darwin'),patch('sys.frozen',True,create=True):branding.apply(root)
        # Tk's iconphoto would replace the rounded .icns Dock icon with square 128 px PNGs.
        root.iconphoto.assert_not_called();root.iconbitmap.assert_not_called()
        root=Mock()
        with patch('sys.platform','win32'),patch('sys.frozen',True,create=True),patch('tkinter.PhotoImage'):branding.apply(root)
        root.iconphoto.assert_called_once()

    def test_game_marks_without_installed_games_use_the_lmu_vector_and_a_real_font(self):
        import simulator_icons
        from PIL import ImageFont
        with patch.object(ImageFont,'load_default',side_effect=AssertionError('PIL fallback font')):
            lmu=simulator_icons.pixels('lmu',64,None,None);evo=simulator_icons.pixels('ac_evo',64,None,None)
        self.assertEqual((lmu.size,evo.size),((64,64),(64,64)))
        # The official LMU website mark (lmu_mark.py), not a text placeholder.
        red=sum(1 for r,g,b,a in lmu.getdata() if a>200 and r>200 and g<90 and b<120)
        self.assertGreater(red,300)

    def test_user_game_icon_is_kept_privately_validated_and_resettable(self):
        import simulator_icons
        from PIL import Image
        with tempfile.TemporaryDirectory(dir=ROOT) as work,patch.dict(os.environ,{'LMU_STINTRIX_DATA_DIR':work}):
            base=Path(work).resolve();original=base/'evo.ico'
            Image.new('RGBA',(64,64),(0,90,255,255)).save(original,sizes=[(64,64),(32,32)]);before=original.read_bytes()
            simulator_icons.source.cache_clear()
            try:
                target=simulator_icons.import_icon('ac_evo',original)
                self.assertEqual(target,base/'assets'/'simulators'/'ac_evo.png');self.assertEqual(original.read_bytes(),before)
                self.assertEqual(simulator_icons.source('ac_evo'),target)
                image=simulator_icons.pixels('ac_evo',32,str(target),(target.stat().st_size,target.stat().st_mtime_ns))
                self.assertEqual(image.getpixel((16,16))[:3],(0,90,255))
                (base/'notes.txt').write_text('not an image')
                with self.assertRaises(ValueError):simulator_icons.import_icon('ac_evo',base/'notes.txt')
                self.assertEqual(simulator_icons.source('ac_evo'),target)
                simulator_icons.reset_icon('ac_evo')
                self.assertFalse(target.exists());self.assertIsNone(simulator_icons.custom_icon('ac_evo'))
            finally:simulator_icons.source.cache_clear()

    @unittest.skipUnless(os.name=='posix','POSIX stand-in for the Vision helper')
    def test_first_mac_ocr_request_allows_model_preparation_then_uses_normal_timeout(self):
        import paths,video_ocr
        from PIL import Image
        with tempfile.TemporaryDirectory(dir=ROOT) as work:
            helper=Path(work)/'tools'/'vision-ocr';helper.parent.mkdir()
            # Like Vision: ready at once; every recognition then takes 0.6 s here.
            helper.write_text('#!/bin/sh\necho \'{"ready":true}\'\nwhile IFS= read -r line; do sleep 0.6; echo \'{"texts":["42"]}\'; done\n')
            helper.chmod(0o755)
            with patch.object(paths,'ASSETS',Path(work)),patch.object(video_ocr.MacOCR,'first_recognition_timeout',3,create=True),\
                    patch.object(video_ocr.MacOCR,'recognition_timeout',.3,create=True):
                ocr=video_ocr.MacOCR()
                try:
                    with Image.new('RGB',(40,20),'white') as image:
                        self.assertEqual(ocr.recognize([image],work),['42'])
                        with self.assertRaisesRegex(ValueError,'超时'):ocr.recognize([image],work)
                finally:ocr.close()
        # Measured cold Vision preparation exceeded 15 s on an M5; Windows timing stays unchanged.
        self.assertGreaterEqual(video_ocr.MacOCR.first_recognition_timeout,60)
        self.assertEqual((video_ocr.WindowsOCR.first_recognition_timeout,video_ocr.WindowsOCR.recognition_timeout),(15,15))

    def test_relative_data_directory_stays_outside_the_signed_mac_bundle(self):
        import paths
        with tempfile.TemporaryDirectory(dir=ROOT) as work:
            work=Path(work).resolve();bundle=work/'LMU-Stintrix.app'/'Contents'/'MacOS';previous=os.getcwd();os.chdir(work)
            try:
                with patch.object(paths,'APP_ROOT',bundle),patch('sys.frozen',True,create=True),patch.dict(os.environ,{'LMU_STINTRIX_DATA_DIR':'Stintrix data'}):
                    with patch('sys.platform','darwin'):self.assertEqual(paths.base_data_directory(),work/'Stintrix data')
                    with patch('sys.platform','win32'):self.assertEqual(paths.base_data_directory(),bundle/'Stintrix data')
            finally:os.chdir(previous)

    def test_explicit_mac_compression_is_lossless_and_windows_keeps_its_backend(self):
        from offline_smoke import fixture
        from storage_actions import compress_local
        from telemetry_file import Path as ReadPath
        with tempfile.TemporaryDirectory(dir=ROOT) as work:
            source=fixture(Path(work)/'session');raw=(source/'inputs.csv').read_bytes();meta=(source/'session.json').read_bytes()
            with patch('sys.platform','darwin'),patch('session_compression.ntfs',return_value=False):result=compress_local(source)
            self.assertTrue(result['supported']);self.assertFalse(result['errors']);self.assertTrue((source/'inputs.csv.stc').is_file())
            self.assertEqual(ReadPath(source/'inputs.csv').read_bytes(),raw);self.assertEqual((source/'session.json').read_bytes(),meta)
            with patch('sys.platform','win32'),patch('session_compression.compress') as original:compress_local(source)
            original.assert_called_once_with(source)

    def test_folder_import_preserves_precision_sources_and_simulator_isolation(self):
        from session_import import import_folder
        from offline_smoke import fixture
        from column_store import convert
        from telemetry_file import Path as ReadPath
        with tempfile.TemporaryDirectory(dir=ROOT) as work:
            base=Path(work);source=fixture(base/'source');original={p.name:p.read_bytes() for p in source.iterdir()}
            result=import_folder(base/'library',source);target=Path(result['folder'])
            for name,blob in original.items():self.assertEqual((target/name).read_bytes(),blob)
            self.assertEqual(import_folder(base/'library',source)['status'],'skipped')
            with self.assertRaisesRegex(ValueError,'simulator'):import_folder(base/'other/Simulators/ac_evo',source)
            convert(source/'inputs.csv',replace=True)
            result=import_folder(base/'columnar',source);target=Path(result['folder'])
            self.assertFalse((target/'inputs.csv').exists())
            self.assertEqual(ReadPath(target/'inputs.csv').read_bytes(),original['inputs.csv'])
            self.assertEqual((source/'session.json').read_bytes(),original['session.json'])

    def test_folder_import_rejects_links_live_data_changes_and_rolls_back(self):
        import session_import as adapter
        from offline_smoke import fixture
        with tempfile.TemporaryDirectory(dir=ROOT) as work:
            base=Path(work);source=fixture(base/'source');meta=json.loads((source/'session.json').read_text())
            meta['status']='recording';(source/'session.json').write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError,'completed'):adapter.import_folder(base/'library',source)
            meta['status']='complete';(source/'session.json').write_text(json.dumps(meta))
            original=adapter.snapshot;calls=[]
            def changed(path):
                value=original(path);calls.append(1)
                if len(calls)>1:value['inputs.csv']=(0,0,0)
                return value
            with patch.object(adapter,'snapshot',side_effect=changed):
                with self.assertRaisesRegex(OSError,'changed'):adapter.import_folder(base/'library',source)
            self.assertEqual(list((base/'library/ImportedLogs').iterdir()),[])
            with patch.object(Path,'is_symlink',return_value=True):
                with self.assertRaisesRegex(ValueError,'link'):adapter.import_folder(base/'library',source)

    def test_mac_paths_renderer_open_and_windows_policy_are_separate(self):
        import paths,platform_runtime,renderer_config
        home=Path.home()
        with patch.dict(os.environ,{'HOME':str(home),'USERPROFILE':str(home)},clear=True),patch.object(paths.sys,'platform','darwin'),patch.object(paths,'local_settings',return_value={}):
            self.assertEqual(paths.base_data_directory(),(Path.home()/'Library/Application Support/LMU-Stintrix').resolve())
            self.assertTrue(platform_runtime.offline_only());self.assertNotIn(0,platform_runtime.page_ids())
            import tkinter
            with patch.object(tkinter,'TkVersion',8.6):self.assertEqual(platform_runtime.wheel_steps(Mock(delta=1)),1)
            self.assertEqual(renderer_config.resolve(),dict(mode='native',executable=''))
            with self.assertRaises(ValueError):renderer_config.resolve('racecom')
            with patch('platform_runtime.subprocess.Popen') as launch:platform_runtime.open_path(ROOT/'README.md')
            self.assertEqual(launch.call_args.args[0],['/usr/bin/open',str(ROOT/'README.md')])
        with patch.dict(os.environ,{'STINTRIX_OFFLINE':'0'}),patch.object(platform_runtime.sys,'platform','win32'):
            self.assertFalse(platform_runtime.offline_only());self.assertEqual(platform_runtime.page_ids(),(0,1,6,4,5,3,2))
            self.assertEqual(platform_runtime.wheel_steps(Mock(delta=120)),1)
            with patch.object(os,'startfile',create=True) as launch:platform_runtime.open_path(ROOT/'README.md')
            launch.assert_called_once_with(ROOT/'README.md')

    def test_portable_png_and_achievement_card_with_real_model(self):
        from offline_smoke import fixture
        from race_model import build_model
        import race_images
        from pillow_png import Canvas
        from PIL import Image
        with tempfile.TemporaryDirectory(dir=ROOT) as work:
            base=Path(work);model=build_model(fixture(base/'session'))
            with patch.object(race_images,'Canvas',Canvas):
                for name,canvas in race_images.pages(model):
                    canvas.save(base/name)
                    with Image.open(base/name) as image:self.assertGreater(image.height,600);image.verify()
            from achievement_card import compose
            with patch('sys.platform','darwin'):
                image=compose(dict(title='圈速纪录',track='测试赛道',layout='GP',vehicle='GT3',group='GT3',time='0:10.000',
                    time_label='个人最快圈',footer_label='本机记录',conditions=[],result='第 1 圈',context='完整圈'))
                self.assertEqual(image.size,(1920,1080));image.close()

    def test_cli_version_is_lazy_and_realtime_flags_are_rejected_offline(self):
        code="import sys;sys.path.insert(0,'src');import inputscope;assert not {'engine','telemetry','hud','tkinter'}.intersection(sys.modules);inputscope.main()"
        with tempfile.TemporaryDirectory(dir=ROOT) as work:
            env={**os.environ,'STINTRIX_OFFLINE':'1','LMU_STINTRIX_DATA_DIR':work,'STINTRIX_SIMULATOR':'lmu'}
            result=subprocess.run([sys.executable,'-c',code,'--version'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([sys.executable,'-c',code,'--hud'],cwd=ROOT,env=env,capture_output=True,text=True,timeout=10)
            self.assertNotEqual(result.returncode,0);self.assertIn('does not start capture',result.stderr)


class UI(unittest.TestCase):
    def test_offline_preferences_import_and_reset_a_game_icon_in_the_selector(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as work,patch.dict(os.environ,{'STINTRIX_OFFLINE':'1','LMU_STINTRIX_DATA_DIR':work,'STINTRIX_SIMULATOR':'lmu'}):
            import control_center as cc,control_offline,simulator_icons
            from PIL import Image
            icon=Path(work)/'evo.png';Image.new('RGBA',(40,40),(0,90,255,255)).save(icon)
            simulator_icons.source.cache_clear()
            with patch.object(cc,'ROOT',Path(work)),patch.object(cc,'SIMULATOR','lmu'):
                app=cc.ControlCenter();errors=[];app.root.report_callback_exception=lambda *e:errors.append(str(e[1]))
                try:
                    app.show_page(2);app.root.update()
                    default=app.simulator_selector.images['ac_evo']
                    with patch.object(control_offline.filedialog,'askopenfilename',return_value=str(icon)):control_offline.choose_icon(app,'ac_evo')
                    chosen=app.simulator_selector.images['ac_evo']
                    self.assertIsNot(chosen,default);self.assertEqual((chosen.width(),chosen.height()),(default.width(),default.height()))
                    self.assertEqual(simulator_icons.source('ac_evo'),Path(work).resolve()/'assets'/'simulators'/'ac_evo.png')
                    control_offline.reset_icons(app)
                    self.assertIsNone(simulator_icons.custom_icon('ac_evo'));self.assertIsNot(app.simulator_selector.images['ac_evo'],chosen)
                    self.assertFalse(errors,errors)
                finally:app.close();simulator_icons.source.cache_clear()

    def test_wheel_units_follow_the_tk_aqua_convention_and_scroll_pages_match_the_main_view(self):
        import tkinter as tk
        from platform_runtime import wheel_steps
        from control_video_widgets import ScrollPage
        from control_widgets import px
        root=tk.Tk();root.withdraw()
        try:
            page=ScrollPage(root);moves=[]
            with patch.object(page.scroller,'add',moves.append):
                # Tk 8.6 Aqua reports line deltas; Windows and Tk 9 report 120 per notch.
                with patch('sys.platform','darwin'),patch.object(tk,'TkVersion',8.6):
                    self.assertEqual(wheel_steps(Mock(delta=2)),2);page.wheel(1)
                with patch('sys.platform','darwin'),patch.object(tk,'TkVersion',9.0):
                    self.assertEqual(wheel_steps(Mock(delta=240)),2);page.wheel(120)
                with patch('sys.platform','win32'),patch.object(tk,'TkVersion',8.6):
                    self.assertEqual(wheel_steps(Mock(delta=240)),2);page.wheel(120)
            self.assertEqual(moves,[-px(page,20),-px(page,20),-px(page,68)])
        finally:root.destroy()

    @unittest.skipUnless(sys.platform=='darwin','Tk Aqua trackpad events')
    def test_tk9_trackpad_scroll_replays_through_existing_wheel_bindings(self):
        import tkinter as tk
        if tk.TkVersion<9:self.skipTest('Tk 8.6 reports trackpads as MouseWheel')
        from platform_runtime import install_touchpad
        root=tk.Tk();root.geometry('240x160+40+40')
        try:
            canvas=tk.Canvas(root,width=120,height=80);canvas.pack();text=tk.Text(root,height=2);text.pack();root.update()
            wheels=[];root.bind_all('<MouseWheel>',lambda e:wheels.append((e.widget,e.delta,e.state&1)))
            install_touchpad(root)
            for widget in (canvas,text):
                widget.event_generate('<TouchpadScroll>',delta=((3&0xFFFF)<<16)|(-5&0xFFFF),x=5,y=5,when='now')
            root.update()
            # Pixel-precise deltas become 20 px/line wheel steps; native widgets keep Tk's own handling.
            self.assertEqual(wheels,[(canvas,-30,0),(canvas,18,1)])
        finally:root.destroy()

    def test_offline_navigation_draws_a_distinct_icon_for_every_page(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as work,patch.dict(os.environ,{'STINTRIX_OFFLINE':'1','LMU_STINTRIX_DATA_DIR':work,'STINTRIX_SIMULATOR':'lmu'}):
            import control_center as cc,control_shell
            with patch.object(cc,'ROOT',Path(work)),patch.object(cc,'SIMULATOR','lmu'):
                app=cc.ControlCenter()
                try:
                    navigation=app.shell.navigation;kinds=[]
                    with patch.object(control_shell,'symbol',lambda canvas,kind,*rest:kinds.append(kind)):
                        navigation.paint_key=None;navigation.paint()
                    self.assertEqual(len(kinds),len(navigation.names))
                    # Preferences reuse the settings glyph of the Windows page they replace.
                    self.assertEqual(len(set(kinds)),len(kinds),list(zip(navigation.names,kinds)))
                finally:app.close()

    @unittest.skipUnless(sys.platform=='darwin','Native Command bindings')
    def test_command_number_switches_pages_with_toplevel_focus(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as work,patch.dict(os.environ,{'LMU_STINTRIX_DATA_DIR':work,'STINTRIX_SIMULATOR':'lmu'}):
            import control_center as cc
            with patch.object(cc,'ROOT',Path(work)),patch.object(cc,'SIMULATOR','lmu'):
                app=cc.ControlCenter()
                try:
                    # Command+3 opens the rail's third entry (the v0.4.2 order follows page_ids).
                    from platform_runtime import page_ids
                    target=page_ids()[2]
                    app.root.update();app.root.focus_force();app.root.update()
                    app.root.event_generate('<Command-Key-3>')
                    until=time.monotonic()+2
                    while app.page!=target and time.monotonic()<until:app.root.update();time.sleep(.01)
                    self.assertEqual(app.page,target)
                finally:app.close()

    def test_offline_pages_palette_and_preferences_in_both_games(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as work,patch.dict(os.environ,{'STINTRIX_OFFLINE':'1','LMU_STINTRIX_DATA_DIR':work,'STINTRIX_SIMULATOR':'lmu'}):
            import control_center as cc
            from platform_runtime import page_ids
            from control_palette import commands
            from paths import base_data_directory
            from simulators import root_for
            for simulator in ('lmu','ac_evo'):
                root=root_for(Path(work),simulator);root.mkdir(parents=True,exist_ok=True)
                with patch.object(cc,'ROOT',root),patch.object(cc,'SIMULATOR',simulator):
                    app=cc.ControlCenter();errors=[]
                    app.root.report_callback_exception=lambda *e:errors.append(str(e[1]))
                    try:
                        self.assertEqual(app.page,1);self.assertEqual(app.visible_pages,page_ids());self.assertFalse(app.active())
                        for page in page_ids():
                            app.show_page(page);until=time.monotonic()+12
                            while not app.pages.active.complete and time.monotonic()<until:app.root.update();time.sleep(.01)
                            self.assertTrue(app.pages.active.complete,(simulator,page,errors));self.assertFalse(app.pages.active.failed)
                        ids={item.key for item in commands(app)}
                        self.assertFalse({'start','demo','layouts','shortcuts','interface','page:0'} & ids)
                        self.assertTrue({'import-folder','import-package','page:6'}<=ids)
                        self.assertEqual(next(item.shortcut for item in commands(app) if item.key=='page:1'),
                            'Cmd+1' if sys.platform=='darwin' else 'Ctrl+1')
                        app.shortcut_sheet.open();app.root.update();app.shortcut_sheet.close()
                        app.set_theme('light');app.toggle_language();app.root.update()
                        self.assertFalse(errors,errors)
                    finally:app.close()
