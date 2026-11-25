# Copyright (c) 2026, IBTINEX contributors
# License: GNU General Public License v3. See license.txt
"""Synthetic connected ERPNext walkthrough, explicitly invoked by an engineer.

No web endpoint and no install/migrate hook calls this module. Use bench execute
on a NEW, designated demo site. Native document validation/posting is retained.
"""

import json
from copy import deepcopy
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal

import frappe

from erpnext.ibtinex_starter.plan import (
	ABBR, BUSINESS_DOCTYPES, COMPANY, COUNTRY, CURRENCY, MARKER_KEY,
	MODULE_COVERAGE, REQUIRED_SITE_FLAGS, SEED_VERSION, coverage_manifest,
	seed_date, validate_request,
)
from erpnext.ibtinex_starter.coverage import doctype_coverage, snapshot_counts

NATIVE_EMAIL_ALERTS = ("Notification for new fiscal year", "Material Request Receipt Notification")


def _guard(expected_site, accept_sample_data=True):
	validate_request(expected_site, frappe.local.site, accept_sample_data, frappe.conf)
	if frappe.session.user != "Administrator":
		frappe.only_for("System Manager")
	import erpnext
	if erpnext.__version__ != "16.60.0" or frappe.__version__ != "16.60.2":
		raise ValueError("This starter is qualified for ERPNext 16.60.0 / Frappe 16.60.2 only.")


def _existing_manifest():
	raw = frappe.db.get_global(MARKER_KEY)
	if not raw:
		return None
	manifest = json.loads(raw)
	if manifest.get("seed_version") != SEED_VERSION or manifest.get("company") != COMPANY:
		raise ValueError("The existing starter marker is incompatible; no data was changed.")
	return manifest


def _assert_fresh():
	occupied = [doctype for doctype in BUSINESS_DOCTYPES if frappe.db.count(doctype)]
	if occupied:
		raise ValueError("Starter requires a fresh site; existing business records: " + ", ".join(occupied))
	# Reject delivery mechanisms before even changing defaults. Reserved .invalid
	# sample addresses are an additional measure, not the primary isolation guard.
	for doctype in ("Email Account", "Webhook", "Email Campaign"):
		if frappe.db.count(doctype):
			raise ValueError(f"Fresh starter site must not contain configured {doctype} records.")
	for notification in frappe.get_all("Notification", fields=["name", "is_standard", "channel"]):
		if notification.name not in NATIVE_EMAIL_ALERTS or not notification.is_standard or notification.channel != "Email":
			raise ValueError("Fresh starter site contains a custom notification; no data was changed.")
	if frappe.db.get_single_value("SMS Settings", "sms_gateway_url"):
		raise ValueError("Fresh starter site must not have an SMS gateway.")
	if frappe.db.get_single_value("Plaid Settings", "enabled"):
		raise ValueError("Fresh starter site must not have Plaid enabled.")
	if frappe.db.count("Email Queue"):
		raise ValueError("Fresh starter site has queued email; no data was changed.")


def install(expected_site, accept_sample_data=False, as_of_date=None):
	"""Seed once; subsequent invocations verify without editing existing records.

	Required site configuration: ibtinex_starter_demo=1, mute_emails=1,
	pause_scheduler=1. This function never relaxes those settings.
	"""
	_guard(expected_site, accept_sample_data)
	with frappe.cache.lock("ibtinex-starter-v1", timeout=900, blocking_timeout=1):
		manifest = _existing_manifest()
		if manifest:
			if as_of_date is not None and seed_date(as_of_date) != manifest["as_of_date"]:
				raise ValueError("A different seed date cannot replace existing starter data.")
			return {**manifest, "status": "already-installed", "verification": _verify(manifest)}
		_assert_fresh()
		anchor = seed_date(as_of_date)
		if date.fromisoformat(anchor) > date.today():
			raise ValueError("Future-dated stock transactions cannot be used as the starter anchor.")
		previous_mute = frappe.flags.mute_emails
		frappe.flags.mute_emails = True
		try:
			seed = Starter(anchor)
			seed.run()
			manifest = seed.manifest()
			manifest["verification"] = _verify(manifest)
			serialized = json.dumps(manifest, sort_keys=True)
			if len(serialized.encode("utf-8")) > 60000:
				raise ValueError("Starter marker exceeds its safe storage limit; no partial seed was committed.")
			frappe.db.set_global(MARKER_KEY, serialized)
			frappe.db.commit()  # One successful seed transaction; no per-record commits.
			return manifest
		except Exception:
			frappe.db.rollback()
			frappe.clear_cache()
			raise
		finally:
			frappe.flags.mute_emails = previous_mute


def verify(expected_site):
	"""Read-only, fails closed if synthetic workflow assertions no longer hold."""
	_guard(expected_site)
	manifest = _existing_manifest()
	if not manifest:
		raise ValueError("No completed IBTINEX starter manifest exists on this site.")
	return _verify(manifest, detailed_coverage=True)


class Starter:
	def __init__(self, anchor):
		self.day = anchor
		self.records = {}
		self.accounts = {}
		self.sequence = 0
		self.baseline_counts = snapshot_counts()

	def remember(self, key, doc):
		if key in self.records:
			raise ValueError(f"Duplicate seed key: {key}")
		self.records[key] = {"doctype": doc.doctype, "name": doc.name, "docstatus": int(doc.docstatus)}
		return doc

	def name(self, key):
		return self.records[key]["name"]

	def doc(self, key):
		row = self.records[key]
		return frappe.get_doc(row["doctype"], row["name"])

	def put(self, key, doctype, values, *, submit=False, name=None):
		meta = frappe.get_meta(doctype)
		unknown = set(values) - {field.fieldname for field in meta.fields} - {"name", "doctype"}
		if unknown:
			raise ValueError(f"Seed has unsupported {doctype} fields: {sorted(unknown)}")
		doc = frappe.new_doc(doctype)
		doc.update(values)
		return self.save(key, doc, submit=submit, name=name)

	def save(self, key, doc, *, submit=False, name=None):
		if isinstance(doc, dict):
			doc = frappe.get_doc(doc)
		identifier = name or "ISE-" + key.replace("_", "-").upper()
		if frappe.db.exists(doc.doctype, identifier):
			raise ValueError(f"Starter identifier already exists: {doc.doctype} {identifier}")
		doc.insert(set_name=identifier)
		if submit:
			doc.submit()
		return self.remember(key, doc)

	def posting(self, doc, minute):
		doc.posting_date = self.day
		if doc.meta.has_field("set_posting_time"):
			doc.set_posting_time = 1
		if doc.meta.has_field("posting_time"):
			doc.posting_time = f"00:{minute:02d}:00"
		if doc.meta.has_field("due_date"):
			doc.due_date = self.day
		return doc

	def account(self, account_type=None, **filters):
		filters.update(company=COMPANY, is_group=0, disabled=0)
		if account_type:
			filters["account_type"] = account_type
		names = frappe.get_all("Account", filters=filters, pluck="name", order_by="name", limit=1)
		if not names:
			raise ValueError(f"Required account missing in synthetic company: {account_type or filters}")
		return names[0]

	def run(self):
		self.setup()
		self.masters()
		self.procurement()
		self.manufacturing()
		self.selling()
		self.subcontracting()
		self.projects_assets()
		self.quality_support()
		self.portal_and_integrations()

	def setup(self):
		from erpnext.setup.setup_wizard.operations import install_fixtures
		# These two enabled standard alerts ship with ERPNext itself. They are not
		# evidence of customer data, but are disabled for this synthetic site.
		for name in NATIVE_EMAIL_ALERTS:
			if frappe.db.exists("Notification", name):
				frappe.db.set_value("Notification", name, "enabled", 0)
		install_fixtures.install(COUNTRY)
		year = date.fromisoformat(self.day).year
		self.put("fiscal_year", "Fiscal Year", {
			"year": f"ISE Training {year}", "year_start_date": f"{year}-01-01",
			"year_end_date": f"{year}-12-31",
		}, name=f"ISE Training {year}")
		self.put("company", "Company", {
			"company_name": COMPANY, "abbr": ABBR, "country": COUNTRY,
			"default_currency": CURRENCY, "chart_of_accounts": "Standard",
			"create_chart_of_accounts_based_on": "Standard Template", "enable_perpetual_inventory": 1,
		}, name=COMPANY)
		install_fixtures.install_defaults(frappe._dict(
			company_name=COMPANY, currency=CURRENCY, country=COUNTRY,
		))
		company = self.doc("company")
		self.accounts = {
			"receivable": self.account("Receivable"), "payable": self.account("Payable"),
			"cash": self.account("Cash"), "stock": self.account("Stock"),
			"cogs": self.account("Cost of Goods Sold"), "expense": self.account("Stock Adjustment"),
			"income": company.default_income_account,
			"equity": self.account(root_type="Equity"), "fixed_asset": self.account("Fixed Asset"),
			"depreciation": self.account("Depreciation"),
			"accumulated_depreciation": self.account("Accumulated Depreciation"),
		}
		if not self.accounts["income"] or not company.cost_center:
			raise ValueError("Native company setup did not create accounting defaults.")
		self.cost_center = company.cost_center
		bank_group = frappe.db.get_value("Account", {"company": COMPANY, "account_type": "Bank", "is_group": 1})
		bank_gl = self.put("bank_gl", "Account", {
			"account_name": "ISE Demonstration Bank", "parent_account": bank_group,
			"company": COMPANY, "account_type": "Bank", "account_currency": CURRENCY,
		}, name="ISE Demonstration Bank - ISE")
		self.accounts["bank"] = bank_gl.name
		company.default_bank_account = bank_gl.name
		company.default_cash_account = self.accounts["cash"]
		company.save()
		self.put("bank", "Bank", {"bank_name": "ISE Fictional Training Bank"}, name="ISE Fictional Training Bank")
		self.put("bank_account", "Bank Account", {
			"account_name": "ISE Training Current Account", "bank": self.name("bank"),
			"account": bank_gl.name, "is_company_account": 1, "company": COMPANY,
			"is_default": 1, "bank_account_no": "DEMO-NOT-A-REAL-ACCOUNT",
		})
		self.put("bank_payment_method", "Mode of Payment", {
			"mode_of_payment": "ISE Demo Bank Transfer", "type": "Bank",
			"accounts": [{"company": COMPANY, "default_account": bank_gl.name}],
		}, name="ISE Demo Bank Transfer")
		self.put("cash_payment_method", "Mode of Payment", {
			"mode_of_payment": "ISE Demo Cash", "type": "Cash",
			"accounts": [{"company": COMPANY, "default_account": self.accounts["cash"]}],
		}, name="ISE Demo Cash")
		self.put("opening_journal", "Journal Entry", {
			"company": COMPANY, "posting_date": self.day, "voucher_type": "Journal Entry",
			"user_remark": "SYNTHETIC: training capital only; no real money moved.",
			"accounts": [
				{"account": bank_gl.name, "debit_in_account_currency": 500000},
				{"account": self.accounts["equity"], "credit_in_account_currency": 500000},
			],
		}, submit=True)
		for key, label in (("raw_warehouse", "ISE Raw Materials"), ("wip_warehouse", "ISE Work In Progress"),
			("finished_warehouse", "ISE Finished Goods"), ("showroom_warehouse", "ISE Showroom"),
			("supplier_warehouse", "ISE Supplier Materials")):
			self.put(key, "Warehouse", {"warehouse_name": label, "company": COMPANY,
				"account": self.accounts["stock"]}, name=label + " - ISE")
		self.put("company_address", "Address", {
			"address_title": "ISE Synthetic Workshop", "address_type": "Office",
			"address_line1": "Training premises (fictional)", "city": "Addis Ababa", "country": COUNTRY,
			"is_your_company_address": 1, "links": [{"link_doctype": "Company", "link_name": COMPANY}],
		})
		self.put("holiday_list", "Holiday List", {
			"holiday_list_name": f"ISE Training Calendar {year}", "from_date": f"{year}-01-01",
			"to_date": f"{year}-12-31",
		}, name=f"ISE Training Calendar {year}")
		self.put("department", "Department", {"department_name": "ISE Operations", "company": COMPANY},
			name="ISE Operations - ISE")
		self.put("employee", "Employee", {
			"first_name": "Aster", "last_name": "Demo", "company": COMPANY, "gender": "Female",
			"date_of_birth": "1990-01-01", "date_of_joining": f"{year}-01-01", "status": "Active",
			"department": self.name("department"), "holiday_list": self.name("holiday_list"),
		})
		frappe.db.set_single_value("System Settings", {
			"country": COUNTRY, "language": "en", "time_zone": "Africa/Addis_Ababa", "currency": CURRENCY,
			"enable_telemetry": 0, "enable_scheduler": 0, "setup_complete": 1,
		})

	def masters(self):
		from frappe.utils.nestedset import get_root_of
		self.put("brand", "Brand", {"brand": "ISE Training Products",
			"description": "Synthetic workshop products used only in the starter walkthrough."}, name="ISE Training Products")
		self.put("item_group", "Item Group", {"item_group_name": "ISE Training Furniture",
			"parent_item_group": get_root_of("Item Group"), "is_group": 0}, name="ISE Training Furniture")
		self.put("item_attribute", "Item Attribute", {"attribute_name": "ISE Training Finish",
			"item_attribute_values": [{"attribute_value": "Natural", "abbr": "NAT"},
				{"attribute_value": "White", "abbr": "WHT"}]}, name="ISE Training Finish")
		self.put("payment_term", "Payment Term", {"payment_term_name": "ISE Due On Receipt", "invoice_portion": 100,
			"due_date_based_on": "Day(s) after invoice date", "credit_days": 0,
			"mode_of_payment": self.name("bank_payment_method")}, name="ISE Due On Receipt")
		self.put("payment_terms_template", "Payment Terms Template", {"template_name": "ISE Due On Receipt",
			"terms": [{"payment_term": self.name("payment_term"), "invoice_portion": 100,
				"due_date_based_on": "Day(s) after invoice date", "credit_days": 0}]}, name="ISE Due On Receipt")
		self.put("terms_and_conditions", "Terms and Conditions", {"title": "ISE Synthetic Training Terms",
			"terms": "Training documents only. All parties, amounts and transactions are synthetic.",
			"selling": 1, "buying": 1}, name="ISE Synthetic Training Terms")
		for key, label in (("customer", "ISE Demo Addis Retail"), ("customer_two", "ISE Demo Adama Trading")):
			self.put(key, "Customer", {"customer_name": label, "customer_type": "Company",
				"customer_group": "Commercial", "territory": COUNTRY, "default_currency": CURRENCY,
				"accounts": [{"company": COMPANY, "account": self.accounts["receivable"]}]}, name=label)
		self.put("supplier", "Supplier", {"supplier_name": "ISE Demo Materials Supplier", "supplier_type": "Company",
			"supplier_group": "Local", "default_currency": CURRENCY,
			"accounts": [{"company": COMPANY, "account": self.accounts["payable"]}]}, name="ISE Demo Materials Supplier")
		for party_key, party_type, city in (("customer", "Customer", "Addis Ababa"), ("customer_two", "Customer", "Adama"), ("supplier", "Supplier", "Addis Ababa")):
			self.put(party_key + "_address", "Address", {"address_title": self.name(party_key),
				"address_type": "Billing", "address_line1": "Synthetic training address; not a real premises",
				"city": city, "country": COUNTRY, "is_primary_address": 1,
				"links": [{"link_doctype": party_type, "link_name": self.name(party_key)}]})
		self.put("customer_contact", "Contact", {"first_name": "Hana", "last_name": "Demo",
			"email_ids": [{"email_id": "hana.demo@example.invalid", "is_primary": 1}],
			"links": [{"link_doctype": "Customer", "link_name": self.name("customer")}], "is_primary_contact": 1})
		for key, label, buying, selling in (("buying_price_list", "ISE Training Buying", 1, 0), ("selling_price_list", "ISE Training Selling", 0, 1)):
			self.put(key, "Price List", {"price_list_name": label, "currency": CURRENCY, "enabled": 1,
				"buying": buying, "selling": selling}, name=label)
		for key, code, label, group, stock, rate in (
			("raw_item", "ISE-DESK-BOARD", "Training desk board", "Raw Material", 1, 600),
			("hardware_item", "ISE-HARDWARE-KIT", "Training hardware kit", "Raw Material", 1, 150),
			("finished_item", "ISE-TRAINING-DESK", "Assembled training desk", self.name("item_group"), 1, 1800),
			("service_item", "ISE-MAINT-SERVICE", "Training maintenance service", "Services", 0, 500),
			("subcontract_service", "ISE-ASSEMBLY-SERVICE", "Training subcontract assembly", "Services", 0, 250),
		):
			warehouse = self.name("finished_warehouse" if key == "finished_item" else "raw_warehouse")
			self.put(key, "Item", {"item_code": code, "item_name": label, "item_group": group,
				"brand": self.name("brand"),
				"stock_uom": "Nos", "is_stock_item": stock, "is_purchase_item": 1, "is_sales_item": 1,
				"description": "SYNTHETIC IBTINEX training product. No commercial inventory.",
				"item_defaults": [{"company": COMPANY, "default_warehouse": warehouse,
					"expense_account": self.accounts["cogs"], "income_account": self.accounts["income"],
					"buying_cost_center": self.cost_center, "selling_cost_center": self.cost_center,
					"default_supplier": self.name("supplier")}],
			}, name=code)
			self.put(key + "_price", "Item Price", {"item_code": code,
				"price_list": self.name("selling_price_list" if key in ("finished_item", "service_item") else "buying_price_list"),
				"price_list_rate": rate, "currency": CURRENCY, "uom": "Nos"})
		tax_parent = frappe.db.get_value("Account", {"company": COMPANY, "account_name": "Duties and Taxes", "is_group": 1})
		self.put("sales_tax_account", "Account", {"account_name": "ISE Illustrative Sales Tax",
			"parent_account": tax_parent, "company": COMPANY, "account_type": "Tax",
			"account_currency": CURRENCY}, name="ISE Illustrative Sales Tax - ISE")
		self.put("sales_tax_template", "Sales Taxes and Charges Template", {
			"title": "ISE Training Tax 15 Percent (Illustrative)", "company": COMPANY, "is_default": 0,
			"taxes": [{"charge_type": "On Net Total", "account_head": self.name("sales_tax_account"),
				"rate": 15, "description": "Illustrative training tax; not statutory configuration"}],
		})
		self.put("sales_person", "Sales Person", {"sales_person_name": "ISE Demo Service Team",
			"is_group": 0, "parent_sales_person": get_root_of("Sales Person")}, name="ISE Demo Service Team")
		self.put("campaign", "Campaign", {"campaign_name": "ISE Synthetic Training Launch"})
		self.put("lead", "Lead", {"company_name": self.name("customer"), "first_name": "Hana",
			"last_name": "Demo", "company": COMPANY, "country": COUNTRY, "customer": self.name("customer"),
			"email_id": "hana.demo@example.invalid", "unsubscribed": 1})
		self.put("opportunity", "Opportunity", {"opportunity_from": "Customer", "party_name": self.name("customer"),
			"company": COMPANY, "transaction_date": self.day, "opportunity_type": "Sales",
			"currency": CURRENCY, "items": [{"item_code": self.name("finished_item"), "qty": 4, "rate": 1800}]})
		self.put("shipping_rule", "Shipping Rule", {"label": "ISE Guided Delivery Example", "disabled": 1,
			"shipping_rule_type": "Selling", "company": COMPANY, "account": self.accounts["income"],
			"cost_center": self.cost_center, "calculate_based_on": "Fixed", "shipping_amount": 200,
			"countries": [{"country": COUNTRY}]}, name="ISE Guided Delivery Example")
		self.put("pricing_rule", "Pricing Rule", {"title": "ISE Bulk Desk Discount Example", "disable": 1,
			"apply_on": "Item Code", "price_or_product_discount": "Price", "selling": 1,
			"company": COMPANY, "currency": CURRENCY, "valid_from": self.day, "min_qty": 20,
			"rate_or_discount": "Discount Percentage", "discount_percentage": 5,
			"items": [{"item_code": self.name("finished_item")}],
			"for_price_list": self.name("selling_price_list"),
			"rule_description": "Disabled guided exercise; enable deliberately to demonstrate bulk pricing."})

	def procurement(self):
		from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_receipt
		from erpnext.stock.doctype.purchase_receipt.purchase_receipt import make_purchase_invoice
		items = [{"item_code": self.name(key), "qty": 100, "rate": rate,
			"schedule_date": self.day, "warehouse": self.name("raw_warehouse")} for key, rate in (("raw_item", 600), ("hardware_item", 150))]
		mr = self.put("material_request", "Material Request", {"company": COMPANY,
			"material_request_type": "Purchase", "transaction_date": self.day, "schedule_date": self.day,
			"items": deepcopy(items)}, submit=True)
		for row, request_row in zip(items, mr.items, strict=True):
			row.update(material_request=mr.name, material_request_item=request_row.name)
		po = self.put("purchase_order", "Purchase Order", {"company": COMPANY, "supplier": self.name("supplier"),
			"transaction_date": self.day, "schedule_date": self.day, "currency": CURRENCY, "conversion_rate": 1,
			"buying_price_list": self.name("buying_price_list"), "price_list_currency": CURRENCY,
			"plc_conversion_rate": 1, "items": items, "taxes": [],
			"payment_terms_template": self.name("payment_terms_template"),
			"tc_name": self.name("terms_and_conditions")}, submit=True)
		pr = self.save("purchase_receipt", self.posting(make_purchase_receipt(po.name), 2), submit=True)
		pi = self.save("purchase_invoice", self.posting(make_purchase_invoice(pr.name), 3), submit=True)
		self.payment("supplier_payment", pi, 4)

	def payment(self, key, invoice, minute):
		from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
		doc = get_payment_entry(invoice.doctype, invoice.name, bank_account=self.accounts["bank"], reference_date=self.day)
		self.posting(doc, minute)
		doc.reference_no = "SYNTHETIC-" + key.upper()
		doc.reference_date = self.day
		doc.mode_of_payment = self.name("bank_payment_method")
		return self.save(key, doc, submit=True)

	def manufacturing(self):
		from erpnext.manufacturing.doctype.work_order.work_order import make_stock_entry
		self.put("workstation", "Workstation", {"workstation_name": "ISE Demo Assembly Bench",
			"production_capacity": 1, "warehouse": self.name("wip_warehouse"),
			"holiday_list": self.name("holiday_list"),
			"working_hours": [{"start_time": "00:00:00", "end_time": "23:59:00"}]}, name="ISE Demo Assembly Bench")
		self.put("operation", "Operation", {"name": "ISE Demo Assembly",
			"description": "Synthetic desk assembly training operation"}, name="ISE Demo Assembly")
		bom = self.put("bom", "BOM", {"item": self.name("finished_item"), "company": COMPANY,
			"quantity": 1, "currency": CURRENCY, "conversion_rate": 1, "is_active": 1, "is_default": 1,
			"rm_cost_as_per": "Price List", "buying_price_list": self.name("buying_price_list"),
			"with_operations": 1, "transfer_material_against": "Work Order",
			"operations": [{"operation": self.name("operation"), "workstation": self.name("workstation"),
				"time_in_mins": 2, "hour_rate": 0, "batch_size": 10}],
			"items": [{"item_code": self.name("raw_item"), "qty": 1, "rate": 600},
				{"item_code": self.name("hardware_item"), "qty": 1, "rate": 150}],
		}, submit=True, name="BOM-ISE-TRAINING-DESK-001")
		wo = frappe.new_doc("Work Order")
		wo.update({"production_item": self.name("finished_item"), "bom_no": bom.name, "company": COMPANY,
			"qty": 10, "source_warehouse": self.name("raw_warehouse"), "wip_warehouse": self.name("wip_warehouse"),
			"fg_warehouse": self.name("finished_warehouse"), "planned_start_date": self.day + " 00:10:00"})
		wo.get_items_and_operations_from_bom()
		wo = self.save("work_order", wo, submit=True)
		transfer = frappe.get_doc(make_stock_entry(wo.name, "Material Transfer for Manufacture", 10))
		self.save("material_transfer", self.posting(transfer, 10), submit=True)
		job_cards = frappe.get_all("Job Card", filters={"work_order": wo.name}, pluck="name", order_by="name")
		if not job_cards:
			raise ValueError("Native work order did not generate its required job card.")
		for index, name in enumerate(job_cards, 1):
			job = frappe.get_doc("Job Card", name)
			job.set("time_logs", [{"from_time": self.day + " 00:11:00", "to_time": self.day + " 00:31:00",
				"completed_qty": job.for_quantity, "employee": self.name("employee")}])
			job.save()
			job.submit()
			self.remember(f"job_card_{index}", job)
		manufacture = frappe.get_doc(make_stock_entry(wo.name, "Manufacture", 10))
		self.save("manufacture", self.posting(manufacture, 32), submit=True)

	def selling(self):
		from erpnext.controllers.accounts_controller import get_taxes_and_charges
		from erpnext.selling.doctype.quotation.quotation import make_sales_order
		from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note
		from erpnext.stock.doctype.delivery_note.delivery_note import make_sales_invoice
		quotation = self.put("quotation", "Quotation", {
			"quotation_to": "Customer", "party_name": self.name("customer"), "company": COMPANY,
			"opportunity": self.name("opportunity"), "transaction_date": self.day,
			"currency": CURRENCY, "conversion_rate": 1, "selling_price_list": self.name("selling_price_list"),
			"price_list_currency": CURRENCY, "plc_conversion_rate": 1,
			"taxes_and_charges": self.name("sales_tax_template"),
			"taxes": get_taxes_and_charges("Sales Taxes and Charges Template", self.name("sales_tax_template")),
			"payment_terms_template": self.name("payment_terms_template"),
			"tc_name": self.name("terms_and_conditions"),
			"items": [{"item_code": self.name("finished_item"), "qty": 4, "rate": 1800,
				"warehouse": self.name("finished_warehouse")}],
		}, submit=True)
		order = make_sales_order(quotation.name)
		order.transaction_date = self.day
		order.delivery_date = self.day
		for row in order.items:
			row.delivery_date = self.day
		order = self.save("sales_order", order, submit=True)
		delivery = self.save("delivery_note", self.posting(make_delivery_note(order.name), 35), submit=True)
		invoice = self.save("sales_invoice", self.posting(make_sales_invoice(delivery.name), 36), submit=True)
		payment = self.payment("customer_payment", invoice, 37)
		self.put("bank_transaction", "Bank Transaction", {"date": self.day, "bank_account": self.name("bank_account"),
			"company": COMPANY, "currency": CURRENCY, "deposit": payment.received_amount,
			"description": "SYNTHETIC: example bank statement credit awaiting reconciliation",
			"reference_number": payment.reference_no, "transaction_id": "ISE-DEMO-BANK-001",
			"party_type": "Customer", "party": self.name("customer")}, submit=True)
		self.put("open_sales_order", "Sales Order", {"customer": self.name("customer_two"), "company": COMPANY,
			"transaction_date": self.day, "delivery_date": self.day, "currency": CURRENCY, "conversion_rate": 1,
			"selling_price_list": self.name("selling_price_list"), "price_list_currency": CURRENCY,
			"plc_conversion_rate": 1, "items": [{"item_code": self.name("finished_item"), "qty": 2,
				"rate": 1800, "delivery_date": self.day, "warehouse": self.name("finished_warehouse")}],
			"taxes": []}, submit=True)
		self.put("stock_transfer", "Stock Entry", {"stock_entry_type": "Material Transfer", "purpose": "Material Transfer",
			"company": COMPANY, "posting_date": self.day, "posting_time": "00:38:00", "set_posting_time": 1,
			"items": [{"item_code": self.name("finished_item"), "qty": 2,
				"s_warehouse": self.name("finished_warehouse"), "t_warehouse": self.name("showroom_warehouse")}],
		}, submit=True)
		self.put("pos_profile", "POS Profile", {"company": COMPANY, "customer": self.name("customer_two"),
			"currency": CURRENCY, "warehouse": self.name("showroom_warehouse"), "selling_price_list": self.name("selling_price_list"),
			"write_off_account": self.account(account_name="Write Off"), "write_off_cost_center": self.cost_center,
			"account_for_change_amount": self.accounts["cash"], "income_account": self.accounts["income"],
			"expense_account": self.accounts["cogs"], "cost_center": self.cost_center,
			"payments": [{"mode_of_payment": self.name("cash_payment_method"), "default": 1}],
		})

	def subcontracting(self):
		from erpnext.buying.doctype.purchase_order.purchase_order import make_subcontracting_order
		self.put("subcontracting_bom", "Subcontracting BOM", {
			"finished_good": self.name("finished_item"), "finished_good_qty": 1, "finished_good_bom": self.name("bom"),
			"service_item": self.name("subcontract_service"), "service_item_qty": 1, "service_item_uom": "Nos",
		})
		order = self.put("subcontracting_purchase_order", "Purchase Order", {
			"supplier": self.name("supplier"), "company": COMPANY, "transaction_date": self.day, "schedule_date": self.day,
			"is_subcontracted": 1, "currency": CURRENCY, "conversion_rate": 1,
			"buying_price_list": self.name("buying_price_list"), "price_list_currency": CURRENCY, "plc_conversion_rate": 1,
			"items": [{"item_code": self.name("subcontract_service"), "qty": 2, "rate": 250,
				"fg_item": self.name("finished_item"), "fg_item_qty": 2, "schedule_date": self.day,
				"warehouse": self.name("finished_warehouse")}], "taxes": [],
		}, submit=True)
		sco = make_subcontracting_order(order.name)
		sco.supplier_warehouse = self.name("supplier_warehouse")
		sco.transaction_date = self.day
		for row in sco.supplied_items:
			row.reserve_warehouse = self.name("raw_warehouse")
		self.save("subcontracting_order", sco, submit=True)

	def projects_assets(self):
		self.put("project", "Project", {"project_name": "ISE Training Room Delivery", "company": COMPANY,
			"customer": self.name("customer"), "sales_order": self.name("sales_order"), "project_type": "External",
			"expected_start_date": self.day, "expected_end_date": self.day, "collect_progress": 0,
			"notes": "SYNTHETIC project connecting workshop production and customer installation."})
		self.put("task_plan", "Task", {"subject": "ISE Plan training room", "project": self.name("project"),
			"status": "Open", "exp_start_date": self.day, "exp_end_date": self.day})
		self.put("task_delivery", "Task", {"subject": "ISE Install training desks", "project": self.name("project"),
			"status": "Open", "exp_start_date": self.day, "exp_end_date": self.day,
			"depends_on": [{"task": self.name("task_plan")}]})
		self.put("activity_type", "Activity Type", {"activity_type": "ISE Installation Training",
			"billing_rate": 500, "costing_rate": 200}, name="ISE Installation Training")
		self.put("timesheet", "Timesheet", {"employee": self.name("employee"), "company": COMPANY,
			"currency": CURRENCY, "time_logs": [{"activity_type": self.name("activity_type"),
				"project": self.name("project"), "task": self.name("task_delivery"),
				"from_time": self.day + " 09:00:00", "to_time": self.day + " 11:00:00",
				"hours": 2, "is_billable": 1, "billing_rate": 500, "costing_rate": 200,
				"description": "Synthetic guided installation exercise"}]}, submit=True)
		self.put("asset_location", "Location", {"location_name": "ISE Demo Workshop"}, name="ISE Demo Workshop")
		self.put("asset_category", "Asset Category", {"asset_category_name": "ISE Training Equipment", "enable_cwip_accounting": 0,
			"accounts": [{"company_name": COMPANY, "fixed_asset_account": self.accounts["fixed_asset"],
				"accumulated_depreciation_account": self.accounts["accumulated_depreciation"],
				"depreciation_expense_account": self.accounts["depreciation"]}],
			"finance_books": [{"depreciation_method": "Straight Line", "total_number_of_depreciations": 12,
				"frequency_of_depreciation": 1}]}, name="ISE Training Equipment")
		self.put("asset_item", "Item", {"item_code": "ISE-DEMO-EQUIPMENT", "item_name": "Synthetic workshop equipment",
			"item_group": "Products", "stock_uom": "Nos", "is_stock_item": 0, "is_fixed_asset": 1,
			"asset_category": self.name("asset_category"), "auto_create_assets": 0}, name="ISE-DEMO-EQUIPMENT")
		self.put("asset", "Asset", {"asset_name": "ISE Demonstration Equipment", "item_code": self.name("asset_item"),
			"company": COMPANY, "asset_category": self.name("asset_category"), "location": self.name("asset_location"),
			"custodian": self.name("employee"), "purchase_date": self.day, "available_for_use_date": self.day,
			"asset_type": "Existing Asset", "net_purchase_amount": 12000, "asset_quantity": 1,
			"calculate_depreciation": 1, "cost_center": self.cost_center,
			"finance_books": [{"depreciation_method": "Straight Line", "total_number_of_depreciations": 12,
				"frequency_of_depreciation": 1, "depreciation_start_date": (date.fromisoformat(self.day) + timedelta(days=30)).isoformat(),
				"expected_value_after_useful_life": 0}],
		}, submit=True)
		self.put("asset_opening_journal", "Journal Entry", {"company": COMPANY, "posting_date": self.day,
			"voucher_type": "Journal Entry", "user_remark": "SYNTHETIC: opening book value of existing training equipment.",
			"accounts": [{"account": self.accounts["fixed_asset"], "debit_in_account_currency": 12000,
				"reference_type": "Asset", "reference_name": self.name("asset")},
				{"account": self.accounts["equity"], "credit_in_account_currency": 12000}]}, submit=True)
		self.put("budget", "Budget", {"budget_against": "Cost Center", "company": COMPANY,
			"cost_center": self.cost_center, "account": self.accounts["cogs"], "budget_amount": 100000,
			"from_fiscal_year": self.name("fiscal_year"), "to_fiscal_year": self.name("fiscal_year"),
			"distribution_frequency": "Monthly", "distribute_equally": 1,
			"applicable_on_booking_actual_expenses": 1, "action_if_annual_budget_exceeded": "Warn",
			"action_if_accumulated_monthly_budget_exceeded": "Warn"})

	def quality_support(self):
		self.put("quality_procedure", "Quality Procedure", {"quality_procedure_name": "ISE Desk Inspection",
			"is_group": 0, "processes": [{"process_description": "Check stability, fasteners and surface finish."}]},
			name="ISE Desk Inspection")
		self.put("quality_goal", "Quality Goal", {"goal": "ISE Stable Training Desks", "procedure": self.name("quality_procedure"),
			"frequency": "None", "objectives": [{"objective": "Stable desks in sample of ten", "target": "10", "uom": "Nos"}]},
			name="ISE Stable Training Desks")
		self.put("quality_review", "Quality Review", {"goal": self.name("quality_goal"), "procedure": self.name("quality_procedure"),
			"date": self.day, "reviews": [{"objective": "Stable desks in sample of ten", "target": "10", "uom": "Nos",
				"review": "Synthetic sample: all ten desks passed visual and stability checks.", "status": "Passed"}]})
		self.put("quality_feedback_template", "Quality Feedback Template", {"template": "ISE Delivery Feedback",
			"parameters": [{"parameter": "Delivery condition"}, {"parameter": "Assembly quality"}]}, name="ISE Delivery Feedback")
		self.put("quality_feedback", "Quality Feedback", {"template": self.name("quality_feedback_template"),
			"document_type": "Customer", "document_name": self.name("customer"),
			"parameters": [{"parameter": "Delivery condition", "rating": "5", "feedback": "Synthetic: delivered as planned."},
				{"parameter": "Assembly quality", "rating": "4", "feedback": "Synthetic: recheck demonstration fastener."}]})
		self.put("quality_action", "Quality Action", {"goal": self.name("quality_goal"), "date": self.day,
			"procedure": self.name("quality_procedure"), "review": self.name("quality_review"),
			"feedback": self.name("quality_feedback"), "corrective_preventive": "Preventive",
			"resolutions": [{"problem": "Training fastener check can be missed.",
				"resolution": "Include a final torque check in the demonstration procedure.",
				"status": "Open", "responsible": frappe.session.user, "completion_by": self.day}]})
		self.put("issue", "Issue", {"subject": "ISE Demo: loose fastener after installation", "customer": self.name("customer"),
			"company": COMPANY, "project": self.name("project"), "raised_by": "hana.demo@example.invalid",
			"priority": "Low", "description": "Synthetic support exercise linked to the training room installation."})
		self.put("support_message", "Communication", {"communication_type": "Communication", "communication_medium": "Email",
			"sent_or_received": "Received", "subject": "ISE synthetic support follow-up",
			"content": "Training-only message: please check the demonstration desk fastener.",
			"sender": "hana.demo@example.invalid", "reference_doctype": "Issue", "reference_name": self.name("issue")})
		self.put("maintenance_schedule", "Maintenance Schedule", {"customer": self.name("customer"), "company": COMPANY,
			"transaction_date": self.day, "items": [{"item_code": self.name("finished_item"), "start_date": self.day,
				"end_date": (date.fromisoformat(self.day) + timedelta(days=90)).isoformat(), "periodicity": "Monthly",
				"no_of_visits": 3, "sales_person": self.name("sales_person")}]})
		self.put("maintenance_visit", "Maintenance Visit", {"customer": self.name("customer"), "company": COMPANY,
			"mntc_date": self.day, "completion_status": "Fully Completed", "maintenance_type": "Unscheduled",
			"purposes": [{"item_code": self.name("finished_item"), "service_person": self.name("sales_person"),
				"work_done": "Synthetic maintenance exercise: inspected and tightened demonstration fastener."}]}, submit=True)

	def portal_and_integrations(self):
		user = self.put("portal_customer", "User", {"email": "ise.portal@example.invalid", "first_name": "ISE",
			"last_name": "Demo Customer", "user_type": "Website User", "enabled": 0, "send_welcome_email": 0,
			"roles": [{"role": "Customer"}]}, name="ise.portal@example.invalid")
		customer = self.doc("customer")
		customer.append("portal_users", {"user": user.name})
		customer.save()
		self.put("communication_medium", "Communication Medium", {"communication_medium_type": "Voice", "disabled": 1},
			name="ISE Disabled Demo Voice")
		self.put("call_log", "Call Log", {"id": "ISE-DEMO-CALL-001", "type": "Outgoing", "status": "Completed",
			"from": "ISE-SYNTHETIC-INTERNAL", "to": "ISE-SYNTHETIC-CUSTOMER", "customer": self.name("customer"),
			"medium": self.name("communication_medium"), "start_time": self.day + " 12:00:00",
			"end_time": self.day + " 12:02:00", "duration": 120,
			"summary": "Synthetic history only; no call was placed.",
			"links": [{"link_doctype": "Customer", "link_name": self.name("customer")}]}, name="ISE-DEMO-CALL-001")
		self.put("edi_code_list", "Code List", {"title": "ISE Synthetic Product Codes", "publisher": "IBTINEX Training",
			"version": "1", "description": "Local demonstration mapping. No official EDI code system or certification."},
			name="ISE Synthetic Product Codes")
		self.put("edi_common_code", "Common Code", {"code_list": self.name("edi_code_list"), "title": "Training desk",
			"common_code": "DEMO-DESK", "applies_to": [{"link_doctype": "Item", "link_name": self.name("finished_item")}]})
		frappe.db.set_single_value("Plaid Settings", {"enabled": 0, "automatic_sync": 0, "plaid_env": "sandbox"})

	def manifest(self):
		for record in self.records.values():
			doc = frappe.get_doc(record["doctype"], record["name"])
			record["docstatus"] = int(doc.docstatus)
			record["child_tables"] = {field.fieldname: len(doc.get(field.fieldname) or [])
				for field in doc.meta.get_table_fields() if doc.get(field.fieldname)}
		return {"status": "installed", "seed_version": SEED_VERSION, "company": COMPANY,
			"as_of_date": self.day, "records": self.records, "coverage": coverage_manifest(self.records),
			"doctype_baseline_counts": self.baseline_counts,
			"limitations": ["Representative connected scenarios across all modules, not every permutation of all ERP features.",
				"No live payment, email, telephone, bank-sync or EDI service; portal sample user disabled.",
				"Illustrative tax and Standard chart are training data, not Ethiopian compliance qualification.",
				"Payroll, Webshop, separate CRM and Helpdesk require separately installed/qualified apps.",
				"Do not promote this populated review database into customer production."],
		}


def _verify(manifest, detailed_coverage=False):
	records = manifest["records"]
	def doc(key):
		r = records[key]
		return frappe.get_doc(r["doctype"], r["name"])
	def require(condition, message):
		if not condition:
			raise ValueError("Starter verification failed; existing data was not reset: " + message)
	for key, record in records.items():
		require(frappe.db.exists(record["doctype"], record["name"]), f"missing {key}")
		current = doc(key)
		require(int(current.docstatus) == record["docstatus"], f"changed document status: {key}")
		if current.meta.has_field("company") and current.company:
			require(current.company == COMPANY, f"wrong company: {key}")
	require(set(MODULE_COVERAGE) == {row["module"] for row in manifest["coverage"]}, "module coverage mismatch")
	coverage_manifest(records)
	require(doc("company").default_currency == CURRENCY and doc("company").country == COUNTRY, "company locale changed")
	for key in ("quotation", "sales_order", "sales_invoice"):
		require(Decimal(str(doc(key).grand_total)) == Decimal("8280"), f"unexpected total: {key}")
		require(Decimal(str(doc(key).total_taxes_and_charges)) == Decimal("1080"), f"unexpected training tax: {key}")
	for key in ("sales_invoice", "purchase_invoice"):
		require(abs(Decimal(str(doc(key).outstanding_amount))) < Decimal("0.01"), f"unsettled {key}")
	require(doc("sales_invoice").items[0].delivery_note == doc("delivery_note").name, "invoice/delivery link")
	require(doc("delivery_note").items[0].against_sales_order == doc("sales_order").name, "delivery/order link")
	require(doc("sales_order").items[0].prevdoc_docname == doc("quotation").name, "order/quotation link")
	require(doc("purchase_invoice").items[0].purchase_receipt == doc("purchase_receipt").name, "purchase invoice/receipt link")
	require(doc("purchase_receipt").items[0].purchase_order == doc("purchase_order").name, "receipt/order link")
	require(float(doc("work_order").produced_qty) == 10, "manufactured quantity")
	for item_key, warehouse_key, expected in (("raw_item", "raw_warehouse", 90), ("hardware_item", "raw_warehouse", 90),
		("finished_item", "finished_warehouse", 4), ("finished_item", "showroom_warehouse", 2)):
		qty = frappe.db.get_value("Bin", {"item_code": doc(item_key).name, "warehouse": doc(warehouse_key).name}, "actual_qty")
		require(Decimal(str(qty or 0)) == Decimal(expected), f"unexpected stock balance: {item_key}/{warehouse_key}")
	ledger = frappe.get_all("GL Entry", filters={"company": COMPANY, "is_cancelled": 0}, fields=["debit", "credit"])
	require(bool(ledger), "no native GL entries")
	imbalance = sum((Decimal(str(row.debit)) - Decimal(str(row.credit)) for row in ledger), Decimal(0))
	require(abs(imbalance) < Decimal("0.01"), "unbalanced general ledger")
	asset_gl = frappe.get_all("GL Entry", filters={"company": COMPANY, "is_cancelled": 0,
		"account": doc("asset_opening_journal").accounts[0].account}, fields=["debit", "credit"])
	asset_balance = sum((Decimal(str(row.debit)) - Decimal(str(row.credit)) for row in asset_gl), Decimal(0))
	require(asset_balance == Decimal(str(doc("asset").net_purchase_amount)), "asset register/opening GL mismatch")
	require(bool(frappe.db.count("Stock Ledger Entry", {"company": COMPANY})), "no native stock ledger")
	require(doc("portal_customer").enabled == 0, "synthetic portal user enabled")
	require(not frappe.db.count("Email Queue"), "unexpected queued email")
	for doctype in ("Email Account", "Webhook", "Email Campaign"):
		require(not frappe.db.count(doctype), f"outbound-capable {doctype} configured")
	require(not frappe.db.get_single_value("SMS Settings", "sms_gateway_url"), "SMS gateway configured")
	require(not frappe.db.count("Notification", {"enabled": 1}), "enabled outgoing notification")
	require(not frappe.db.get_single_value("Plaid Settings", "enabled"), "Plaid enabled")
	require(doc("communication_medium").disabled == 1, "synthetic voice medium enabled")
	require(doc("subcontracting_order").purchase_order == doc("subcontracting_purchase_order").name, "subcontract link")
	# Exercise the reports users actually open, in addition to checking raw ledgers.
	from erpnext.accounts.report.general_ledger.general_ledger import execute as general_ledger
	from erpnext.stock.report.stock_balance.stock_balance import execute as stock_balance
	filters = {"company": COMPANY, "from_date": manifest["as_of_date"], "to_date": manifest["as_of_date"]}
	gl_columns, gl_rows = general_ledger(frappe._dict(filters))
	stock_columns, stock_rows = stock_balance(frappe._dict(filters))
	require(bool(gl_columns) and bool(gl_rows), "General Ledger report is empty")
	require(bool(stock_columns) and bool(stock_rows), "Stock Balance report is empty")
	posted_vouchers = {row.get("voucher_no") for row in gl_rows if row.get("voucher_no")}
	for key in ("opening_journal", "purchase_receipt", "purchase_invoice", "supplier_payment",
		"delivery_note", "sales_invoice", "customer_payment", "asset_opening_journal"):
		require(doc(key).name in posted_vouchers, f"General Ledger report omits {key}")
	bank_rows = [row for row in gl_rows if row.get("account") == doc("bank_gl").name and row.get("voucher_no")]
	bank_balance = sum((Decimal(str(row.get("debit") or 0)) - Decimal(str(row.get("credit") or 0))
		for row in bank_rows), Decimal(0))
	require(bank_balance == Decimal("433280"), "General Ledger report bank balance")
	stock_map = {(row.get("item_code"), row.get("warehouse")): row for row in stock_rows}
	for item_key, warehouse_key, expected_qty, expected_value in (
		("raw_item", "raw_warehouse", 90, 54000), ("hardware_item", "raw_warehouse", 90, 13500),
		("finished_item", "finished_warehouse", 4, 3000), ("finished_item", "showroom_warehouse", 2, 1500)):
		row = stock_map.get((doc(item_key).name, doc(warehouse_key).name))
		require(bool(row), f"Stock Balance report omits {item_key}/{warehouse_key}")
		require(row.get("company") == COMPANY, "Stock Balance report contains another company")
		require(Decimal(str(row.get("bal_qty") or 0)) == Decimal(expected_qty), f"Stock Balance report quantity: {item_key}/{warehouse_key}")
		require(abs(Decimal(str(row.get("bal_val") or 0)) - Decimal(expected_value)) < Decimal("0.01"),
			f"Stock Balance report value: {item_key}/{warehouse_key}")
	stock_value = sum((Decimal(str(row.get("bal_val") or 0)) for row in stock_rows), Decimal(0))
	require(abs(stock_value - Decimal("72000")) < Decimal("0.01"), "Stock Balance report total value")
	coverage = doctype_coverage(manifest["doctype_baseline_counts"], records)
	result = {"status": "passed", "seed_version": SEED_VERSION, "company": COMPANY,
		"record_count": len(records), "counts_by_doctype": dict(sorted(Counter(r["doctype"] for r in records.values()).items())),
		"module_count": len(manifest["coverage"]), "gl_entry_count": len(ledger), "gl_imbalance": str(imbalance),
		"sales_outstanding": str(doc("sales_invoice").outstanding_amount),
		"purchase_outstanding": str(doc("purchase_invoice").outstanding_amount),
		"manufactured_qty": str(doc("work_order").produced_qty), "outbound_integrations": "inert",
		"fixed_asset_book_value": str(asset_balance), "doctype_coverage_summary": coverage["summary"],
		"reports": {"general_ledger": {"status": "passed", "rows": len(gl_rows), "bank_balance": str(bank_balance)},
			"stock_balance": {"status": "passed", "rows": len(stock_rows), "inventory_value": str(stock_value)}},
	}
	if detailed_coverage:
		result["doctype_coverage"] = coverage
	return result
