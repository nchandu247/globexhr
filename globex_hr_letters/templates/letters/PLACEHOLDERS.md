# Authoring Letter Templates — Placeholder Guide

Two kinds of templates exist:

1. **Shipped HTML templates** (`html/*.html`) — developer-maintained,
   pixel-perfect, extend `_base.html`. Edit in code, not in the UI.
2. **HR-authored DOCX templates** — upload a Word file with
   `{{ placeholder }}` variables on a Letter Type with render engine
   **DOCX**. This guide is mainly for those.

## How values are filled (in order)

1. **Recipient fields** — any Employee (or Job Applicant) fieldname works as
   a placeholder: `{{ employee_name }}`, `{{ designation }}`,
   `{{ date_of_joining }}`, `{{ branch }}`, ... Dates come pre-formatted
   ("01 June 2026"), amounts in Indian comma style ("6,00,000", no ₹ — add
   `₹` in the template where wanted).
2. **Company / letterhead fields** — from HR Letters Settings:
   `{{ company_name }}`, `{{ company_address }}`, `{{ company_phone }}`,
   `{{ company_email }}`, `{{ company_website }}`,
   `{{ signatory_name }}`, `{{ signatory_designation }}`.
3. **Compensation table** — when the Letter Type has "Uses Compensation
   Table" checked, the HR Letter's breakup rows are available as a loop plus
   totals:

   ```
   {% for row in compensation %}
   {{ row.component }}  {{ row.monthly }}  {{ row.annual }}
   {% endfor %}
   Gross: {{ gross_monthly }} / {{ gross_annual }}
   CTC:   {{ monthly_ctc }} / {{ annual_ctc }}
   ```

4. **Always available** — `{{ ref_number }}` (HR Letter ID),
   `{{ letter_date }}`, `{{ current_date }}`, `{{ recipient_name }}`,
   and for Employees `{{ employee_id }}`, `{{ tenure }}`,
   `{{ last_working_day }}` (when a relieving date is set).
5. **Anything else** — prompted to HR in a dialog when clicking Generate.
   Name placeholders in snake_case (`{{ effective_date }}`,
   `{{ warning_reason }}`) — the dialog label is derived from the name.

**A placeholder that ends up with no value is a hard error** — the letter
never renders with silent blanks.

## Signature letters (DOCX)

For Letter Types with "Requires Signature", the rendered DOCX is uploaded to
Zoho Sign (Zoho converts it to PDF — LibreOffice is not needed). Signature
fields are auto-placed via invisible text tags `{{S:R1*}}` (company signer)
and `{{S:R2*}}` (recipient) that the system appends to the document
automatically — you do not need to add them to your DOCX.

## Old MailMerge templates

Legacy `«Field»` MailMerge placeholders are not supported — convert them to
`{{ snake_case }}` Jinja variables before uploading.
