"""Small default checks and explicit change scopes; full history stays opt-in."""
import ast
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
SMOKE=(
    'tests.test_modularity.ModularityTests.test_core_and_cli_version_do_not_import_tk',
    'tests.test_distribution.DistributionTests.test_private_files_are_rejected_even_inside_source',
    'tests.test_lossless_storage.LosslessStorageTests.test_stream_boundaries_unicode_null_and_float64_match_standard_json',
    'tests.test_modularity.ModularityTests.test_shutdown_finishes_queued_writes_and_rejects_new_tasks',
    'tests.test_vehicle.VehicleTests.test_normal_shutdown_waits_for_every_pending_export_before_destroying_tk',
    'tests.test_personal_records.FeatureTests.test_record_winners_separate_layout_class_and_skip_demo_and_invalid',
)
UI=(
    'tests.test_navigation.NavigationTests.test_last_requested_page_wins_and_partial_build_is_cancelled',
    'tests.test_ui_polish51.PolishUITests.test_theme_and_language_rebuild_remove_old_toolbar_callbacks',
    'tests.test_ui_polish52.PolishUITests.test_home_controls_fit_with_recent_session_in_both_languages',
)
GROUPS=(
    (('control_report_tasks',),('tests.test_processing316.Data.test_report_receipts_use_game_steps_exclude_foreign_data_and_do_not_scan_samples','tests.test_processing316.UI.test_evo_shared_selection_recovery_only_failed_stage_and_cache_view')),
    (('curve_exports',),('tests.test_processing315.Processing.test_curve_reuse_across_views_invalidates_source_assets_and_missing_output',)),
    (('evo_comparison','evo_laps','evo_control','evo_compare'),('tests.test_evo_comparison314',)),
    (('report_pipeline','simulator_profiles'),('tests.test_refactor313.Reports','tests.test_refactor313.Capabilities')),
    (('control_view_state','control_run_actions'),('tests.test_refactor313.UI',)),
    (('hud_shutdown','control_hud_stop','hud'),('tests.test_ui_polish74',)),
    (('hud_layouts','hud_presentation','layout_actions','native_hotkeys','shortcut_','control_layouts','control_layout_','control_shortcuts'),('tests.test_hud_workflows',)),
    (('control_shell','control_widgets','control_theme','control_motion','control_pages','control_surface','control_toolbar','control_flow'),UI),
    (('control_image_viewport','control_report_images','report_images'),('tests.test_ui_polish59.Loader','tests.test_ui_polish59.UI.test_zoom_is_pointer_anchored_tiles_are_bounded_and_scroll_reaches_both_ends')),
    (('race_mode','race_mode_','control_race_mode','control_participation'),('tests.test_ui_polish70.Rules','tests.test_ui_polish71.Rules')),
    (('personal_records','control_records','control_record_','control_podiums','control_podium_','record_history'),('tests.test_personal_records',)),
    (('session_delete','control_delete','control_danger'),('tests.test_session_delete',)),
    (('column_store','telemetry_file','cache_budget','cache_tokens'),('tests.test_storage40',)),
    (('storage','storage_','session_compression','json_store','analysis_spool'),('tests.test_lossless_storage',)),
    (('telemetry_import','native_import'),('tests.test_lossless_storage.LosslessStorageTests.test_native_batch_duplicate_boundary_and_lookup_preserve_source_hash',)),
    (('engine','sampling','recorder','telemetry','telemetry_'),('tests.test_core','tests.test_telemetry_continuity')),
    (('session_archive','sevenzip','archive_preferences','control_transfers'),('tests.test_archives','tests.test_archive_modes')),
    (('guide','guide_','guidebook','control_guide','control_guide_','branding'),('tests.test_guide',)),
    (('video','video_','control_video','control_video_'),('tests.test_video_analysis','tests.test_video_ui')),
    (('report_','session_reports','race_report'),('tests.test_workflow_polish.RecoveryTests',)),
)

def git(*args):
    command=['git','-c','safe.directory='+ROOT.as_posix(),*args]
    return subprocess.check_output(command,cwd=ROOT,stderr=subprocess.DEVNULL).decode('utf-8')

def base_commit(base):
    try:return git('rev-parse','--verify','--end-of-options',base+'^{commit}').strip()
    except subprocess.CalledProcessError as error:raise ValueError('Cannot resolve test base: '+base) from error

def changed_paths(base=None):
    ref=base_commit(base or 'HEAD')
    paths=git('diff','--name-only','--no-renames','-z',ref,'--').split('\0')
    paths+=git('ls-files','--others','--exclude-standard','-z').split('\0')
    return list(dict.fromkeys(p for p in paths if p)),ref

def changed_test_targets(name,base):
    """A changed test body selects that method; shared fixtures select its module."""
    path=ROOT/name
    if not path.exists():return []
    module=name[:-3].replace('/','.')
    if base is None:return [module]
    diff=git('diff','--unified=0','--no-renames',base,'--',name)
    hunks=[(int(a),int(b or 1)) for a,b in re.findall(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@',diff)]
    if not hunks:return [module]
    tree=ast.parse(path.read_text('utf-8-sig'));methods=[]
    for cls in tree.body:
        if isinstance(cls,ast.ClassDef):
            methods.extend((node.lineno,node.end_lineno,module+'.'+cls.name+'.'+node.name) for node in cls.body if isinstance(node,ast.FunctionDef) and node.name.startswith('test_'))
    selected=[]
    for start,count in hunks:
        matches=[target for lo,hi,target in methods if lo<=start and start+max(1,count)-1<=hi]
        if not matches:return [module]
        selected.extend(matches)
    return list(dict.fromkeys(selected))

def related_targets(paths,base=None):
    paths=[name.replace('\\','/') for name in paths]
    runtime=[p for p in paths if not (p.startswith('docs/') or p.endswith('.md'))]
    if paths and not runtime:return []
    selected=list(SMOKE)
    for name in runtime:
        if name.startswith('tests/test_') and name.endswith('.py'):
            selected.extend(changed_test_targets(name,base));continue
        if name in ('tools/run_tests.py','tools/test_scope.py') or name.startswith('.github/workflows/'):
            selected.append('tests.test_test_scope');continue
        if name in ('tools/build.py','tools/check_bundle.py','tools/audit_publication.py') or name.startswith('requirements'):
            selected.append('tests.test_distribution');continue
        if not name.startswith('src/'):continue
        stem=Path(name).stem;matched=False
        for prefixes,targets in GROUPS:
            if any(stem==prefix or (prefix.endswith('_') and stem.startswith(prefix)) for prefix in prefixes):
                selected.extend(targets);matched=True;break
        if not matched and stem.startswith('control_'):selected.append(UI[0])
    return list(dict.fromkeys(selected))

def full_targets():
    return ['tests.'+path.stem for path in sorted((ROOT/'tests').glob('test_*.py'))]
