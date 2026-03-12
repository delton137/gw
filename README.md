# Gene Wizard

Whole genome interpretation platform. Analyzes raw genetic data from 23andMe, AncestryDNA, and WGS VCFs.

## Local Development

### Prerequisites

- Python 3.12
- Node 22 (via nvm)
- PostgreSQL 16 (native, no Docker)

### Backend

```bash
sudo systemctl start postgresql
source .venv/bin/activate
alembic upgrade head
python -m scripts.seed_pgx_definitions
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
PATH="/home/dan/.nvm/versions/node/v22.22.0/bin:$PATH"
npm install
npm run dev
```

Runs on http://localhost:3000. API requests proxy to http://localhost:8000.

### Dropbox users

Exclude build artifacts from sync to avoid corruption:

```bash
dropbox exclude add frontend/.next frontend/node_modules
```

If `npm install` fails with ENOENT errors, stop Dropbox first, install, then restart it.
