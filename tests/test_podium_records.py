"""Real podium criteria, archival duplicates, bounded telemetry and tab navigation."""
import csv,json,os,shutil,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from podium_records import index,detail
from tests.test_personal_records import FeatureTests
from laps import export_fastest

class PodiumTests(unittest.TestCase):
    def session(self,root,name,place=1,**summary):
        folder=FeatureTests().session(root,name,track='Sebring International Raceway',vehicle='Porsche 911 GT3 R LMGT3',vehicle_class='GT3',session=10,source='LMU_Data',started_utc='2026-10-12T12:00:'+str(len(list((Path(root)/'Logs').glob('*')))).zfill(2)+'+00:00')
        s=dict(available=True,finish_flag=1,finish_class_place=place,class_position_available=True,class_size=10,
            grid_place=20,finish_place=8,grid_class_place=4,vehicle_class='GT3',team='Test Team',recording_started_mid_session=False)
        s.update(summary);(folder/'race_summary.json').write_text(json.dumps(s),encoding='utf-8')
        export_fastest(folder,ROOT/'src/compare.html');return folder

    def test_only_confirmed_class_podiums_not_overall_positions(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            for p in (1,2,3,4):self.session(t,'rank'+str(p),p,finish_place=12)
            self.session(t,'overall-win',4,finish_place=1)
            self.session(t,'dnf',1,finish_flag=2);self.session(t,'dq',1,finish_flag=3)
            self.session(t,'unfinished',1,finish_flag=0);self.session(t,'unknown',None)
            self.session(t,'false-rank',True);self.session(t,'unavailable',1,class_position_available=False)
            self.session(t,'impossible',3,class_size=2)
            result=index(t);self.assertEqual([e['place'] for e in result['entries']],[1,2,3])
            self.assertEqual(result['counts'],{1:1,2:1,3:1});self.assertTrue(all(e['vehicle_class']=='LMGT3' for e in result['entries']))

    def test_practice_qualifying_demo_and_active_sessions_are_excluded(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            for name,extra in [('practice',dict(session=0)),('qualify',dict(session=5)),('demo',dict(source='Synthetic demo')),('active',dict(status='recording'))]:
                f=self.session(t,name);m=json.loads((f/'session.json').read_text());m.update(extra);(f/'session.json').write_text(json.dumps(m))
            self.assertFalse(index(t)['entries'])

    def test_duplicate_imports_are_one_race_and_conflicts_are_not_awards(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            original=self.session(t,'winner');imported=Path(t)/'ImportedLogs'/'copy';imported.parent.mkdir();shutil.copytree(original,imported)
            self.assertEqual(len(index(t)['entries']),1)
            s=json.loads((imported/'race_summary.json').read_text());s['finish_class_place']=2;(imported/'race_summary.json').write_text(json.dumps(s))
            result=index(t);self.assertEqual(result['conflicts'],1);self.assertFalse(result['entries'])

    def test_explicit_end_journal_recovers_missing_summary_without_inventing_ranks(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            f=self.session(t,'journal');(f/'race_summary.json').unlink()
            with (f/'race_events.csv').open('w',newline='') as stream:
                w=csv.DictWriter(stream,fieldnames=['session_time_s','event','payload_json']);w.writeheader()
                w.writerow(dict(session_time_s=30,event='recording_end',payload_json=json.dumps(dict(finish_flag=1,class_place=2,class_size=8,vehicle_class='GT3'))))
            self.assertEqual(index(t)['entries'][0]['place'],2)
            (f/'race_events.csv').write_text('session_time_s,event,payload_json\n')
            self.assertFalse(index(t)['entries'])

    def test_race_detail_reads_whole_recording_conditions_and_bounded_curves(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            f=self.session(t,'winner',race_started_et=1,race_finished_et=35)
            p=f/'inputs.csv'
            with p.open(newline='') as stream:r=csv.DictReader(stream);columns=r.fieldnames;rows=list(r)
            extras=['fuel_l','tyre_front_name','tyre_rear_name','track_temp_c','wetness','rain']
            with p.open('w',newline='') as stream:
                w=csv.DictWriter(stream,fieldnames=[*columns,*[k for k in extras if k not in columns]]);w.writeheader()
                for i,row in enumerate(rows):w.writerow({**row,'fuel_l':60-i/len(rows)*10,'tyre_front_name':'Medium','tyre_rear_name':'Medium','track_temp_c':30+i/len(rows),'wetness':0,'rain':0})
            before={p:p.read_bytes() for p in f.iterdir() if p.is_file()};entry=index(t)['entries'][0];value=detail(entry)
            self.assertEqual(value['race_s'],34);self.assertEqual(value['start']['fuel_l'],60)
            self.assertLess(value['end']['fuel_l'],51);self.assertEqual(value['start']['tyre_front_name'],'Medium')
            self.assertGreater(value['recorded_s'],0);self.assertTrue(value['pace']);self.assertLessEqual(len(value['inputs']),600)
            self.assertEqual({p:p.read_bytes() for p in before},before)

    def test_race_clock_uses_observed_green_and_first_successful_finish_only(self):
        from race_journal import RaceJournal
        from tests.test_race_images import sample
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            initial=sample(10,state=dict(phase=3));journal=RaceJournal(t,initial);journal.observe(initial)
            journal.observe(sample(20,state=dict(phase=5)))
            journal.observe(sample(30,state=dict(phase=6)))
            journal.observe(sample(40,state=dict(phase=5)))
            journal.observe(sample(100,finish=1));journal.observe(sample(101,finish=1));journal.finish('test')
            self.assertEqual(journal.summary['race_started_et'],20)
            self.assertEqual(journal.summary['race_finished_et'],100)
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t:
            initial=sample(20);journal=RaceJournal(t,initial);journal.observe(initial)
            journal.observe(sample(100,finish=2));journal.finish('test')
            self.assertNotIn('race_started_et',journal.summary)
            self.assertNotIn('race_finished_et',journal.summary)

    @unittest.skipUnless(os.name=='nt','Windows native UI')
    def test_sibling_tabs_categories_refresh_and_language_preserve_navigation(self):
        import control_center,i18n
        from control_widgets import Pill
        from control_list import SessionList
        from control_metrics import Metrics
        def walk(w):
            for c in w.winfo_children():yield c;yield from walk(c)
        with tempfile.TemporaryDirectory(dir=ROOT/'_local') as t,patch('control_center.ROOT',Path(t)),patch('control_center.ControlCenter.repair_windows_entry'):
            for p in (1,2,3):self.session(t,'race'+str(p),p)
            center=control_center.ControlCenter();errors=[];center.root.report_callback_exception=lambda *args:errors.append(str(args))
            def wait(test):
                deadline=time.monotonic()+8
                while time.monotonic()<deadline:
                    center.root.update();time.sleep(.01)
                    if test():return
                self.fail('Podium UI did not settle')
            try:
                center.show_page(6)
                tab=next(w for w in walk(center.content) if isinstance(w,Pill) and w.label=='领奖台记录');tab.command()
                wait(lambda:'场同组领奖台赛事' in center.status.get())
                table=next(w for w in walk(center.content) if isinstance(w,SessionList));self.assertEqual(len(table.rows),3)
                button=next(w for w in walk(center.content) if isinstance(w,Pill) and w.label.startswith('亚军'));button.command()
                self.assertEqual(len(table.rows),1)
                wait(lambda:any(isinstance(w,Metrics) and 'recorded' in w.values and w.values['recorded'].cget('text')!='—' for w in walk(center.content)))
                center.toggle_language();wait(lambda:'class podium races' in center.status.get())
                center.show_page(0);center.show_page(6);wait(lambda:'class podium races' in center.status.get())
                self.assertEqual(center.personal_record_view,'podium');self.assertFalse(errors,errors)
            finally:center.close();i18n.set_language('zh')

if __name__=='__main__':unittest.main()
