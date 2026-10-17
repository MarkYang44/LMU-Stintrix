"""Run Tcl and worker fixtures in separate processes; no personal fixtures."""
import argparse
from pathlib import Path
import subprocess
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def flatten(suite):
    for case in suite:
        if isinstance(case,unittest.TestSuite):yield from flatten(case)
        else:yield case

def main():
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8',errors='replace')
    if hasattr(sys.stderr,'reconfigure'):sys.stderr.reconfigure(encoding='utf-8',errors='replace')
    parser=argparse.ArgumentParser();parser.add_argument('--quick',action='store_true');parser.add_argument('--modules',nargs='+');args=parser.parse_args()
    modules=['tests.test_distribution'] if args.quick else ['tests.test_core','tests.test_upgrades','tests.test_laplab','tests.test_selected_laps','tests.test_vehicle','tests.test_endurance','tests.test_distribution','tests.test_lightweight','tests.test_archives','tests.test_modularity','tests.test_race_images','tests.test_control_center']
    if not args.quick:modules.extend(['tests.test_desktop','tests.test_guide','tests.test_desktop_controls','tests.test_language','tests.test_navigation','tests.test_session_delete','tests.test_maps','tests.test_memory','tests.test_lossless_storage','tests.test_archive_modes','tests.test_personal_records','tests.test_review_layout','tests.test_class_positions','tests.test_podium_records'])
    if not args.quick:modules.extend(['tests.test_review_filters','tests.test_record_intelligence','tests.test_motion','tests.test_feedback','tests.test_career_analysis','tests.test_telemetry_continuity','tests.test_race_modes','tests.test_event_catalog','tests.test_event_filter_ui'])
    if not args.quick:modules.extend(['tests.test_video_analysis','tests.test_video_ui','tests.test_video_motion','tests.test_video_history','tests.test_video_assist'])
    if not args.quick:modules.extend(['tests.test_storage40','tests.test_video_guide'])
    if args.modules:modules=args.modules
    names=[case.id() for module in modules for case in flatten(unittest.defaultTestLoader.loadTestsFromName(module))]
    if not args.quick and not args.modules:names.extend(case.id() for case in flatten(unittest.defaultTestLoader.loadTestsFromName('tests.test_workflow_polish')))
    failed=[]
    for name in names:
        result=subprocess.run([sys.executable,'-m','unittest',name,'-q'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
        print(('PASS' if result.returncode==0 else 'FAIL')+' '+name,flush=True)
        if result.returncode:failed.append(name);print(result.stdout+result.stderr,flush=True)
    print(f'{len(names)-len(failed)}/{len(names)} passed');return int(bool(failed))

if __name__=='__main__':raise SystemExit(main())
