# Copyright (c) 2026, Globex Digital Solutions Pvt Ltd
# License: Proprietary

"""
HR Letter — one record per letter issued to an Employee or Job Applicant.

Lifecycle (status field; docstatus in parentheses):

  Draft (0) → [Generate] → Generated (0)
    → requires_signature: [Send for Signature] → Sent for Signature (1)
        → Zoho webhook → Signed (1)
    → else: [Issue] → Issued (1), emailed to recipient
  Cancel at any point → Cancelled

Regeneration is allowed while docstatus is 0 (Draft/Generated). After
submission, use Frappe-native cancel + amend.
"""
import json

import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

from globex_hr_letters.letters import engine


class HRLetter(Document):
    def validate(self):
        self._validate_letter_type()
        self._set_recipient_name()
        self._default_compensation_annual()

    def _validate_letter_type(self):
        lt = frappe.get_doc("Letter Type", self.letter_type)
        if not lt.is_active:
            frappe.throw(f"Letter Type '{lt.name}' is inactive.")
        if lt.recipient_kind != self.recipient_type:
            frappe.throw(
                f"Letter Type '{lt.name}' is addressed to a {lt.recipient_kind}, "
                f"but this letter's recipient is a {self.recipient_type}."
            )

    def _set_recipient_name(self):
        field = "employee_name" if self.recipient_type == "Employee" else "applicant_name"
        self.recipient_name = frappe.db.get_value(
            self.recipient_type, self.recipient, field
        ) or self.recipient

    def _default_compensation_annual(self):
        for row in (self.compensation or []):
            if row.monthly_amount and not row.annual_amount:
                row.annual_amount = row.monthly_amount * 12

    def before_submit(self):
        if self.status not in ("Generated", "Sent for Signature", "Issued"):
            frappe.throw("Generate the letter before submitting.")

    def on_cancel(self):
        self.db_set("status", "Cancelled")

    # ── whitelisted doc methods (called from the form via frm.call) ──────────

    @frappe.whitelist()
    def get_missing_placeholders(self) -> list:
        """Placeholders the generate dialog must prompt HR for."""
        return engine.get_missing_placeholders(self)

    @frappe.whitelist()
    def generate_letter(self, values=None) -> dict:
        """
        Render the letter (synchronous — HR sees the PDF immediately).
        *values* is the dict of prompt-filled placeholder values from the
        dialog; stored on filled_values for audit.
        """
        if self.docstatus != 0:
            frappe.throw("Cannot regenerate a submitted letter. Cancel and amend instead.")

        if values:
            if isinstance(values, str):
                values = json.loads(values)
            merged = {}
            existing = self.filled_values
            if existing:
                merged.update(existing if isinstance(existing, dict) else json.loads(existing))
            merged.update(values)
            self.db_set("filled_values", json.dumps(merged))
            self.reload()

        engine.generate(self)
        self.reload()
        return {"status": self.status, "generated_pdf": self.generated_pdf}

    @frappe.whitelist()
    def send_for_signature(self) -> dict:
        """Submit the letter and dispatch to Zoho Sign in the background."""
        self._require_generated()
        lt = frappe.get_doc("Letter Type", self.letter_type)
        if not lt.requires_signature:
            frappe.throw(
                f"Letter Type '{lt.name}' does not require a signature. Use Issue instead."
            )
        if self.docstatus == 0:
            self.submit()
        frappe.enqueue(
            "globex_hr_letters.letters.engine.dispatch_signature",
            queue="default",
            hr_letter_name=self.name,
        )
        return {"status": "enqueued"}

    @frappe.whitelist()
    def issue_letter(self) -> dict:
        """Submit the letter, mark Issued, and email it in the background."""
        self._require_generated()
        lt = frappe.get_doc("Letter Type", self.letter_type)
        if lt.requires_signature:
            frappe.throw(
                f"Letter Type '{lt.name}' requires a signature. Use Send for Signature."
            )
        if self.docstatus == 0:
            self.submit()
        self.db_set("status", "Issued")
        self.db_set("issued_on", now_datetime())
        self.db_set("issued_by", frappe.session.user)
        frappe.enqueue(
            "globex_hr_letters.letters.engine.deliver_issued_letter",
            queue="default",
            hr_letter_name=self.name,
        )
        return {"status": "Issued"}

    def _require_generated(self):
        if self.status not in ("Generated",):
            frappe.throw("Generate the letter first.")
