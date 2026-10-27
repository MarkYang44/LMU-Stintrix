"""Focused numeric projection fidelity, training-window equivalence and icon UI."""
import csv,io,json,math,os,random,struct,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tests import test_selected_laps as fixtures
ROOT=fixtures.ROOT


class Processing(unittest.TestCase):
    def test_numeric_projection_preserves_duplicate_names_multiline_utc_seeks_and_missing(self):
        from laps import read_rows
        from lap_scan_index import raw_rows
        from column_store import convert,values,rows
        fields=['session_time_s','lap','lap_distance_m','throttle','brake','filtered_throttle','filtered_brake','speed_kmh','utc','brake','fuel_l']
        line=['.12345678901234567','1','-0.0','.12345678901234567','.2','.3','.4','199.999999999','时间,"甲"\r\n下一行','.9876543210987654','']
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            path=Path(t)/'inputs.csv'
            (Path(t)/'session.json').write_text('{"status":"complete"}',encoding='utf-8')
            with path.open('w',encoding='utf-8-sig',newline='') as f:
                writer=csv.writer(f);writer.writerow(fields)
                for _ in range(400):writer.writerow(line)
            with path.open(encoding='utf-8-sig',newline='') as f:original=list(csv.DictReader(f))
            expected=[{key:(float(value) if key!='utc' else value) for key,value in r.items() if key=='utc' or value!=''} for r in original]
            cookies=[];self.assertEqual([dict(r) for r in read_rows(path,capture=cookies)],expected)
            self.assertEqual([dict(r) for r in read_rows(path,197,211,cookies)],expected[197:211])
            projected=['utc','brake','fuel_l','absent']
            self.assertEqual(list(values(path,projected,12,18)),[tuple(r.get(k,'') for k in projected) for r in original[12:18]])
            before=path.read_bytes();convert(path,replace=True)
            self.assertFalse(path.exists());self.assertEqual([dict(r) for r in read_rows(path)],expected)
            self.assertEqual([dict(r) for r in read_rows(path,197,211)],expected[197:211])
            self.assertEqual(list(values(path,projected)),[tuple(r.get(k,'') for k in projected) for r in rows(path,projected)])
            from telemetry_file import Path as ReadPath
            self.assertEqual(ReadPath(path).read_bytes(),before)
            r=next(read_rows(path));self.assertEqual(math.copysign(1,r['lap_distance_m']),-1)
            for bad in ('','nan','inf'):
                raw=Path(t)/('bad'+str(len(bad))+'.csv');badrow=line.copy();badrow[3]=bad
                with raw.open('w',encoding='utf-8',newline='') as f:writer=csv.writer(f);writer.writerow(fields);writer.writerow(badrow)
                with self.assertRaises(ValueError):list(read_rows(raw))

    def test_linear_full_throttle_window_keeps_inclusive_boundaries_and_unknowns(self):
        from training_report import measure,interpolate
        from training_zones import feature_time
        rng=random.Random(34)
        for case in range(200):
            data=[];distance=0.
            for i in range(80):
                distance+=rng.choice([0.,.25,1.,6.,12.]);throttle=rng.choice([.89,.9,.91,1.,0.])
                data.append([distance,i*.123456789,throttle,rng.choice([0.,.05,.2]),0,0,80+i])
            if case%7==0:data[30],data[31]=data[31],data[30]
            lap=dict(data=data)
            if case%2:lap['features']=dict(known_s=dict(coast=1,abs=1,tc=1),coverage={k:[[0,distance,20.]] for k in ('coast','abs','tc')},intervals={k:[[12,36,1.23456789]] for k in ('coast','abs','tc')})
            zone=dict(start=0.,end=distance,apex=distance/2)
            part=[interpolate(data,zone['start']),*[r for r in data if zone['start']<r[0]<zone['end']],interpolate(data,zone['end'])]
            after=[r for r in part if r[0]>=zone['apex']];expected=None
            for i,row in enumerate(after):
                tail=[r for r in after[i:] if r[0]<=row[0]+12]
                if row[2]>=.9 and after[-1][0]>=row[0]+12 and all(r[2]>=.9 for r in tail):expected=row[0];break
            result=measure(lap,zone);self.assertEqual(result['full_m'],expected)
            for key in ('abs','tc'):self.assertEqual(result[key+'_s'],feature_time(lap,zone,key))


@unittest.skipUnless(os.name=='nt','Windows Tk')
class UI(unittest.TestCase):
    from tests import test_ui_efficiency as helpers
    app=helpers.EfficiencyTests.app;pump=helpers.EfficiencyTests.pump
    def test_simulator_icons_survive_theme_language_keyboard_and_missing_install(self):
        app,root,errors=self.app()
        from simulator_icons import pixels
        for game in ('lmu','ac_evo'):self.assertIsNotNone(pixels(game,32,None,None).getbbox())
        for mode in ('dark','light'):
            app.set_theme(mode);app.toggle_language();self.pump(app,.12)
            box=app.simulator_selector;self.assertEqual(set(box.images),{'lmu','ac_evo'})
            self.assertTrue(box.itemcget(box.icon,'image'));self.assertGreater(box.coords(box.caption)[0],14*box.s)
            box.open();self.pump(app,.08)
            self.assertEqual(sum(box.panel.type(i)=='image' for i in box.panel.find_all()),2)
            self.assertLessEqual(box.winfo_rootx()+box.winfo_width(),app.shell.language_button.winfo_rootx())
            before=app.simulator_choice.get();box.event_generate('<Escape>');self.pump(app,.05)
            self.assertIsNone(box.popup);self.assertEqual(app.simulator_choice.get(),before)
        self.assertFalse(errors)


if __name__=='__main__':unittest.main()
