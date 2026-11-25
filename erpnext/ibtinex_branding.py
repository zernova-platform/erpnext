# Copyright (c) 2026, IBTINEX and contributors
# License: GNU General Public License v3. See license.txt

"""Apply distribution identity through Frappe's existing presentation settings.

Called explicitly by the installation/visual-upgrade recipe. No public API is
exposed. Changes remain in the caller's transaction, and customer names and logos
are preserved. The compiled, screen-only theme is included through asset hooks;
company data, letterheads, print formats and business settings are untouched.
"""

import json
from pathlib import Path


STATE_KEY = "ibtinex_branding_v1"
PRODUCT_NAME = "IBTINEX ERP"
LOGO = "/assets/erpnext/images/ibtinex-logo.svg"
FAVICON = "/assets/erpnext/images/ibtinex-favicon.svg"
_SAVEPOINT = "ibtinex_branding"
_FIELDS = {
	"Website Settings.app_logo": LOGO,
	"Navbar Settings.app_logo": LOGO,
	"Website Settings.favicon": FAVICON,
	"Website Settings.splash_image": LOGO,
	"Website Settings.app_name": PRODUCT_NAME,
	"System Settings.app_name": PRODUCT_NAME,
}
_UPSTREAM_VALUES = {
	"",
	None,
	"/assets/erpnext/images/erpnext-logo.svg",
	"/assets/erpnext/images/erpnext-favicon.svg",
	"/assets/frappe/images/frappe-framework-logo.svg",
	"/assets/frappe/images/frappe-favicon.svg",
}
_NAME_KEYS = ("Website Settings.app_name", "System Settings.app_name")


def _upstream_values(key):
	# Name defaults must never make a coincidentally named customer logo eligible
	# for replacement. Keep the existing ownership record backward-compatible.
	if key in _NAME_KEYS:
		return {"", None, "ERPNext", "Frappe"}
	return _UPSTREAM_VALUES


def _check_assets():
	for url in (LOGO, FAVICON):
		path = Path(__file__).parent / "public" / url.removeprefix("/assets/erpnext/")
		if not path.is_file() or not path.stat().st_size:
			raise RuntimeError("IBTINEX branding assets are missing from this image.")


def _state(frappe):
	encoded = frappe.db.get_default(STATE_KEY)
	if not encoded:
		return {"version": 1, "managed": {}}
	try:
		state = json.loads(encoded)
		if state["version"] != 1 or not isinstance(state["managed"], dict):
			raise ValueError
		for key, item in state["managed"].items():
			if key not in _FIELDS or not isinstance(item, dict) or set(item) != {"previous", "applied"}:
				raise ValueError
			if item["previous"] is not None and not isinstance(item["previous"], str):
				raise ValueError
			if not isinstance(item["applied"], str):
				raise ValueError
	except (KeyError, TypeError, ValueError):
		raise RuntimeError("IBTINEX branding ownership record is invalid; no settings were changed.") from None
	return state


def _read_values(frappe):
	values = {}
	for key in _FIELDS:
		doctype, field = key.split(".", 1)
		if not frappe.get_meta(doctype).has_field(field):
			raise RuntimeError("This Frappe version does not expose the expected branding settings.")
		values[key] = frappe.db.get_single_value(doctype, field, cache=False, for_update=True)
	return values


def _write(frappe, key, value):
	doctype, field = key.split(".", 1)
	frappe.db.set_single_value(doctype, field, value)


def apply():
	"""Default stock identity once; preserve later edits and customer-owned branding."""
	import frappe

	_check_assets()
	state = _state(frappe)
	values = _read_values(frappe)
	managed = state["managed"]
	result = {"changed": [], "unchanged": [], "preserved": []}

	# Website Settings takes precedence over Navbar Settings. Do not fill an empty
	# website logo when doing so would hide a customer's existing navbar logo.
	logo_keys = ("Website Settings.app_logo", "Navbar Settings.app_logo")
	custom_logo = any(
		values[key] not in _UPSTREAM_VALUES
		and values[key] != _FIELDS[key]
		and values[key] != managed.get(key, {}).get("applied")
		for key in logo_keys
	)
	# Website name wins over System Settings on the login page. The same
	# precedence protection as logos avoids hiding a customer's system app name.
	custom_name = any(
		values[key] not in _upstream_values(key)
		and values[key] != _FIELDS[key]
		and values[key] != managed.get(key, {}).get("applied")
		for key in _NAME_KEYS
	)

	frappe.db.savepoint(_SAVEPOINT)
	try:
		for key, wanted in _FIELDS.items():
			current = values[key]
			owned = managed.get(key)
			custom_value = current != owned["applied"] if owned else current not in _upstream_values(key)
			if current == wanted:
				result["unchanged"].append(key)
				continue
			if (key in logo_keys and custom_logo) or (key in _NAME_KEYS and custom_name) or custom_value:
				result["preserved"].append(key)
				continue
			_write(frappe, key, wanted)
			managed[key] = {"previous": owned["previous"] if owned else current, "applied": wanted}
			result["changed"].append(key)
		if result["changed"]:
			frappe.db.set_default(STATE_KEY, json.dumps(state, sort_keys=True))
			frappe.clear_cache()
	except Exception:
		frappe.db.rollback(save_point=_SAVEPOINT)
		raise
	return result


def update_website_context(context):
	"""Expose the native login name for presentation, without touching authentication.

	Frappe's login controller already resolves Website/System Settings precedence.
	Its web boot dictionary is JSON-escaped by the native base template. The tiny
	web asset uses textContent, never HTML, for customer-provided display names.
	"""
	if context.get("path") != "login" or not context.get("app_name"):
		return
	name = context["app_name"]
	if isinstance(context.get("boot"), dict):
		context["boot"]["ibtinex_app_name"] = name
	context["title"] = f"{name} · {context.get('title') or 'Login'}"


def restore():
	"""Undo only settings still owned by this recipe; retain subsequent custom edits."""
	import frappe

	state = _state(frappe)
	values = _read_values(frappe)
	result = {"restored": [], "preserved": []}
	frappe.db.savepoint(_SAVEPOINT)
	try:
		for key, owned in list(state["managed"].items()):
			if values[key] != owned["applied"]:
				result["preserved"].append(key)
				continue
			_write(frappe, key, owned["previous"])
			del state["managed"][key]
			result["restored"].append(key)
		if result["restored"]:
			frappe.db.set_default(STATE_KEY, json.dumps(state, sort_keys=True))
			frappe.clear_cache()
	except Exception:
		frappe.db.rollback(save_point=_SAVEPOINT)
		raise
	return result
