"""
One-shot: convert the HR-approved offer-letter DOCX into a merger-ready template.

Reads:  templates/Globex Digital Solutions _ Template _ Offer Letter.docx
Writes: greythr_bridge/templates/letters/offer_letter.docx

What it does:
  1. Replaces every old MailMerge `«FieldName»` with `{{ jinja_variable }}`
  2. Fixes the `{{ candidate_name }` typo (missing closing brace) on page 5
  3. Preserves all original formatting, logo, fonts, tables, header/footer

Run from repo root:
    python scripts/build_offer_template.py
"""
import os
import sys

from docx import Document


# ── Substitution map (old → new) ─────────────────────────────────────────────
REPLACEMENTS = {
    # Annexure A table — old MailMerge fields
    "«Band»":                       "{{ band }}",
    "«Basic_YTD»":                  "{{ basic_annual }}",
    "«HRA_YTD»":                    "{{ hra_annual }}",
    "«Conveyance_Allowance_YTD»":   "{{ conveyance_annual }}",
    "«Medical_Allowance_YTD»":      "{{ medical_allowance_annual }}",
    "«Special_Allowance_YTD»":      "{{ special_allowance_annual }}",
    "«Monthly_Gross»":              "{{ gross_monthly }}",
    "«Monthly_Gross_YTD»":          "{{ gross_annual }}",
    "«Provident_Fund_YTD»":         "{{ employee_pf_annual }}",
    "«ESI_YTD»":                    "{{ employee_esi_annual }}",
    "«Professional_Tax_YTD»":       "{{ professional_tax_annual }}",
    "«Decutions»":                  "{{ total_deductions_monthly }}",
    "«Decutions_YTD»":              "{{ total_deductions_annual }}",
    "«Employer_PF_YTD»":            "{{ employer_pf_annual }}",
    "«Medical_Insurance_YTD»":      "{{ employer_esi_annual }}",
    "«Employer_Deductions_YTD»":    "{{ employer_deductions_annual }}",
    "«Net_Salary»":                 "{{ net_take_home }}",
    "«Net_Salary_YTD»":             "{{ net_take_home_annual }}",
    "«Annual_CTC_YTD»":             "{{ annual_ctc }}",
    "«Current_Date»":               "{{ current_date }}",

    # Typo fix on page 5: "{{ candidate_name }" → "{{ candidate_name }}"
    # Use a unique left-side marker so we don't double-fix valid placeholders.
    "{{ candidate_name }  ": "{{ candidate_name }}  ",
    "{{ candidate_name } ":  "{{ candidate_name }} ",
}

# Special two-pass: handle the "{{ candidate_name }" without trailing space too
# (typo where the SECOND brace is missing). Do this AFTER the main pass so we
# don't accidentally re-break a correct "{{ candidate_name }}".
def fix_candidate_name_typo(text: str) -> str:
    """If text has '{{ candidate_name }' NOT followed by another '}', add one."""
    import re
    # Match '{{ candidate_name }' that is NOT immediately followed by another '}'
    return re.sub(r"\{\{\s*candidate_name\s*\}(?!\})", "{{ candidate_name }}", text)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _apply_to_paragraph(paragraph) -> int:
    """
    Replace placeholders in a paragraph. Returns count of substitutions made.

    Strategy: get full paragraph text, do all replacements, then write the
    result back into the FIRST run (preserving its font) and clear all other
    runs. This loses intra-paragraph formatting (e.g. one bold word inside a
    sentence) but is the only reliable way to handle text split across runs,
    which is very common in Word documents.
    """
    full_text = paragraph.text
    if not full_text:
        return 0

    new_text = full_text
    for old, new in REPLACEMENTS.items():
        new_text = new_text.replace(old, new)
    new_text = fix_candidate_name_typo(new_text)

    if new_text == full_text:
        return 0

    if paragraph.runs:
        paragraph.runs[0].text = new_text
        for run in paragraph.runs[1:]:
            run.text = ""
    else:
        paragraph.add_run(new_text)

    # Count how many distinct substitutions hit
    count = 0
    for old in REPLACEMENTS:
        if old in full_text:
            count += full_text.count(old)
    return count


def _process_container(container) -> int:
    """Walk paragraphs and tables inside a container (body, cell, header, footer)."""
    total = 0
    for para in getattr(container, "paragraphs", []):
        total += _apply_to_paragraph(para)
    for table in getattr(container, "tables", []):
        for row in table.rows:
            for cell in row.cells:
                total += _process_container(cell)
    return total


def main():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    src = os.path.join(
        repo_root, "templates",
        "Globex Digital Solutions _ Template _ Offer Letter.docx",
    )
    dst_dir = os.path.join(repo_root, "greythr_bridge", "templates", "letters")
    dst = os.path.join(dst_dir, "offer_letter.docx")

    if not os.path.exists(src):
        sys.exit(f"ERROR: source template not found: {src}")

    os.makedirs(dst_dir, exist_ok=True)

    doc = Document(src)
    total = 0

    # Body
    total += _process_container(doc)

    # Headers and footers in each section
    for section in doc.sections:
        total += _process_container(section.header)
        total += _process_container(section.footer)

    doc.save(dst)
    print(f"OK: substitutions applied = {total}")
    print(f"OK: wrote {dst}")


if __name__ == "__main__":
    main()
