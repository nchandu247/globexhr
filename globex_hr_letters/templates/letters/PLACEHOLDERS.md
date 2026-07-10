# DOCX Template Placeholders — Offer Letter

The HR offer-letter template already uses `{{ variable }}` for most fields.
Some old MailMerge `«field»` style placeholders still remain and must be
converted to `{{ }}` before the merger will fill them.

> **All numbers are bare** (e.g. `6,00,000`) with **no `₹` symbol**.
> Add `₹` in the Word template where you want it, e.g. `₹ {{ annual_ctc }}`.
> Numbers are formatted in Indian comma style (`6,00,000`, not `600,000`).

---

## 1. Fix these typos / old placeholders in `offer_letter.docx`

| Current (in your DOCX) | Replace with | Notes |
|---|---|---|
| `«Band»` | `{{ band }}` | new — comes from Job Offer `custom_band` |
| `«Basic_YTD»` | `{{ basic_annual }}` | annual = monthly × 12 |
| `«HRA_YTD»` | `{{ hra_annual }}` | |
| `«Conveyance_Allowance_YTD»` | `{{ conveyance_annual }}` | |
| `«Medical_Allowance_YTD»` | `{{ medical_allowance_annual }}` | |
| `«Special_Allowance_YTD»` | `{{ special_allowance_annual }}` | |
| `«Monthly_Gross»` | `{{ gross_monthly }}` | Total Earnings (A) — monthly |
| `«Monthly_Gross_YTD»` | `{{ gross_annual }}` | Total Earnings (A) — annual |
| `«Provident_Fund_YTD»` | `{{ employee_pf_annual }}` | |
| `«ESI_YTD»` | `{{ employee_esi_annual }}` | |
| `«Professional_Tax_YTD»` | `{{ professional_tax_annual }}` | |
| `«Decutions»` | `{{ total_deductions_monthly }}` | Total Deductions (B) — monthly |
| `«Decutions_YTD»` | `{{ total_deductions_annual }}` | Total Deductions (B) — annual |
| `«Employer_PF_YTD»` | `{{ employer_pf_annual }}` | |
| `«Medical_Insurance_YTD»` | `{{ employer_esi_annual }}` | ESI / Medical Insurance Benefits — annual |
| `«Employer_Deductions_YTD»` | `{{ employer_deductions_annual }}` | Total Deduction (C) — annual |
| `«Net_Salary»` | `{{ net_take_home }}` | Net Salary (A−B) — monthly |
| `«Net_Salary_YTD»` | `{{ net_take_home_annual }}` | Net Salary (A−B) — annual |
| `«Annual_CTC_YTD»` | `{{ annual_ctc }}` | Annual CTC (A+C) |
| `«Current_Date»` | `{{ current_date }}` | today's date when letter is generated |

## 2. Fix this typo

On page 5 of the PDF the template shows `{{ candidate_name }` (missing one `}`).
Fix it to `{{ candidate_name }}` (with both closing braces).

---

## 3. Complete placeholder reference

### Header / addressing

| Placeholder | Example | Source |
|---|---|---|
| `{{ ref_number }}` | OFR-2025-0042 | Job Offer name |
| `{{ offer_date }}` | 01 June 2025 | Job Offer `offer_date` |
| `{{ current_date }}` | 20 May 2026 | today's date at generation |
| `{{ candidate_name }}` | Ramesh Kumar | Job Offer `applicant_name` |
| `{{ candidate_email }}` | ramesh@example.com | Job Applicant `email_id` |
| `{{ candidate_mobile }}` | +91 98765 43210 | Job Applicant `phone_number` |
| `{{ candidate_address }}` | Hyderabad, India | Job Applicant `country` / `custom_address` |
| `{{ designation }}` | Software Engineer | Job Offer `designation` |
| `{{ department }}` | Engineering | Job Offer `department` |
| `{{ band }}` | B3 | Job Offer `custom_band` |
| `{{ date_of_joining }}` | 16 June 2025 | Job Offer `custom_date_of_joining` |
| `{{ acceptance_deadline }}` | 10 June 2025 | Job Offer `custom_acceptance_deadline` |

### Offer terms

| Placeholder | Example | Source | Default |
|---|---|---|---|
| `{{ work_location }}` | Hyderabad | Job Offer `custom_work_location` | "Hyderabad" |
| `{{ reporting_to }}` | Priya Sharma | Job Offer `custom_reporting_to` (Link → Employee) | empty |
| `{{ probation_period }}` | 6 months | Job Offer `custom_probation_period` | "6 months" |
| `{{ notice_period }}` | 60 days | Job Offer `custom_notice_period` | "60 days" |
| `{{ joining_bonus }}` | 50,000 | Job Offer `custom_joining_bonus` | 0 |
| `{{ variable_pay_annual }}` | 1,00,000 | Job Offer `custom_variable_pay_annual` | 0 |

### CTC summary (page 2)

| Placeholder | Example |
|---|---|
| `{{ annual_ctc }}` | 6,00,000 |
| `{{ monthly_ctc }}` | 50,000 |
| `{{ gross_monthly }}` | 43,200 |
| `{{ gross_annual }}` | 5,18,400 |
| `{{ net_take_home }}` | 40,784 |
| `{{ net_take_home_annual }}` | 4,89,408 |

### Annexure A — Earnings (page 4 table)

| Placeholder (Monthly) | Placeholder (Annually) |
|---|---|
| `{{ basic_monthly }}` | `{{ basic_annual }}` |
| `{{ hra_monthly }}` | `{{ hra_annual }}` |
| `{{ conveyance_monthly }}` | `{{ conveyance_annual }}` |
| `{{ medical_allowance_monthly }}` | `{{ medical_allowance_annual }}` |
| `{{ special_allowance_monthly }}` | `{{ special_allowance_annual }}` |
| `{{ gross_monthly }}` (Total Earnings A) | `{{ gross_annual }}` |

### Annexure A — Employee Deductions

| Placeholder (Monthly) | Placeholder (Annually) |
|---|---|
| `{{ employee_pf_monthly }}` | `{{ employee_pf_annual }}` |
| `{{ employee_esi_monthly }}` | `{{ employee_esi_annual }}` |
| `{{ professional_tax_monthly }}` | `{{ professional_tax_annual }}` |
| `{{ total_deductions_monthly }}` (Total B) | `{{ total_deductions_annual }}` |

### Annexure A — Employer Deductions

| Placeholder (Monthly) | Placeholder (Annually) |
|---|---|
| `{{ employer_pf_monthly }}` | `{{ employer_pf_annual }}` |
| `{{ employer_esi_monthly }}` | `{{ employer_esi_annual }}` |
| `{{ medical_insurance_monthly }}` | `{{ medical_insurance_annual }}` |
| _(no monthly cell shown in template)_ | `{{ employer_deductions_annual }}` (Total C) |

### Optional conditional blocks

Use these in Word to hide rows that don't apply:

```
{% if not esi_applies %}
ESI / Medical Insurance Benefits: {{ employer_esi_monthly }}
{% endif %}

{% if not pf_opted_out %}
Provident Fund: {{ employee_pf_monthly }}
{% endif %}

{% if has_joining_bonus %}
Joining Bonus: {{ joining_bonus }} (one-time, payable with first salary).
{% endif %}

{% if has_variable_pay %}
Performance-linked variable pay: {{ variable_pay_annual }} per annum.
{% endif %}
```

---

## 4. Custom fields on Job Offer (auto-installed)

These 8 fields are defined in `globex_hr_letters/fixtures/custom_field.json`
and get created automatically when you run `bench migrate`:

| Fieldname | Label | Type | Default |
|---|---|---|---|
| `custom_band` | Band | Data | — |
| `custom_work_location` | Work Location | Data | "Hyderabad" |
| `custom_reporting_to` | Reporting To | Link → Employee | — |
| `custom_probation_period` | Probation Period | Data | "6 months" |
| `custom_notice_period` | Notice Period | Data | "60 days" |
| `custom_joining_bonus` | Joining Bonus | Currency | — |
| `custom_variable_pay_annual` | Variable Pay (Annual) | Currency | — |
| `custom_acceptance_deadline` | Acceptance Deadline | Date | — |

To install on the live site:
```bash
bench --site hr-globexdigital migrate
```

If you add more custom fields via the UI later, export with:
```bash
bench --site hr-globexdigital export-fixtures --app globex_hr_letters
```
(`hooks.py` is already configured to capture `custom_*` fields on Job Offer,
Employee, and Salary Structure Assignment.)

---

## Other letter templates (still to be built)

| Filename | Source DOCX | DocType |
|---|---|---|
| `consultant_offer_letter.docx` | Consultant Offer Letter format_ Template.docx | Job Offer |
| `intern_offer_letter.docx` | Globex Digital Solutions _ Intern Offer Template.docx | Job Offer |
| `increment_letter.docx` | Globex Digital Solutions _ Template _ Apprisal Letter.docx | Salary Structure Assignment |
| `promotion_letter.docx` | Globex Digital Solutions _ Template _ Promotion Letter.docx | Employee |
| `experience_letter.docx` | Globex Digital Solutions _ Template _ Experience Letter.docx | Employee Separation |
| `relieving_letter.docx` | Globex Digital Solutions _ Template _ Relieveing Letter.docx | Employee Separation |
| `service_certificate.docx` | Globex Digital Solutions _ Service CertificateLetter _ template.docx | Employee |

---

## How to prepare the offer letter template

1. Open `templates/Globex Digital Solutions _ Template _ Offer Letter.docx` in Word
2. Apply all the `«…»` → `{{ }}` substitutions from Section 1 above
3. Fix the `{{ candidate_name }` typo on page 5
4. Save-As to `globex_hr_letters/templates/letters/offer_letter.docx`
5. Test by submitting a Job Offer in Frappe — a PDF will be generated and sent to Zoho Sign
