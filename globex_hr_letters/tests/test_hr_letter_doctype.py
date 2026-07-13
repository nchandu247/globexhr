"""
Offline guards for hr_letter.json schema invariants.

Same spirit as test_workspace_fixture.py: doctype JSON mistakes fail
silently on the site, so pin the load-bearing bits here.
"""
import json
import os

DOCTYPE_JSON = os.path.normpath(os.path.join(
    os.path.dirname(__file__), "..", "hr_letters", "doctype",
    "hr_letter", "hr_letter.json",
))


def _fields():
    with open(DOCTYPE_JSON) as f:
        return {fld["fieldname"]: fld for fld in json.load(f)["fields"]}


def test_amend_does_not_copy_stale_lifecycle_fields():
    """Cancel + amend is the sanctioned correction path. Without no_copy,
    the amended draft inherits status 'Cancelled' and a stale
    zoho_request_id — dispatch_signature's idempotency guard then silently
    skips, and the corrected letter can never be re-sent for signature."""
    fields = _fields()
    for fieldname in (
        "status", "zoho_request_id", "generated_pdf", "issued_on", "issued_by",
    ):
        assert fields[fieldname].get("no_copy") == 1, \
            f"{fieldname} must be no_copy=1 or amend copies a stale value"


def test_status_defaults_to_draft():
    """no_copy resets status to its default on amend — that default must
    exist and be Draft, or amended letters start stateless."""
    assert _fields()["status"].get("default") == "Draft"


def test_filled_values_stays_copyable():
    """Deliberate: amend keeps HR's typed prompt values so the corrected
    letter regenerates without re-typing the whole dialog."""
    assert not _fields()["filled_values"].get("no_copy")
