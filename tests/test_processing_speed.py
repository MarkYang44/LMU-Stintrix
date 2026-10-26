"""Focused safeguards for shared report work and exact streaming fast paths."""
import json,math,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'src')]


class Processing(unittest.TestCase):
    def test_report_shares_one_extraction_and_releases_scope_afterwards(self):
        from tests.test_upgrades import clean_session
        from tests.test_vehicle import VehicleTests
        import sessionlab,laps
        from processing_context import batch,current
        from reporting import VehicleJSON,json_chunks
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            f=clean_session(Path(tmp)/'session');VehicleTests.write_vehicle(f);original=(f/'inputs.csv').read_bytes()
            with batch(f) as shared,patch('sessionlab.extract_best',wraps=sessionlab.extract_best) as scan,patch('laps.extract_best',side_effect=AssertionError('Report must reuse its validated extraction')):
                analysis=sessionlab.analyze_session(f);self.assertEqual(scan.call_count,1);self.assertEqual(analysis['recent_stability']['count'],4)
                fastest,summary=laps.export_fastest(f,ROOT/'src/compare.html');self.assertEqual(summary['lap']['time_s'],fastest['lap']['time_s'])
                stable=json.loads((f/analysis['stable_reference_file']).read_text());self.assertEqual(stable['lap']['number'],3)
                reused=json.loads(b''.join(json_chunks(VehicleJSON(f,json.loads((f/'session.json').read_text())))))
            self.assertIsNone(current(f));self.assertFalse(shared.values)
            fresh=json.loads(b''.join(json_chunks(VehicleJSON(f,json.loads((f/'session.json').read_text())))));self.assertEqual(reused,fresh);self.assertEqual((f/'inputs.csv').read_bytes(),original)

    def test_scope_never_crosses_sources_and_changed_data_cannot_be_reused(self):
        from processing_context import batch,current
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            a=Path(tmp)/'a';b=Path(tmp)/'b';a.mkdir();b.mkdir();p=a/'session.json';p.write_text('{"status":"complete"}')
            with batch(a) as first:
                first.values['marker']=17;self.assertIs(current(a),first);self.assertIsNone(current(b))
                with batch(b) as second:self.assertIs(current(b),second);self.assertIsNone(current(a))
                self.assertIs(current(a),first);p.write_text('{"status":"complete","changed":true}')
                with self.assertRaises(OSError):current(a)
            self.assertFalse(first.values);self.assertIsNone(current(a))

    def test_stream_iteration_keeps_missing_values_utf8_and_nested_random_reads(self):
        from analysis_spool import DiskTable,LapRows
        from buffers import CompactRow
        from reporting import json_chunks
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            values=[[i*.01234567890123456,None if i%5 else -0.,1.234567890123456e-120] for i in range(6000)]
            table=DiskTable(values,3,tmp,nullable=True)
            for i,row in enumerate(table):
                self.assertEqual(row,values[i])
                if i%97==0:self.assertEqual(table[-1],values[-1]);self.assertEqual(list(table[:2]),values[:2])
            self.assertEqual(json.loads(b''.join(json_chunks(table))),values)
            rows=LapRows(tmp);layout={'time_s':0,'optional':1};texts=[]
            for i in range(3000):
                text=f'2026-10-26T12:00:{i}Z·赛车'+('🛰️'*(i%17));texts.append(text);rows.append(CompactRow(layout,[i*.123456789012345,math.nan if i%3 else 0.],text))
            rows.seal()
            for i,row in enumerate(rows):
                self.assertEqual(row['utc'],texts[i]);self.assertEqual(row['time_s'],i*.123456789012345);self.assertEqual('optional' in row,i%3==0)
                if i%73==0:self.assertEqual(rows[-1]['utc'],texts[-1])
            rows.close();table.close()

    def test_constant_column_reuse_keeps_identical_compressed_bytes_and_bounded_cache(self):
        from column_store import _encode,_encode_uncached,_constant,_decode
        _constant.cache_clear()
        for count in (1,700,2048):
            for value in (b'',b'0',b'"a,b\n"',bytes(range(256))):
                values=(value,)*count;expected=_encode_uncached(values);self.assertEqual(_encode(values),expected);self.assertEqual(_encode(values),expected);self.assertEqual(_decode(expected,count),list(values))
        self.assertGreater(_constant.cache_info().hits,0);self.assertLessEqual(_constant.cache_info().currsize,128)
