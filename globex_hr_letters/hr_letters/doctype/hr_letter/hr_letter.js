// Copyright (c) 2026, Globex Digital Solutions Pvt Ltd
// License: Proprietary

frappe.ui.form.on("HR Letter", {
	refresh(frm) {
		if (frm.is_new()) return;

		// ── Generate (Draft / Generated, docstatus 0) ─────────────────────
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(
				frm.doc.status === "Generated" ? __("Regenerate") : __("Generate"),
				() => generate_letter(frm)
			).addClass("btn-primary");
		}

		// ── Post-generation actions ───────────────────────────────────────
		if (frm.doc.docstatus === 0 && frm.doc.status === "Generated") {
			frappe.db.get_value("Letter Type", frm.doc.letter_type, "requires_signature")
				.then((r) => {
					if (cint(r.message.requires_signature)) {
						frm.add_custom_button(__("Send for Signature"), () => {
							frappe.confirm(
								__("Submit this letter and send it to Zoho Sign?"),
								() => frm.call("send_for_signature").then(() => frm.reload_doc())
							);
						}).addClass("btn-primary");
					} else {
						frm.add_custom_button(__("Issue"), () => {
							frappe.confirm(
								__("Submit this letter and email it to the recipient?"),
								() => frm.call("issue_letter").then(() => frm.reload_doc())
							);
						}).addClass("btn-primary");
					}
				});
		}

		// ── Resend reminder while waiting on signature ────────────────────
		if (frm.doc.status === "Sent for Signature" && frm.doc.zoho_request_id) {
			frm.add_custom_button(__("Resend Signing Request"), () => {
				frappe.call({
					method: "globex_hr_letters.api.zoho_sign.resend_signing_request",
					args: { request_id: frm.doc.zoho_request_id },
					callback: () => frappe.show_alert({
						message: __("Reminder sent to pending signers."),
						indicator: "green",
					}),
				});
			});
		}
	},
});

function generate_letter(frm) {
	// Ask the server which placeholders still need values, prompt for them,
	// then generate.
	frm.call("get_missing_placeholders").then((r) => {
		const missing = r.message || [];
		if (!missing.length) {
			return run_generate(frm, {});
		}
		const fields = missing.map((name) => ({
			fieldname: name,
			fieldtype: "Data",
			label: frappe.model.unscrub(name),
			reqd: 1,
		}));
		const d = new frappe.ui.Dialog({
			title: __("Fill Letter Details"),
			fields: fields,
			primary_action_label: __("Generate"),
			primary_action(values) {
				d.hide();
				run_generate(frm, values);
			},
		});
		d.show();
	});
}

function run_generate(frm, values) {
	frappe.dom.freeze(__("Generating letter..."));
	frm.call("generate_letter", { values: values })
		.then(() => frm.reload_doc())
		.finally(() => frappe.dom.unfreeze());
}
