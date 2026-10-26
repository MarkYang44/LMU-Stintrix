"""Target only affected checks and retain failure visibility and full coverage."""
import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from tools import test_scope

class ScopeTests(unittest.TestCase):
    def test_default_is_small_and_docs_do_not_start_runtime_checks(self):
        self.assertEqual(test_scope.related_targets([]),list(test_scope.SMOKE))
        self.assertEqual(len(test_scope.SMOKE),6)
        self.assertEqual(test_scope.related_targets(['docs/USAGE.md','README.md']),[])

    def test_hud_change_does_not_select_unrelated_historical_suites(self):
        selected=test_scope.related_targets(['src/hud_shutdown.py'])
        self.assertIn('tests.test_ui_polish74',selected)
        self.assertFalse(any('video' in name or 'archive' in name or 'polish51' in name for name in selected))

    def test_only_edited_test_body_is_selected_and_shared_fixture_is_not_missed(self):
        with tempfile.TemporaryDirectory(dir=test_scope.ROOT/'_local') as folder:
            root=Path(folder);(root/'tests').mkdir();path=root/'tests/test_example.py'
            path.write_text('class Example:\n    def test_first(self):\n        pass\n    def test_second(self):\n        pass\n','utf-8')
            with patch.object(test_scope,'ROOT',root),patch.object(test_scope,'git',return_value='@@ -3 +3 @@\n'):
                self.assertEqual(test_scope.changed_test_targets('tests/test_example.py','base'),['tests.test_example.Example.test_first'])
            with patch.object(test_scope,'ROOT',root),patch.object(test_scope,'git',return_value='@@ -1 +1 @@\n'):
                self.assertEqual(test_scope.changed_test_targets('tests/test_example.py','base'),['tests.test_example'])

    def test_imported_duplicate_cases_run_once_and_missing_targets_still_fail(self):
        from tools.run_tests import case_names
        targets=['tests.test_personal_records.FeatureTests','tests.test_podium_records']
        names,removed=case_names(targets)
        self.assertEqual(removed,8);self.assertEqual(len(names),len(set(names)))
        missing,_=case_names(['tests.no_such_test_scope_module'])
        self.assertEqual(len(missing),1);self.assertIn('_FailedTest',missing[0])

    def test_invalid_diff_base_is_an_error_not_an_empty_success(self):
        with self.assertRaises(ValueError):test_scope.changed_paths('refs/heads/nonexistent-test-scope-base')
