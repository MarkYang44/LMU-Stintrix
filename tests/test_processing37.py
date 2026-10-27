"""Exact numeric conversion, standalone vehicle streams and draft-only resets."""
import csv,io,json,math,os,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tests import test_selected_laps as fixtures
ROOT=fixtures.ROOT


class Processing(unittest.TestCase):
    def test_numeric_complete_and_nullable_rows_preserve_float64_and_reject_all_nonfinite(self):
        from laps import read_rows
        fields=['utc','session_time_s','lap','lap_distance_m','throttle','brake','filtered_throttle','filtered_brake','speed_kmh','fuel_l','tc_active']
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            path=Path(t)/'inputs.csv'
            def write(rows):
                with path.open('w',encoding='utf-8-sig',newline='') as f:
                    writer=csv.writer(f);writer.writerow(fields);writer.writerows(rows)
            row=['时间,"甲"\r\n下一行','.12345678901234567','1','-0.0','.11111111111111111','.25','.5','-0.0','179.12345678901234','23.12345678901234','0']
            blank=row.copy();blank[-2]='';short=row[:-2];write([row,blank,short])
            result=list(read_rows(path));self.assertEqual(len(result),3)
            for value,raw in zip(result,(row,blank,short)):
                expected={k:float(v) for k,v in zip(fields[1:],raw[1:]) if v!=''}
                self.assertEqual(dict(value),dict(expected,utc=row[0]))
                for key,v in expected.items():self.assertEqual(struct.pack('<d',value[key]),struct.pack('<d',v))
            for key in ('throttle','fuel_l'):
                for text in ('nan','NaN','inf','-inf','1e9999'):
                    bad=row.copy();bad[fields.index(key)]=text;write([bad])
                    with self.assertRaises(ValueError):list(read_rows(path))
            bad=row.copy();bad[fields.index('throttle')]='';write([bad])
            with self.assertRaises(ValueError):list(read_rows(path))

    def test_vehicle_window_streams_each_sample_once_without_changing_boundaries_or_summary(self):
        from analysis_spool import DiskTable
        from vehiclelab import lap_telemetry,summarize
        columns=['fuel_l','virtual_energy_pct',*[f'extra_{i}' for i in range(80)]]
        rows=[[i*.1,50-i*.01,90-i*.02,*[None if (i+j)%7==0 else -0. if j==0 else i/(j+1) for j in range(80)]] for i in range(1400)]
        start,end=20.03,90.03;best=dict(start_s=start,end_s=end,time_s=end-start)
        selected=[[round(row[0]-start,6),*row[1:]] for row in rows[200:902]]
        expected=dict(columns=columns,data=selected);expected['summary']=summarize(expected,0,end-start)
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            table=DiskTable(rows,len(columns)+1,t,nullable=True)
            try:
                # Only the two bisects may use random reads; extraction is sequential.
                original=DiskTable.__getitem__;calls=[]
                def read(source,index):calls.append(index);return original(source,index)
                with patch.object(DiskTable,'__getitem__',read):actual=lap_telemetry(best,dict(columns=columns,data=table))
                self.assertLess(len(calls),30)
                self.assertEqual(json.dumps(actual,allow_nan=False),json.dumps(expected,allow_nan=False))
                self.assertEqual(lap_telemetry(best,dict(columns=columns,data=rows)),actual)
            finally:table.close()

    def test_standalone_vehicle_json_matches_dict_reader_for_packed_duplicates_short_rows_and_cancel(self):
        from reporting import VehicleJSON,json_chunks
        from vehiclelab import COLUMNS,DEFAULT_PROFILE,number
        from column_store import convert
        from telemetry_file import Path as ReadPath
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            root=Path(t);path=root/'vehicle.csv';meta=dict(status='complete',source='Private source',vehicle_telemetry=dict(target_hz=10))
            (root/'session.json').write_text(json.dumps(meta),encoding='utf-8')
            fields=['session_time_s','time_s','fuel_l','fuel_l','virtual_energy_pct','note'];rows=[[str(5+i*.1),str(i*.1),'99','-0.0' if i==0 else '.12345678901234567','', '时间,"甲"\r\n下一行'] for i in range(600)]
            def write(values):
                with path.open('w',encoding='utf-8-sig',newline='') as f:w=csv.writer(f);w.writerow(fields);w.writerows(values)
            def expected():
                with ReadPath(path).open(encoding='utf-8-sig',newline='') as f:values=list(csv.DictReader(f))
                columns=[k for k in COLUMNS if k not in ('time_s','session_time_s')]
                origin=(number(values[0].get('session_time_s')) or 0)-(number(values[0].get('time_s')) or 0) if values else 0
                return dict(version=1,columns=columns,record_hz=10,source='Private source',time_origin_s=origin,profile=DEFAULT_PROFILE,strategy={},strategy_history=[],data=[[number(r.get('session_time_s')),*[number(r.get(k)) for k in columns]] for r in values])
            write(rows);original=path.read_bytes();reference=expected();before=b''.join(json_chunks(VehicleJSON(root,meta)))
            self.assertEqual(before,json.dumps(reference,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8'))
            self.assertTrue(convert(path,replace=True)['converted']);self.assertFalse(path.exists());self.assertEqual(b''.join(json_chunks(VehicleJSON(root,meta))),before);self.assertEqual(ReadPath(path).read_bytes(),original)
            # A different private file exercises short rows without converting it.
            short=root/'short';short.mkdir();path=short/'vehicle.csv';write([rows[0][:4],rows[1]])
            reference=expected();self.assertEqual(json.loads(b''.join(json_chunks(VehicleJSON(short,meta)))),reference)
            import lap_scan_index
            original_rows=lap_scan_index.raw_rows;closed=[]
            def tracked(*a,**kw):
                try:yield from original_rows(*a,**kw)
                finally:closed.append(True)
            with patch('lap_scan_index.raw_rows',tracked):
                stream=VehicleJSON(short,meta).chunks();next(stream);stream.close();self.assertEqual(closed,[True])
            write([rows[0],rows[0]])
            with self.assertRaises(ValueError):b''.join(json_chunks(VehicleJSON(short,meta)))


@unittest.skipUnless(os.name=='nt','Native Windows Tk')
class UI(unittest.TestCase):
    from tests import test_ui_polish60 as helpers
    app=helpers.UI.app;pump=helpers.UI.pump;panel=helpers.UI.panel

    def test_defaults_reset_only_draft_keep_unknown_preferences_and_wait_for_one_apply(self):
        from condition_match import DEFAULTS
        app,root,errors=self.app();path=root/'PersonalRecords/comparable_settings.json';path.parent.mkdir(exist_ok=True)
        saved=dict(DEFAULTS,fuel_l=1.2,ambient_temp_c=2.,min_laps=5,include_unknown=True,cross_mode=True,cross_phase=True,custom={'keep':7});path.write_text(json.dumps(saved));original=path.read_bytes()
        window,p,e=self.panel(app,root,'comparable');self.assertEqual(path.read_bytes(),original)
        p.form.inputs['rain'].set('invalid');p.apply();self.assertTrue(p.form.fields['rain'].error);jobs=[]
        with patch.object(app,'run_background',side_effect=lambda work,done:jobs.append((work,done))):
            p.form.defaults.invoke();self.assertFalse(jobs);self.assertEqual(p.policy(),DEFAULTS);self.assertFalse(p.form.fields['rain'].error);self.assertEqual(path.read_bytes(),original);self.assertFalse(p.ready())
            p.apply();self.assertEqual(len(jobs),1);work,done=jobs.pop();done(work(),None)
        self.assertTrue(p.ready());self.assertEqual(json.loads(path.read_text())['custom'],{'keep':7})
        p.exporting=True;p.sync();self.assertFalse(p.form.defaults.enabled);p.form.inputs['fuel_l'].set('1.5');p.form.reset();self.assertEqual(p.form.inputs['fuel_l'].get(),'1.5');p.exporting=False;p.sync()
        app.set_theme('light');app.toggle_language();window.maxsize(4096,4096);window.geometry('780x560');self.pump(app,.2)
        self.assertIn('Air 5.0',p.form.summary.get());self.assertIn('Wetness 0.1',p.form.summary.get());self.assertIn('Rain 0.05',p.form.summary.get())
        for b in (p.form.toggle,p.form.defaults):
            self.assertLessEqual(b.winfo_rootx()+b.winfo_width(),window.winfo_rootx()+window.winfo_width());self.assertLessEqual(b.font.measure(__import__('i18n').tr(b.label))+36*b.s,b.winfo_width()+1)
        p.edited=False;self.assertFalse(errors)


if __name__=='__main__':unittest.main()
