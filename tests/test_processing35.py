"""Narrow scratch-column decoding and analysis-job catalog reuse boundaries."""
import json,math,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor
from tests import test_selected_laps as fixtures
ROOT=fixtures.ROOT


class Processing(unittest.TestCase):
    def test_projected_lap_rows_keep_float64_utc_nulls_slices_and_all_calculations(self):
        from analysis_spool import LapRows,project_rows
        from buffers import CompactRow
        from sessionlab import actions,lap_conditions
        from training_zones import features
        from laps import comparison_data,trajectory_data
        class Legacy(list):pass
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            names=['session_time_s','lap_distance_m','throttle','brake','steering','filtered_throttle','filtered_brake','filtered_steering','speed_kmh','abs_active','tc_active','world_x_m','world_z_m','fuel_l',*[f'extra_{i}' for i in range(24)]]
            layout={k:i for i,k in enumerate(names)};rows=LapRows(t)
            for i in range(3000):
                values=[12345+i*.01,i*2.,(i%21)/20,(i%31)/30,math.sin(i/100),.12345678901234567,.25,-0.,180.,i%2,i%3,math.sin(i/100)*100,math.cos(i/100)*100,30.,*[float('nan') if (i+j)%7==0 else i/(j+1) for j in range(24)]]
                if i%13==0:values[11]=float('nan')
                rows.append(CompactRow(layout,values,'时间,"原文"\r\n'+str(i)))
            rows.seal();selected=['extra_23','absent','session_time_s','extra_0','world_x_m']
            view=project_rows(rows,selected)
            expected=lambda row:{k:v for k,v in dict(row).items() if k=='utc' or k in selected}
            for span in (slice(13,2500),slice(None,None,-31),slice(-90,None)):
                self.assertEqual([dict(v) for v in view[span]],[expected(v) for v in rows[span]])
            for i,row in enumerate(view):
                if i%211==0:self.assertEqual(rows[-1].utc,'时间,"原文"\r\n2999')
                self.assertEqual(dict(row),expected(rows[i]))
            self.assertEqual([dict(v) for v in view[100:300][11:31]],[expected(rows[i]) for i in range(111,131)])
            legacy=Legacy(dict(r) for r in rows);legacy.directory=t
            self.assertEqual(actions(rows),actions(legacy));self.assertEqual(lap_conditions(rows),lap_conditions(legacy))
            start=rows[0]['session_time_s'];end=rows[-1]['session_time_s']+.01;length=6000.
            self.assertEqual(features(rows,start,end,length),features(legacy,start,end,length))
            following=dict(rows[-1],session_time_s=end,lap_distance_m=length)
            best=dict(rows=rows,start_s=start,end_s=end,length_m=length,first_distance_index=0,next_row=following)
            before=comparison_data(dict(best,rows=legacy));after=comparison_data(best)
            self.assertEqual(list(after),list(before));self.assertEqual(trajectory_data(best,after),trajectory_data(dict(best,rows=legacy),before))
            before.close();after.close();rows.close()

    def test_catalog_reuses_metadata_per_job_rechecks_changes_and_does_not_publish_failed_writes(self):
        import training_cache as cache
        from storage import atomic_json
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t);folder=root/'Logs/a';folder.mkdir(parents=True)
            (folder/'inputs.csv').write_text('fixture');(folder/'session.json').write_text('{}')
            first=cache.path(root,folder);index=root/'PersonalRecords/TrainingCache/sources.json';original=cache.read_json
            @cache.catalogued
            def job():
                self.assertEqual(cache.path(root,folder),first);self.assertEqual(cache.path(root,folder),first)
                self.assertEqual(read.call_count,1)
                data=json.loads(index.read_text('utf-8'));data['Logs/a']['token']='f'*32;atomic_json(index,data)
                changed=cache.path(root,folder);self.assertNotEqual(changed,first);self.assertEqual(read.call_count,2)
                saved=index.read_bytes();(folder/'inputs.csv').write_text('source changed')
                with patch('training_cache.atomic_json',side_effect=OSError('fixture denied')):
                    with self.assertRaises(OSError):cache.path(root,folder)
                self.assertEqual(index.read_bytes(),saved)
                updated=cache.path(root,folder);self.assertNotEqual(updated,changed)
                self.assertEqual(cache.path(root,folder),updated)
            with patch('training_cache.read_json',wraps=original) as read:job()
            self.assertIsNone(cache._catalog.get())
            with patch('training_cache.read_json',wraps=original) as read:
                cache.catalogued(lambda:cache.path(root,folder))();self.assertEqual(read.call_count,1)

    def test_parallel_catalogs_have_separate_lifetimes(self):
        import training_cache as cache
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t);folder=root/'Logs/a';folder.mkdir(parents=True)
            (folder/'inputs.csv').write_text('fixture');(folder/'session.json').write_text('{}');expected=cache.path(root,folder)
            gate=threading.Barrier(2);original=cache.read_json
            @cache.catalogued
            def job():
                a=cache.path(root,folder);gate.wait(3);b=cache.path(root,folder);return a,b
            with patch('training_cache.read_json',wraps=original) as read,ThreadPoolExecutor(2) as pool:
                a=pool.submit(job);b=pool.submit(job);self.assertEqual(a.result(5),(expected,expected));self.assertEqual(b.result(5),(expected,expected));self.assertEqual(read.call_count,2)
            self.assertIsNone(cache._catalog.get())


if __name__=='__main__':unittest.main()
