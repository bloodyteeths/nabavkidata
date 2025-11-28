# Multi-Agent Workflow
Roles and guardrails so parallel agents do not collide. Production code boundaries must be respected.

## Current Agents
- **Claude (primary build agent):**
  - Owns scrapers (e-nabavki/epazar), backend Python, FastAPI endpoints, database models/migrations, security and RAG backend changes.
  - Handles enrichment jobs (embeddings, CPV backfill), scraper fixes, billing/webhook logic, and any code touching production data paths.
  - Runs integration tests that exercise scrapers, API, DB writes, and RAG generation.
- **Codex (you are here):**
  - Produces static documentation, architecture maps, audits, helper scaffolds/scripts that are read-only.
  - Allowed paths: `docs/`, `devtools/`, `scripts/audit/`.
  - Must not modify scrapers, backend Python, FastAPI endpoints, DB models/migrations, UI React/Next code, embedding/RAG logic, or security files.

## Future/Supporting Agents
- **Data steward:** validates datasets, sets data quality thresholds, approves migrations; may backfill missing values through controlled ETL.
- **QA/bot runner:** executes automated test suites, load tests, and synthetic monitoring; reports regressions without changing code.
- **Ops/infra agent:** manages deployment manifests (K8s/Terraform), observability, and secrets rotation under change control.
- **UX/design agent:** ships Figma flows, copy, and component specs without touching production code unless coordinated with Claude.
- **AI safety reviewer:** audits prompts, redaction rules, and RAG grounding; recommends guardrails but does not ship code directly.

## Coordination Rules
- Single owner per change domain; if a task touches scrapers/API/DB schema, Claude leads. If it is documentation/audit/spec work, Codex leads.
- Avoid overlapping files; Codex stays within permitted directories, leaving scraper/backend/UI files untouched.
- When producing helper scripts, default to read-only behavior and isolate outputs under `devtools/` or `scripts/audit/`.
- Document assumptions and TODOs instead of hotfixing code that might conflict with Claude’s branches.
- If unexpected external edits appear in restricted areas, pause and ask for direction before proceeding.
