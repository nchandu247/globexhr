// ============================================================
// Frappe Client Script — Job Offer
// Auto-calculates all salary fields from Annual CTC
//
// Install: Frappe site → Client Script → New
//   DocType: Job Offer | Module: greytHR
//   Paste this file → Save
//
// Rules:
//   Basic          = 50% of Gross
//   HRA            = 50% of Basic (Hyderabad metro)
//   Conveyance     = ₹1,600 fixed
//   Medical Allow  = ₹1,250 fixed
//   Special Allow  = Gross − Basic − HRA − Conv − Medical
//   Employee PF    = if opted out → 0
//                    else 12% of Basic capped at ₹1,800
//   Employer PF    = if opted out → 0
//                    else (12% Basic, cap ₹1,800) + (1% Basic EDLI, cap ₹150)
//   Employee ESI   = auto: 0.75% of Gross if Gross ≤ ₹21,000 else 0
//   Employer ESI   = auto: 3.25% of Gross if Gross ≤ ₹21,000 else 0
//   Med Insurance  = auto: annual_premium÷12 if Gross > ₹21,000
//                    AND not opted out; else 0
//   Prof Tax (TS)  = ₹200 if Gross > ₹20,000 | ₹150 if > ₹15,000 | ₹0
//   PF opt-out     = shown only when Gross > ₹35,000
//   Med opt-out    = shown only when ESI does not apply
// ============================================================

frappe.ui.form.on('Job Offer', {

    custom_ctc: function(frm) {
        calculate_salary(frm);
    },
    custom_pf_opted_out: function(frm) {
        calculate_salary(frm);
    },
    custom_medical_opted_out: function(frm) {
        calculate_salary(frm);
    },
    custom_medical_insurance_annual: function(frm) {
        calculate_salary(frm);
    },

    refresh: function(frm) {
        frm.add_custom_button('Recalculate Salary', function() {
            calculate_salary(frm);
        }, 'Salary');

        // Set default medical premium if blank
        if (!frm.doc.custom_medical_insurance_annual) {
            frm.set_value('custom_medical_insurance_annual', 10000);
        }
        // Apply field visibility based on current values
        _update_visibility(frm, frm.doc.custom_employee_esi > 0, frm.doc.custom_basic || 0);
    }

});


function calculate_salary(frm) {
    const annual_ctc = frm.doc.custom_ctc || 0;
    if (!annual_ctc || annual_ctc <= 0) return;

    const monthly_ctc        = annual_ctc / 12;
    const pf_opted_out       = frm.doc.custom_pf_opted_out ? true : false;
    const medical_opted_out  = frm.doc.custom_medical_opted_out ? true : false;
    const medical_annual     = frm.doc.custom_medical_insurance_annual || 10000;
    const medical_monthly    = Math.round(medical_annual / 12);

    // ── Iterative convergence ─────────────────────────────────────────────────
    // Gross ↔ Employer PF / ESI / Medical Insurance are circular.
    // Iterate until Gross stabilises (converges in ≤ 5 iterations).

    let gross = monthly_ctc - 1950; // initial estimate

    for (let i = 0; i < 10; i++) {
        const basic_est   = gross * 0.50;
        const esi_applies = gross <= 21000;

        // Employer PF + EDLI + Admin
        let er_pf = 0;
        if (!pf_opted_out) {
            const er_pf_base = basic_est > 15000 ? 1800 : Math.round(basic_est * 0.12);
            const edli_admin = basic_est > 15000 ? 150  : Math.round(basic_est * 0.01);
            er_pf = er_pf_base + edli_admin;
        }

        // Employer ESI (statutory, cannot opt out)
        const er_esi = esi_applies ? Math.round(gross * 0.0325) : 0;

        // Medical Insurance (employer cost in CTC, only when ESI doesn't apply)
        const med_in_ctc = (!esi_applies && !medical_opted_out) ? medical_monthly : 0;

        const new_gross = monthly_ctc - er_pf - er_esi - med_in_ctc;
        if (Math.abs(new_gross - gross) < 0.5) { gross = new_gross; break; }
        gross = new_gross;
    }

    // ── Compute final components ──────────────────────────────────────────────
    gross = Math.round(gross);

    const basic        = Math.round(gross * 0.50);
    const hra          = Math.round(basic * 0.50);
    const conv         = 1600;
    const medical_all  = 1250;
    // When medical insurance is opted out, ₹833 flows naturally into Special Allowance
    // (Gross is ₹833 higher because med_in_ctc = 0), giving higher net take-home.
    const special      = Math.max(0, gross - basic - hra - conv - medical_all);

    const esi_applies_final = gross <= 21000;

    // Employee PF
    const emp_pf  = (!pf_opted_out && basic > 15000) ? 1800
                  : (!pf_opted_out)                  ? Math.round(basic * 0.12)
                  : 0;

    // Employee ESI (auto)
    const emp_esi = esi_applies_final ? Math.round(gross * 0.0075) : 0;

    // Professional Tax — Telangana
    let pt = 0;
    if      (gross > 20000) pt = 200;
    else if (gross > 15000) pt = 150;

    // Net take-home
    const net = gross - emp_pf - emp_esi - pt;

    // Employer PF final
    let er_pf_final = 0;
    if (!pf_opted_out) {
        const er_pf_base = basic > 15000 ? 1800 : Math.round(basic * 0.12);
        const edli_admin = basic > 15000 ? 150  : Math.round(basic * 0.01);
        er_pf_final = er_pf_base + edli_admin;
    }

    // Employer ESI final
    const er_esi_final = esi_applies_final ? Math.round(gross * 0.0325) : 0;

    // ── Update field visibility ───────────────────────────────────────────────
    _update_visibility(frm, esi_applies_final, gross);

    // Auto-uncheck PF opt-out if gross falls back below threshold
    if (gross <= 35000 && pf_opted_out) {
        frm.set_value('custom_pf_opted_out', 0);
    }

    // ── Set all salary fields ─────────────────────────────────────────────────
    frm.set_value('custom_basic',              basic);
    frm.set_value('custom_hra',                hra);
    frm.set_value('custom_conveyance',         conv);
    frm.set_value('custom_medical_allowance',  medical_all);
    frm.set_value('custom_special_allowance',  special);
    frm.set_value('custom_employee_pf',        emp_pf);
    frm.set_value('custom_employee_esi',       emp_esi);
    frm.set_value('custom_professional_tax',   pt);
    frm.set_value('custom_employer_pf',        er_pf_final);
    frm.set_value('custom_employer_insurance', er_esi_final);

    // ── Summary alert ─────────────────────────────────────────────────────────
    const fmt = n => '₹' + Math.round(n).toLocaleString('en-IN');
    const med_label = esi_applies_final ? 'ESI' : (medical_opted_out ? 'No Med Ins' : `Med Ins ${fmt(medical_monthly)}/mo`);
    frappe.show_alert({
        message: `Gross: ${fmt(gross)} | Net: ${fmt(net)} | Monthly CTC: ${fmt(monthly_ctc)} | ${med_label}${pf_opted_out ? ' | PF Opted Out' : ''}`,
        indicator: 'green'
    }, 10);
}


function _update_visibility(frm, esi_applies, gross) {
    // PF opt-out: show only when Gross > ₹35,000
    const show_pf_opt = gross > 35000;
    frm.set_df_property('custom_pf_opted_out', 'hidden', show_pf_opt ? 0 : 1);

    // Medical opt-out + premium: show only when ESI does NOT apply
    const show_med = !esi_applies;
    frm.set_df_property('custom_medical_opted_out',       'hidden', show_med ? 0 : 1);
    frm.set_df_property('custom_medical_insurance_annual','hidden', show_med ? 0 : 1);

    frm.refresh_fields([
        'custom_pf_opted_out',
        'custom_medical_opted_out',
        'custom_medical_insurance_annual'
    ]);
}
