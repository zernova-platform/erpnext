#!/usr/bin/env python3
"""Real Chromium checks for the disposable IBTINEX qualification installation.

No mocked ERP pages, authentication traces, cookies, or HTML are exported. The
"before" reference is the *same candidate runtime* with its isolated IBTINEX
theme stylesheet disabled; it is not represented as a screenshot of an old image.
This is a focused visual/accessibility regression gate, not WCAG certification.

Dependencies: playwright==1.62.0; python -m playwright install --with-deps chromium
"""

import argparse
import hashlib
import html
import json
from pathlib import Path
import platform
import re
import sys
from urllib.parse import urlsplit


THEME_BUNDLE = "ibtinex-theme.bundle"
COMPANY = "IBTINEX Starter Ethiopia"
VIEWPORTS = {"desktop": {"width": 1440, "height": 1000}, "mobile": {"width": 390, "height": 844}}


def contrast_ratio(foreground, background):
    """WCAG relative luminance for opaque sRGB triples, range 0..255."""
    def luminance(rgb):
        values = [channel / 255 for channel in rgb]
        linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in values]
        return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

    light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


def validate_target(base_url, site):
    parsed = urlsplit(base_url)
    if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost", "::1")
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ("", "/")):
        raise ValueError("Visual qualification requires a loopback HTTP origin without credentials or path.")
    if not site.endswith(".ibtinex-ci.invalid") or not re.fullmatch(r"[a-z0-9.-]+", site):
        raise ValueError("Visual qualification is restricted to the dedicated CI site suffix.")
    return base_url.rstrip("/")


# Return rendered colour samples without exporting document text, business data,
# DOM, cookies, session storage, or input values. Alpha is composited correctly.
COLOUR_SAMPLES = r"""(selector) => {
    const rgba = value => {
        const matches = value.match(/[\d.]+/g);
        if (!matches || matches.length < 3) return null;
        const values = matches.map(Number);
        return [values[0], values[1], values[2], values.length > 3 ? values[3] : 1];
    };
    const composite = (fg, bg) => fg.slice(0, 3).map((c, i) => c * fg[3] + bg[i] * (1 - fg[3]));
    const background = el => {
        const ancestors = [];
        for (let n = el; n; n = n.parentElement) ancestors.unshift(n);
        let colour = [255, 255, 255];
        let uncertain = false;
        for (const n of ancestors) {
            const css = getComputedStyle(n);
            if (css.backgroundImage !== 'none' || Number(css.opacity) < 1) uncertain = true;
            const value = rgba(css.backgroundColor);
            if (value) colour = composite(value, colour);
        }
        return { colour, uncertain };
    };
    const result = [];
    for (const el of document.querySelectorAll(selector)) {
        const css = getComputedStyle(el), box = el.getBoundingClientRect();
        if (!box.width || !box.height || css.visibility !== 'visible' || css.display === 'none'
                || !el.innerText?.trim() || el.disabled || el.closest('[aria-disabled=true]')) continue;
        if (box.bottom < 0 || box.top > innerHeight || box.right < 0 || box.left > innerWidth) continue;
        const bg = background(el), fg = rgba(css.color);
        if (!fg) continue;
        const size = parseFloat(css.fontSize), weight = parseInt(css.fontWeight) || 400;
        result.push({
            element: el.tagName.toLowerCase(),
            classes: String(el.className).slice(0, 180),
            foreground: composite(fg, bg.colour), background: bg.colour,
            threshold: size >= 24 || (size >= 18.6667 && weight >= 700) ? 3 : 4.5,
            font_size_px: size, font_weight: weight,
            manual_background_review: bg.uncertain
        });
        if (result.length >= 120) break;
    }
    return result;
}"""


class VisualQualification:
    def __init__(self, page, output):
        self.page = page
        self.output = output
        self.report = {
            "schema_version": 1,
            "status": "running",
            "runner_os": platform.system(),
            "browser": "Chromium",
            "baseline_method": "Same candidate runtime; only ibtinex-theme.bundle stylesheet disabled",
            "scope": "Disposable synthetic starter installation",
            "screenshots": [],
            "checks": [],
            "contrast_samples": [],
            "semantic_text_contrast": {},
            "accessibility_findings": [],
            "theme_contrast_regressions": [],
            "not_verified": [
                "Full WCAG 2.2 AA conformance, screen-reader usability, and human visual acceptance",
                "Windows Docker Desktop installation (this browser suite does not perform it)",
                "macOS Safari, Firefox, real touch hardware, and operating-system high-contrast settings",
            ],
        }

    def record(self, name, **details):
        self.report["checks"].append({"name": name, "status": "passed", **details})

    def ready(self, desk=False):
        if desk:
            self.page.wait_for_function("window.frappe?.app && frappe.request.ajax_count === 0", timeout=90000)
            self.page.locator(".layout-main-section:visible").first.wait_for(state="visible")
        self.page.evaluate("() => document.fonts.ready")
        self.page.wait_for_function("document.querySelectorAll('link[rel=stylesheet]').length > 0")

    def theme(self, mode):
        self.page.evaluate("""mode => {
            document.documentElement.setAttribute('data-theme-mode', mode);
            document.documentElement.setAttribute('data-theme', mode);
            if (window.frappe?.ui?.set_theme) frappe.ui.set_theme(mode);
        }""", mode)

    def switch_stylesheet(self, enabled):
        count = self.page.evaluate("""({needle, enabled}) => {
            let count = 0;
            for (const sheet of document.styleSheets) {
                if (sheet.href?.includes(needle)) { sheet.disabled = !enabled; count++; }
            }
            return count;
        }""", {"needle": THEME_BUNDLE, "enabled": enabled})
        if not count:
            raise AssertionError("Compiled IBTINEX theme bundle is missing from the rendered page.")
        self.page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")

    def colour_samples(self):
        samples = self.page.evaluate(COLOUR_SAMPLES,
            "h1,h2,h3,h4,label,button,a,small,.control-label,.indicator-pill,.field-error,.alert")
        for sample in samples:
            sample["ratio"] = round(contrast_ratio(sample["foreground"], sample["background"]), 3)
            sample["passed"] = sample["ratio"] >= sample["threshold"]
        return samples

    def contrast(self, name, before):
        samples = self.colour_samples()
        # Stylesheet toggling leaves the document structure unchanged. Match by
        # stable class/tag occurrence, not document text or generated selectors.
        def keyed(items):
            counts, result = {}, {}
            for item in items:
                key = (item["element"], item["classes"])
                counts[key] = counts.get(key, 0) + 1
                result[(*key, counts[key])] = item
            return result
        previous = keyed(before)
        for key, sample in keyed(samples).items():
            sample["surface"] = name
            self.report["contrast_samples"].append(sample)
            if not sample["passed"] or sample["manual_background_review"]:
                self.report["accessibility_findings"].append(sample)
            native = previous.get(key)
            if (native and native["passed"] and not sample["passed"]
                    and not native["manual_background_review"] and not sample["manual_background_review"]):
                self.report["theme_contrast_regressions"].append({
                    **sample, "native_ratio": native["ratio"],
                })

    def semantic_contrast(self, mode):
        pairs = [("text", "page"), ("text", "surface"), ("muted", "surface"),
                 ("muted", "surface-secondary"), ("primary-text", "primary"),
                 ("nav-text", "brand"), ("nav-muted", "brand"),
                 ("success", "success-bg"), ("warning", "warning-bg"),
                 ("danger", "danger-bg"), ("info", "info-bg")]
        colours = self.page.evaluate("""pairs => {
            const el = document.createElement('span');
            el.style.display = 'none'; document.body.append(el);
            const colour = name => {
                el.style.color = `var(--ibtinex-${name})`;
                return getComputedStyle(el).color.match(/[\\d.]+/g).slice(0,3).map(Number);
            };
            const result = pairs.map(([fg, bg]) => ({fg, bg, foreground: colour(fg), background: colour(bg)}));
            el.remove(); return result;
        }""", pairs)
        for sample in colours:
            ratio = contrast_ratio(sample["foreground"], sample["background"])
            self.report["semantic_text_contrast"].setdefault(mode, {})[
                f"{sample['fg']}/{sample['bg']}"] = round(ratio, 3)
            if ratio < 4.5:
                raise AssertionError(f"{mode} semantic text pair {sample['fg']}/{sample['bg']} has contrast {ratio:.2f}:1.")

    def pair(self, name, mode, viewport):
        self.theme(mode)
        stem = f"{name}-{viewport}-{mode}"
        self.switch_stylesheet(False)
        before = self.output / f"{stem}-before-native-theme.png"
        self.page.screenshot(path=str(before), animations="disabled", caret="hide")
        before_colours = self.colour_samples()
        self.switch_stylesheet(True)
        token = self.page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--ibtinex-brand').trim()")
        if token.lower() not in ("#102b21", "rgb(16, 43, 33)"):
            raise AssertionError("Compiled IBTINEX semantic brand token is not applied.")
        self.semantic_contrast(mode)
        after = self.output / f"{stem}-after-ibtinex.png"
        self.page.screenshot(path=str(after), animations="disabled", caret="hide")
        before_hash, after_hash = (hashlib.sha256(p.read_bytes()).hexdigest() for p in (before, after))
        if before_hash == after_hash:
            raise AssertionError(f"The isolated brand stylesheet made no visible difference on {stem}.")
        self.report["screenshots"].append({
            "surface": name, "viewport": viewport, "theme": mode,
            "before": before.name, "after": after.name,
            "before_sha256": before_hash, "after_sha256": after_hash,
        })
        self.contrast(stem, before_colours)

    def variants(self, name):
        for viewport, dimensions in VIEWPORTS.items():
            self.page.set_viewport_size(dimensions)
            if viewport == "mobile" and self.page.evaluate("!!window.frappe?.app"):
                self.page.wait_for_function("window.frappe?.ui?.mobile_nav?.defined && frappe.ui.BottomSheet", timeout=60000)
            for mode in ("light", "dark"):
                self.pair(name, mode, viewport)
        self.page.set_viewport_size(VIEWPORTS["desktop"])
        self.theme("light")

    def route(self, parts):
        # Frappe 16 public workspaces use /desk/<slug>, not /desk/Workspaces/<name>.
        self.page.evaluate("parts => frappe.set_route(parts[0] === 'Workspaces' ? frappe.router.slug(parts[1]) : parts)", parts)
        self.ready(desk=True)
        self.page.wait_for_function("parts => frappe.get_route().slice(0, parts.length).join('/') === parts.join('/')", arg=parts)

    def keyboard_focus(self, locator, name):
        locator.focus()
        self.page.keyboard.press("Tab")
        self.page.keyboard.press("Shift+Tab")
        state = locator.evaluate("""el => {
            const css = getComputedStyle(el), box = el.getBoundingClientRect();
            return {focused: document.activeElement === el, focus_visible: el.matches(':focus-visible'),
                outline_style: css.outlineStyle, outline_width: parseFloat(css.outlineWidth),
                box_shadow: css.boxShadow, width: box.width, height: box.height};
        }""")
        if not (state["focused"] and state["focus_visible"] and state["width"] and state["height"]):
            raise AssertionError(f"Keyboard cannot return visible focus to {name}.")
        if not ((state["outline_style"] != "none" and state["outline_width"] >= 2)
                or state["box_shadow"] != "none"):
            raise AssertionError(f"No visible focus indicator found on {name}.")
        self.record(name, **state)

    def print_isolation(self):
        self.page.emulate_media(media="print")
        try:
            self.switch_stylesheet(True)
            branded = self.page.evaluate("""() => {
                const css = getComputedStyle(document.body);
                return [css.color, css.backgroundColor,
                    getComputedStyle(document.documentElement).getPropertyValue('--ibtinex-brand')];
            }""")
            self.switch_stylesheet(False)
            native = self.page.evaluate("""() => {
                const css = getComputedStyle(document.body);
                return [css.color, css.backgroundColor,
                    getComputedStyle(document.documentElement).getPropertyValue('--ibtinex-brand')];
            }""")
            if branded != native:
                raise AssertionError("The screen-only IBTINEX stylesheet changes print computed styles.")
            self.record("theme_does_not_change_print_computed_styles")
        finally:
            self.page.emulate_media(media="screen")
            self.switch_stylesheet(True)

    def run(self, base_url, password):
        response = self.page.goto(base_url + "/login", wait_until="domcontentloaded")
        if not response or response.status != 200:
            raise AssertionError("Native login page did not load.")
        self.page.locator("#login_email:visible").wait_for()
        self.ready()
        self.page.locator(".for-login .ibtinex-product-name").wait_for()
        if self.page.locator(".for-login .ibtinex-product-name").inner_text().strip() != "IBTINEX ERP":
            raise AssertionError("Fresh-site login does not visibly identify IBTINEX ERP.")
        self.record("fresh_login_visibly_identifies_ibtinex_erp")
        self.variants("login")
        self.keyboard_focus(self.page.locator("#login_email:visible"), "login_email_keyboard_focus")
        self.keyboard_focus(self.page.locator("#login_password:visible"), "login_password_keyboard_focus")
        self.print_isolation()
        self.page.locator(".for-login button[type=submit]:visible").click()
        self.page.wait_for_function("Array.from(document.querySelectorAll('.for-login .field-error')).some(el => el.innerText.trim())")
        self.pair("login-validation", "light", "desktop")
        self.record("native_login_required_field_validation")
        self.page.locator("#login_email:visible").fill("Administrator")
        self.page.locator("#login_password:visible").fill(password)
        self.page.locator(".for-login button[type=submit]:visible").click()
        self.page.wait_for_url("**/desk**", timeout=90000)
        self.ready(desk=True)
        if self.page.evaluate("frappe.session.user") != "Administrator":
            raise AssertionError("Native administrator login was not established.")
        self.record("administrator_login_through_native_form")
        # Pinned fixture API prevents screenshots of an unintended non-test site.
        companies = self.page.evaluate("() => frappe.db.get_list('Company', {fields: ['name'], limit: 20})")
        if not any(c["name"] == COMPANY for c in companies):
            raise AssertionError("The dedicated fictional starter company was not found.")
        self.record("native_company_lookup")
        self.variants("desk-home")
        self.route(["Workspaces", "Selling"])
        self.variants("selling-workspace")

        self.page.set_viewport_size(VIEWPORTS["mobile"])
        self.page.wait_for_function("window.frappe?.ui?.mobile_nav?.defined && frappe.ui.BottomSheet", timeout=60000)
        self.page.evaluate("frappe.ui.mobile_nav.open_navigation()")
        self.page.locator(".desk-mobile-sheet:visible").wait_for()
        self.pair("mobile-navigation", "light", "mobile")
        self.pair("mobile-navigation", "dark", "mobile")
        self.page.keyboard.press("Escape")
        self.page.wait_for_function("!document.querySelector('.desk-mobile-sheet') || !document.querySelector('.desk-mobile-sheet').getBoundingClientRect().height")
        self.record("native_mobile_navigation_opens_and_keyboard_closes")
        self.page.set_viewport_size(VIEWPORTS["desktop"])
        self.theme("light")

        for doctype, label in (("Sales Order", "sales-form"), ("Purchase Order", "purchase-form")):
            docs = self.page.evaluate("doctype => frappe.db.get_list(doctype, {fields: ['name'], filters: {company: 'IBTINEX Starter Ethiopia'}, limit: 1})", doctype)
            if not docs:
                raise AssertionError(f"No seeded {doctype} exists for native form verification.")
            self.route(["Form", doctype, docs[0]["name"]])
            self.page.wait_for_function("doctype => window.cur_frm?.doctype === doctype && !!cur_frm.doc?.name", arg=doctype)
            self.variants(label)
            self.record(f"native_{label}_opens_seeded_document")

        self.route(["List", "Sales Order", "List"])
        self.page.wait_for_function("window.cur_list?.doctype === 'Sales Order' && Array.isArray(cur_list.data)")
        self.variants("sales-list")
        self.record("native_sales_order_list_renders")

        self.route(["query-report", "General Ledger"])
        self.page.wait_for_function("window.frappe?.query_report?.report_name === 'General Ledger' && frappe.query_report.filters?.length")
        self.page.evaluate("""async () => {
            await frappe.query_report.set_filter_value('company', 'IBTINEX Starter Ethiopia');
            await frappe.query_report.refresh();
        }""")
        self.page.wait_for_function("Array.isArray(frappe.query_report.data) && frappe.query_report.data.length > 0", timeout=90000)
        self.variants("general-ledger")
        self.record("native_general_ledger_has_fixture_rows")

        # A native framework dialog exercises field/button/modal styling without
        # modifying records, creating messages, or submitting business documents.
        self.page.evaluate("""() => {
            window.ibtinex_visual_dialog = new frappe.ui.Dialog({
                title: 'Review display settings', fields: [
                    {fieldname: 'reference', label: 'Reference', fieldtype: 'Data', reqd: 1},
                    {fieldname: 'notes', label: 'Notes', fieldtype: 'Small Text'}
                ], primary_action_label: 'Continue',
                primary_action() { window.ibtinex_visual_dialog.hide(); }
            });
            window.ibtinex_visual_dialog.show();
        }""")
        self.page.locator(".modal:visible").last.wait_for()
        self.variants("native-dialog")
        self.keyboard_focus(self.page.locator(".modal:visible [data-fieldname=reference] input:visible"), "dialog_field_keyboard_focus")
        self.page.keyboard.press("Escape")
        self.page.locator(".modal:visible").last.wait_for(state="hidden")
        self.record("native_dialog_keyboard_escape")

        self.page.set_viewport_size({"width": 720, "height": 1000})
        self.page.evaluate("document.documentElement.style.fontSize = '200%'")
        self.pair("text-scaling-200-percent", "light", "narrow-desktop")
        self.page.evaluate("document.documentElement.style.removeProperty('font-size')")
        self.record("text_scaling_200_percent_capture", scope="Visual review required; not browser-zoom conformance certification")
        reduced = self.page.evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches")
        if not reduced:
            raise AssertionError("Reduced-motion preference was not enabled during browser qualification.")
        self.record("reduced_motion_preference_exercised")
        if self.report["theme_contrast_regressions"]:
            raise AssertionError(f"IBTINEX theme introduced {len(self.report['theme_contrast_regressions'])} visible text contrast regressions; see visual-verification.json.")
        self.report["status"] = "passed"
        self.report["accessibility_review_required"] = bool(self.report["accessibility_findings"])
        return self.report


def write_gallery(output, report):
    cards = []
    for shot in report["screenshots"]:
        name = html.escape(f"{shot['surface']} · {shot['viewport']} · {shot['theme']}")
        cards.append(f'<section><h2>{name}</h2><div class="pair"><figure>'
                     f'<img loading="lazy" src="{html.escape(shot["before"])}" alt="Native theme reference for {name}">'
                     '<figcaption>Before: native theme reference</figcaption></figure><figure>'
                     f'<img loading="lazy" src="{html.escape(shot["after"])}" alt="IBTINEX theme for {name}">'
                     '<figcaption>After: IBTINEX theme</figcaption></figure></div></section>')
    page = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    page += '<title>IBTINEX ERP visual verification</title><style>'
    page += 'body{margin:0;background:#f4f5ef;color:#1b241f;font:16px/1.55 system-ui,sans-serif}header{padding:32px;background:#102b21;color:#fff}main{padding:24px;max-width:1800px;margin:auto}h1,h2{margin:0 0 12px}h2{font-size:20px}section{margin:0 0 32px}.pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}figure{margin:0;background:#fff;border:1px solid #c9d1c7;border-radius:8px;overflow:hidden}img{display:block;width:100%;height:auto}figcaption{padding:12px}a{color:inherit}header p{max-width:1000px}@media(max-width:800px){.pair{grid-template-columns:1fr}}</style>'
    page += '<header><h1>IBTINEX ERP visual verification</h1>'
    page += f'<p>Runtime smoke checks: <strong>{html.escape(report["status"])}</strong>. '
    page += f'{len(report["screenshots"])} screenshot pairs. '
    page += f'{len(report["accessibility_findings"])} contrast samples need review; '
    page += f'{len(report["theme_contrast_regressions"])} newly failing text samples.</p>'
    page += '<p>Both images use the same candidate runtime and fictional starter data. '
    page += 'The native reference disables only the isolated IBTINEX theme stylesheet. '
    page += 'These checks do not certify WCAG conformance or Windows installation.</p>'
    page += '<a href="visual-verification.json">Open detailed checks and accessibility findings</a></header><main>'
    page += '\n'.join(cards) + '</main></html>\n'
    (output / "index.html").write_text(page, encoding="utf-8")


def run_visual_checks(base_url, password_file, output, site):
    """Called by CI before publishing; raises if real runtime smoke checks fail."""
    from playwright.sync_api import sync_playwright

    base_url = validate_target(base_url, site)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    password = Path(password_file).read_bytes().decode("ascii").rstrip("\r\n")
    if not password or any(char in password for char in "\r\n\0"):
        raise ValueError("Administrator password file has an invalid byte format.")
    runner = None
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            context = browser.new_context(viewport=VIEWPORTS["desktop"], reduced_motion="reduce", locale="en-US")
            context.set_default_timeout(30000)
            page = context.new_page()
            runner = VisualQualification(page, output)
            runner.report["browser_version"] = browser.version
            result = runner.run(base_url, password)
            return result
        except Exception as error:
            if runner:
                runner.report["status"] = "failed"
                runner.report["failure"] = str(error).replace(password, "[REDACTED]")[-5000:]
            raise RuntimeError(str(error).replace(password, "[REDACTED]")) from None
        finally:
            if runner:
                (output / "visual-verification.json").write_text(json.dumps(runner.report, indent=2) + "\n", encoding="utf-8")
                write_gallery(output, runner.report)
            browser.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--password-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--site", required=True)
    args = parser.parse_args()
    result = run_visual_checks(args.base_url, args.password_file, args.output, args.site)
    print(json.dumps({"status": result["status"], "screenshot_pairs": len(result["screenshots"]),
                      "checks": len(result["checks"]), "accessibility_findings": len(result["accessibility_findings"])}))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"Visual qualification failed: {error}", file=sys.stderr)
        sys.exit(1)
