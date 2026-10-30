"""Delayed EVO finish-line fields must not invalidate genuine completed laps."""
import csv,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))


def delayed(root,mode='normal'):
    from tests.test_evo_records310 import fixture
    folder=fixture(root)
    with (folder/'inputs.csv').open(encoding='utf-8',newline='') as stream:
        reader=csv.DictReader(stream);fields=reader.fieldnames;rows=list(reader)
    rows[100].update(evo_lap_time_ms='33',lap_distance_m='4999')
    rows[101].update(time_s='20.008333333333333',evo_lap_time_ms='44',lap_distance_m='1.2345678901234567')
    rows[199]['evo_lap_time_ms']='20021'
    rows[200]['evo_lap_time_ms']='33'
    if mode=='overshoot':rows[199]['evo_lap_time_ms']='20101'
    if mode=='late':rows[101]['time_s']='20.2'
    if mode=='middle':rows[150]['lap_distance_m']='0'
    if mode=='crossing-gap':
        for row in rows[200:]:row['time_s']=str(float(row['time_s'])+5)
    if mode=='flag':rows[150]['lap_invalidated']='1'
    if mode=='unknown':rows[150]['lap_invalidated']=''
    if mode=='pit':rows[150]['in_pits']='1'
    if mode=='skip':
        for row in rows[200:]:row['lap']='4'
    with (folder/'inputs.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    return folder


class Rules(unittest.TestCase):
    def test_bounded_boundary_skew_keeps_game_time_every_original_row_and_cache_revision(self):
        import evo_laps
        from evo_comparison import selected
        from race_model import build_model
        from racecom_bridge import adapt
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            folder=delayed(Path(temp));source=folder/'inputs.csv';before=source.read_bytes()
            old=evo_laps.scan(folder);old['signature']=dict(version=2,source=evo_laps.stamp(folder)['source'])
            (folder/'evo_laps_index.json').write_text(json.dumps(old),'utf-8')
            value=evo_laps.index(folder);lap=value['fastest']
            self.assertEqual(value['version'],4);self.assertEqual(value['signature']['version'],4)
            self.assertEqual((lap['num'],lap['time'],lap['samples']),(2,20.,100))
            self.assertTrue(lap['valid']);self.assertFalse(lap['partial']);self.assertTrue(lap['boundary_distance_wrap'])
            self.assertEqual(lap['boundary_timer_delta_ms'],-21)
            item,record=selected(folder,2,value,json.loads((folder/'session.json').read_text('utf-8')))
            try:
                self.assertEqual(len(record['data']),100)
                self.assertEqual(record['data'][0][0],4999)
                self.assertEqual(record['data'][1][0],1.2345678901234567)
                with Path(item['csv']).open(encoding='utf-8-sig',newline='') as stream:exported=list(csv.DictReader(stream))
                with source.open(encoding='utf-8',newline='') as stream:original=list(csv.DictReader(stream))
                self.assertEqual(exported,original[100:200])
            finally:record['data'].close()
            model=build_model(folder);self.assertEqual(model['fastest']['num'],2)
            output=adapt(model);self.assertTrue(next(l for l in output['laps'] if l['num']==2)['valid'])
            self.assertEqual(source.read_bytes(),before)

    def test_genuine_invalid_unknown_pit_gap_reset_and_unbounded_skew_stay_excluded(self):
        from evo_laps import scan
        from racecom_bridge import adapt
        from race_model import build_model
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            for mode in ('overshoot','late','middle','crossing-gap','flag','unknown','pit','skip'):
                folder=delayed(Path(temp)/mode,mode);value=scan(folder)
                self.assertIsNone(value['fastest'],mode)
                if mode in ('overshoot','late','middle','crossing-gap','skip'):
                    self.assertTrue(next(l for l in value['laps'] if l['num']==2)['partial'],mode)
            model=build_model(delayed(Path(temp)/'note','middle'));output=adapt(model)
            lap=next(l for l in output['laps'] if l['num']==2)
            self.assertTrue(lap['game_valid']);self.assertFalse(lap['valid']);self.assertIn('游戏有效 / 未计入统计',lap['note'])
            model['session']['simulator_id']='lmu';lap=next(l for l in adapt(model)['laps'] if l['num']==2)
            self.assertTrue(lap['note'].startswith('游戏有效 / 未计入统计 / '))

    def test_image_cache_tracks_evo_lap_rules_and_retains_prior_images(self):
        import evo_laps,race_report
        from evo_reports import overview
        class Canvas:
            def save(self,path):path.write_bytes(b'rendered test image')
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as temp:
            folder=delayed(Path(temp));meta=json.loads((folder/'session.json').read_text('utf-8'))
            with patch('race_report.pages',return_value=[('圈速单.png',Canvas())]),patch('race_report.select_car',return_value=None),patch('evo_art.item',return_value=None):
                first=race_report.generate(folder,renderer='native');self.assertEqual(first['fingerprint']['lap_rules'],4)
                with patch('race_report.build_model',side_effect=AssertionError('unchanged rules reuse images')):
                    self.assertEqual(race_report.generate(folder,renderer='native'),first)
                with patch.object(evo_laps,'VERSION',5):
                    fresh=race_report.generate(folder,renderer='native');self.assertEqual(fresh['fingerprint']['lap_rules'],5)
            self.assertTrue(list((folder/'_report_history').glob('renderer-*/圈速单.png')))
            overview(folder,meta);self.assertIn('最快圈',(folder/'review.html').read_text('utf-8'))


if __name__=='__main__':unittest.main()
