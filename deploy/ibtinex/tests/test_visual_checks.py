import sys
import json
from pathlib import Path
import subprocess
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from visual_checks import MOBILE_READY_PREDICATE, contrast_ratio, validate_target


class VisualChecksTests(unittest.TestCase):
    def test_mobile_ready_predicate_returns_boolean_without_invoking_class(self):
        # Exercise Playwright's function-valued predicate convention with a real
        # JS class. Calling BottomSheet as a predicate used to throw before new.
        script = """
const source = JSON.parse(process.argv[1]);
const cases = [undefined, {}, {ui: {}}, {ui: {mobile_nav: {defined: false}, BottomSheet: class BottomSheet {}}},
    {ui: {mobile_nav: {defined: true}}}, {ui: {mobile_nav: {defined: true}, BottomSheet: class BottomSheet {}}}];
const actual = cases.map(frappe => {
    globalThis.window = {frappe};
    let predicate = globalThis.eval(source);
    if (typeof predicate === 'function') predicate = predicate();
    if (typeof predicate !== 'boolean') throw Error('Readiness must be a boolean.');
    return predicate;
});
process.stdout.write(JSON.stringify(actual));
"""
        result = subprocess.run(['node', '-e', script, json.dumps(MOBILE_READY_PREDICATE)],
                                check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(result.stdout), [False, False, False, False, False, True])

    def test_wcag_luminance_reference_pairs(self):
        self.assertAlmostEqual(contrast_ratio((0, 0, 0), (255, 255, 255)), 21)
        self.assertAlmostEqual(contrast_ratio((80, 80, 80), (80, 80, 80)), 1)
        self.assertLess(contrast_ratio((119, 119, 119), (255, 255, 255)), 4.5)
        self.assertGreater(contrast_ratio((118, 118, 118), (255, 255, 255)), 4.5)

    def test_brand_text_and_primary_pairs_are_readable(self):
        for fg, bg in [((27, 36, 31), (244, 245, 239)),
                       ((255, 255, 255), (16, 43, 33)),
                       ((16, 43, 33), (212, 245, 148))]:
            with self.subTest(foreground=fg, background=bg):
                self.assertGreaterEqual(contrast_ratio(fg, bg), 4.5)

    def test_browser_can_only_target_dedicated_local_ci_site(self):
        self.assertEqual(validate_target("http://127.0.0.1:8081/", "starter.ibtinex-ci.invalid"), "http://127.0.0.1:8081")
        for origin, site in [
            ("https://customer.example", "starter.ibtinex-ci.invalid"),
            ("http://localhost:8081", "customer.localhost"),
            ("http://user:secret@localhost:8081", "starter.ibtinex-ci.invalid"),
            ("http://localhost:8081/path", "starter.ibtinex-ci.invalid"),
            ("http://localhost:8081?token=secret", "starter.ibtinex-ci.invalid"),
        ]:
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                validate_target(origin, site)


if __name__ == "__main__":
    unittest.main()
