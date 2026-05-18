# greythr_bridge

Custom Frappe app for Globex Digital Solutions Pvt Ltd.
Integrates Frappe HR with greytHR Cloud for employee sync, letter generation, and e-signature workflows.

## Overview

- Pulls employee master data from greytHR into Frappe HR (every 15 min)
- Pushes signed offer letters and new joiners back to greytHR
- Orchestrates e-signature flows via Zoho Sign

See `PLAN.md` for the full architecture and phase-by-phase build plan.

## Requirements

- Python 3.10+
- Frappe 15+ with Frappe HR (`hrms`) installed
- greytHR Essential plan with API access enabled
- Zoho Sign business account (India DC)

## Installation

```bash
# On your Frappe bench
bench get-app https://github.com/nchandu247/globexhr.git
bench --site hr.globexdigital.ai install-app greythr_bridge
bench --site hr.globexdigital.ai migrate
```

## Configuration

1. In Frappe HR, open **greytHR Settings** (search in the top bar)
2. Enable the integration toggle
3. Fill in:
   - `api_base_url`: `https://api.greythr.com`
   - `tenant_domain`: `globex.greythr.com`
   - `client_id` and `client_secret` from greytHR Admin → API Users
   - `zoho_sign_api_key`, `zoho_sign_account_id`, `zoho_sign_webhook_secret` from Zoho Sign console
4. Click **Save**
5. Run the smoke test: `bench --site hr.globexdigital.ai execute greythr_bridge.api.client.test_connection`

## Running Tests

```bash
pip install -r requirements.txt
pytest greythr_bridge/tests/ -v
```

Tests run fully offline — no real API calls are made in the test suite.

## Development

See `PLAN.md` for conventions, phase tasks, and the implementation spec.
See `CLAUDE.md` for coding rules used in every Claude Code session.
See `NOTES_greythr_api.md` for the greytHR API schema reference.
See `CHANGELOG.md` for what has changed.
