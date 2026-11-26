// Copyright (c) 2026, IBTINEX and contributors
// License: GNU General Public License v3. See license.txt

// Presentation only: keep Frappe's login forms, handlers, providers and redirects.
// The name is resolved by the native login controller and safely serialized in boot.
frappe.ready(() => {
	if (document.body.dataset.path !== "login") return;
	const name = frappe.boot?.ibtinex_app_name;
	if (typeof name !== "string" || !name.trim()) return;

	document.querySelectorAll(".page-card-head").forEach((header) => {
		if (header.querySelector(".ibtinex-product-name")) return;
		const logo = header.querySelector("img.app-logo");
		if (!logo) return;
		if (!logo.getAttribute("alt")) logo.setAttribute("alt", name);
		const label = document.createElement("p");
		label.className = "ibtinex-product-name";
		label.textContent = name;
		logo.insertAdjacentElement("afterend", label);
	});
});
