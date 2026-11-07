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
            self.assertEqual(platform_runtime.wheel_steps(Mock(delta=1)),1)
            self.assertEqual(renderer_config.resolve(),dict(mode='native',executable=''))
            with self.assertRaises(ValueError):renderer_config.resolve('racecom')
            with patch('platform_runtime.subprocess.Popen') as launch:platform_runtime.open_path(ROOT/'README.md')
            self.assertEqual(launch.call_args.args[0],['/usr/bin/open',str(ROOT/'README.md')])
        with patch.dict(os.environ,{'STINTRIX_OFFLINE':'0'}),patch.object(platform_runtime.sys,'platform','win32'):
            self.assertFalse(platform_runtime.offline_only());self.assertEqual(platform_runtime.page_ids(),tuple(range(7)))
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
                        app.shortcut_sheet.open();app.root.update();app.shortcut_sheet.close()
                        app.set_theme('light');app.toggle_language();app.root.update()
                        self.assertFalse(errors,errors)
                    finally:app.close()
