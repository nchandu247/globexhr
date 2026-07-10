# Copyright (c) 2026, Globex Digital Solutions Pvt Ltd
# License: Proprietary

import os

import frappe
from frappe.model.document import Document


class LetterType(Document):
    def validate(self):
        self._validate_template()

    def _validate_template(self):
        """Fail fast on a broken template reference so HR sees the error at
        save time, not at first letter generation."""
        if self.render_engine == "HTML":
            if not self.html_template:
                frappe.throw("HTML Template File is required for the HTML render engine.")
            from globex_hr_letters.letters.merger import html_template_exists
            if not html_template_exists(self.html_template):
                frappe.throw(
                    f"HTML template not found: {self.html_template}. "
                    "It must exist under templates/letters/html/ in the app."
                )
        elif self.render_engine == "DOCX":
            if not self.template:
                frappe.throw("DOCX Template attachment is required for the DOCX render engine.")
            ext = os.path.splitext(self.template)[1].lower()
            if ext != ".docx":
                frappe.throw(f"DOCX Template must be a .docx file, got '{ext}'.")
