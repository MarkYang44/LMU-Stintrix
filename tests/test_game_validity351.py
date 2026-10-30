"""Game-first decisions, pending legacy evidence, and separate renderer stats."""
import csv,json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


class Rules(unittest.TestCase):
    def test_evo_two_native_flags_positive_wins_and_pending_is_saved_losslessly(self):
        from tests.test_simulators import frame
        from acevo import extract
        from recorder import Recorder
        from column_store import convert
        from telemetry_file import Path as TPath
        p,g,s,_=frame();expected=[]
        for positive,negative,invalid in ((1,0,False),(1,1,False),(0,1,True),(0,0,None)):
            g.is_valid_lap=positive;g.timing_state.is_invalid=negative
            v=extract(p,g,s,float(len(expected)));self.assertIs(v['lap_invalidated'],invalid)
            self.assertEqual(v['native']['evo_is_valid_lap'],positive);self.assertEqual(v['native']['evo_timing_invalid'],negative)
            expected.append(v)
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp,patch.object(Recorder,'_report',staticmethod(lambda folder:None)):
            rec=Recorder(Path(temp)/'Logs');rec.start(expected[0])
            for sample in expected:self.assertTrue(rec.add(sample))
            rec.finish('test')
            for worker in rec.pending_reports:worker.join(5)
            source=rec.folder/'inputs.csv';before=source.read_bytes()
            with source.open(encoding='utf-8-sig',newline='') as stream:rows=list(csv.DictReader(stream))
            self.assertEqual([r['lap_invalidated'] for r in rows],['0','0','1',''])
            self.assertEqual([(r['evo_is_valid_lap'],r['evo_timing_invalid']) for r in rows],[('1','0'),('1','1'),('0','1'),('0','0')])
            convert(source,replace=True);self.assertEqual(TPath(source).read_bytes(),before)

    def test_evo_completed_game_verdict_overrides_early_flags_legacy_negative_stays_pending(self):
        from tests.test_evo_records310 import fixture
        from evo_laps import scan
        from race_model import lap_status
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            for mode in ('clear','conflict','negative','pending','legacy'):
                folder=fixture(Path(temp)/mode);source=folder/'inputs.csv'
                with source.open(encoding='utf-8',newline='') as stream:reader=csv.DictReader(stream);fields=reader.fieldnames;rows=list(reader)
                for i,row in enumerate(rows[100:200],100):
                    if mode!='legacy':row.update(evo_is_valid_lap='1',evo_timing_invalid='0')
                    if i==100:row.update(lap_invalidated='1',evo_is_valid_lap='0' if mode!='legacy' else '',evo_timing_invalid='1' if mode!='legacy' else '')
                terminal=rows[199]
                if mode=='conflict':terminal.update(evo_is_valid_lap='1',evo_timing_invalid='1',lap_invalidated='1')
                if mode=='negative':terminal.update(evo_is_valid_lap='0',evo_timing_invalid='1',lap_invalidated='1')
                if mode=='pending':terminal.update(evo_is_valid_lap='0',evo_timing_invalid='0',lap_invalidated='')
                if mode=='legacy':terminal['lap_invalidated']='1'
                with source.open('w',encoding='utf-8',newline='') as stream:writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
                before=source.read_bytes();value=scan(folder);lap=value['laps'][1]
                self.assertIs(lap['game_valid'],True if mode in ('clear','conflict') else False if mode=='negative' else None)
                if mode in ('clear','conflict'):self.assertEqual(value['fastest']['num'],2)
                else:self.assertIsNone(value['fastest'])
                if mode in ('pending','legacy'):self.assertIn('待确认',lap_status(lap));self.assertNotIn('无效',lap_status(lap))
                self.assertEqual(source.read_bytes(),before)

    def test_quality_exclusion_does_not_change_displayed_game_decision_for_either_simulator(self):
        from tests.test_evo_records310 import fixture
        from race_model import build_model,lap_status,describe
        from racecom_bridge import adapt
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            model=build_model(fixture(Path(temp)));base=model['laps'][1]
            for game in ('lmu','ac_evo'):
                model['session']['simulator_id']=game
                model['laps']=[dict(base,valid=True,game_valid=True,partial=True,best=False)]
                value=adapt(model);lap=value['laps'][0]
                self.assertTrue(lap['game_valid']);self.assertFalse(lap['statistics_eligible']);self.assertFalse(lap['valid'])
                self.assertIn('游戏有效',lap['note']);self.assertNotIn('无效',lap['note'])
                self.assertIn('有效',lap_status(model['laps'][0]));self.assertNotIn('无效',describe(dict(event='reconstructed_lap',data=model['laps'][0])))
            model['laps']=[dict(base,valid=False,game_valid=None,partial=False,best=False)]
            self.assertIn('待确认',adapt(model)['laps'][0]['note']);self.assertNotIn('无效',adapt(model)['laps'][0]['note'])

    def test_renderer_hook_keeps_property_slots_colors_and_statistics_independent(self):
        from racecom_validity_hook import install
        class Lap:
            __slots__=('num','time','valid','best','delta','extra_note')
            def __init__(self,n,t):self.num=n;self.time=t;self.valid=True;self.best=False;self.delta=None;self.extra_note=''
        class Sheet:
            def __init__(self,path):self.source=path;self.laps=[Lap(1,5),Lap(2,20),Lap(3,4),Lap(4,3)]
            @property
            def reference_best(self):return min((lap.time for lap in self.laps if lap.valid),default=0)
            def best_lap(self):return next((lap for lap in self.laps if lap.valid and lap.time==self.reference_best),None)
            def best_sector(self,key):return None,0
        def recompute(sheet):
            for lap in sheet.laps:lap.best=bool(lap.valid and lap.time==sheet.reference_best)
        class Pil:
            def __init__(self,sheet):self.sheet=sheet
            def rows(self):return [(str(l.num),str(l.time),'','','','','') for l in self.sheet.laps]
        class Log:
            def _lap_row_flags(self,rows):return min((i for i,r in enumerate(rows) if '无效' not in r[6]),key=lambda i:float(rows[i][1]),default=None),{}
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            path=Path(temp)/'laps.xlsx'
            items=[dict(num=i,game_valid=g,statistics_eligible=e,note=n) for i,g,e,n in ((1,True,False,'游戏有效 / 部分记录'),(2,True,True,'最快'),(3,None,False,'待确认'),(4,False,False,'无效'))]
            (path.parent/'race_log.json').write_text(json.dumps(dict(stintrix_validity_policy=1,laps=items)),'utf-8')
            ns=dict(LapSheet=Sheet,load_lap_sheet=Sheet,recompute_lap_flags=recompute,LapSheetPilRenderer=Pil,RaceLogRenderer=Log)
            install(ns);install(ns);sheet=ns['load_lap_sheet'](path)
            self.assertEqual([l.valid for l in sheet.laps],[True,True,True,False]);self.assertEqual(sheet.reference_best,20);self.assertEqual(sheet.best_lap().num,2)
            self.assertEqual([l.best for l in sheet.laps],[False,True,False,False]);self.assertIn('待确认',Pil(sheet).rows()[2][6])
            rows=Pil(sheet).rows();obj=SimpleNamespace(data=SimpleNamespace(source_txt=path.parent/'race_log.txt'))
            self.assertEqual(Log._lap_row_flags(obj,rows),(1,{}));self.assertEqual(rows[0][6],'游戏有效 / 部分记录')


if __name__=='__main__':unittest.main()
