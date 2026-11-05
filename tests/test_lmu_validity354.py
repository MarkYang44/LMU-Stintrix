"""LMU pending verdicts and repeated-number outlaps in the original renderer."""
import builtins,csv,json,sys,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


class Rules(unittest.TestCase):
    def test_frozen_renderer_loader_upgrades_only_our_footer_without_pkgutil(self):
        from racecom_validity import prepare,LEGACY_SUFFIX
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            base=Path(temp);hooks=base/'_customization/racecom_hooks.py';hooks.parent.mkdir()
            prefix=('import os\nROOT='+repr(str(base))+"\ndef install_image(ns): ns['custom_preserved']=True\n").encode()
            original=prefix+LEGACY_SUFFIX.encode();hooks.write_bytes(original)
            assets=base/'assets';assets.mkdir();(assets/'racecom_validity_hook.py').write_text("def install(ns): ns['adapter_loaded']=True\n",'utf-8')
            with patch('racecom_validity.ASSETS',assets):prepare(base/'Image Generate.exe')
            updated=hooks.read_bytes();self.assertTrue(updated.startswith(prefix));self.assertEqual(updated.count(b'# STINTRIX_GAME_VALIDITY_V1'),1)
            self.assertTrue(any(p.read_bytes()==original for p in (base/'_stintrix_validity_history').iterdir()))
            original_import=builtins.__import__
            def limited_import(name,*args,**kwargs):
                if name in ('pkgutil','runpy'):raise ModuleNotFoundError(name)
                return original_import(name,*args,**kwargs)
            with patch('builtins.__import__',side_effect=limited_import):
                ns={};exec(compile(updated,str(hooks),'exec'),ns);value={};ns['install_image'](value)
            self.assertEqual(value,dict(custom_preserved=True,adapter_loaded=True))
            with patch('racecom_validity.ASSETS',assets):prepare(base/'Image Generate.exe')
            self.assertEqual(hooks.read_bytes(),updated)

    def test_lmu_pending_is_invalid_in_rows_events_bridge_and_best_without_source_edits(self):
        from tests.test_core import Tests
        from race_model import build_model,describe,lap_status
        from racecom_bridge import adapt
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            folder=Tests().lap_csv(Path(temp)/'session');initial=build_model(folder);best=initial['fastest']
            value={k:best.get(k) for k in ('num','time','start','telemetry_lap','s1','s2','s3')}
            value.update(valid=None,partial=False,in_pits=False)
            with (folder/'race_events.csv').open('w',encoding='utf-8',newline='') as stream:
                writer=csv.writer(stream);writer.writerow(('session_time_s','event','payload_json'));writer.writerow((best['start']+best['time'],'official_lap',json.dumps(value)))
            before={p:p.read_bytes() for p in (folder/'inputs.csv',folder/'session.json',folder/'race_events.csv')}
            model=build_model(folder);lap=next(l for l in model['laps'] if l['start']==best['start']);self.assertIs(lap['valid'],False);self.assertIs(lap['game_valid'],False)
            self.assertFalse(lap['best']);self.assertIn('无效',lap_status(lap));self.assertNotIn('待确认',lap_status(lap))
            self.assertIn('无效',describe(model['events'][0]));self.assertNotIn('待确认',describe(model['events'][0]))
            item=next(l for l in adapt(model)['laps'] if l['num']==best['num'])
            self.assertIs(item['game_valid'],False);self.assertFalse(item['statistics_eligible']);self.assertIn('无效',item['note'])
            self.assertEqual({p:p.read_bytes() for p in before},before)

    def test_lmu_pil_statistics_keep_duplicate_numbers_times_and_outlap_notes_separate(self):
        from racecom_validity_hook import install,matched
        class Lap:
            __slots__=('num','time','valid','best','delta','extra_note')
            def __init__(self,n,t):self.num=n;self.time=t;self.valid=True;self.best=False;self.delta=None;self.extra_note=''
        class Sheet:
            def __init__(self,path):self.source=path;self.laps=[Lap(1,51.390),Lap(1,132.568),Lap(17,100.954)]
            @property
            def reference_best(self):return min((l.time for l in self.laps if l.valid),default=None)
            def best_lap(self):return next((l for l in self.laps if l.valid and l.time==self.reference_best),None)
            def best_sector(self,key):return None,0
        def recompute(sheet):
            for lap in sheet.laps:lap.best=lap.valid and lap.time==sheet.reference_best;lap.delta=lap.time-sheet.reference_best if lap.valid else None
        class Pil:
            def __init__(self,sheet):self.sheet=sheet
            def rows(self):return [(str(l.num),str(l.time),'','10.0' if l.time<60 else '26.4','37.0','36.8','') for l in self.sheet.laps]
        class Log:
            def _lap_row_flags(self,rows):return next((i for i,r in enumerate(rows) if '无效' not in r[6]),None),{}
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            path=Path(temp)/'laps.xlsx';items=[dict(num=n,time=t,game_valid=True,statistics_eligible=e,note=note) for n,t,e,note in ((1,51.39,False,'部分记录 / PIT'),(1,132.56814575195312,True,'完整圈'),(17,100.954345703125,True,'最快'))]
            (path.parent/'race_log.json').write_text(json.dumps(dict(stintrix_validity_policy=1,simulator_id='lmu',laps=items)),'utf-8')
            ns=dict(LapSheet=Sheet,load_lap_sheet=Sheet,recompute_lap_flags=recompute,LapSheetPilRenderer=Pil,RaceLogRenderer=Log,parse_lap_time=float)
            install(ns);sheet=ns['load_lap_sheet'](path);rows=Pil(sheet).rows()
            self.assertEqual(sheet.best_lap().num,17);self.assertEqual(sheet.reference_best,100.954);self.assertFalse(sheet.laps[0].best);self.assertIsNone(sheet.laps[0].delta)
            self.assertEqual(rows[0][6],'部分记录 / PIT');self.assertEqual(rows[1][6],'完整圈');self.assertEqual(str(rows[0][1]),'51.39')
            self.assertEqual(ns['parse_lap_time'](rows[0][1]),0.0);self.assertEqual(ns['parse_lap_time'](rows[1][1]),132.568)
            self.assertEqual(ns['parse_lap_time'](rows[0][3]),0.0);self.assertEqual(ns['parse_lap_time'](rows[1][3]),26.4)
            self.assertEqual(ns['parse_lap_time']('51.39'),51.39)
            repeated=[dict(num=1,time=51.39,statistics_eligible=False),dict(num=1,time=51.39,statistics_eligible=True)]
            self.assertEqual([r['statistics_eligible'] for _,r in matched([(1,'0:51.390'),(1,'0:51.390')],repeated,lambda r:r)],[False,True])
