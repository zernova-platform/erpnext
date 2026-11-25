# Copyright (c) 2026, IBTINEX contributors
# License: GNU General Public License v3. See license.txt
"""Observed coverage for every DocType in the pinned ERPNext source inventory.

The inventory is complete; the starter scenarios are deliberately finite. A
record count is not a claim to have exercised every action or report in a module.
Only counts, document names and reasons are exported, never field contents.
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

INVENTORY_PATH = Path(__file__).with_name("doctype_inventory.json")

# These are reference masters populated by ERPNext's own initial fixtures.
REFERENCE_FIXTURES = {
	"Customer Group", "Supplier Group", "Territory", "UOM", "UOM Conversion Factor",
	"Industry Type", "Market Segment", "Opportunity Type", "Lead Source", "Sales Stage",
	"Designation", "Branch", "Department", "Employment Type", "Project Type", "Salutation",
	"Gender", "Stock Entry Type", "Item Group", "Sales Person", "Mode of Payment",
	"Price List", "Quality Procedure", "Transaction Deletion Record Item",
}

EXTERNAL_REASONS = {
	"Plaid Settings": "Disabled sandbox configuration only; no bank credentials, synchronization or provider calls.",
	"GoCardless Settings": "No payment-provider account, token or real direct-debit mandate is configured.",
	"Mpesa Settings": "No mobile-money merchant account, credentials or live transaction is configured.",
	"Payment Gateway Account": "A real payment-provider integration is not part of this synthetic walkthrough.",
	"Payment Request": "No payable external checkout or emailed payment request is created; ledger payments are native Payment Entries.",
	"Payment Order": "No bank-executable payment instruction is created; sample supplier payment is a local ledger entry.",
	"Process Payment Reconciliation": "No background reconciliation operation is fabricated; native payment allocations are verified directly.",
	"Video": "A playable video requires a real YouTube/Vimeo resource; no fake external video record is created.",
	"Video Settings": "External video tracking and its API credentials are not enabled.",
	"Email Campaign": "No recipients are scheduled for email; the sample Campaign has no email schedule.",
	"Newsletter Email Group": "No external marketing audience or distribution is created.",
	"SMS Center": "No SMS gateway, recipient list or transmission is configured.",
}

DEFERRED_REASONS = {
	"POS Opening Entry": "POS Profile and showroom stock are ready; an engineer opens a deliberate cash session during review.",
	"POS Closing Entry": "No cash session has been opened or closed; a fabricated cash-shift summary would misrepresent activity.",
	"POS Invoice": "The connected sale uses Sales Invoice; POS checkout remains a separate guided cash-session exercise.",
	"Subcontracting Receipt": "The submitted subcontracting order is awaiting a deliberate dispatch/receipt exercise; the sample in-house manufacturing flow is completed.",
	"Serial No": "The starter products are un-serialized; serial tracking needs a separate deliberately configured item/workflow.",
	"Batch": "The starter products are un-batched; expiry and batch handling need a separate deliberately configured item/workflow.",
	"Serial and Batch Bundle": "No serialized or batched starter item exists, so native bundle records are not fabricated.",
	"Stock Reconciliation": "Opening quantities arise from the submitted Purchase Receipt; no balancing adjustment masks transaction errors.",
	"Stock Reposting Settings": "Native settings retained; no repair/reposting operation is needed on a fresh synthetic ledger.",
	"Repost Item Valuation": "No historical repair is requested; stock ledger consistency is checked after native posting.",
	"Repost Accounting Ledger": "No historical accounting repair is requested; native posting is verified without fabricating repair jobs.",
	"Bulk Transaction Log": "Generated only by a real bulk operation; no fabricated success/audit log or destructive bulk action.",
	"Transaction Deletion Record": "No business transactions are deleted and no cleanup job is simulated.",
	"Account Closing Balance": "No closed financial period is claimed; the starter books remain open for review.",
	"Period Closing Voucher": "The training fiscal year stays open; year-end profit transfer is a separate accounting review exercise.",
	"Purchase Invoice Advance": "The supplier invoice is paid after posting, so an advance allocation row is not fabricated.",
	"Sales Invoice Advance": "The customer invoice is paid after posting, so an advance allocation row is not fabricated.",
	"Warranty Claim": "The linked Issue and Maintenance Visit cover service support; a warranty entitlement/return is not asserted.",
	"Asset Repair": "The synthetic existing asset has no recorded breakdown; repair capitalization is a separate scenario.",
	"Asset Value Adjustment": "The existing asset's opening value reconciles to GL; no artificial revaluation is posted.",
	"Website Item": "The optional Webshop app is not installed or qualified by this ERPNext-only image.",
}


def load_inventory():
	return json.loads(INVENTORY_PATH.read_text())


def snapshot_counts():
	"""Compact positional counts; inventory order/version makes them auditable."""
	import frappe
	counts = []
	for entry in load_inventory()["doctypes"]:
		if entry["is_virtual"]:
			counts.append(None)
		elif entry["is_single"]:
			counts.append(len(frappe.db.get_singles_dict(entry["doctype"])))
		else:
			counts.append(frappe.db.count(entry["doctype"]))
	return counts


def classify(entry, before, after, direct_keys):
	"""Return an evidence-based disposition; never infer a functional test from count alone."""
	name = entry["doctype"]
	if entry["is_virtual"]:
		return "not-seeded", "Virtual DocType reads other data; there is no independent persisted record to fabricate."
	if direct_keys:
		return "created", "Explicit starter document(s): " + ", ".join(direct_keys) + ". Native validation was retained."
	if entry["is_child"]:
		if after:
			return "generated-child", "Rows exist only through native parent documents/fixtures; no standalone child records were inserted."
		return "not-seeded", "Child rows require a scenario in their owning parent field; no orphan rows are fabricated. Owners: " + ", ".join(entry["parents"])
	if name in EXTERNAL_REASONS or entry["module"] == "ERPNext Integrations":
		return "inert-external", EXTERNAL_REASONS.get(name, "External integration is left unconfigured; no credentials, real accounts or provider traffic.")
	if entry["is_single"]:
		return "native-default-configuration", "Native singleton defaults/settings retained or set by ERPNext's fixture installer; configured-field count is not a business-record count."
	if after and (after == before or name in REFERENCE_FIXTURES):
		return "default-fixture", "Reference records supplied by native application installation/setup fixtures; no fabricated customer operation."
	if after and after > (before or 0):
		return "generated-native", "Native setup or submitted starter workflows generated these records (for example accounts, ledgers or schedules)."
	return "not-seeded", DEFERRED_REASONS.get(name, f"No {name} scenario is included in starter v1. The native screen remains available; this is an explicit coverage gap, not a claim that the feature was tested.")


def doctype_coverage(baseline_counts, records, current_counts=None):
	inventory = load_inventory()
	entries = inventory["doctypes"]
	if len(baseline_counts) != len(entries):
		raise ValueError("Starter coverage inventory and stored baseline counts do not match.")
	if current_counts is None:
		current_counts = snapshot_counts()
	if len(current_counts) != len(entries):
		raise ValueError("Current DocType count vector does not match the pinned inventory.")
	direct = defaultdict(list)
	for key, record in records.items():
		direct[record["doctype"]].append(key)
	rows = []
	for entry, before, after in zip(entries, baseline_counts, current_counts, strict=True):
		status, reason = classify(entry, before, after, sorted(direct[entry["doctype"]]))
		rows.append({**entry, "status": status, "reason": reason, "before_count": before,
			"current_count": after, "explicit_record_keys": sorted(direct[entry["doctype"]])})
	return {"erpnext_version": inventory["erpnext_version"], "upstream_commit": inventory["upstream_commit"],
		"scope": "Every ERPNext DocType schema, including child tables and technical/configuration records. Framework-only and optional-app DocTypes are outside this inventory.",
		"summary": {"total_doctypes": len(rows), "by_status": dict(sorted(Counter(r["status"] for r in rows).items())),
			"by_module": dict(sorted(Counter(r["module"] for r in rows).items()))}, "doctypes": rows}
