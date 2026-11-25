# ERPNext functional and user-interface review for the IBTINEX fork

## Review baseline and evidence limits

Reviewed on 2026-11-25. ERPNext application baseline: tag `v16.60.0`, commit `886ab6ae187244e7f1b852393384ab6019d56264`. This is the image tag in upstream `frappe/frappe_docker/main/pwd.yml` at the time of inspection, whose file blob is `cf492ed7034a7a402d8de8202afd218f1ea60b68`. The review also inspected the live Windows ERP Installed Applications screen and confirmed ERPNext 16.60.0 with Frappe 16.60.2; the UI showed UNVERSIONED Git branches. The source baseline is therefore the matching upstream tags, with Frappe `v16.60.2` at commit `2df0425571ebbaed878eabc3edc5b7e7c3327ae0`. Runtime image digests still require separate capture. Upstream ERPNext `v16.61.0` was also observed, but should be qualified as a separate update after the first branding release.

Evidence: a complete Git tree (7,185 entries; `truncated: false`), all 21 module names, the source hooks, navigation configurations, representative business schemas/controllers/reports/tests, setup fixtures and country data, framework branding schemas, and upstream READMEs for separate apps. This is a broad source inspection with representative deeper reads, not a line-by-line security audit or successful runtime test.

The inventory contains 5,774 tracked blobs, 534 DocType schema JSONs including child tables, 194 Report schema JSONs, 15 Workspace schema JSONs, and 550 files named `test_*.py`. Schema counts require the JSON basename to equal its parent directory, excluding `test_records.json`. These counts were independently reproduced against the local clone at the same commit using `git ls-tree -r --name-only HEAD`; all counted DocType/Report/Workspace JSONs parsed and their `doctype` values matched the expected category. Test presence does not mean tests were executed.

Pinned source root: https://github.com/frappe/erpnext/tree/886ab6ae187244e7f1b852393384ab6019d56264

## Functional coverage and minimal-change decision

Every module named in `erpnext/modules.txt` is represented below. Paths are relative to that pinned source root. Schema/report counts are inventory counts, not customer-visible feature counts.

| Area | Schemas / reports | Observed sources and capabilities | Decision for the first branded release |
|---|---:|---|---|
| Accounts | 191 / 57 | `erpnext/accounts/`: sales/purchase invoices, GL/payment ledgers, payments, tax templates, reconciliation, financial statements, POS, subscriptions, budgets | Retain upstream calculations, posting, cancellation, reports and permission behavior. Configure customer chart, tax templates, letterheads and naming. |
| CRM | 28 / 9 | `erpnext/crm/`: leads, prospects, opportunities, campaigns, contracts, appointments | Keep built-in ERP CRM intact. Do not imply this includes the separate Frappe CRM application. |
| Buying | 20 / 10 | `erpnext/buying/`: supplier, RFQ, quotations, purchase orders, scorecards | Keep procurement flow; configure terms and defaults. |
| Projects | 15 / 5 | `erpnext/projects/`: projects, tasks, timesheets, costing and templates | Keep native screens, task links and accounting integration. |
| Selling | 20 / 23 | `erpnext/selling/`: customer, quotation, sales order, bundles, pro forma invoice, sales teams | Keep familiar labels and document actions; change only brand-bearing shell. |
| Setup | 40 / 0 | `erpnext/setup/`: company, branch, employees, department, currency exchange, UOM, terms, territory and setup wizard | Product installer may apply approved defaults. Company identity and accounting settings remain customer configuration. |
| Manufacturing | 50 / 21 | `erpnext/manufacturing/`: BOM, production plan, work order, workstation, job card, planning and costing | Preserve core. Enable in customer blueprint only where required. |
| Stock | 76 / 52 | `erpnext/stock/`: item, warehouse, receipt/delivery, stock entry, reservation, serial/batch, valuation, inspection and landed cost | Preserve ledger and valuation behavior; test barcode/serial/batch and printing surfaces. |
| Support | 11 / 4 | `erpnext/support/`: issues, SLA, priority and warranty | Keep native support. The separate Frappe Helpdesk product is not automatically installed. |
| Utilities | 4 / 1 | `erpnext/utilities/`: portal user, rename tool, video/settings | Retain utility behavior and permissions; review external tutorial links as branding/support choices. |
| Assets | 26 / 3 | `erpnext/assets/`: asset, capitalization, depreciation, maintenance, repair, movement and location | Keep accounting/asset lifecycle unchanged. |
| Portal | 2 / 0 | `erpnext/portal/` plus `erpnext/www/`, templates, route hooks and controller | Brand customer/supplier views while retaining party-scoped access and native URLs. |
| Maintenance | 5 / 1 | `erpnext/maintenance/`: schedules and visits | Retain; source maps this to the Quality sidebar. |
| Regional | 5 / 4 | `erpnext/regional/`, chart templates, setup tax data | Treat country setup as a separate validated blueprint. Ethiopia-specific compliance remains an open qualification task. |
| ERPNext Integrations | 1 / 0 | `erpnext/erpnext_integrations/`: Plaid settings | Do not promise a full iPaaS from this module. Keep its native capability; external product integrations remain independently qualified. |
| Quality Management | 16 / 1 | `erpnext/quality_management/`: goals, procedures, reviews, feedback, actions and nonconformance | Preserve workflow; use native navigation. |
| Communication | 2 / 0 | `erpnext/communication/`: communication medium and timeslots | Preserve small configuration surface, grouped under Setup by hooks. |
| Telephony | 5 / 0 | `erpnext/telephony/`: call logs, voice settings, schedules/types | Keep optional; provider setup is not solved by a logo change. |
| Bulk Transaction | 2 / 0 | `erpnext/bulk_transaction/`: operation logs and details | Preserve authorization and background-job behavior. |
| Subcontracting | 13 / 3 | `erpnext/subcontracting/`: inward/outward orders and receipts | Preserve links to manufacturing/stock/accounting; appears under Manufacturing in hooks. |
| EDI | 2 / 0 | `erpnext/edi/`: code lists and common codes | Do not advertise an entire EDI integration platform merely because this module exists. Preserve native data model. |

The hooks explicitly group smaller modules under parent navigation areas through `code_only_modules`. Therefore the module count must not be used as a count of top-level navigation buttons.

## Navigation and visual surfaces actually found

This v16 snapshot uses more than the older Workspace records:

- `erpnext/dock/erpnext/erpnext.json`: the standard application dock. Setup, Accounts, Selling, Buying, Stock, Manufacturing, Projects, Assets, Quality and Portal are configured; CRM and Support entries exist with `hidden: 1`.
- `erpnext/workspace_sidebar/*.json`: 14 source sidebar files, including Selling, Buying, Stock, financial reports, invoicing and payments.
- `erpnext/desktop_icon/*.json`: 24 source icon records. `erpnext.json` carries the ERPNext name, upstream logo and app link.
- `erpnext/report_center/accounting.json`: accounting report navigation.
- Per-module `workspace/*/*.json`: 15 Workspaces with links, cards, charts and role restrictions.
- `erpnext/hooks.py`: `app_title`, publisher metadata, `app_logo_url`, `app_home`, `add_to_apps_screen`, JS/CSS bundles, website context, icon sheets, menu/route hooks.
- `erpnext/public/`: brand assets plus Desk, POS and web bundles; inspect actual runtime screenshots before selecting CSS overrides.

**Recommendation:** preserve the module names, document names, URLs and native ERP workflow. Change the product title, approved logo/favicon/splash, limited color tokens, help/support links, and relevant sign-in/about surfaces. Do not globally replace `erpnext` or `frappe` strings: they are package names, asset paths, DocType references and integration contracts. Keep public upstream attribution and source identity accurate.

The default source dock hides CRM/Support, but that is a navigation choice, not evidence the functionality is absent. Module visibility is also not an authorization boundary.

## Branding through configuration and one extension app

Frappe `v16.60.2` schemas confirm these configurable fields:

| Surface | Confirmed settings source | Configuration available |
|---|---|---|
| Global application identity | `frappe/core/doctype/system_settings/system_settings.json` | `default_app`, `otp_issuer_name`; legacy `app_name` exists but is hidden in this UI. Prefer Website Settings for visible application naming. |
| Application navbar | `frappe/core/doctype/navbar_settings/navbar_settings.json` | `app_logo`, settings/help menus, announcement widget |
| Website/login/portal | `frappe/website/doctype/website_settings/website_settings.json` | `app_name`, `app_logo`, favicon, splash, title prefix, theme, footer logo/powered text, navbar/footer templates, show footer on login |
| Printed commercial documents | `frappe/printing/doctype/letter_head/letter_head.json`; `print_settings/print_settings.json` | Header/footer image or HTML, custom CSS, default letterhead, print style, font, PDF size/generator and draft/cancelled policies |
| Welcome/password-reset emails | System Settings + `frappe/email/doctype/email_template/email_template.json` | Dedicated welcome/reset templates; footer controls; custom email templates |
| Customer commercial identity | `erpnext/setup/doctype/company/company.json` | Company logo, default letterhead, country, tax ID, currency, default accounts |
| Per-document printing | `erpnext/accounts/doctype/sales_invoice/sales_invoice.json` | Letterhead, print language and print heading |
| Workspaces | `frappe/desk/doctype/workspace/workspace.json` | Roles, label/title, content, links, cards, shortcuts, hidden/standard/private fields |
| New sidebars | `frappe/desk/doctype/workspace_sidebar/workspace_sidebar.json` | Source-managed app/module/items. Generic CRUD permission flags do not offer simple write/create, so use the supported customization/sync path after inspecting its implementation. |

Use a small `ibtinex_branding` app (name is a proposed implementation choice) for approved assets, CSS bundles, ownership-aware install/migrate defaults and bounded templates. Export the customizations that are actually supported, rather than editing installed site files manually.

Installation must be idempotent. An upgrade must not overwrite a customer's legal company name, company logo, chart of accounts, tax configuration, letterhead or email identity. Separate IBTINEX software branding from the customer's invoice/quotation branding. Default values may be initialized on a new site; subsequent changes require explicit ownership and drift handling.

Framework source root for those schema reads:
https://github.com/frappe/frappe/tree/2df0425571ebbaed878eabc3edc5b7e7c3327ae0

## Roles, reports and portal behavior to preserve

Sales Invoice's schema contains explicit permissions for Accounts Manager and Accounts User, plus permission-level rules. General Ledger's report metadata grants roles Accounts User, Accounts Manager and Auditor. The query/controller code has its own validation/filtering. Hiding a sidebar item does not replace these checks.

Sources:
- https://github.com/frappe/erpnext/blob/886ab6ae187244e7f1b852393384ab6019d56264/erpnext/accounts/doctype/sales_invoice/sales_invoice.json
- https://github.com/frappe/erpnext/blob/886ab6ae187244e7f1b852393384ab6019d56264/erpnext/accounts/report/general_ledger/general_ledger.json
- https://github.com/frappe/erpnext/blob/886ab6ae187244e7f1b852393384ab6019d56264/erpnext/accounts/report/general_ledger/general_ledger.py

Portal routing and menus are declared in `hooks.py`, including orders, invoices, quotations, shipments, purchase orders/invoices, supplier quotations, RFQs, projects and timesheets. `erpnext/controllers/website_list_for_contact.py` resolves portal users to Customers/Suppliers and deliberately returns a constrained row view instead of exposing full transactions with internal cost/margin fields.

Release checks must cover direct URLs, REST reads, report exports and portal customer-to-customer denial, not only screen visibility. Preserve these native safeguards in the branding app.

## Ethiopia qualification

Observed source facts:

1. `erpnext/setup/setup_wizard/data/country_wise_tax.json` contains an Ethiopia tax preset labelled VAT with rate 15. This is an upstream software default, **not a verification of current tax law or applicability**.
2. `erpnext/accounts/doctype/account/chart_of_accounts/unverified/et_l10n_et.json` is explicitly named “Ethiopia - Chart of Accounts”. Its placement is `unverified/`.
3. The audited `erpnext/regional/` tree has no dedicated Ethiopia implementation.
4. The audited `erpnext/locale/` list has no `am.po`. This does not prove no translation exists in other apps or external services, but it means a complete Amharic ERP user interface cannot be claimed from this core snapshot.

For a first review build, configure Ethiopia/ETB and appropriate timezone/date/number presentation using approved customer setup. Before customer release, qualify chart mapping, VAT/withholding rules and reporting, tax IDs, invoice numbering/content, fiscal periods, government reporting or fiscal-device integrations actually required by the target customer, Ethiopian-language input/search/PDF font rendering, banking/payment adapters and payroll where included. These are local accounting/legal/product qualification tasks; do not invent legal readiness from a country dropdown. Any localization logic should be its own versioned app/configuration profile instead of edits to accounting calculations.

Pinned sources:
- https://github.com/frappe/erpnext/blob/886ab6ae187244e7f1b852393384ab6019d56264/erpnext/accounts/doctype/account/chart_of_accounts/unverified/et_l10n_et.json
- https://github.com/frappe/erpnext/blob/886ab6ae187244e7f1b852393384ab6019d56264/erpnext/setup/setup_wizard/data/country_wise_tax.json
- https://github.com/frappe/erpnext/tree/886ab6ae187244e7f1b852393384ab6019d56264/erpnext/locale

## App boundaries

- Frappe Framework supplies Desk, document framework, core permissions/authentication, REST APIs, website and print infrastructure. A fork of ERPNext alone does not copy the whole runtime.
- ERPNext includes built-in CRM, Support and Employee master records, but the dedicated HR/payroll product is `frappe/hrms`. Its README says HR was separated from ERPNext from version 14 onward.
- `frappe/crm` is a separate product with its own frontend, compatibility branches and ERPNext integration.
- `frappe/webshop` is a separate ecommerce app integrated with ERPNext; do not assume a full storefront is bundled because `erpnext/shopping_cart/` compatibility files exist.
- Helpdesk, Learning, Insights, Payments and other optional ecosystem applications require their own scope, license/dependency review and compatibility qualification. Do not bundle them simply to claim more modules.

Primary source references inspected: https://github.com/frappe/hrms/blob/develop/README.md ; https://github.com/frappe/webshop/blob/develop/README.md ; https://github.com/frappe/crm (README of its default branch returned at inspection). These optional-app READMEs are identification evidence, not a pinned bill of materials.

## Representative acceptance flows for the branded release

These are **proposed tests, not observed passes**. Run on a synthetic isolated site at the locked image digest; record expected balances/statuses and compare with the same upstream baseline.

1. Fresh install: native company setup completes, selected customer blueprint applies once, all required installed-app versions are recorded, and a second provision run does not duplicate company or role data.
2. Branding: login, password reset, Desk/apps screen/dock, modal messages, light/dark modes, narrow viewport, portal, PDF and transactional emails show approved assets without broken layout or missing upstream notices.
3. Sales: Customer → Quotation → Sales Order → Delivery Note → Sales Invoice → Payment Entry. Check quantities, tax/rounding, GL/payment ledger, receivable report, return/cancellation/amendment and PDF.
4. Purchasing: Supplier → RFQ/Quotation → Purchase Order → Receipt → Purchase Invoice → Payment. Check stock, payable and accounting linkage.
5. Stock: receipt, transfer, delivery, reconciliation, serial/batch tracking, reservation and valuation report; verify permissions for a warehouse-restricted user.
6. Manufacturing (when selected): BOM → Work Order → Job Card/material issue → finished-goods receipt; verify consumption, costs, partial completion and cancellation behavior.
7. Assets/projects/support (when selected): asset depreciation schedule; project/task/timesheet billing; issue/SLA lifecycle. Verify each module's native roles.
8. Permissions: salesperson, stock clerk, accountant, approver, auditor, portal Customer A/B and administrator; verify denied direct reads, API calls, report export and cross-company access.
9. Documents: invoice/quotation/delivery note and reports, long multi-page print, customer letterhead retained, fonts and Amharic text input/rendering, CSV/XLSX exports.
10. Operational upgrade: install the branding app, perform a supported version migration, rebuild assets/clear caches, and verify a customer's edited letterhead and module settings survive. Restore a backup into a separate test environment to verify rollback beyond image replacement.

Native test sources inspected for scenario breadth include `erpnext/accounts/doctype/sales_invoice/test_sales_invoice.py`, `erpnext/selling/doctype/sales_order/test_sales_order.py`, `erpnext/stock/doctype/stock_entry/test_stock_entry.py`, and `erpnext/manufacturing/doctype/work_order/test_work_order.py`. They cover substantial posting, returns, currency/rounding, quantity, cancellation and dependency behavior; retaining and running appropriate upstream suites is more valuable than duplicating their business logic in branding-specific tests.

## Recommended first-release scope

The first IBTINEX ERPNext-derived release should be the qualified upstream ERPNext/Frappe pair plus one small branding app and a reproducible deployment profile. Include native functionality already in the selected ERPNext version; expose only the modules needed by the review/customer blueprint. Keep any branding-only fork diff easy to review and rebase. Add localization and other Frappe apps only as separately scoped, tested capabilities. Do not market the Windows demo as a completed deployment or this source inspection as release qualification.

## Framework and frontend coverage

The exact Frappe snapshot has 5,761 tracked files and 17 declared modules. The complete structural inventory is in `module_inventory.json`; deeper consumer and permission reads are documented in `SECURITY_AND_BRANDING_REVIEW.md`. The framework areas below are preserved by the first branding release.

| Framework area | Modules / source surfaces | Review boundary and release implication |
|---|---|---|
| Documents, identity and operations | Core, Users, System | Settings/authentication and permission consumers inspected. Preserve document framework and test restricted roles. |
| Desk and customization | Desk, Custom, Build | App metadata, navigation, customization and workspace consumers inspected. Keep schema and route identities. |
| Website and contacts | Website, Contacts, Geo | Login/website branding and portal sources inspected; geospatial services were inventoried, not externally connected or tested. |
| Communication and integration | Email, Integrations | Template, API, social login, webhook and job boundaries inspected. Test actual mail and provider configuration separately. |
| Workflow and data operations | Workflow, Automation, Data | Included in the schema/module inventory; retain native behavior. No automated trigger, import or bulk workflow was executed. |
| Documents and output | Printing | Settings/schema and runtime image support reviewed; actual font/PDF acceptance remains required. |
| Visual app builder | Studio; `studio/frontend`, `frappe/studio` | Entry documentation, package manifest and permission entry points inspected. The baseline README marks this as early development and not yet recommended for production. A core ERP branding release does not require building a replacement UI with Studio. |
| AI assistant | Flow; `flow`, `frappe/flow` | Entry documentation, package manifest, launcher and role/session permission surface inspected. The documentation describes an agent harness requiring process management and provider/model configuration. Source inclusion is not proof it is operational in the demo or qualified for customers. |
| Shared frontend and embedded applications | `ui`, ERPNext `banking`, `islands` | Package/build relationships and branding consumers inspected. Keep native assets and framework UI dependencies; exercise these screens in image acceptance. |

Sources: [framework modules](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/modules.txt), [shared UI](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/ui/README.md), [Studio entry documentation](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/studio/frontend/README.md), [Studio API permissions](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/studio/api.py), [Flow entry documentation](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/flow/README.md), [Flow permissions](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/flow/permissions.py), [Banking title/authentication context](https://github.com/frappe/erpnext/blob/886ab6ae187244e7f1b852393384ab6019d56264/erpnext/www/banking.py).

