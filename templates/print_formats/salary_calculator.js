// ============================================================
// Frappe Client Script — Job Offer
// Auto-calculates all salary fields from Annual CTC
//
// How to install:
// 1. Go to your Frappe site → search "Client Script" → New
// 2. DocType: Job Offer
// 3. Module: greytHR  (or leave blank)
// 4. Paste this entire file content → Save
//
// Salary rules:
//   Basic          = 50% of Gross
//   HRA            = 50% of Basic (Hyderabad metro)
//   Conveyance     = ₹1,600 fixed (IT Act exempt)
//   Medical        = ₹1,250 fixed (IT Act exempt)
//   Special Allow  = Gross − Basic − HRA − Conv − Medical
//   Employee PF    = 12% of Basic, capped at ₹1,800 (Basic > ₹15,000)
//   Employee ESI   = 0.75% of Gross if Gross ≤ ₹21,000, else ₹0
//   Prof Tax (TS)  = ₹200 if Gross > ₹20,000 | ₹150 if > ₹15,000 | ₹0
//   Employer PF    = 12% of Basic (max ₹1,800) + EDLI/Admin 1% of Basic (max ₹150)
//   Employer ESI   = 3.25% of Gross if Gross ≤ ₹21,000, else ₹0
// ============================================================

frappe.ui.form.on('Job Offer', {

    custom_ctc: function(frm) {
        calculate_salary_from_ctc(frm);
    },

    refresh: function(frm) {
        // Add a manual recalculate button in case HR adjusts fields and wants to reset
        if (!frm.is_new() || frm.doc.custom_ctc) {
            frm.add_custom_button('Recalculate Salary', function() {
                calculate_salary_from_ctc(frm);
            }, 'Salary');
        }
    }

});


function calculate_salary_from_ctc(frm) {
    const annual_ctc = frm.doc.custom_ctc || 0;
    if (!annual_ctc || annual_ctc <= 0) return;

    const monthly_ctc = annual_ctc / 12;

    // ── Iterative convergence ─────────────────────────────────────────────────
    // Gross ↔ Employer PF/ESI are circular: PF and ESI depend on Gross, but
    // Gross = Monthly CTC − Employer PF − Employer ESI.
    // We iterate until Gross stabilises (converges in 3–5 iterations).

    let gross = monthly_ctc - 1950; // initial estimate (high-salary case)

    for (let i = 0; i < 10; i++) {
        const basic_est = gross * 0.50;

        // Employer PF (12% of Basic, capped at ₹1,800)
        const er_pf_base = basic_est > 15000 ? 1800 : Math.round(basic_est * 0.12);
        // EDLI + Admin charges (1% of Basic, capped at ₹150 when Basic > ₹15,000)
        const edli_admin = basic_est > 15000 ? 150 : Math.round(basic_est * 0.01);
        const er_pf_total = er_pf_base + edli_admin;

        // Employer ESI (3.25% of Gross if Gross ≤ ₹21,000, else ₹0)
        const er_esi = gross <= 21000 ? Math.round(gross * 0.0325) : 0;

        const new_gross = monthly_ctc - er_pf_total - er_esi;

        if (Math.abs(new_gross - gross) < 0.5) {
            gross = new_gross;
            break;
        }
        gross = new_gross;
    }

    // ── Round and compute components ──────────────────────────────────────────
    gross = Math.round(gross);

    const basic   = Math.round(gross * 0.50);
    const hra     = Math.round(basic * 0.50);   // 50% of Basic (metro)
    const conv    = 1600;                         // fixed exempt limit
    const medical = 1250;                         // fixed exempt limit
    const special = Math.max(0, gross - basic - hra - conv - medical);

    // Employee contributions
    const emp_pf  = basic > 15000 ? 1800 : Math.round(basic * 0.12);
    const emp_esi = gross <= 21000 ? Math.round(gross * 0.0075) : 0;

    // Professional Tax — Telangana slabs
    let pt = 0;
    if      (gross > 20000) pt = 200;
    else if (gross > 15000) pt = 150;

    const net = gross - emp_pf - emp_esi - pt;

    // Employer contributions (final, using converged gross/basic)
    const er_pf_base_final = basic > 15000 ? 1800 : Math.round(basic * 0.12);
    const edli_final       = basic > 15000 ? 150  : Math.round(basic * 0.01);
    const er_pf_total_final = er_pf_base_final + edli_final;
    const er_esi_final     = gross <= 21000 ? Math.round(gross * 0.0325) : 0;

    // ── Set fields ────────────────────────────────────────────────────────────
    frm.set_value('custom_basic',             basic);
    frm.set_value('custom_hra',               hra);
    frm.set_value('custom_conveyance',        conv);
    frm.set_value('custom_medical_allowance', medical);
    frm.set_value('custom_special_allowance', special);
    frm.set_value('custom_employee_pf',       emp_pf);
    frm.set_value('custom_employee_esi',      emp_esi);
    frm.set_value('custom_professional_tax',  pt);
    frm.set_value('custom_employer_pf',       er_pf_total_final);  // PF + EDLI + Admin
    frm.set_value('custom_employer_insurance',er_esi_final);

    // ── Summary alert ─────────────────────────────────────────────────────────
    const fmt = n => '₹' + n.toLocaleString('en-IN');
    frappe.show_alert({
        message: `Gross: ${fmt(gross)} | Net Take-Home: ${fmt(net)} | Monthly CTC: ${fmt(Math.round(monthly_ctc))}`,
        indicator: 'green'
    }, 8);
}
