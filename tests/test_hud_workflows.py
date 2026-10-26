"""Presentation changes preserve recording; shortcuts and backups fail atomically."""
import json,os,sys,tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from hud_layouts import LayoutStore,defaults,normalize
from native_hotkeys import Registration
from shortcut_keys import validate,parse,legacy_state
from recent_session import RecentSession,remember


class WorkflowTests(unittest.TestCase):
    def test_layout_switch_backup_restores_unsaved_runtime_and_profile_catalog(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as d:
            store=LayoutStore(d);a=defaults();store.save('Practice',a,a)
            b=defaults();b['panels']['weather']['visible']=True;store.save('Race',b,a)
            unsaved=defaults();unsaved['panels']['main']['opacity']=.6
            store.select('Practice',unsaved);checkpoint=store.load()['history'][-1]['id']
            restored=store.restore(checkpoint,b)
            self.assertEqual(restored,unsaved);self.assertEqual(store.load()['active'],'Race')
            self.assertEqual(store.current(),unsaved);self.assertEqual(store.load()['profiles']['Race'],b)
    def test_overwrite_and_history_are_bounded_and_input_is_not_mutated(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as d:
            store=LayoutStore(d);a=defaults();store.save('A',a,a)
            for i in range(20):
                snapshot=defaults();snapshot['panels']['main']['x']=i;store.save('A',snapshot,a)
            self.assertEqual(a,defaults());self.assertEqual(len(store.load()['history']),12)
            self.assertEqual(store.load()['history'][-1]['profiles']['A']['panels']['main']['x'],18)
    def test_bad_layout_and_failed_write_preserve_existing_file(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as d:
            store=LayoutStore(d);store.save('A',defaults(),defaults());before=store.path.read_bytes()
            with patch('hud_layouts.atomic_json',side_effect=OSError('disk full')):
                with self.assertRaises(OSError):store.select('A',defaults())
            self.assertEqual(before,store.path.read_bytes())
            store.path.write_bytes(b'broken original')
            with self.assertRaises(ValueError):store.save('B',defaults(),defaults())
            self.assertEqual(store.path.read_bytes(),b'broken original')
            for value in (float('nan'),float('inf'),True):
                invalid=defaults();invalid['panels']['main']['x']=value
                with self.assertRaises(ValueError):normalize(invalid)
    def test_registration_swap_reuses_keys_and_conflict_keeps_original(self):
        taken=set();released=[]
        def register(i,m,k):
            if (m,k) in taken:return False
            taken.add((m,k));return True
        r=Registration(register,lambda i:released.append(i))
        self.assertTrue(r.update(dict(a='Ctrl+F1',b='Ctrl+F2'))['ok']);before=dict(r.combos)
        self.assertTrue(r.update(dict(b='Ctrl+F1',a='Ctrl+F2'))['ok']);self.assertEqual(before,r.combos)
        taken.add((2,ord('X')))
        self.assertFalse(r.update(dict(a='Ctrl+F3',b='Ctrl+X'))['ok']);self.assertEqual(before,r.combos)
        self.assertTrue(released);self.assertEqual(set(r.actions.values()),{'a','b'})
    def test_shortcuts_validate_disabled_duplicate_and_reserved_keys(self):
        self.assertEqual(parse('shift+ctrl+f9')[0],'Ctrl+Shift+F9')
        self.assertEqual(validate(dict(enabled=False,bindings=dict(center='')))['bindings']['center'],'')
        for text in ('F9','Ctrl+F12','Alt+F4','Ctrl+Ctrl+A','Win+F1','Ctrl+Tab'):
            with self.assertRaises(ValueError):parse(text)
        with self.assertRaises(ValueError):validate(dict(bindings=dict(visibility='Ctrl+A',lock='Ctrl+A')))
    def test_modifier_chord_does_not_leak_into_legacy_key_after_modifier_release(self):
        values={0x78:0x8001,0x11:0x8000};app=SimpleNamespace(user32=SimpleNamespace(GetAsyncKeyState=lambda key:values.get(key,0)))
        self.assertEqual(legacy_state(app,0x78),0)
        values[0x11]=0;self.assertEqual(legacy_state(app,0x78),0)
        values[0x78]=0;self.assertEqual(legacy_state(app,0x78),0)
        values[0x78]=0x8001;self.assertEqual(legacy_state(app,0x78),0x8001)
    def test_recent_actions_wait_for_each_report_and_keep_source_bytes(self):
        from report_state import remember as receipt
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as d:
            root=Path(d);folder=root/'Logs'/'real';folder.mkdir(parents=True)
            (folder/'session.json').write_text(json.dumps(dict(status='complete',source='LMU',track='Monza',vehicle='720S')),encoding='utf8')
            (folder/'inputs.csv').write_bytes(b'original,precision\r\n1,0.123456789012345\r\n');original=(folder/'inputs.csv').read_bytes()
            tracker=RecentSession(root);tracker.observe(SimpleNamespace(engine=SimpleNamespace(last_folder=folder)))
            receipt(folder,dict(state='building',steps={},updated_utc='1'));state=tracker.state();self.assertTrue(state['note']);self.assertFalse(state['review'])
            (folder/'review.html').write_text('review');receipt(folder,dict(state='building',steps=dict(review=dict(state='ready')),updated_utc='2'))
            self.assertTrue(tracker.state()['review']);self.assertFalse(tracker.state()['laps'])
            (folder/'圈速单.png').write_bytes(b'fixture');receipt(folder,dict(state='ready',steps=dict(review=dict(state='ready'),images=dict(state='ready')),updated_utc='3'))
            self.assertTrue(tracker.state()['laps']);self.assertEqual(RecentSession(root).folder,folder.resolve())
            self.assertEqual((folder/'inputs.csv').read_bytes(),original)
    def test_demo_failed_and_outside_sessions_never_replace_recent_real_session(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as d:
            root=Path(d);real=root/'Logs'/'real';real.mkdir(parents=True)
            (real/'session.json').write_text(json.dumps(dict(status='complete',source='LMU')));remember(root,real)
            before=(root/'recent_session.json').read_bytes()
            for name,status,source in [('demo','complete','Synthetic demo'),('failed','write_error','LMU')]:
                folder=root/'Logs'/name;folder.mkdir();(folder/'session.json').write_text(json.dumps(dict(status=status,source=source)))
                self.assertIsNone(remember(root,folder))
            self.assertIsNone(remember(root,root.parent));self.assertEqual(before,(root/'recent_session.json').read_bytes())
    def test_recent_pointer_write_failure_does_not_lose_current_session(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as d:
            root=Path(d);folder=root/'Logs'/'finished';folder.mkdir(parents=True)
            (folder/'session.json').write_text(json.dumps(dict(status='complete',source='LMU')))
            tracker=RecentSession(root)
            with patch('recent_session.atomic_json',side_effect=OSError('disk full')):
                tracker.observe(SimpleNamespace(engine=SimpleNamespace(last_folder=folder)))
            self.assertEqual(tracker.folder,folder.resolve())


@unittest.skipUnless(os.name=='nt','Win32 native integration')
class NativeShortcutTests(unittest.TestCase):
    def test_os_conflict_dispatch_and_cleanup(self):
        from native_hotkeys import NativeHotkeys
        first=NativeHotkeys();second=NativeHotkeys();self.addCleanup(first.close);self.addCleanup(second.close)
        def configure(service):
            result=[];service.configure(dict(center='Ctrl+Alt+Shift+F24'),result.append);deadline=time.monotonic()+3
            while not result and time.monotonic()<deadline:service.drain();time.sleep(.01)
            self.assertTrue(result);return result[0]
        self.assertTrue(configure(first)['ok']);self.assertFalse(configure(second)['ok'])
        first.user.PostThreadMessageW(first.thread_id,0x312,101,0);deadline=time.monotonic()+2;actions=[]
        while not actions and time.monotonic()<deadline:actions+=first.drain();time.sleep(.01)
        self.assertEqual(actions,['center']);first.close();self.assertFalse(first.thread.is_alive());self.assertTrue(configure(second)['ok'])


if __name__=='__main__':unittest.main()
