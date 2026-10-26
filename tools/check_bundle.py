"""Extract a fresh portable ZIP and verify it without the source virtualenv."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import uuid
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'src'))
from tools.build import bundle_audit

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--no-checksums',action='store_true');parser.add_argument('--archive',type=Path);args=parser.parse_args()
    version=(ROOT/'VERSION').read_text().strip()
    archive=args.archive or ROOT/'dist'/f'LMU-Stintrix-v{version}-windows-x64.zip'
    target=ROOT/'_local'/'validation'/uuid.uuid4().hex[:12];target.mkdir(parents=True)
    with zipfile.ZipFile(archive) as source:
        for name in source.namelist():
            resolved=(target/name).resolve()
            if not resolved.is_relative_to(target.resolve()):raise ValueError('Unsafe ZIP member')
        source.extractall(target)
    bundle=target/'LMU-Stintrix';bundle_audit(bundle)
    manifest=json.loads((bundle/'build-manifest.json').read_text(encoding='utf-8'))
    assert manifest['version']==version
    actual={p.relative_to(bundle).as_posix() for p in bundle.rglob('*') if p.is_file() and p.name!='build-manifest.json'}
    assert actual==set(manifest['files'])
    for name,digest in manifest['files'].items():
        if manifest.get('file_metadata')=='size':
            assert (bundle/name).stat().st_size==digest,name
            continue
        if args.no_checksums:continue
        h=hashlib.sha256()
        with (bundle/name).open('rb') as stream:
            for block in iter(lambda:stream.read(1048576),b''):h.update(block)
        assert h.hexdigest()==digest,name
    from PyInstaller.archive.readers import CArchiveReader
    archive=CArchiveReader(str(bundle/'LMU-Stintrix.exe'))
    modules=set();embedded=None
    for name in archive.toc:
        if name.endswith('.pyz'):
            embedded=archive.open_embedded_archive(name);modules.update(embedded.toc)
    # Check the shipping read path, including the default-map regression that
    # was not exercised by older custom-map fixtures. No file hashing needed.
    import types
    def codes(code):
        yield code
        for item in code.co_consts:
            if isinstance(item,types.CodeType):yield from codes(item)
    telemetry_codes=list(codes(embedded.extract('telemetry')))
    reader_read=next(c for c in telemetry_codes if c.co_name=='read')
    assert 'gate' not in reader_read.co_names and 'ready' not in reader_read.co_names,'Shipping reader still consumes update gate signals'
    contract=embedded.extract('telemetry_contract')
    assert any(c.co_name=='EventPresence' for c in codes(contract))
    assert not any('WaitForSingleObject' in c.co_names for c in codes(contract)),'Interface diagnostics must not consume game notifications'
    assert {'library','laps','session_archive','sevenzip','archive_preferences'}<=modules
    assert {'control_forms','control_transfers','video_sampling','video_results','control_video_results'}<=modules
    assert {'control_context','control_toolbar','control_sections','control_data','control_disposal','control_video_options'}<=modules
    assert {'control_surface','control_page_error'}<=modules
    for name,required in [('race_mode_overrides',{'load','save','apply'}),('control_race_mode',{'show'}),('control_best_view',{'Layout','resize','details','listing'})]:
        assert name in modules and required<={c.co_name for c in codes(embedded.extract(name))},'Shipping participation or record workflow is stale: '+name
    for name,required in [('control_surface',{'begin','reveal','redraw'}),('control_pages',{'hold','commit','fail'}),('control_guide',{'install_actions'})]:
        assert required<={c.co_name for c in codes(embedded.extract(name))},'Shipping page handoff is stale: '+name
    assert {'control_action_menu','control_search'}<=modules
    for name,required in [('control_immediate_save',{'submit','retry','reload'}),('control_data_browser',{'mount','sync','install_actions','resize_table'}),('control_sampling_intro',{'build','refresh'})]:
        assert name in modules and required<={c.co_name for c in codes(embedded.extract(name))},'Shipping compact data/settings workflow is stale: '+name
    assert any(c.co_name=='flush' and 'force' in c.co_varnames for c in codes(embedded.extract('control_search'))),'Shipping search clear handling is stale'
    for name,required in [('control_renderer',{'save','capture','close_draft'}),('control_table_layouts',{'compact','use','actions'}),('control_batch_results',{'sync','open_review','locate'}),('control_session_location',{'locate','augment','restore'})]:
        assert name in modules and required<={c.co_name for c in codes(embedded.extract(name))},'Shipping draft/result workflow is stale: '+name
    assert 'select' in {c.co_name for c in codes(embedded.extract('control_form_bar'))},'Shipping save scope is stale'
    assert 'issue_text' in {c.co_name for c in codes(embedded.extract('control_batch'))},'Shipping batch errors can still be blank'
    for name,required in [('control_library',{'show','Library','locate','restore_location','refresh'}),('control_library_actions',{'Actions','note','compare','reference','image'})]:
        assert name in modules and required<={c.co_name for c in codes(embedded.extract(name))},'Shipping full-record manager is stale: '+name
    video_codes=list(codes(embedded.extract('control_video_results')))
    assert any(c.co_name=='refresh' and 'pending' in c.co_consts for c in video_codes),'Shipping video refresh requests are not bounded'
    assert any(c.co_name=='selected' and 'len' in c.co_names for c in video_codes),'Shipping video single-item actions are unguarded'
    assert {'hud_layouts','hud_presentation','layout_actions','shortcut_keys','native_hotkeys','shortcut_service','control_layouts','control_shortcuts','recent_session','control_recent_session'}<=modules
    assert {'control_layout_preview','control_run_state','control_table_preferences'}<=modules
    assert {'control_confirm','control_validation','control_settings_search','control_tooltip','preference_error'}<=modules
    assert {'control_batch','control_video_close','control_table_sort'}<=modules
    assert {'control_notes','control_danger','control_form_bar','control_flow'}<=modules
    assert {'control_worklist','control_report_tasks','control_cache_panel'}<=modules
    assert {'control_analysis_window','control_analysis_policy'}<=modules
    assert 'control_record_browser' in modules
    assert 'control_record_details' in modules
    for name,required in [('control_best',{'detail_key','populate_best','render_selection','toggle_filters','install_actions'}),('control_guide_compare',{'Comparison','layout','fit','sources'}),('control_guide',{'go_page','update_pagers','focus_search','browse'})]:
        assert name in modules and required<={c.co_name for c in codes(embedded.extract(name))},'Shipping record/library workflow is stale: '+name
    assert any(c.co_name=='select' and 'failures' in c.co_names and '未提供错误详情' in c.co_consts for c in codes(embedded.extract('control_record_details'))),'Shipping detail retry handling is stale'
    assert any(c.co_name=='run' and {'type','__name__'}<=set(c.co_names) for c in codes(embedded.extract('background'))),'Shipping background errors can still be blank'
    for name,required in [('control_record_details',{'key','select','start','detach'}),('control_podiums',{'read_index','read_detail','detail_waiting','apply_detail','open_primary','refresh_records'})]:
        assert required<={c.co_name for c in codes(embedded.extract(name))},'Shipping podium browser is stale: '+name
    assert any(c.co_name=='layout' and {'wrap','captions'}<=set(c.co_names) for c in codes(embedded.extract('control_metrics'))),'Shipping detail grid still uses self-sizing labels'
    for name,required in [('control_record_browser',{'bind','read','start','dispose','curve_identity','save_curve'}),('control_history',{'report_update','render_selection','read_history'}),('control_official_results',{'read_results','sync_results','sync_folder'})]:
        assert required<={c.co_name for c in codes(embedded.extract(name))},'Shipping record browser is stale: '+name
    for name,required in [('control_zone_editor',{'apply_form','reset','undo','commit','dispose'}),('control_training_goals',{'refresh','start','finish','dispose'})]:
        assert required<={c.co_name for c in codes(embedded.extract(name))},'Shipping training editor is stale: '+name
    for name,required in [('control_analysis_window',{'existing','analyse','continue_scan','start','close','export'}),('control_analysis_policy',{'read','layout'}),('control_training',{'set_goal','render'}),('control_comparable',{'identity','render'})]:
        assert required<={c.co_name for c in codes(embedded.extract(name))},'Shipping analysis workflow is stale: '+name
    assert {'control_report_images','control_image_viewport','report_images'}<=modules
    for name,required in [('control_report_images',{'show','reread','generated'}),('control_image_viewport',{'paint','zoom','scrollbar'}),('report_images',{'request','poll','close'})]:
        assert required<={c.co_name for c in codes(embedded.extract(name))},'Shipping report viewer is stale: '+name
    assert any(c.co_name=='generate' and 'force' in c.co_varnames for c in codes(embedded.extract('race_report')))
    for name,required in [('control_achievement',{'record_key','start_preview','open_last','dispose'}),('achievement_card',{'save_image'})]:
        assert required<={c.co_name for c in codes(embedded.extract(name))},'Shipping achievement workflow is stale: '+name
    for name,required in [('control_maintenance',{'offline_ready'}),('control_report_tasks',{'readable','progress'}),('control_worklist',{'load','dispose'}),('split_checks',{'checked_state','unmark'})]:
        assert required<={c.co_name for c in codes(embedded.extract(name))},'Shipping maintenance workflow is stale: '+name
    for name,required in [('control_profile',{'defaults','recorded_cars','focus_field'}),('control_lap_pair',{'filter_events','select_initial','open_last'}),('control_batch',{'render','copy_errors'}),('control_video_results',{'open_result','dispose'}),('control_video_history',{'snapshot','dirty','source_text'})]:
        assert required<={c.co_name for c in codes(embedded.extract(name))},'Shipping workflow is stale: '+name
    assert {'control_lap_pair','lap_comparison','lap_identity','personal_records','control_records','recording_policy'}<=modules
    assert {'track_names','record_presentation','control_metrics'}<=modules
    assert 'class_positions' in modules
    assert {'podium_records','control_podiums'}<=modules
    assert 'control_record_art' in modules
    assert 'control_feedback' in modules
    assert {'race_mode','control_mode_filters','session_groups'}<=modules
    assert {'official_results','control_official_results','telemetry_contract','control_interface','training_zones','control_zone_map','control_zone_editor','condition_match','comparable_progress','control_comparable','comparable_presentation'}<=set(modules)
    assert {'training_report','training_presentation','control_training','record_history','control_history','history_view','control_history_chart','achievement_card','control_achievement'}<=modules
    assert {'review_filters','control_review_filters','lmu_mark'}<=modules
    assert {'control_video','video_cli','video_media','video_signal','video_alignment','video_analysis','video_ocr','video_report'}<=modules
    assert {'control_video_layout','control_video_widgets'}<=modules
    assert {'control_video_history','video_history'}<=modules
    assert {'control_video_assist','video_preferences'}<=modules
    assert {'column_store','telemetry_file','cache_budget','cache_tokens','report_assets','lap_exports','export_cache','storage_actions'}<=modules
    codec={};exec(embedded.extract('column_store'),codec)
    assert codec['MAGIC']==b'STXCOL2\n' and codec['LEGACY_MAGIC']==b'STXCOL1\n','Shipping column format is stale'
    values=[str(i).encode() for i in range(2048)]
    assert codec['_decode'](codec['_encode'](values),len(values))==values,'Shipping compact column roundtrip failed'
    video_methods={c.co_name for c in codes(embedded.extract('control_video'))}
    assist_methods={c.co_name for c in codes(embedded.extract('control_video_assist'))}
    assert {'manual_zoom','preview_resized'}<=video_methods and {'preview_stamp','remember_preview'}<=assist_methods,'Shipping video preview code is stale'
    assert 'control_video_guide' in modules
    assert {'primary_action','show_help','range_issue'}<={c.co_name for c in codes(embedded.extract('control_video_guide'))},'Shipping onboarding is stale'
    from sevenzip import SHA256
    if not args.no_checksums:assert hashlib.sha256((bundle/'_internal/src/tools/7zr.exe').read_bytes()).hexdigest()==SHA256
    assert not any(name.split('.')[0] in {'doctor','release_smoke','tests','tools'} for name in modules)
    assert {'session_delete','control_delete','control_repaint','control_pages','control_fields','windows_integration','control_shell','control_motion','control_list','control_theme','branding','guidebook','control_guide','guide_library','guide_cards','PIL.ImageTk','PIL.WebPImagePlugin'}<=modules
    import pefile
    executable=pefile.PE(str(bundle/'LMU-Stintrix.exe'))
    resources={entry.id:entry for entry in executable.DIRECTORY_ENTRY_RESOURCE.entries}
    icons=[]
    for entry in resources[3].directory.entries:
        data=entry.directory.entries[0].data.struct
        icons.append(executable.get_data(data.OffsetToData,data.Size))
    import struct
    ico=(bundle/'_internal/src/branding/stintrix.ico').read_bytes();count=struct.unpack_from('<H',ico,4)[0];expected=[]
    for i in range(count):
        length,offset=struct.unpack_from('<II',ico,6+i*16+8);expected.append(ico[offset:offset+length])
    assert set(icons)==set(expected) and count==6,'EXE icon differs from reviewed STX icon'
    from tools.audit_publication import PUBLIC_ASSETS
    from tools.build_brand import render
    reviewed=render(target/'reviewed-branding')
    assert ico==(reviewed/'stintrix.ico').read_bytes()
    for name in ('menu-icon.png','menu-icon-light.png'):
        assert (bundle/'_internal/src/branding'/name).read_bytes()==(reviewed/name).read_bytes()
    for name,wanted in PUBLIC_ASSETS.items():
        if not args.no_checksums and name.startswith('src/guide/'):assert hashlib.sha256((bundle/'_internal'/name).read_bytes()).hexdigest()==wanted,name
    guide=json.loads((bundle/'_internal/src/guide/catalog.json').read_text(encoding='utf-8'))
    assert len(guide['tracks'])==18 and len(guide['cars'])==24 and guide['total_recommendations']==144
    executable.close()
    print('Portable manifest, privacy and development-code exclusion: PASS',flush=True)
    if args.smoke:
        from tests.portable_smoke import run
        run(bundle,target/'synthetic-data')
        print('Shipping EXE, normal shutdown, complete-lap reports and archive roundtrip: PASS',flush=True)
    print('Validation folder: '+str(bundle))

if __name__=='__main__':main()
