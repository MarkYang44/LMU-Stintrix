"""Class aliases, multiclass scoring, event persistence and rendered summaries."""
import csv,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from tests import test_core,test_race_images,test_personal_records
from lap_identity import canonical_class,vehicle_class
from race_journal import capture,RaceJournal
from race_model import build_model,describe
from class_positions import fields,description
from personal_records import records
from laps import export_fastest


class ClassPositionTests(unittest.TestCase):
    def grid(self):
        data=test_core.fixture();info=data.scoring.scoringInfo;info.mNumVehicles=5;info.mCurrentET=10
        for i,(group,place) in enumerate(((b'Hypercar',1),(b'GT3',4),(b'LMGT3',2),(b'LMP2',3),(b'GT3',5))):
            v=data.scoring.vehScoringInfo[i];v.mID=42 if i==1 else i+100;v.mVehicleClass=group;v.mPlace=place
        return data,info,data.scoring.vehScoringInfo[1],data.telemetry.telemInfo[0]

    def test_aliases_merge_gt3_records_but_preserve_other_classes_and_layouts(self):
        self.assertEqual(vehicle_class(dict(vehicle_class='GT3',vehicle='Porsche 911 GT3 R LMGT3')),'LMGT3')
        self.assertEqual(canonical_class('LM GT3'),'LMGT3');self.assertEqual(canonical_class('LMDH'),'Hypercar')
        self.assertEqual(canonical_class('GTE'),'GTE');self.assertEqual(canonical_class('Custom Cup'),'Custom Cup')
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            fixture=test_personal_records.FeatureTests()
            old=fixture.session(t,'old',vehicle_class='LMGT3');new=fixture.session(t,'new',vehicle_class='GT3')
            path=new/'inputs.csv'
            with path.open(encoding='utf-8',newline='') as stream:reader=csv.DictReader(stream);columns=reader.fieldnames;rows=list(reader)
            with path.open('w',encoding='utf-8',newline='') as stream:
                writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader()
                for row in rows:
                    for key in ('time_s','session_time_s','lap_start_s'):
                        if row.get(key):row[key]=str(float(row[key])*.9)
                    writer.writerow(row)
            other=fixture.session(t,'prototype',vehicle_class='Hypercar');short=fixture.session(t,'short',vehicle_class='GT3',track_layout='Short')
            for folder in (old,new,other,short):export_fastest(folder,ROOT/'src/compare.html')
            before={p:p.read_bytes() for folder in (old,new,other,short) for p in folder.iterdir() if p.is_file()}
            result=records(t);self.assertEqual(len(result),3)
            winner=next(v for v in result if v['vehicle_class']=='LMGT3' and v['layout']!='Short')
            self.assertEqual(Path(winner['folder']),new);self.assertAlmostEqual(winner['time_s'],9.9)
            self.assertEqual({p:p.read_bytes() for p in before},before)

    def test_multiclass_rank_uses_same_class_order_and_cache_updates(self):
        data,info,player,car=self.grid();state=capture(data,car,player,info)
        self.assertEqual((state['place'],state['class_place'],state['class_size']),(4,2,3))
        self.assertEqual(state['vehicle_class'],'LMGT3');self.assertTrue(state['class_position_available'])
        info.mCurrentET+=.1;data.scoring.vehScoringInfo[2].mPlace=5;data.scoring.vehScoringInfo[4].mPlace=2
        again=capture(data,car,player,info,state);self.assertEqual(again['class_place'],2)
        info.mCurrentET+=.1;data.scoring.vehScoringInfo[2].mPlace=4;player.mPlace=2;data.scoring.vehScoringInfo[4].mPlace=5
        again=capture(data,car,player,info,again);self.assertEqual((again['place'],again['class_place']),(2,1))

    def test_missing_classes_invalid_places_and_truncated_grid_stay_unknown(self):
        data,info,player,car=self.grid()
        data.scoring.vehScoringInfo[0].mVehicleClass=b''
        value=capture(data,car,player,info);self.assertIsNone(value['class_place']);self.assertFalse(value['class_position_available'])
        data.scoring.vehScoringInfo[0].mVehicleClass=b'Hypercar';info.mCurrentET+=1
        data.scoring.vehScoringInfo[0].mPlace=0;self.assertIsNone(capture(data,car,player,info)['class_place'])
        info.mNumVehicles=105;self.assertIsNone(capture(data,car,player,info)['class_size'])

    def test_journal_keeps_class_start_finish_and_separate_changes(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            sample=test_race_images.sample
            initial=sample(state=dict(phase=2,place=4,vehicle_class='GT3',class_place=2,class_size=3,class_position_available=True))
            journal=RaceJournal(t,initial);journal.observe(initial)
            journal.observe(sample(.1,state=dict(phase=5,place=3,vehicle_class='GT3',class_place=1,class_size=3,class_position_available=True)))
            journal.observe(sample(.2,finish=1,state=dict(phase=8,place=3,vehicle_class='GT3',class_place=1,class_size=3,class_position_available=True)))
            journal.finish('test');summary=json.loads((Path(t)/'race_summary.json').read_text(encoding='utf-8'))
            self.assertEqual((summary['grid_place'],summary['grid_class_place'],summary['finish_class_place']),(4,2,1))
            self.assertEqual(summary['position_display_version'],1)
            with (Path(t)/'race_events.csv').open(encoding='utf-8',newline='') as stream:
                events=[dict(event=r['event'],data=json.loads(r['payload_json'])) for r in csv.DictReader(stream)]
            event=next(e for e in events if e['event']=='class_position');self.assertIn('LMGT3 组内名次',describe(event));self.assertIn('P2 → P1/3',describe(event))

    def test_reports_keep_overall_places_without_class_summary(self):
        from racecom_bridge import adapt,write_inputs
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=test_core.Tests().lap_csv(Path(t)/'session');model=build_model(folder)
            model['summary'].update(grid_place=14,finish_place=12,vehicle_class='LMGT3',grid_class_place=3,finish_class_place=2)
            model['events'].append(dict(time=30,event='class_position',data=dict(vehicle_class='LMGT3',**{'from':3,'to':2})))
            value=adapt(model)
            self.assertEqual((value['start_place'],value['finish_place']),(14,12))
            self.assertNotIn('finish_class_place',value)
            self.assertFalse(any('组内' in e['text'] for e in value['events']))
            inputs=write_inputs(folder,model)
            self.assertNotIn('组内', (inputs/'race_log.txt').read_text(encoding='utf-8'))

    def test_only_new_journals_show_inline_class_positions(self):
        from class_positions import inline_positions
        from racecom_bridge import adapt
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=test_core.Tests().lap_csv(Path(t)/'session');model=build_model(folder)
            model['summary'].update(grid_place=32,finish_place=29,grid_class_place=14,finish_class_place=12)
            self.assertEqual(inline_positions(model),(None,None))
            model['summary']['position_display_version']=1
            self.assertEqual(inline_positions(model),('P32 / 同组 P14','P29 / 同组 P12'))
            self.assertEqual(adapt(model)['stintrix_position_cards']['finish'],'P29 / 同组 P12')
            model['summary']['grid_class_place']=None
            self.assertEqual(inline_positions(model)[0],'P32 / 同组 未知')
            model['summary']['finish_flag']=2
            self.assertEqual(inline_positions(model)[1],'DNF / 同组 DNF')

    def test_renderer_failure_retains_both_original_images(self):
        from racecom_bridge import render
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            folder=test_core.Tests().lap_csv(Path(t)/'session');model=build_model(folder)
            for name in ('圈速单.png','比赛日志.png'):(folder/name).write_bytes(b'original')
            calls=[]
            def fake(args,cwd):
                calls.append(args);Path(args[2]).write_bytes(b'\x89PNG\r\n\x1a\nfixture')
                return int(len(calls)==2)
            with patch('racecom_bridge.run',side_effect=fake):
                with self.assertRaises(RuntimeError):render(folder,model,Path(t)/'Image Generate.exe')
            self.assertTrue(all((folder/name).read_bytes()==b'original' for name in ('圈速单.png','比赛日志.png')))
            self.assertFalse(list(folder.glob('*.pending')))


if __name__=='__main__':unittest.main()
