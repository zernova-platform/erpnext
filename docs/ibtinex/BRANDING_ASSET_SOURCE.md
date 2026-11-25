# IBTINEX icon source and adaptation

The two SVG files in this release are a portable adaptation of the **existing CSS mark shipped in IBTINEX Deployment Studio 0.3.0-dev.41**. They are not a newly designed identity, a recolored ERPNext/Frappe logo, or a claim that a separate approved production SVG master was supplied.

## Source artifact

| Item | Evidence |
|---|---|
| Existing artifact | `IBTINEX-Deployment-Studio-0.3.0-dev.41.vsix`, retrieved from the project's existing files |
| Artifact SHA-256 | `e58ba1d11dec104c2f8c2c87bafd53af3ac9beff4d785f5deeab6007b3c71e4d` |
| CSS inside the artifact | `extension/media/app.css` |
| CSS SHA-256 | `c89b80d872b4fdfc9d538b6edf9599de2060a6b7e39eabe0c7c5b67b9a0a1dd5` |
| Source selector | `body:not(.vscode-high-contrast):not(.vscode-high-contrast-light) .topbar .wordmark::before` |
| Source character | Uppercase `I` |
| Geometry | 27 × 27 px square, 7 px corner radius, centered character |
| Mark colors | Background `#d4f594`; character `#102b21` |
| Character styling | 16 px, inherited weight 700, letter spacing 0 |
| Inherited font stack | `Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif` |

The original CSS creates the mark with a centered pseudo-element. The SVG expresses the same mark using a rounded rectangle and centered SVG text, preserving the character, proportions, colors, weight, and font stack. No external font, remote image, script, or external resource reference is embedded.

The VSIX also contains Noto Sans fonts for its PDF reports. Those are **not** the font stack used by this CSS mark and were not used to invent a different fixed glyph. Because the original mark uses system font fallbacks, the exact shape of `I` can vary between operating systems. The SVG deliberately retains that behavior instead of asserting that an unspecified fallback glyph is a master logo.

## Packaged outputs

| Path | SHA-256 |
|---|---|
| `erpnext/public/images/ibtinex-logo.svg` | `e93e788c016926c3fe2f8bd26b0950ba9409492094d21e122fce99751446b3cd` |
| `erpnext/public/images/ibtinex-favicon.svg` | `e93e788c016926c3fe2f8bd26b0950ba9409492094d21e122fce99751446b3cd` |

The files intentionally contain the same square mark. The browser scales the favicon to its required size.

## Scope of this release

Only the main application icon and favicon/splash icon references change. ERPNext's black-and-white interface, CSS, colors outside the icon, layout, display title, document names, routes, email templates, letterheads, company records, and upstream attribution remain unchanged.

The ERPNext-owned Apps-screen hook and legacy root desktop icon reference the mark. Site initialization calls `erpnext.ibtinex_branding.apply()` explicitly to set otherwise stock/empty Website and Navbar icon settings. It preserves customer-owned settings and later edits. It is not an unconditional migration hook.

`erpnext.ibtinex_branding.restore()` restores only settings still owned by the recipe. Restoring the upstream UI completely also requires the previous image, because the IBTINEX fork retains its icon fallback references.

## Verification performed

- Parsed the packaged SVG and checked matching logo/favicon bytes, the source colors, geometry, character, font size and weight, and the absence of script/resource references.
- Ran the focused branding suite: **12 tests passed**, covering assets/metadata, repeat application, preservation of custom logo/favicon/splash values, preserving a Navbar logo when the Website logo is empty, rollback after a partial write failure, schema mismatch, corrupt ownership records, and undo after later customization.
- Rendered the logo at 270 px and the favicon at 16 px with Inkscape and visually inspected both. The rounded mark and character are visible without clipping. These previews use the executor's available font fallback; they do not establish identical pixels on every operating system.
- Inspected the pinned Frappe `v16.60.2` database APIs used by the helper: `get_single_value(..., cache=False, for_update=True)`, `set_single_value`, default-value storage, savepoints, and rollback are supported by that version. The focused tests use a database double; runtime behavior in a real site must also be checked by the image/deployment validation workflow.

No customer rollout or live-site branding mutation was performed as part of this asset adaptation.
