# Running TailoredResume

The complete and maintained setup guide is in [README.md](README.md).

Quick Docker start:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

Quick local verification:

```powershell
python -m pytest tests
Set-Location web
npm ci
npm run verify
```

The frontend runs on `http://localhost:3000` and the API on `http://localhost:8001`.
