"""Lossless blocks, projected reads, legacy analysis, resource and cache lifetimes."""
import csv,gc,io,json,os,random,struct,sys,tempfile,time,unittest,zlib
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from column_store import convert,Reader,rows,packed
from telemetry_file import Path as ReadPath


class StorageTests(unittest.TestCase):
    def test_legacy_v1_container_and_both_legacy_column_encodings_still_read(self):
        from column_store import HEAD,U32
        header=b'time_s,notes\r\n'
        times=[b'-0.0000',b'1.0000000000000002',b'1.0000000000000002']
        notes=[b'""\r\n',b'"x\n""y"""\r\n',b'\r\n']
        repeat=b''.join(U32.pack(1)+U32.pack(len(v))+v for v in times)
        prefix=b''.join(U32.pack(0)+U32.pack(len(v))+v for v in notes)
        original=header+b''.join(a+b','+b for a,b in zip(times,notes))
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            path=Path(t)/'inputs.csv.stc';entries=[]
            with path.open('wb') as f:
                f.write(b'STXCOL1\n'+HEAD.pack(len(original),123,len(header),2)+header)
                for kind,data in ((0,repeat),(1,prefix)):
                    encoded=bytes([kind])+zlib.compress(data);entries.append([f.tell(),len(encoded)]);f.write(encoded)
                index=json.dumps([dict(rows=3,columns=entries)],separators=(',',':')).encode()
                f.write(index+struct.pack('<Q',len(index))+b'STXEND1\n')
            reader=Reader(path);self.assertEqual(reader.version,1)
            self.assertEqual(b''.join(reader.bytes()),original)
            self.assertEqual(list(rows(Path(t)/'inputs.csv',['notes'],1,2)),[{'notes':'x\n"y"'}])

    def test_v2_adaptive_columns_preserve_lexical_values_and_reduce_realistic_payloads(self):
        from column_store import _encode,_decode,U32
        rng=random.Random(41)
        dictionary=[bytes(rng.randrange(32,127) for _ in range(100)) for _ in range(256)]
        groups=[['中文,"A"\nB'.encode(),b'',b'-0.000000',b'1.0000000000000002']*512,
            [f'{i*.010001:.6f}'.encode() for i in range(2048)],
            [rng.choice(dictionary) for _ in range(2048)],
            [b'a'*150+str(i).encode()+b'z'*150 for i in range(2048)],
            [b'']*2048,[b'0.0']*2048]
        selected=[]
        for values in groups:
            encoded=_encode(values);selected.append(encoded[0]);self.assertEqual(_decode(encoded,len(values)),values)
            # Independent v1 candidates give a storage ceiling for every column.
            runs=[];last=None;count=0;prefix=bytearray();previous=b''
            for value in values:
                if last is not None and value!=last:runs.append(U32.pack(count)+U32.pack(len(last))+last);count=0
                count+=1;last=value;shared=0
                while shared<min(len(previous),len(value)) and previous[shared]==value[shared]:shared+=1
                suffix=value[shared:];prefix.extend(U32.pack(shared)+U32.pack(len(suffix))+suffix);previous=value
            runs.append(U32.pack(count)+U32.pack(len(last))+last)
            ceiling=min(len(zlib.compress(b''.join(runs))),len(zlib.compress(prefix)))+1
            self.assertLessEqual(len(encoded),ceiling)
        self.assertIn(2,selected);self.assertIn(4,selected)

    def test_v2_mixed_line_endings_bom_and_final_row_without_newline(self):
        original=b'\xef\xbb\xbftime_s,notes\r\n'+b''.join(
            str(i).encode()+b',"quoted, \"\"text\"\""'+(b'\r\n' if i%2 else b'\n') for i in range(2600))+b'-0.0000,"last\nfield"'
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            p=Path(t)/'inputs.csv';p.write_bytes(original);(p.parent/'session.json').write_text('{"status":"complete"}')
            self.assertTrue(convert(p,replace=True)['converted']);reader=Reader(packed(p))
            self.assertEqual(reader.version,2);self.assertEqual(b''.join(reader.bytes()),original)
            self.assertEqual(list(rows(p,['notes'],2600,2601)),[{'notes':'last\nfield'}])

    def test_new_column_encodings_and_malformed_blocks(self):
        from column_store import _decode
        # Handwritten wire fixtures are independent of the production encoder.
        fixtures=[(2,b'\x00\x03abc\x02\x01d',[b'abc',b'abd']),
            (3,b'\x00\x04-0.0',[b'',b'-0.0']),
            (4,b'\x02\x00\x03abc\x01\x00\x01',[b'abc',b'',b'abc'])]
        for kind,raw,expected in fixtures:
            self.assertEqual(_decode(bytes([kind])+zlib.compress(raw),len(expected)),expected)
        invalid=[(2,b'\x80',1),(2,b'\xff\xff\xff\xff\x1f',1),
            (2,b'\x01\x00',1),(2,b'\x00\x02a',1),(3,b'\x00\x00',1),
            (4,b'\x00',1),(4,b'\x02',1),(4,b'\x01\x02a',1),
            (4,b'\x01\x00\x01',1),(4,b'\x01\x00\x00\x00',1)]
        for kind,raw,count in invalid:
            with self.subTest(kind=kind,raw=raw):
                with self.assertRaises(ValueError):_decode(bytes([kind])+zlib.compress(raw),count)

    def fixture(self,root):
        root=Path(root);root.mkdir(parents=True,exist_ok=True);(root/'session.json').write_text('{"status":"complete"}')
        s=io.StringIO(newline='');w=csv.writer(s);w.writerow(['time_s','throttle','brake','notes'])
        for i in range(7000):w.writerow([f'{i*.010001:.6f}','1.000000' if i<4097 else '-0.000000','',('中文,"A"\nB' if i%10==0 else 'fixed')])
        source=s.getvalue().encode('utf-8');p=root/'inputs.csv';p.write_bytes(source);return p,source

    def test_exact_csv_bytes_types_quotes_newlines_and_irregular_timestamps_survive(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            p,original=self.fixture(t);stamp=p.stat();result=convert(p,replace=True)
            self.assertTrue(result['converted']);self.assertFalse(p.exists());self.assertLess(packed(p).stat().st_size,len(original))
            self.assertEqual(ReadPath(p).read_bytes(),original);self.assertEqual(ReadPath(p).stat().st_mtime_ns,stamp.st_mtime_ns)
            self.assertEqual(ReadPath(p).stat().st_size,len(original));self.assertTrue(ReadPath(p).is_file())
            expected=list(csv.DictReader(io.StringIO(original.decode(),newline='')))
            self.assertEqual(list(rows(p)),expected)
            projected=list(rows(p,['notes','time_s'],2040,2060))
            self.assertEqual(projected,[{k:r[k] for k in ('notes','time_s')} for r in expected[2040:2060]])
            self.assertEqual(next(rows(p,['missing','time_s']))['missing'],'')
            from column_store import restore
            self.assertTrue(restore(p)['restored']);self.assertEqual(p.read_bytes(),original);self.assertFalse(packed(p).exists())

    def test_projection_does_not_decode_unrequested_columns_and_stat_does_not_load_index(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            p,_=self.fixture(t);convert(p,replace=True);r=Reader(packed(p));self.assertNotIn('blocks',r.__dict__)
            offset,size=r.blocks[0]['columns'][2]
            with packed(p).open('r+b') as f:f.seek(offset);f.write(b'X'*size)
            self.assertEqual(len(list(rows(p,['throttle'],0,10))),10)
            with self.assertRaises(zlib.error):ReadPath(p).read_bytes()

    def test_active_recording_and_unprofitable_conversion_keep_original(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            p,_=self.fixture(t);(p.parent/'session.json').write_text('{"status":"recording"}')
            with self.assertRaises(ValueError):convert(p,replace=True)
            self.assertTrue(p.is_file());self.assertFalse(packed(p).exists())
            (p.parent/'session.json').write_text('{"status":"complete"}');p.write_text('a,b\n1,2\n')
            self.assertFalse(convert(p,replace=True)['converted']);self.assertEqual(p.read_text(),'a,b\n1,2\n')

    def test_csv_reader_lock_does_not_leave_a_second_copy_or_remove_original(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            p,original=self.fixture(t);unlink=Path.unlink
            def locked(path,*args,**kwargs):
                if path==p:raise PermissionError('reader holds CSV')
                return unlink(path,*args,**kwargs)
            with patch.object(Path,'unlink',locked):
                with self.assertRaises(PermissionError):convert(p,replace=True)
            self.assertEqual(p.read_bytes(),original);self.assertFalse(packed(p).exists());self.assertFalse(list(p.parent.glob('*.pending')))

    def test_real_analysis_csv_export_and_zip_use_adapter_without_content_hashes(self):
        from tests.test_archives import ArchiveTests
        from laps import complete_laps,export_selected_laps
        from storage_actions import export
        from session_archive import export_session,import_session
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root,folder=ArchiveTests().fixture(t);original=(folder/'inputs.csv').read_bytes()
            convert(folder/'inputs.csv',replace=True);self.assertEqual(len(complete_laps(folder)['laps']),4)
            with patch('hashlib.sha256',side_effect=AssertionError('no file hashing')):
                out=export_session(root,'Logs/Fixture',Path(t)/'out')
                again=export_session(root,'Logs/Fixture',Path(t)/'out');self.assertEqual(out['path'],again['path']);self.assertTrue(again['reused'])
                imported=import_session(Path(t)/'restored',out['path'])
            restored=Path(imported['folder']);self.assertEqual((restored/'inputs.csv').read_bytes(),original)
            receipt=json.loads((restored/'_archive_receipt.json').read_text());self.assertEqual(receipt['verification'],'none')
            result=export(folder,Path(t)/'csv','csv');self.assertEqual((Path(result['path'])/'inputs.csv').read_bytes(),original)

    def test_cache_budget_protects_pinned_entries_and_user_exports(self):
        from cache_budget import enforce,hold
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t);(root/'storage_settings.json').write_text('{"cache_limit_mb":32}')
            a=root/'PersonalRecords/TrainingCache'/('a'*32);b=root/'PersonalRecords/Cache'/('b'*32)
            for p in (a,b):p.mkdir(parents=True);(p/'cache.bin').write_bytes(b'X'*1024);os.utime(p,(1,1))
            class Owner:pass
            owner=Owner();hold(owner,a)
            from cache_budget import limit
            with patch('cache_budget.limit',return_value=0):
                result=enforce(root,force=True);self.assertTrue(a.exists());self.assertFalse(b.exists())
                del owner;gc.collect();enforce(root,force=True);self.assertFalse(a.exists())

    def test_same_fastest_csv_is_shared_and_atomic_regeneration_keeps_snapshot(self):
        from tests.test_archives import ArchiveTests
        from laps import export_fastest,export_selected_laps
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root,folder=ArchiveTests().fixture(t);(folder/'vehicle.csv').unlink();template=ROOT/'src/compare.html';export_fastest(folder,template)
            selected=export_selected_laps(folder,[4],template);p=Path(selected['exports'][0]['csv']);snapshot=p.read_bytes()
            if os.name=='nt':self.assertTrue(os.path.samefile(p,folder/'fastest_lap.csv'))
            stamp=p.stat().st_mtime_ns;export_selected_laps(folder,[4],template);self.assertEqual(p.stat().st_mtime_ns,stamp)
            export_fastest(folder,template);self.assertEqual(p.read_bytes(),snapshot)

    def test_catalog_and_history_copies_keep_cache_lease_until_last_view_is_released(self):
        from cache_budget import hold,enforce
        from personal_records import CacheRecord
        from event_catalog import attach
        from record_history import history
        from tests.test_record_intelligence import entry
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t);cache=root/'PersonalRecords/Cache'/('c'*32);cache.mkdir(parents=True);file=cache/'record.lap.json';file.write_text('{}')
            original=CacheRecord(dict(entry(),file=str(file)));hold(original,cache)
            attached=attach(root,[original])
            with patch('record_history.entries',return_value=[original]):chronology=history(root)
            del original;gc.collect()
            with patch('cache_budget.limit',return_value=0):
                enforce(root,force=True);self.assertTrue(file.exists())
                del attached,chronology;gc.collect();enforce(root,force=True);self.assertFalse(cache.exists())

    def test_local_resources_share_storage_and_standalone_html_remains_portable(self):
        from tests.test_archives import ArchiveTests
        from reporting import render_review
        from laps import track_script
        from report_assets import standalone
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root,a=ArchiveTests().fixture(t,'A');_,b=ArchiveTests().fixture(t,'B')
            for folder in (a,b):
                (folder/'vehicle.csv').unlink();render_review(folder,ROOT/'src',track_script(ROOT/'src'),local=True)
            one=next((a/'.stintrix-assets').glob('*.js'));two=next((b/'.stintrix-assets').glob('*.js'))
            if os.name=='nt':self.assertTrue(os.path.samefile(one,two))
            text=standalone(a/'review.html');self.assertIn('type="module" data-stintrix-main',text);self.assertNotIn('data-stintrix-shared=',text)

    def test_vehicle_analysis_keeps_full_float64_values_after_column_conversion(self):
        from vehiclelab import load_recording
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t);(root/'session.json').write_text('{"status":"complete"}');p=root/'vehicle.csv'
            with p.open('w',newline='') as f:
                w=csv.writer(f);w.writerow(['time_s','session_time_s','fuel_l','speed_kmh'])
                for i in range(5000):w.writerow([i/10,100+i/10,12.3456789012345,123.456789012345])
            before=load_recording(root);expected=list(before['data'][117]);before['data'].close()
            self.assertTrue(convert(p,replace=True)['converted'])
            after=load_recording(root);self.assertEqual(list(after['data'][117]),expected);self.assertEqual(len(after['data']),5000);after['data'].close()

    def test_sevenzip_of_columnar_session_exports_normal_csv_and_is_reused(self):
        from tests.test_archives import ArchiveTests
        from session_archive import export_session,import_session
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root,folder=ArchiveTests().fixture(t);original=(folder/'inputs.csv').read_bytes();convert(folder/'inputs.csv',replace=True)
            out=export_session(root,'Logs/Fixture',Path(t)/'out',format='7z')
            self.assertEqual(export_session(root,'Logs/Fixture',Path(t)/'out',format='7z')['path'],out['path'])
            restored=import_session(Path(t)/'restored',out['path']);self.assertEqual((Path(restored['folder'])/'inputs.csv').read_bytes(),original)
