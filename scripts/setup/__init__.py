"""00_setup — first-run install wizard.

Five sub-features:
- wizard:       orchestration, prompts, phase detection
- db_bootstrap: Phase 1 — role/db creation + migrations
- vault_init:   Phase 2 — MDK generation + DSN seeding into the vault
- first_admin:  Phase 3 — first admin user creation
- settings:     Phase 4 — seed 10_fct_settings rows
"""
