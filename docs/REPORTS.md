**Reports Storage and Samples**

- Keep all full reports, archives, and large artifacts local or in external object storage (S3, GCS, Azure Blob, or an organization file share). Do NOT commit large reports into this git repository.
- The repository includes a tiny sample report at `reports_samples/sample_report.csv` intended for CI/examples only; real reports should not be pushed.

Recommended workflow

1. Local working copy: store generated reports under `analysis_output/`, `archived_jsons*/`, `pdf_images/` or another local folder — these are listed in `.gitignore` and will not be pushed.
2. External storage: upload large archives (zip/tar.gz) to an object store (S3/GCS) or a secure shared drive and add an entry in `docs/REPORTS.md` or a short text file in the repo pointing to the stable storage URL.
3. Samples: if you need to include a small, representative sample in the repo for testing, place it under `reports_samples/` and keep it <1MB.
4. Secrets: never hardcode credentials or API keys in reports or repo files. Use the local `.env` (copy from `.env.example`) and keep it out of version control.

How to create your local `.env` from the example

```bash
cp .env.example .env
# Edit .env and set real values for POSTGRES_PASSWORD, MONGO_PASSWORD, OPENAI_API_KEY, etc.
```

Rotating secrets

- If a secret (API key/password) was previously committed, rotate it immediately and consider those credentials compromised. After rotating, verify no sensitive values remain in history (we removed large artifacts already).

If you want, I can add an example script to upload reports to S3 and write the storage URL into a small metadata file; tell me which provider you prefer.
