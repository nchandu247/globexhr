import frappe


def execute():
	"""Reload the HR Letters DocType schemas on migrate.

	Exists so a commit carrying no other schema change still counts as a
	pending patch. Frappe Cloud's "Update Site Pull" skips ``bench migrate``
	when a deploy has no unrun patch — and fixtures (Letter Types, Client
	Scripts) only sync during migrate. This patch guarantees migrate runs on
	deploy; ``sync_fixtures`` then loads the shipped catalog automatically.
	"""
	for doctype in (
		"Letter Type",
		"HR Letter",
		"HR Letter Compensation Row",
		"HR Letters Settings",
	):
		frappe.reload_doc("hr_letters", "doctype", frappe.scrub(doctype))
