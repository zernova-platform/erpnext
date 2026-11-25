"""Recognize completed starter installation without revalidating user-edited stock."""
import json

def completed_starter(db, *, marker_key, seed_version, company):
    raw = db.get_global(marker_key)
    if not raw:
        return None
    try:
        manifest = json.loads(raw)
        reference = manifest['records']['company']
        compatible = (manifest['status'] == 'installed'
                      and manifest['seed_version'] == seed_version
                      and manifest['company'] == company
                      and manifest['verification']['status'] == 'passed'
                      and reference['doctype'] == 'Company'
                      and reference['name'] == company)
    except (ValueError, TypeError, KeyError):
        compatible = False
    if not compatible or not db.exists('Company', company):
        raise RuntimeError('The completed starter marker or its company is incompatible; no reseeding was attempted.')
    return {'status': 'already-present', 'seed_version': seed_version, 'company': company}
