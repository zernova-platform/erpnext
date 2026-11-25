# IBTINEX starter company walkthrough

This review edition keeps ERPNext's native interface and changes its main icon
and favicon to the existing IBTINEX mark. The optional starter company is
**IBTINEX Starter Ethiopia** (`ISE`), a fictional workshop and service business
using ETB and the Africa/Addis_Ababa time zone.

Choose starter data when creating a fresh review installation. The same image
also supports an empty installation. The installer never adds the sample company
automatically to an existing business site.

## Explore the connected examples

Use the normal ERPNext workspaces and filter by the starter company where a
Company filter is available. Record names and descriptions identify the examples
with `ISE`, `Demo`, `Training`, or `Synthetic`.

| Workspace | Open these records | What to follow |
|---|---|---|
| Buying | Supplier, Material Request, Purchase Order, Purchase Receipt, Purchase Invoice | Follow the same raw materials from request through receipt and supplier payment. |
| Stock | Items, Warehouses, Stock Entry, Stock Ledger | Inspect the materials received, transferred into production, assembled, delivered, and moved into the showroom. |
| Manufacturing | BOM, Work Order, Job Card | Follow a training desk from its component list through a completed manufacturing example. |
| CRM | Lead, Opportunity, Campaign, Quotation | Review the prospective customer's request and its quotation. Campaigns do not send mail. |
| Selling | Sales Order, Delivery Note, Sales Invoice | Follow the completed sale and customer payment; a second order remains open for a guided exercise. |
| Accounting | Journal Entry, Payment Entry, Bank Transaction, General Ledger | Inspect opening balances, posted purchases and sales, payments, and a synthetic bank statement transaction. |
| Point of Sale | POS Profile | Open the prepared showroom profile for a deliberate POS session. A cash shift is not invented. |
| Projects | Project, Task, Timesheet | Review the customer installation project, dependent tasks, and recorded work. |
| Assets | Asset Category, Asset, Asset Depreciation Schedule | Inspect the workshop equipment and its depreciation setup. |
| Support and Maintenance | Issue, Communication, Maintenance Schedule, Maintenance Visit | Follow a training support request and the related service examples. |
| Quality | Quality Procedure, Quality Goal, Quality Review | Inspect the workshop's sample quality process and review. |
| Subcontracting | Subcontracting BOM, Purchase Order, Subcontracting Order | Review the linked outside-assembly order; remaining processing is identified in the coverage report. |
| Setup and Portal | Company, Employee, Address, Contact, Customer portal users | Inspect the fictional organization's setup and customer linkage. The sample portal account is disabled. |
| Communication, Telephony and EDI | Communication Medium, Call Log, Code List, Common Code | Inspect local examples. No live call, message, bank synchronization, or EDI transmission is performed. |

The installation's generated coverage report is the authority for which exact
records were created, supplied by native setup, generated through a parent
document, or deliberately left unseeded. A module being covered does not mean
every feature variant or every technical table has a synthetic record.

## Check the installed result

The packaged qualification command checks native versions, linked documents,
stock quantities, posted ledger balance, settled invoice balances, and the
absence of outbound integrations. Repeating the installer verifies the existing
starter instead of recreating its records.

The image build also tests a separate blank site, rejection of missing consent
and the wrong site name, serving the icon assets, and execution of a real queued
background job. Only the observed build evidence establishes which checks passed
for a particular image digest.

## Keep the review useful

The company, people, addresses, products, and transactions are fictional. The
chart and illustrative training tax are starter examples; customer configuration
is a separate installation choice. Payroll and other separately installed Frappe
applications are outside this ERPNext image.

To return to the starting point, create another isolated review installation
from the same image and starter option. Keep an edited review installation if
you want to preserve your exploration; the seed does not overwrite those edits.

For removal and rollback, use the scoped procedures in the deployment package.
Do not remove another Compose project's containers or volumes.
