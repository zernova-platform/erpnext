# IBTINEX ERP: branding, identity, and integration source review

Reviewed 2026-11-25. Read-only review; no application code or customer configuration was changed by this reviewer. The organization fork and live UI observations are recorded in README.md.

## Exact baseline and evidence boundary

- ERPNext `v16.60.0`, commit `886ab6ae187244e7f1b852393384ab6019d56264`.
- Frappe `v16.60.2`, commit `2df0425571ebbaed878eabc3edc5b7e7c3327ae0`.
- These match the Installed Applications screen observed in the running evaluation system. That screen reports `UNVERSIONED` for the image's Git branches; source tag correspondence is a reviewed baseline, not a measured image digest.
- This review inspected the named source consumers, schemas, and relevant upstream tests. It did not execute authentication, API, permission, migration, or rebranding tests, and is not a complete security audit of every source line.

Source links below use the exact audited commits. Local clones were checked against those commits.

## 1. Smallest reliable branding design

Use a very small presentation-only patch in the ERPNext fork plus an `ibtinex_branding` companion Frappe app for settings, assets/CSS, and deployment-owned configuration. Preserve Python app identity `erpnext`, DocType names, module names, document identifiers, routes, permissions, business logic, and upstream version numbers. Track the IBTINEX distribution/branding version separately.

### Why settings alone will not rename the ERP application tile

The exact Frappe version has several consumers of application metadata:

- `frappe/boot.py:get_app_data()` reads `add_to_apps_screen`, `app_title`, and `app_logo_url` **for each owning app**. Its `app_data` drives the Apps screen and app-specific dock.
- `frappe/apps.py:get_apps()` independently reads the owning app's `add_to_apps_screen` for application metadata and navigation/default-path logic.
- `frappe/utils/change_log.py:get_versions()` independently reads the owning app's title and logo for About/version information.
- `frappe/desk/doctype/workspace/workspace.py:mount_workspace()` returns a fresh `get_app_data()` payload. A boot-only mutation can therefore be replaced later.
- `frappe/public/js/frappe/utils/utils.js:get_apps_screen_apps()` and `app_logo()` consume this metadata for the switcher, app tile, and dock branding.

Adding an `add_to_apps_screen` entry to the companion app would create a second application instead of reliably changing the existing ERP entry. Changing the companion app's `app_title` does not override ERPNext's app-scoped metadata. Avoid runtime monkey-patching and duplicate/hidden-tile tricks.

**Recommended tiny fork patch:** in `erpnext/hooks.py`, set the display `app_title` to `IBTINEX ERP`, use the approved IBTINEX logo in `app_logo_url` and `add_to_apps_screen[0].logo`, and preserve `name=erpnext`, the existing route, permission function, and sequence. Keep assets referenced by this patch inside the fork so the ERP source remains internally coherent. Preserve upstream copyright/license notices and accurate attribution.

The legacy `erpnext/desktop_icon/erpnext.json` contains a display `label` and `logo_url`; update those only if that supported navigation mode remains in the release acceptance scope. Keep its document `name` as `ERPNext`: children refer to `parent_icon: ERPNext`. Keep the `Dock` document name and `app` as `erpnext`. Changing every occurrence of “ERPNext” would damage technical identifiers and attribution.

Sources: [ERP hooks](https://github.com/frappe/erpnext/blob/886ab6ae187244e7f1b852393384ab6019d56264/erpnext/hooks.py), [boot metadata](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/boot.py), [app metadata/default routes](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/apps.py), [version metadata](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/utils/change_log.py), [workspace refresh](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/desk/doctype/workspace/workspace.py), [client metadata consumers](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/public/js/frappe/utils/utils.js), [legacy root icon](https://github.com/frappe/erpnext/blob/886ab6ae187244e7f1b852393384ab6019d56264/erpnext/desktop_icon/erpnext.json).

### Configurable branding surfaces

| Surface | Exact source support | Planned implementation |
|---|---|---|
| Login application name and document title | Website Settings `app_name`; login and Desk context prefer it, then System Settings `app_name` | Set Website Settings `app_name=IBTINEX ERP` through an idempotent installer. System Settings `app_name` exists but is hidden in this version. |
| Global application/login logo | `get_app_logo()` prefers Website Settings `app_logo`, then Navbar Settings `app_logo`, then hook fallback | Explicitly set a deployment-owned website logo; do not depend on hook-order fallback after installing a third app. |
| Favicon and splash | Website Settings `favicon` and `splash_image` override fallback hook defaults | Use versioned approved assets and test cache refresh. |
| Light/dark accents | `app_include_css` for Desk, `web_include_css`/Website Theme for web surfaces | Small scoped stylesheet using existing layout/theme tokens; retain controls, spacing, responsiveness, error/status colors, keyboard navigation. |
| Help/support links | Navbar Settings help/settings tables and standard hook items | Add an IBTINEX support entry without breaking standard item synchronization. Verify which menus the new dock actually renders. |
| Email branding | `email_brand_image`, `default_mail_footer`, email CSS hooks, configured email templates | Override presentation via companion hooks/templates; inspect actual welcome/reset/report messages. Keep notices where required. |
| Portal/footer | Website Settings footer fields, `footer_powered`, website context and template selection | Use a deliberate IBTINEX presentation with truthful ERPNext/Frappe attribution. Avoid replacing business portal routes. |
| PDF/printed documents | Company/Letter Head/Print Format remain business configuration | The customer's company name/logo/address and document values remain theirs. IBTINEX product branding is separate from the trading entity on invoices. |
| About/diagnostics | Upstream app/package/version identities remain useful | Show distribution identity plus actual ERPNext/Frappe component versions; never falsify the upstream version to a marketing release number. |

`frappe/www/desk.html` contains hard-coded browser-theme meta colors. Leave these in the first light rebrand unless visual acceptance makes them necessary; do not fork or copy the entire Frappe page merely to recolor mobile browser chrome.

Sources: [website schema](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/website/doctype/website_settings/website_settings.json), [website settings precedence](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/website/doctype/website_settings/website_settings.py), [navbar/logo consumer](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/core/doctype/navbar_settings/navbar_settings.py), [system schema](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/core/doctype/system_settings/system_settings.json), [login context](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/www/login.py), [Desk context](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/www/desk.py), [Desk template](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/www/desk.html).

### Installer and upgrade rules

Maintain a versioned allowlist of product-owned settings and saved previous values. Fresh installation writes approved defaults after ERPNext installation. Reapplying a recipe must not create another app tile, duplicate help links, reset a company, create sample business transactions, or overwrite later engineer/customer customization. During upgrade, update a value only if it still equals the previous managed value, unless the engineer explicitly selects a reviewed replacement. Report drift instead of silently taking ownership.

Use supported app lifecycle hooks/patches, own fixtures, and schema checks. Validate that a target setting exists on the pinned version before updating it. Keep branding assets public and secrets in Password fields/secret provisioning. Do not export whole Single DocTypes or customer-owned tables as uncontrolled fixtures. Undo restores only the product-owned values that still match the values installed by the product. Database migration rollback still requires the matched backups specified by the release plan.

## 2. Keycloak: native support exists, full policy needs implementation

Frappe `v16.60.2` includes a built-in **Keycloak** Social Login Key provider. Its callback is `/api/method/frappe.integrations.oauth2_logins.login_via_keycloak`; default relative authorization, token, and userinfo paths are `/protocol/openid-connect/auth`, `/protocol/openid-connect/token`, and `/protocol/openid-connect/userinfo`. Configure the full realm base URL, client credentials, exact HTTPS redirect URI, and required claims. Its helper concatenates base URL plus relative path, so normalize trailing slashes deliberately.

The native Keycloak callback performs the authorization-code exchange and reads userinfo. It does not mean arbitrary Keycloak JWT bearer tokens are automatically accepted by ERP REST endpoints. Default REST bearer authentication uses Frappe's OAuth Bearer Token records; API key authentication is a separate mechanism.

Native social-login state is a generated single-use cache entry with a ten-minute expiry. However, user resolution uses the returned email, the stock email check accepts an email's presence rather than requiring `email_verified=true`, and Keycloak's default stored user-id property is `preferred_username`. For an enterprise recipe, require verified email and a controlled identity-binding policy. Prefer a stable subject identifier for binding and explicitly handle renamed/reassigned emails. These requirements are implementation and negative-test work, not properties established by adding the provider.

Provider `sign_ups=Deny` plus controlled provisioning is the simple initial policy. Stock auto-provisioning otherwise creates a Website User, not an ERP operator with approved business roles. `on_social_login(user, provider, claims)` is a supported hook that can refuse login or apply explicitly allowed role/profile assignments before session creation. Upstream tests exercise the hook, but we did not execute them here. Do not turn every Keycloak realm/group claim into an ERP administrative role. Test removal of a role and account deactivation, not only first-login assignment.

### Password-login exception needs care

`LoginManager.login()` checks the global `disable_user_pass_login` setting **before resolving the user**. There is no Administrator exception at that check. Enabling it indiscriminately would block the desired local administrator recovery path.

For the desired “Keycloak for ordinary users, local recovery administrator” policy, use a small, reviewed companion `before_login` policy that rejects normal password logins while allowing only the explicitly configured local recovery identity through the unchanged native authentication/MFA path. Keep the global flag consistent with that policy. A friendly login redirect is not enforcement; direct POST login must also be tested. Disable unused email-link/LDAP/other-provider channels, or explicitly include them in the approved policy. Keep recovery access limited to the management route/network and verify it before enforcing SSO.

Stock logout runs `on_logout`, deletes the Frappe session, and clears its cookies. This source path does not by itself establish Keycloak single logout, back-channel revocation, or immediate termination of an already active ERP session after disabling an identity in Keycloak. Define those behaviors and test them; use a supported extension for logout/revocation only if required.

Sources: [Keycloak provider](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/integrations/doctype/social_login_key/social_login_key.py), [provider schema](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/integrations/doctype/social_login_key/social_login_key.json), [callbacks](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/integrations/oauth2_logins.py), [OAuth state/user provisioning/hooks](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/utils/oauth.py), [password/API auth/logout](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/auth.py), [social-login tests](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/integrations/doctype/social_login_key/test_social_login_key.py).

## 3. API, jobs, webhooks, and files

Preserve the native REST/RPC APIs. `/api/resource` and `/api/method` remain supported, alongside versioned `/api/v1` and `/api/v2` routes. V1 document reads check read permission and apply field-level permissions; writes call normal document insert/save/delete and write checks. The RPC dispatcher requires whitelisted methods and allowed HTTP methods. Whitelisting does not prove an arbitrary custom method has the correct business authorization: any new integration endpoint must validate its own business permission boundary.

Use separately provisioned integration users with minimum roles and dedicated credentials. Keep them distinct from engineer/admin identities. Authentication to Keycloak for a human browser session does not itself grant API roles, nor does a token magically limit access to one requested product. Test negative read/write cases and cross-company restrictions using those real accounts.

Background jobs carry a site and user context; the worker uses that context. Correct queue execution, actual scheduler activity, email sending, report generation, and permissions inside custom jobs require runtime tests. A responding web server alone does not establish that these services work.

Webhook security can generate an HMAC-SHA256 header. The exact implementation also records URL, headers, request data, response body, and errors in Webhook Request Log. Therefore avoid putting credentials, activation requests, signed license material, or other secrets in webhook bodies/static headers that will be logged; configure a redacted or purpose-built integration path where necessary. ZEDAS report export must use an allowlist, not dump these logs.

File handling distinguishes public and private attachments and implements document/ownership checks. Verify protected file downloads, uploads, generated PDF files, report exports, and backups through the actual proxy configuration. Public asset paths for IBTINEX logos are appropriate; business attachments and site secrets are not branding assets.

Sources: [API routing](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/api/__init__.py), [V1 document API](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/api/v1.py), [RPC/upload handler](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/handler.py), [job context](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/utils/background_jobs.py), [webhook signing/logging](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/integrations/doctype/webhook/webhook.py), [file access](https://github.com/frappe/frappe/blob/2df0425571ebbaed878eabc3edc5b7e7c3327ae0/frappe/core/doctype/file/file.py).

## 4. Required acceptance checks for the implementation agent

1. Fresh site: install ERPNext then branding app; validate one ERP tile, correct display name/logo, preserved `erpnext` identity, expected dock entries and default route.
2. Existing demo clone: install branding twice; preserve company records, preferences, document values, customer letterheads, and permissions. Confirm no duplicates or unintended reset.
3. Exercise page refresh, app switcher, dock manager, workspace customization/remount, About/version view, setup wizard, portal login and error pages; the branding must not revert or duplicate across independent metadata consumers.
4. Compare native Selling/Buying/Stock/Accounts/POS workflows, print previews/PDFs and email samples before/after. Test light/dark appearance, keyboard focus and small viewports.
5. SSO: approved provisioned user succeeds; disabled user, denied signup, missing/unverified email, unapproved role and reused/invalid state fail. Test email/subject changes and role revocation deliberately.
6. Direct username/password login for a normal account fails; the approved recovery administrator still succeeds using native credentials/MFA through its management route. Test email-link, LDAP, other-provider and direct API paths against the chosen policy.
7. Test the stated logout/revocation behavior and document any retained ERP session lifetime. Do not advertise single logout until observed.
8. API least privilege: allowed read/write succeeds, prohibited document/field/company/file access fails; key rotation/revocation works. Preserve CSRF protection for browser sessions.
9. Scheduler, worker queues, prepared reports, email and signed webhook delivery succeed with realistic synthetic data; log/report exports contain no credentials or license material.
10. Branding migration and rollback preserve customized customer values. Verify the same behavior against a separately qualified upstream update before moving the stable baseline.

No claim is made here that these acceptance checks passed. They are the concrete test contract for the implementation/deployment phase.
