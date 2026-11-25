# CODEX IMPLEMENTATION TASK
## IBTINEX ERP v0.1.1 — Complete Visual Rebranding and Windows Deployment

### Mission

Implement and release the next version of **IBTINEX ERP**, built on our existing ERPNext fork.

This is an implementation assignment, not a request to produce another proposal. Inspect the repository, implement the changes, test them, build the Docker image, publish a verified release, and produce a working Windows installer.

**Critical restriction: Change the appearance, not the business functionality.**

### 1. Existing project

GitHub repository: `https://github.com/zernova-platform/erpnext`

Current implementation branch: `ibtinex/starter-0.1.0`

Also inspect the existing `ibtinex/rebrand-plan-v16.60.0` branch for relevant work, but do not blindly merge outdated code.

Baseline versions:
- ERPNext 16.60.0
- Frappe 16.60.2
- Existing private GHCR image: `ghcr.io/zernova-platform/ibtinex-erpnext`
- Current published candidate: `0.1.0-rc.1-g28e3808696bf`

The existing release contains the IBTINEX icon/favicon and an optional fictional Ethiopian starter company. Its integration tests, native workflows, and Docker packaging have already been developed.

**Preserve all existing working implementation.**

Create a dedicated branch named `feat/ibtinex-erp-v0.1.1-branding` from the latest suitable tested implementation commit.

### 2. Branding rules

The application name is **IBTINEX ERP**.

The provided screenshot of the ZERNOVA website is the visual reference, not the product identity.

- Do not display the ZERNOVA name or logo in the ERP UI.
- Do not introduce a different product name.
- Reuse the approved IBTINEX identity and existing "I" icon.
- Maintain required ERPNext/Frappe license notices and legally required attribution.
- Do not invent a new corporate logo.

The desired appearance is professional, understated, simple, calming, and highly readable.

### 3. Color palette

Use these starting design tokens, refining only as needed for accessible contrast.

| Token | Color | Purpose |
|---|---|---|
| Deep green | `#102B21` | Main brand, navigation |
| Secondary green | `#1C332A` | Navigation hover, selected dark surfaces |
| Soft off-white | `#F4F5EF` | Main page background |
| White | `#FFFFFF` | Forms, cards, tables |
| Soft green-gray | `#EDEFE7` | Secondary surfaces |
| Lime accent | `#D4F594` | Primary accents, selected controls |
| Dark text | `#1B241F` | Main body text |
| Muted border | `#C9D1C7` | Dividers and borders |

The screenshot's most important visual relationship is **dark green + comfortable off-white + restrained light-green accents**.

Do not convert the ERP into a predominantly dark application.

The default should be a comfortable light working environment, with dark-green navigation and carefully applied accent colors.

If the existing ERPNext version supports dark mode, preserve and style it appropriately.

### 4. Design principles

Preserve ERPNext's native design philosophy.

The resulting application should feel like a polished branded ERPNext installation, not an unrelated custom dashboard.

Requirements:
- Maintain existing page layout and navigation structure.
- Keep normal forms, lists, tables, reports, and workflows familiar.
- Prefer subtle surfaces and borders over large shadows.
- Use accent green sparingly.
- Avoid saturated green backgrounds behind large amounts of text.
- Avoid excessive gradients, animations, glass effects, and decorative graphics.
- Preserve readable font sizes and visual hierarchy.
- Avoid introducing new layout frameworks.
- Keep desktop, tablet, and mobile responsiveness.
- Respect keyboard navigation and reduced-motion preferences.

Meet WCAG 2.2 AA contrast requirements wherever applicable. Ensure semantic success, warning, danger, and informational states remain distinguishable; do not make every status green.

### 5. Pages and components to update

Apply a consistent visual system to all appropriate native ERPNext UI areas.

**A. Login and authentication**

Update logo presentation, background, login card, labels, fields, focus states, primary button, links, and feedback messages.

Keep authentication behavior exactly the same.

**B. Main application shell**

Update the header, navigation, workspace sidebar, application logo, active navigation indicators, search presentation, breadcrumbs, menus, and dropdown surfaces.

Keep the existing navigation structure and behavior.

**C. ERP workspaces**

Update card backgrounds, section headings, shortcuts, charts' surrounding surfaces, link accents, and workspace action buttons.

Preserve workspace configuration, destinations, charts, and data.

**D. Forms and records**

Update field borders, focus rings, section separators, buttons, tabs, record headers, validation appearance, and dialogs.

Do not modify validation logic, field requirements, document transitions, or permissions.

**E. Lists, tables, and reports**

Improve header surfaces, row-hover states, selected rows, filters, pagination, status chips, and action controls.

Preserve sorting, filtering, exports, report calculations, and table behavior.

**F. Other native interfaces**

Review Kanban, Calendar, dashboards, notifications, settings, file attachments, portal pages, mobile menus, and print preview.

Apply only appropriate visual changes without disrupting their original behavior.

### 6. Technical implementation

First inspect the actual branding and frontend architecture in the repository.

Important existing file:

`erpnext/ibtinex_branding.py`

Current branding assets include:

`erpnext/public/images/ibtinex-logo.svg`

The current branding implementation manages selected logo and favicon settings while preserving user customizations.

**Extend the existing solution where appropriate instead of building a duplicate branding system.**

Use Frappe's supported theme, CSS, asset, and hook mechanisms where available.

Implementation requirements:

1. Introduce centralized semantic CSS tokens.
2. Keep brand styling isolated and maintainable.
3. Avoid invasive overrides of upstream frontend code.
4. Avoid brittle selectors dependent on generated class names.
5. Avoid broad `!important` overrides.
6. Do not create another Frappe application unless a verified technical requirement makes one necessary.
7. Ensure CSS is compiled and included in the Docker image.
8. Ensure login and authenticated Desk pages both receive the required styling.
9. Avoid changing print output or official business documents unless explicitly required to correct a visual regression.
10. Preserve existing customer-selected logos and other user-managed settings.
11. Retain full ERPNext/Frappe upgrade compatibility as far as reasonably possible.

### 7. Strict functional protection

Do not change:

- ERPNext business logic
- Frappe business logic
- DocType schemas
- Database structure
- APIs and integration contracts
- Authentication and permissions
- Accounting calculations
- Stock transactions
- Sales or purchasing behavior
- Manufacturing logic
- Workflow transitions
- Report formulas
- Existing starter data
- Background jobs
- Existing external integration configuration

No functional customization is authorized by this task.

If a functional modification appears necessary, document the issue and avoid making the change without clear justification and explicit scope approval.

### 8. Fix the Windows installation experience

The user has successfully installed and accessed the previous image on Windows using Docker Desktop.

However, the original installation encountered MariaDB authentication and incomplete-site recovery failures.

Inspect and reproduce those failures. In particular, examine how Python creates the `.secrets` password files on Windows and how MariaDB and Frappe read them.

Correct the root cause. Do not simply hide errors.

Ensure:
- Windows password files use consistent bytes without unexpected CRLF characters.
- The generated site and database credentials agree.
- Repeated installation commands do not corrupt partially completed installations.
- Failed setup produces actionable errors.
- Secrets are never printed to logs.
- Database volumes are never silently deleted.
- The installer detects existing installations.
- Installation is idempotent where safe.
- Recovery paths do not overwrite existing business data.
- Existing Docker projects remain untouched.

### 9. Support both fresh installs and upgrades

The new release must support two distinct situations.

**Fresh installation**

A customer should be able to download a ZIP installer, log into GHCR, and install the application on Docker Desktop.

Provide clear commands from the extracted installer folder.

**Upgrade of the existing installation**

This is equally important.

The user already has a running IBTINEX ERP installation with persistent volumes.

Provide a safe, tested upgrade process that replaces the application image and applies the new visual assets while preserving:

- Database contents
- Site configuration
- Existing passwords
- Company records
- Customer-entered transactions
- ERP settings
- Docker volumes

Implement a dedicated upgrade path in the installer, preferably an explicit `upgrade` command with validation, backup guidance, and rollback support.

Do not require creating a brand-new site to receive the theme.

An image-only rollback must not be described as sufficient unless the exact version and data compatibility have been verified.

### 10. Testing requirements

Run the existing regression suites and introduce focused branding tests.

Verify the following:

**Visual checks**
- Login page
- Desk homepage
- Workspaces
- Sales form
- Purchase form
- Accounting report
- List view
- Dialogs
- Mobile responsive navigation
- Light and existing dark modes

Capture before-and-after screenshots at representative desktop and mobile viewport sizes.

**Accessibility**
- Text contrast
- Button contrast
- Focus visibility
- Keyboard navigation
- Error and success states
- Zoom and text scaling
- Reduced-motion behavior

**Functional regression**
- Administrator login
- Existing user permissions
- Company lookup
- Opening and saving native ERP documents
- Form validation
- Lists, filters, and reports
- Existing seeded transactions and ledger invariants
- Background job processing
- API access
- Container restart persistence

**Windows deployment**
- Fresh installation from ZIP
- Consistent password-file formatting
- Successful MariaDB and ERPNext initialization
- Existing-site restart
- Failure recovery
- Upgrade preserving data
- Rollback of the visual release

Do not report Windows testing as passed if it was only tested on a Linux GitHub Actions runner.

### 11. Docker release

Target release:

**IBTINEX ERP v0.1.1**

Publish a release candidate first.

Build the application using the established GitHub Actions pipeline and matching source versions.

Required release properties:
- Private GHCR image
- Immutable SHA-256 digest
- Reproducible source reference
- Versioned release manifest
- Updated installer ZIP
- No secrets in published artifacts
- License notices retained
- Successful automated qualification before release

Use the existing repository's release workflow as the starting point and extend its branch targeting as required.

Do not overwrite the previous tested image tag.

Do not call the new release production-ready unless the required release gates have actually passed.

### 12. Windows installation documentation

Provide a short, beginner-friendly Windows guide in addition to technical documentation.

Assume the user has:
- Windows
- Docker Desktop
- Python
- CMD
- GitHub Container Registry credentials

Include:
1. Download installer.
2. Extract ZIP.
3. Open CMD in the extracted folder.
4. Log in to GHCR with GitHub username and PAT.
5. Start a fresh ERP installation.
6. Open the local URL.
7. Retrieve the generated Administrator password.
8. Stop and restart ERP safely.
9. Upgrade an existing ERP installation without losing data.
10. Troubleshoot common installation errors.

Use actual commands tested against the finished installer.

The existing working directory convention is:

`C:\work-space\IBTINEX-ERP\ibtinex-erp-review-installer`

Do not assume `deploy.py` is in its parent folder.

Document how to identify the user's actual installation directory, Compose project, and published port rather than assuming only the default values.

### 13. Final deliverables

Deliver:

1. Completed code on a dedicated GitHub branch.
2. Pull request with a change summary.
3. Updated IBTINEX branding assets and styles.
4. Before/after UI screenshots.
5. Functional and accessibility test results.
6. Fixed Windows installer.
7. Verified Docker image and immutable digest.
8. Downloadable installer ZIP.
9. Fresh-install instructions.
10. Existing-installation upgrade instructions.
11. Rollback procedure.
12. List of tests that could not be executed or passed.

### 14. Acceptance criteria

The work is complete only when:

- The product visibly says **IBTINEX ERP**.
- The visual language matches the supplied reference's calm dark-green/off-white style.
- The application remains recognizable as native ERPNext.
- The original workflows behave exactly as before.
- Branding works consistently across important UI areas.
- The release has passed its required tests.
- A fresh Windows installation works without manual password repair.
- An existing Windows installation can receive the updated theme without losing business data.
- The user receives simple commands to install and upgrade the Docker image.

**Proceed through implementation, verification, GitHub delivery, and packaging. Do not stop after writing a design proposal. Report any genuinely blocked release gate rather than claiming an unverified success.**