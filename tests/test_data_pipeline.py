"""Shared sequential reads, exact CSV projection and reusable training output."""
import csv,io,json,shutil,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tests import test_selected_laps as fixtures
ROOT=fixtures.ROOT


class Pipeline(unittest.TestCase):
    def test_retired_csv_training_cache_tracks_physical_packed_source(self):
        import os
        from training_cache import path
        from column_store import convert
        from telemetry_file import Path as ReadPath
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            root=Path(tmp);folder=fixtures.SelectedLapTests().session(root)
            raw=path(root,folder);convert(folder/'inputs.csv',replace=True);packed=path(root,folder)
            self.assertNotEqual(raw,packed);logical=ReadPath(folder/'inputs.csv').stat().st_mtime_ns
            file=folder/'inputs.csv.stc';stamp=file.stat();os.utime(file,ns=(stamp.st_atime_ns,stamp.st_mtime_ns+2000000))
            self.assertEqual(ReadPath(folder/'inputs.csv').stat().st_mtime_ns,logical)
            self.assertNotEqual(path(root,folder),packed)

    def test_slices_and_columns_preserve_order_nulls_precision_and_nested_reads(self):
        from analysis_spool import DiskTable,LapRows,Column
        from buffers import CompactRow
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            expected=[[i*.010000000000000002,None if i%7==0 else i/19] for i in range(10000)]
            table=DiskTable(expected,2,tmp,nullable=True)
            for span in (slice(3,8500),slice(None,None,-3),slice(-90,None),slice(20,3)):
                self.assertEqual(list(table[span]),expected[span])
            for i,row in enumerate(table[5:9500]):
                if i%500==0:self.assertEqual(table[-1],expected[-1])
                self.assertEqual(row,expected[i+5])
            self.assertEqual(list(Column(table,offset=.123)),[r[0]-.123 for r in expected])
            rows=LapRows(tmp)
            for i in range(3000):rows.append(CompactRow({'session_time_s':0,'fuel_l':1},[i*.01,float('nan') if i%7==0 else i/19],'时间,"原文"\r\n'+str(i)))
            rows.seal()
            self.assertEqual([dict(r) for r in rows[1600:2700]],[dict(rows[i]) for i in range(1600,2700)])
            rows.close();table.close()

    def test_projection_keeps_duplicate_headers_missing_cells_and_multiline_fields(self):
        from column_store import rows,_fields
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            path=Path(tmp)/'inputs.csv';data='\ufeffa,b,a,c\r\n1,"多行\n文字",2,\r\n\r\n3,x\r\n4,y,5,6,extra\r\n'
            path.write_bytes(data.encode('utf-8'));columns=['a','b','c','absent']
            original=list(csv.DictReader(io.StringIO(data.removeprefix('\ufeff'),newline='')))
            self.assertEqual(list(rows(path,columns)),[{k:row.get(k,'') for k in columns} for row in original])
            self.assertEqual(list(rows(path,columns,1,2)),[{k:original[1].get(k,'') for k in columns}])
            for record in (b'0.0000000000000001,,1e-33\r\n',b'"a,b","multi\nline",-0.0\r\n',b'\xef\xbb\xbf0,1,2',b'"a""b",,3\n'):
                self.assertEqual(b','.join(_fields(record)),record)

    def test_analysis_warms_identical_training_profiles_and_cache_failure_is_optional(self):
        import training_report,sessionlab
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            root=Path(tmp);folder=fixtures.SelectedLapTests().session(root/'fixture');(root/'Logs').mkdir();target=root/'Logs/race';folder.rename(target);folder=target
            original=(folder/'inputs.csv').read_bytes()
            cold=training_report.profiles(root,folder);expected=list(cold['laps']);excluded=cold['excluded'];del cold
            (root/'PersonalRecords').rename(root/'before-training')
            analysis=sessionlab.analyze_session(folder)
            with patch('training_report.extract_best',side_effect=AssertionError('A completed analysis already produced the training profiles')):
                warm=training_report.profiles(root,folder)
                self.assertEqual(list(warm['laps']),expected);self.assertEqual(warm['excluded'],excluded)
            self.assertEqual((folder/'inputs.csv').read_bytes(),original)
            (root/'PersonalRecords').rename(root/'warm-training')
            with patch('training_report.lap_profile',side_effect=OSError('Read-only optional cache')):
                again=sessionlab.analyze_session(folder)
            self.assertEqual(again,analysis)

    @unittest.skipUnless(shutil.which('node'),'Node required for native plot window check')
    def test_native_plot_window_keeps_every_visible_sample_and_duplicate_boundary(self):
        page=(ROOT/'src/report.html').read_text('utf-8');source=page[page.index('function nativeTime'):page.index('function drawNative')]
        checks=r'''
const assert=require('assert'),session={native_time_offset_s:.123},native={event_offset_s:5};
for(const event of [false,true])for(const [start,end] of [[-100,100],[2,2],[2,4],[5000,5100],[-9,-1]]){
 const series={event},data=Array.from({length:100000},(_,i)=>[Math.floor(i/2)*.01,Math.sin(i)]);
 const expected=data.filter(r=>nativeTime(series,r)>=start&&nativeTime(series,r)<=end);
 assert.deepStrictEqual([...nativeWindow(series,data,start,end)],expected);
}
'''
        result=subprocess.run([shutil.which('node'),'-'],input=source+checks,capture_output=True,text=True,encoding='utf-8',timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
