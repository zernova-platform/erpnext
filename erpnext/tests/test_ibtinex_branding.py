# Copyright (c) 2026, IBTINEX and contributors
# License: GNU General Public License v3. See license.txt

"""Focused recipe tests, runnable without installing the full Frappe runtime.

These test the real recipe against a transactional database double. They do not
replace the live browser and database checks required for a release image.
"""

import copy
import importlib.util
import json
import re
import sys
import types
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch


_ERP_DIR = Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location("ibtinex_branding_under_test", _ERP_DIR / "ibtinex_branding.py")
branding = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(branding)


class FakeDatabase:
	def __init__(self):
		self.values = dict.fromkeys(branding._FIELDS, "")
		self.values["Company.company_name"] = "Customer business"
		self.values["Letter Head.content"] = "Customer letterhead"
		self.values["Website Settings.website_theme"] = "Existing monochrome theme"
		self.values["System Settings.app_name"] = "ERPNext"
		self.defaults = {}
		self.writes = []
		self.failure_key = None

	def get_default(self, key):
		return self.defaults.get(key)

	def set_default(self, key, value):
		self.defaults[key] = value

	def get_single_value(self, doctype, field, **kwargs):
		return self.values.get(f"{doctype}.{field}")

	def set_single_value(self, doctype, field, value):
		key = f"{doctype}.{field}"
		if key == self.failure_key:
			raise RuntimeError("Simulated write failure")
		self.values[key] = value
		self.writes.append(key)

	def savepoint(self, name):
		self.snapshot = copy.deepcopy((self.values, self.defaults, self.writes))

	def rollback(self, *, save_point):
		self.values, self.defaults, self.writes = self.snapshot


class TestBrandingOwnership(unittest.TestCase):
	def setUp(self):
		self.db = FakeDatabase()
		self.frappe = types.ModuleType("frappe")
		self.frappe.db = self.db
		self.frappe.get_meta = lambda doctype: types.SimpleNamespace(has_field=lambda field: True)
		self.frappe.clear_cache = lambda: None
		self.addCleanup(patch.stopall)
		patch.dict(sys.modules, {"frappe": self.frappe}).start()
		patch.object(branding, "_check_assets").start()

	def test_fresh_install_and_repeat_preserve_non_branding_fields(self):
		before = {key: value for key, value in self.db.values.items() if key not in branding._FIELDS}
		first = branding.apply()
		self.assertEqual(set(first["changed"]), set(branding._FIELDS))
		self.assertEqual(self.db.values["Website Settings.app_logo"], branding.LOGO)
		self.assertEqual(self.db.values["Website Settings.favicon"], branding.FAVICON)
		writes = len(self.db.writes)
		self.assertEqual(branding.apply()["changed"], [])
		self.assertEqual(len(self.db.writes), writes)
		self.assertEqual({key: self.db.values[key] for key in before}, before)

	def test_empty_website_logo_does_not_hide_custom_navbar_logo(self):
		self.db.values["Navbar Settings.app_logo"] = "/files/customer-logo.png"
		result = branding.apply()
		self.assertEqual(self.db.values["Website Settings.app_logo"], "")
		self.assertEqual(self.db.values["Navbar Settings.app_logo"], "/files/customer-logo.png")
		self.assertIn("Website Settings.app_logo", result["preserved"])

	def test_default_product_name_and_existing_ownership_upgrade(self):
		# An installed 0.1.0 site already owns icons but has no app-name entries.
		old_managed = {}
		for key, value in branding._FIELDS.items():
			if key not in branding._NAME_KEYS:
				self.db.values[key] = value
				old_managed[key] = {"previous": "", "applied": value}
		self.db.defaults[branding.STATE_KEY] = json.dumps({"version": 1, "managed": old_managed})
		result = branding.apply()
		self.assertEqual(set(result["changed"]), set(branding._NAME_KEYS))
		self.assertEqual(self.db.values["System Settings.app_name"], "IBTINEX ERP")
		self.assertEqual(self.db.values["Website Settings.app_name"], "IBTINEX ERP")
		self.assertEqual(branding.apply()["changed"], [])
		branding.restore()
		self.assertEqual(self.db.values["System Settings.app_name"], "ERPNext")
		self.assertEqual(self.db.values["Website Settings.app_name"], "")

	def test_empty_website_name_does_not_hide_customer_system_name(self):
		self.db.values["System Settings.app_name"] = "Acme Business"
		result = branding.apply()
		self.assertEqual(self.db.values["Website Settings.app_name"], "")
		self.assertEqual(self.db.values["System Settings.app_name"], "Acme Business")
		self.assertTrue(set(branding._NAME_KEYS).issubset(result["preserved"]))

	def test_customer_website_name_preserves_both_existing_name_settings(self):
		self.db.values["Website Settings.app_name"] = "My business portal"
		branding.apply()
		self.assertEqual(self.db.values["Website Settings.app_name"], "My business portal")
		self.assertEqual(self.db.values["System Settings.app_name"], "ERPNext")

	def test_customer_name_edit_is_not_overwritten_by_reapply_or_restore(self):
		branding.apply()
		self.db.values["System Settings.app_name"] = "Changed by customer"
		branding.apply()
		branding.restore()
		self.assertEqual(self.db.values["System Settings.app_name"], "Changed by customer")

	def test_customer_favicon_and_splash_are_preserved(self):
		self.db.values["Website Settings.favicon"] = "/files/customer.ico"
		self.db.values["Website Settings.splash_image"] = "/files/customer-splash.png"
		result = branding.apply()
		self.assertIn("Website Settings.favicon", result["preserved"])
		self.assertEqual(self.db.values["Website Settings.splash_image"], "/files/customer-splash.png")

	def test_manual_change_to_blank_is_not_reclaimed(self):
		branding.apply()
		self.db.values["Website Settings.favicon"] = ""
		result = branding.apply()
		self.assertIn("Website Settings.favicon", result["preserved"])
		self.assertEqual(self.db.values["Website Settings.favicon"], "")

	def test_restore_preserves_later_custom_edits(self):
		branding.apply()
		self.db.values["Website Settings.favicon"] = "/files/later-choice.ico"
		result = branding.restore()
		self.assertEqual(self.db.values["Website Settings.app_logo"], "")
		self.assertEqual(self.db.values["Website Settings.favicon"], "/files/later-choice.ico")
		self.assertIn("Website Settings.favicon", result["preserved"])
		self.assertEqual(branding.restore()["restored"], [])

	def test_partial_failure_rolls_back_values_and_ownership(self):
		before = copy.deepcopy(self.db.values)
		self.db.failure_key = "Website Settings.favicon"
		with self.assertRaisesRegex(RuntimeError, "Simulated write failure"):
			branding.apply()
		self.assertEqual(self.db.values, before)
		self.assertEqual(self.db.defaults, {})

	def test_invalid_ownership_fails_before_mutating_any_setting(self):
		self.db.defaults[branding.STATE_KEY] = json.dumps({"version": 2, "managed": {}})
		with self.assertRaisesRegex(RuntimeError, "ownership record is invalid"):
			branding.apply()
		self.assertEqual(self.db.writes, [])

	def test_missing_expected_schema_does_not_partially_apply(self):
		self.frappe.get_meta = lambda doctype: types.SimpleNamespace(
			has_field=lambda field: field != "favicon"
		)
		with self.assertRaisesRegex(RuntimeError, "expected branding settings"):
			branding.apply()
		self.assertEqual(self.db.writes, [])

	def test_existing_matching_value_is_not_claimed_for_rollback(self):
		self.db.values["Website Settings.favicon"] = branding.FAVICON
		branding.apply()
		branding.restore()
		self.assertEqual(self.db.values["Website Settings.favicon"], branding.FAVICON)


class TestBrandingAssetContract(unittest.TestCase):
	def test_shipped_mark_assets_exist_in_checkout(self):
		branding._check_assets()

	def test_icons_reuse_existing_studio_mark_without_remote_resources(self):
		logo = (_ERP_DIR / "public/images/ibtinex-logo.svg").read_bytes()
		favicon = (_ERP_DIR / "public/images/ibtinex-favicon.svg").read_bytes()
		self.assertEqual(logo, favicon)
		root = ET.fromstring(logo)
		self.assertEqual(root.get("viewBox"), "0 0 27 27")
		ns = {"svg": "http://www.w3.org/2000/svg"}
		rect = root.find("svg:rect", ns)
		text = root.find("svg:text", ns)
		self.assertEqual(rect.get("rx"), "7")
		self.assertEqual(rect.get("fill"), "#d4f594")
		self.assertEqual(text.text, "I")
		self.assertEqual(text.get("fill"), "#102b21")
		self.assertEqual(text.get("font-weight"), "700")
		self.assertEqual(text.get("font-size"), "16")
		self.assertTrue(text.get("font-family").startswith("Inter,"))
		self.assertFalse(any(el.tag.rsplit("}", 1)[-1] not in {"svg", "title", "rect", "text"} for el in root.iter()))
		self.assertFalse(any("href" in key or key.startswith("on") for el in root.iter() for key in el.attrib))

	def test_hooks_preserve_app_identity_and_reference_packaged_icons(self):
		# hooks.py is declarative metadata; executing it imports no framework.
		hooks = {}
		exec(compile((_ERP_DIR / "hooks.py").read_text(), "hooks.py", "exec"), hooks)
		self.assertEqual(hooks["app_name"], "erpnext")
		self.assertEqual(hooks["app_title"], branding.PRODUCT_NAME)
		self.assertEqual(hooks["app_logo_url"], branding.LOGO)
		self.assertEqual(hooks["add_to_apps_screen"][0]["name"], "erpnext")
		self.assertEqual(hooks["add_to_apps_screen"][0]["logo"], branding.LOGO)
		self.assertEqual(hooks["add_to_apps_screen"][0]["title"], branding.PRODUCT_NAME)
		self.assertEqual(hooks["website_context"]["favicon"], branding.FAVICON)
		legacy_icon = json.loads((_ERP_DIR / "desktop_icon" / "erpnext.json").read_text())
		self.assertEqual(legacy_icon["name"], "ERPNext")
		# This hidden legacy record keeps its stable name/label; the native Apps
		# screen reads display metadata from hooks, including on existing sites.
		self.assertEqual(legacy_icon["label"], "ERPNext")
		self.assertEqual(legacy_icon["logo_url"], branding.LOGO)
		self.assertEqual(hooks["app_include_css"][-1], "ibtinex-theme.bundle.css")
		self.assertEqual(hooks["web_include_css"][-1], "ibtinex-theme.bundle.css")
		self.assertNotIn("ibtinex-theme.bundle.css", hooks["email_css"])


class TestLoginPresentationContext(unittest.TestCase):
	def test_login_exposes_native_resolved_name_without_altering_authentication(self):
		context = {
			"path": "login", "app_name": "Customer & Co", "title": "Login", "boot": {"lang": "en"},
			"disable_user_pass_login": True, "provider_logins": [{"name": "keycloak"}],
		}
		before = copy.deepcopy(context)
		branding.update_website_context(context)
		self.assertEqual(context["boot"]["ibtinex_app_name"], "Customer & Co")
		self.assertEqual(context["title"], "Customer & Co · Login")
		self.assertEqual(context["provider_logins"], before["provider_logins"])
		self.assertEqual(context["disable_user_pass_login"], before["disable_user_pass_login"])
		self.assertEqual(context["boot"]["lang"], "en")

	def test_non_login_context_including_print_is_untouched(self):
		for path in ("printview", "printpreview", "orders", "desk", ""):
			with self.subTest(path=path):
				context = {"path": path, "app_name": "IBTINEX ERP", "title": "Invoice", "boot": {}}
				before = copy.deepcopy(context)
				branding.update_website_context(context)
				self.assertEqual(context, before)


class TestThemeContrast(unittest.TestCase):
	"""Measure the shipped palette; runtime checks cover actual resolved DOM styles."""

	@staticmethod
	def luminance(value):
		rgb = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
		linear = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
			for channel in rgb]
		return sum(channel * weight for channel, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

	def test_actual_light_and_dark_palette_text_and_control_contrast(self):
		css = (_ERP_DIR / "public/scss/ibtinex-theme.bundle.scss").read_text()
		palette = {}
		for mode in ("light", "dark"):
			block = re.search(r'\[data-theme="' + mode + r'"\]\s*\{([^}]+)\}', css).group(1)
			palette.update(dict(re.findall(r"--ibtinex-([\w-]+):\s*(#[0-9a-f]{6});", block)))
			pairs = [
				("text", surface, 4.5) for surface in ("page", "surface", "surface-secondary", "selection")
			] + [
				("muted", surface, 4.5) for surface in ("page", "surface", "surface-secondary", "surface-hover")
			] + [
				("primary-text", "primary", 4.5), ("primary-text", "primary-hover", 4.5),
				("nav-text", "brand", 4.5), ("nav-muted", "brand", 4.5),
				("nav-muted", "brand-hover", 4.5), ("accent", "brand-hover", 4.5),
				("link", "surface", 4.5), ("link", "selection", 4.5),
				("focus", "page", 3), ("focus", "surface", 3),
				("control-border", "surface", 3), ("control-border", "surface-secondary", 3),
			] + [(state, f"{state}-bg", 4.5) for state in ("success", "warning", "danger", "info")]
			for foreground, background, required in pairs:
				with self.subTest(mode=mode, foreground=foreground, background=background):
					levels = sorted((self.luminance(palette[foreground]), self.luminance(palette[background])))
					ratio = (levels[1] + 0.05) / (levels[0] + 0.05)
					self.assertGreaterEqual(ratio, required, f"Contrast {ratio:.2f}:1 < {required}:1")


if __name__ == "__main__":
	unittest.main()
