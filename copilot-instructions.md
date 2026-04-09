Copilot feature implementation guidelines for this repository.

- Keep secrets out of the repository. Use `.env` locally (copy from `.env.example`).
- Write docs (in `docs/`) before implementing code changes for a feature.
- Add tests in `tests/` and ensure CI (if any) runs them locally.
- When requesting automated code review, include the scope and which files to focus on.

Feature example: `upload_reports_to_s3.py` — uploader script lives in `scripts/` and is covered by unit tests in `tests/`.
