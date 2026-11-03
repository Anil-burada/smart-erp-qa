# Existing Kagami Indent -> LPO -> GRN script

This is the user's supplied full script, kept for compatibility and gradual extraction. It is **not** the multi-ERP engine and is not automatically called by the dashboard. The only intentional edits are replacing password=username with `ERPQA_KAGAMI_<ACCOUNT>_PASSWORD`, and requiring `ERPQA_RUN_LEGACY_WRITES=YES_IN_AUTHORIZED_TEST` before its main entrypoint can execute any records.

It is specific to one Kagami ERP's Material UI fields, account IDs and business logic. Its approval functions currently report click success, not verified ERP approval completion. Do not run this file on production or treat a click as an independently verified approval.
