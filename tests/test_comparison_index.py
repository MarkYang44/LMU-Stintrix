"""Source-bound lap seeks and unchanged browser measurements."""
import csv,json,os,shutil,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tests import test_selected_laps as fixtures
ROOT=fixtures.ROOT;TEMPLATE=fixtures.TEMPLATE


class Index(unittest.TestCase):
    def test_new_pair_reuses_complete_lap_exports_and_packed_change_invalidates_them(self):
        import laps
        from lap_comparison import export_pair
        from lap_exports import cached
        from column_store import convert
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            folder=fixtures.SelectedLapTests().session(tmp)
            first=export_pair(tmp,[(folder,1),(folder,4)],TEMPLATE)
            stamps={Path(item[k]):Path(item[k]).stat().st_mtime_ns for item in first['exports'] for k in ('json','csv')}
            with patch('laps._select_laps',side_effect=AssertionError('Known laps must not be re-extracted')),patch('vehiclelab.load_recording',side_effect=AssertionError('Known vehicle channels must not be reparsed')):
                reverse=export_pair(tmp,[(folder,4),(folder,1)],TEMPLATE)
                self.assertNotEqual(reverse['comparison'],first['comparison'])
                self.assertEqual(export_pair(tmp,[(folder,1),(folder,4)],TEMPLATE),first)
            self.assertEqual({path:path.stat().st_mtime_ns for path in stamps},stamps)
            convert(folder/'inputs.csv',replace=True)
            self.assertIsNone(cached(folder,[1],None,individual=True))
            export_pair(tmp,[(folder,1),(folder,4)],TEMPLATE)
            self.assertIsNotNone(cached(folder,[1],None,individual=True))
            packed=folder/'inputs.csv.stc';stamp=packed.stat();os.utime(packed,ns=(stamp.st_atime_ns,stamp.st_mtime_ns+2000000))
            self.assertIsNone(cached(folder,[1],None,individual=True))

    def test_local_seek_cache_is_excluded_from_archives_and_publication(self):
        import laps
        from session_archive import _files
        from tools.audit_publication import allowed
        from tools.build import bundle_audit
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            folder=fixtures.SelectedLapTests().session(tmp);laps.complete_laps(folder)
            self.assertTrue((folder/'_lap_scan.json').is_file())
            self.assertNotIn('_lap_scan.json',[name for name,_,_ in _files(folder)])
            self.assertFalse(allowed('src/_lap_scan.json'))
            package=Path(tmp)/'package';private=package/'_internal/src/_lap_scan.json';private.parent.mkdir(parents=True);private.write_text('{}')
            with self.assertRaisesRegex(ValueError,'Private output'):bundle_audit(package)

    def test_restarted_inventory_and_selected_ranges_keep_exact_csv_and_full_payload(self):
        import laps,comparison_cache,lap_scan_index
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            helper=fixtures.SelectedLapTests();folder=helper.session(tmp);fields,rows=helper.load_rows(folder)
            fields+=['tyre_front_name','tyre_rear_name','note'];expanded=[]
            for row in rows:
                for part in range(10):
                    expanded.append(dict(row,session_time_s=str(float(row['session_time_s'])+part*.001),
                        time_s=str(float(row['time_s'])+part*.001),utc='时间,"原样"\r\n第二行',
                        tyre_front_name='软胎,"A"',tyre_rear_name='后胎',note='a\nb,"c"'))
            helper.save_rows(folder,fields,expanded);original=(folder/'inputs.csv').read_bytes()
            inventory=laps.complete_laps(folder);self.assertEqual([v['number'] for v in inventory['laps']],[1,2,3,4])
            self.assertGreater(len(lap_scan_index.load(folder)['cookies']),2)
            comparison_cache._scans.clear()
            with patch('laps.extract_best',side_effect=AssertionError('Already validated source must not be scanned again')):
                self.assertEqual(laps.complete_laps(folder),inventory)
                metadata,selected=laps._select_laps(folder,[1,4])
                result,records=laps._export_laps(folder,[1,4],metadata,selected)
            for item,best,record in zip(result['exports'],selected.values(),records):
                ordinary=dict(best);ordinary.pop('_range');ordinary.pop('_text_range')
                reference=folder/('expected-'+str(best['number'])+'.csv')
                laps.write_lap_csv(reference,ordinary,metadata,folder/'inputs.csv')
                self.assertEqual(Path(item['csv']).read_bytes(),reference.read_bytes())
                expected=laps.lap_record(folder,ordinary,metadata,kind='selected')
                def value(v):return json.loads(b''.join(__import__('reporting').json_chunks(v)))
                self.assertEqual(value(record),value(expected))
            self.assertEqual((folder/'inputs.csv').read_bytes(),original)
            cache=folder/'_lap_scan.json';value=json.loads(cache.read_text('utf-8'));value['value']['groups'][0]['time_s']=1;cache.write_text(json.dumps(value),'utf-8')
            self.assertIsNone(lap_scan_index.load(folder))
            comparison_cache._scans.clear()
            with patch('laps.extract_best',wraps=laps.extract_best) as read:
                self.assertEqual(laps.complete_laps(folder),inventory);self.assertEqual(read.call_count,1)

    def test_report_builds_same_flagged_inventory_and_packed_ranges_preserve_values(self):
        import laps,lap_scan_index,comparison_cache
        from sessionlab import analyze_session
        from column_store import convert
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as tmp:
            folder=fixtures.SelectedLapTests().session(tmp)
            expected=laps._lap_inventory(laps.extract_best(folder/'inputs.csv',include_flagged=True,retain_best=False)[1],None)
            analyze_session(folder)
            with patch('laps.extract_best',side_effect=AssertionError('Analysis already verified all lap boundaries')):
                self.assertEqual(laps.complete_laps(folder),expected)
                metadata,selected=laps._select_laps(folder,[1,4])
            before={n:[dict(row) for row in best['rows']] for n,best in selected.items()}
            convert(folder/'inputs.csv',replace=True);self.assertIsNone(lap_scan_index.load(folder))
            comparison_cache._scans.clear();self.assertEqual(laps.complete_laps(folder),expected)
            with patch('laps.extract_best',side_effect=AssertionError('Packed index must also be reusable')):
                _,after=laps._select_laps(folder,[1,4])
            self.assertEqual({n:[dict(row) for row in best['rows']] for n,best in after.items()},before)

    @unittest.skipUnless(shutil.which('node'),'Node required for offline browser measurement check')
    def test_linear_corner_measurement_matches_previous_inclusive_window_results(self):
        source=(ROOT/'src/laplab.js').read_text('utf-8')
        checks=r'''
const assert=require('assert');
function previous(lap,corner,at,offset=2){
 const step=Math.max(1,(corner.end-corner.start)/1500),rows=[];
 for(let d=corner.start;d<corner.end;d+=step)rows.push(at(lap,d));rows.push(at(lap,corner.end));
 const brake=rows.find(r=>r[0]<=corner.apex&&r[offset+1]>=.05),released=brake?rows.find(r=>r[0]>brake[0]&&r[offset+1]<.05):null;
 const after=rows.filter(r=>r[0]>=corner.apex),recovery=after.find((r,i)=>r[offset]>=.9&&after.slice(i).some(q=>q[0]>=r[0]+12)&&after.filter(q=>q[0]>=r[0]&&q[0]<=r[0]+12).every(q=>q[offset]>=.9));
 return {brake:brake?.[0]??null,release:released?.[0]??null,minimum:Math.min(...rows.map(r=>r[6])),entry:rows[0][6],exit:rows.at(-1)[6],full:recovery?.[0]??null,time:rows.at(-1)[1]-rows[0][1]};
}
for(let seed=0;seed<80;seed++)for(const offset of [2,4]){
 const c={start:seed/3,apex:seed/3+seed%70,end:seed/3+20+seed*23.3};
 const at=(_,d)=>{const t=Math.floor(d+seed),a=t%31<18?.9:.899999999999,b=t%43<5?.05:0;return [d,d*.023,a,b,t%17<14?1:0,t%29<8?.2:0,40+(d%150)]};
 assert.deepStrictEqual(InputScopeLab.measure(null,c,at,offset),previous(null,c,at,offset));
}
console.log('160 corner/channel cases match, including inclusive 12 m boundaries');
'''
        page=(ROOT/'src/compare.html').read_text('utf-8')
        cache=page[page.index('function loadCorners()'):page.index('function seekDistance(')]
        cache_checks=r'''
let cornerSections=[],cornerKey='key',cornerDefinitions=[{start:0,apex:50,end:120}],referenceId='A',channel='raw';
const base=()=>({lap:{track_length_m:200},session:{track:'test'}}),cornerStorageKey=()=>'key',grid=()=>({events:[]}),$=()=>({value:channel});
const valueAt=(_,d)=>[d,d*.02,.95,.05,.3,.1,90];
let calls=0;const actual=InputScopeLab.measure;InputScopeLab.measure=(...args)=>{calls++;return actual(...args)};
'''+cache+r'''
const v={};loadCorners();const raw=cornerMeasurement(v,cornerSections[0]);
assert.deepStrictEqual(cornerMeasurement(v,cornerSections[0]),raw);assert.strictEqual(calls,1);
channel='filtered';loadCorners();const filtered=cornerMeasurement(v,cornerSections[0]);assert.strictEqual(calls,2);assert.notDeepStrictEqual(filtered,raw);
cornerDefinitions=[{start:10,apex:60,end:140}];loadCorners();cornerMeasurement(v,cornerSections[0]);assert.strictEqual(calls,3);
referenceId='B';loadCorners();cornerMeasurement(v,cornerSections[0]);assert.strictEqual(calls,4);
console.log('Browser measurements reuse unchanged work and invalidate on channel, corners and reference changes');
'''
        result=subprocess.run([shutil.which('node'),'-'],input=source+checks+cache_checks,capture_output=True,text=True,encoding='utf-8',timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
