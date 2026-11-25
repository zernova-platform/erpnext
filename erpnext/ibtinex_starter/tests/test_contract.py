"""Dependency-free qualification of opt-in boundaries and pinned schema payloads.

Run from the repository root:
    python -m unittest discover -s erpnext/ibtinex_starter/tests -v
Set FRAPPE_SOURCE_ROOT when the pinned Framework checkout is not beside ERPNext.
Runtime posting/ledger/stock checks are seed.verify(), not mocked here.
"""

import ast
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]


def module(name):
	spec = importlib.util.spec_from_file_location("starter_" + name, PACKAGE / (name + ".py"))
	loaded = importlib.util.module_from_spec(spec)
	spec.loader.exec_module(loaded)
	return loaded


plan = module("plan")
coverage = module("coverage")


class ConsentContract(unittest.TestCase):
	def setUp(self):
		self.flags = dict.fromkeys(plan.REQUIRED_SITE_FLAGS, 1)

	def test_only_explicit_boolean_consent_is_accepted(self):
		plan.validate_request("review.local", "review.local", True, self.flags)
		for value in (False, None, 0, 1, "true", "yes"):
			with self.subTest(value=value), self.assertRaises(ValueError):
				plan.validate_request("review.local", "review.local", value, self.flags)

	def test_target_site_must_match_exactly(self):
		for target in ("", None, "production.local", "review.local ", "Review.local"):
			with self.subTest(target=target), self.assertRaises(ValueError):
				plan.validate_request(target, "review.local", True, self.flags)

	def test_each_isolation_flag_is_required(self):
		for flag in plan.REQUIRED_SITE_FLAGS:
			for value in (None, 0, "1", "true"):
				with self.subTest(flag=flag, value=value), self.assertRaises(ValueError):
					plan.validate_request("review.local", "review.local", True, {**self.flags, flag: value})

	def test_date_contract(self):
		self.assertEqual(plan.seed_date("2024-02-29"), "2024-02-29")
		for value in ("2026-02-29", "2026-1-01", "20260101", "2019-01-01", "2101-01-01", 20260101):
			with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
				plan.seed_date(value)


class CoverageContract(unittest.TestCase):
	def test_inventory_is_exactly_all_pinned_source_doctypes(self):
		actual = {}
		for path in (REPO / "erpnext").glob("*/doctype/*/*.json"):
			value = json.loads(path.read_text())
			if isinstance(value, dict) and value.get("doctype") == "DocType":
				actual[value["name"]] = value
		entries = coverage.load_inventory()["doctypes"]
		self.assertEqual(len(entries), 534)
		self.assertEqual(set(actual), {entry["doctype"] for entry in entries})
		for entry in entries:
			with self.subTest(doctype=entry["doctype"]):
				self.assertTrue((REPO / entry["source_path"]).is_file())
				self.assertEqual(actual[entry["doctype"]]["module"], entry["module"])
				self.assertEqual(bool(actual[entry["doctype"]].get("istable")), entry["is_child"])

	def test_all_modules_have_an_explicit_disposition(self):
		expected = set((REPO / "erpnext" / "modules.txt").read_text().splitlines())
		self.assertEqual(expected, set(plan.MODULE_COVERAGE))
		keys = {key: {} for _, names, _ in plan.MODULE_COVERAGE.values() for key in names}
		self.assertEqual(len(plan.coverage_manifest(keys)), 21)
		del keys["sales_invoice"]
		with self.assertRaisesRegex(ValueError, "Missing coverage records"):
			plan.coverage_manifest(keys)

	def test_empty_business_tables_are_explicit_gaps(self):
		entries = coverage.load_inventory()["doctypes"]
		report = coverage.doctype_coverage([0] * len(entries), {}, [0] * len(entries))
		self.assertEqual(len(report["doctypes"]), 534)
		by_name = {row["doctype"]: row for row in report["doctypes"]}
		self.assertEqual(by_name["Sales Invoice"]["status"], "not-seeded")
		self.assertEqual(by_name["Video"]["status"], "inert-external")
		self.assertEqual(by_name["Plaid Settings"]["status"], "inert-external")
		self.assertEqual(by_name["Sales Invoice Item"]["status"], "not-seeded")
		self.assertIn("Owners:", by_name["Sales Invoice Item"]["reason"])
		self.assertTrue(all(row["reason"] for row in report["doctypes"]))

	def test_created_and_child_evidence_are_distinguished(self):
		entries = coverage.load_inventory()["doctypes"]
		counts = [int(entry["doctype"] in ("Sales Invoice", "Sales Invoice Item", "GL Entry")) for entry in entries]
		records = {"invoice": {"doctype": "Sales Invoice", "name": "ISE-INVOICE"}}
		report = coverage.doctype_coverage([0] * len(entries), records, counts)
		by_name = {row["doctype"]: row for row in report["doctypes"]}
		self.assertEqual(by_name["Sales Invoice"]["status"], "created")
		self.assertEqual(by_name["Sales Invoice Item"]["status"], "generated-child")
		self.assertEqual(by_name["GL Entry"]["status"], "generated-native")
		with self.assertRaises(ValueError):
			coverage.doctype_coverage([], records, counts)


class NativeNotificationContract(unittest.TestCase):
	def setUp(self):
		self.fields = [{"fieldname": key, "fieldtype": kind} for key, kind in (
			("enabled", "Check"), ("is_standard", "Check"), ("channel", "Select"),
			("subject", "Data"), ("message", "Code"), ("email_template", "Link"),
			("sender_email", "Data"))]
		self.fields.append({"fieldname": "recipients", "fieldtype": "Table", "options": "Notification Recipient"})
		self.children = {"Notification Recipient": [{"fieldname": key, "fieldtype": "Data"}
			for key in ("receiver_by_role", "receiver_by_document_field", "cc", "bcc", "condition")]}
		self.expected = {"name": "Error Log", "enabled": 0, "is_standard": 0, "channel": "Email",
			"subject": "[Error] {{ doc.method }}", "message": "Pinned upstream template",
			"recipients": [{"receiver_by_role": "System Manager"}]}

	def matches(self, actual):
		return plan.matches_notification_template(actual, self.expected, self.fields, self.children)

	def test_native_bookkeeping_and_empty_defaults_are_not_customization(self):
		actual = deepcopy(self.expected)
		actual.update(owner="Administrator", creation="2026-11-25", modified="2026-11-25", sender_email="")
		actual["recipients"][0].update(name="random-native-id", parent="Error Log", idx=1, cc="")
		self.assertTrue(self.matches(actual))

	def test_enabled_or_changed_delivery_rules_are_rejected(self):
		for key, value in (("enabled", 1), ("is_standard", 1), ("channel", "SMS"),
			("name", "Customer Error Log"), ("message", "Custom template"),
			("sender_email", "custom@example.invalid"), ("email_template", "Custom Template")):
			with self.subTest(field=key):
				actual = deepcopy(self.expected)
				actual[key] = value
				self.assertFalse(self.matches(actual))

	def test_changed_or_added_recipient_is_rejected(self):
		actual = deepcopy(self.expected)
		actual["recipients"][0]["receiver_by_role"] = "Customer"
		self.assertFalse(self.matches(actual))
		actual = deepcopy(self.expected)
		actual["recipients"].append({"receiver_by_document_field": "owner"})
		self.assertFalse(self.matches(actual))


class PinnedSchemaPayloads(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		frappe_source = os.environ.get("FRAPPE_SOURCE_ROOT")
		if not frappe_source:
			frappe_source = next((path for path in (REPO.parent / "frappe", REPO.parent / "frappe-baseline")
				if (path / "frappe" / "__init__.py").exists()), None)
		if not frappe_source:
			raise RuntimeError("Pinned Framework source required: set FRAPPE_SOURCE_ROOT to the Frappe 16.60.2 checkout.")
		cls.schemas = {}
		for root in (REPO / "erpnext", Path(frappe_source) / "frappe"):
			for path in root.glob("*/doctype/*/*.json"):
				value = json.loads(path.read_text())
				if isinstance(value, dict) and value.get("doctype") == "DocType":
					cls.schemas[value["name"]] = value
		# ERPNext adds this supported field to Framework Address during after_install.
		setup_source = (REPO / "erpnext/setup/install.py").read_text()
		if '"fieldname": "is_your_company_address"' not in setup_source:
			raise RuntimeError("ERPNext's Address custom field installer changed; review the seed before proceeding.")
		cls.schemas["Address"]["fields"].append({"fieldname": "is_your_company_address", "fieldtype": "Check"})

	def check_values(self, doctype, node):
		self.assertIn(doctype, self.schemas)
		fields = {field["fieldname"]: field for field in self.schemas[doctype].get("fields", [])}
		for key, value in zip(node.keys, node.values, strict=True):
			if not isinstance(key, ast.Constant):
				continue
			name = key.value
			if name in ("name", "doctype"):
				continue
			self.assertIn(name, fields, f"{doctype}.{name} absent from pinned schema")
			field = fields[name]
			if field["fieldtype"] == "Select" and field.get("options") and isinstance(value, ast.Constant):
				options = (field.get("options") or "").splitlines()
				self.assertIn(value.value, options, f"Unsupported {doctype}.{name} choice")
			if field["fieldtype"] in ("Table", "Table MultiSelect") and isinstance(value, (ast.List, ast.Tuple)):
				for child in value.elts:
					if isinstance(child, ast.Dict):
						self.check_values(field["options"], child)

	def test_literal_parent_and_child_payloads_match_exact_schemas(self):
		tree = ast.parse((PACKAGE / "seed.py").read_text())
		checked = 0
		for node in ast.walk(tree):
			if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
				continue
			if node.func.attr == "put" and len(node.args) >= 3 and isinstance(node.args[1], ast.Constant) and isinstance(node.args[2], ast.Dict):
				with self.subTest(doctype=node.args[1].value, line=node.lineno):
					self.check_values(node.args[1].value, node.args[2])
				checked += 1
			if node.func.attr == "set_single_value" and len(node.args) >= 2 and isinstance(node.args[0], ast.Constant) and isinstance(node.args[1], ast.Dict):
				with self.subTest(single=node.args[0].value, line=node.lineno):
					self.check_values(node.args[0].value, node.args[1])
		self.assertGreater(checked, 60)

	def test_framework_templates_are_exactly_the_known_disabled_email_rules(self):
		root = os.environ.get("FRAPPE_SOURCE_ROOT")
		if not root:
			root = next(path for path in (REPO.parent / "frappe", REPO.parent / "frappe-baseline")
				if (path / "frappe" / "__init__.py").exists())
		folder = Path(root) / "frappe/email/doctype/notification/templates"
		templates = [json.loads(path.read_text()) for path in folder.glob("*/*.json")]
		self.assertEqual({row["name"] for row in templates}, set(plan.FRAMEWORK_NOTIFICATION_TEMPLATES))
		self.assertTrue(all(row["enabled"] == 0 and row["channel"] == "Email" for row in templates))


if __name__ == "__main__":
	unittest.main()
