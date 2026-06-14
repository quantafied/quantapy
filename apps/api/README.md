# Quantapy API

FastAPI wrapper around the local Quantapy library.

Run from the repository root:

```bash
source .env/bin/activate
uvicorn apps.api.quantapy_api.main:app --reload --port 8000
```

The API stores MVP workspaces in memory. Restarting the server clears them.

