# API Examples

```bash
curl http://localhost:8000/healthz
curl "http://localhost:8000/api/tracts?state=25&limit=10"
curl http://localhost:8000/api/tracts/25017383100/explanation
curl "http://localhost:8000/api/search?q=pharmacy&type=amenity"
```

Admin ingestion triggers require `X-Admin-Token`.

```bash
curl -X POST http://localhost:8000/api/admin/ingest/census_acs \
  -H "X-Admin-Token: change-me"
```

On Windows PowerShell, prefer `curl.exe` so PowerShell does not alias `curl` to
`Invoke-WebRequest`. If your token contains characters such as `'` or `.`, keep
the header in double quotes:

```powershell
curl.exe -X POST "http://localhost:8000/api/admin/ingest/census_acs" `
  -H "X-Admin-Token: your'token.with.dots"
```

After changing `ADMIN_TOKEN` in `.env`, recreate the API container so Docker
Compose passes the new value into the running service:

```powershell
docker compose up -d --force-recreate api
```
