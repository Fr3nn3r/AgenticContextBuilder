# Deploy & Monitor — ContextBuilder on Azure

## Architecture

```
Local Machine                              Azure (Switzerland North)
┌──────────────┐                          ┌──────────────────────────────┐
│ Run pipeline │    azcopy sync           │ App Service: contextbuilder- │
│ locally      │ ──────────────────────>  │   nsa (Linux B1, port 8000)  │
│              │                          │   Image: contextbuilderacr.  │
│ workspaces/  │                          │     azurecr.io/contextbuilder│
│   nsa/       │                          │   Mount: /data/nsa ──────────┤──┐
└──────────────┘                          └──────────────────────────────┘  │
                                          ┌──────────────────────────────┐  │
                                          │ Storage: claimsevidenceprod  │  │
                                          │   File Share: workspace      │<─┘
                                          │   (10 GB, SMB mount)         │
                                          └──────────────────────────────┘
                                          ┌──────────────────────────────┐
                                          │ ACR: contextbuilderacr       │
                                          │   (Basic SKU)                │
                                          └──────────────────────────────┘
```

## Azure Resources

| Resource | Name | Resource Group |
|---|---|---|
| App Service | `contextbuilder-nsa` | `azure-resource-group-claims-ai-prod` |
| App Service Plan | `contextbuilder-plan` (B1 Linux) | same |
| Container Registry | `contextbuilderacr` (Basic) | same |
| Storage Account | `claimsevidenceprod` | same |
| File Share | `workspace` (10 GB) mounted at `/data/nsa` | same |
| Region | Switzerland North | — |

**Live URL**: https://contextbuilder-nsa.azurewebsites.net

## Deploy Code Changes

When source code (Python or React) has changed:

```powershell
# 1. Build Docker image (uses layer caching — fast if only src/ changed)
docker build -t contextbuilderacr.azurecr.io/contextbuilder:latest .

# 2. Push to ACR (only changed layers are transferred)
docker push contextbuilderacr.azurecr.io/contextbuilder:latest

# 3. Restart to pull new image
az webapp restart --name contextbuilder-nsa --resource-group azure-resource-group-claims-ai-prod
```

**Note**: If `az` is not in PATH, use full path: `"C:\Program Files\Microsoft SDKs\Azure\CLI2\wbin\az.cmd"`

**What gets transferred**: Only changed Docker layers. If only `src/` changed, ~10-50 MB. The base image and pip dependencies layer (~200 MB) stays cached unless `pyproject.toml` changes.

### Force fresh image pull

If `az webapp restart` doesn't pick up the new image (still serves old code), stop and start instead:

```powershell
az webapp stop  --name contextbuilder-nsa --resource-group azure-resource-group-claims-ai-prod
az webapp start --name contextbuilder-nsa --resource-group azure-resource-group-claims-ai-prod
```

## Sync Workspace Data

When pipeline has produced new claims/runs locally:

```powershell
.\scripts\sync-workspace.ps1                  # Upload local -> Azure Files
.\scripts\sync-workspace.ps1 -Direction down   # Download Azure -> local
.\scripts\sync-workspace.ps1 -DryRun           # Preview without transferring
.\scripts\sync-workspace.ps1 -IncludeLogs      # Include logs/ dir (700+ MB, excluded by default)
```

The sync script auto-generates a SAS token via `az CLI` (requires `az login`). Uses `azcopy sync` so only changed files are transferred.

**No rebuild needed for data-only changes** — Azure Files is live-mounted at `/data/nsa`.

## Verify Deployment

```powershell
# Health check (should return {"status":"healthy","data_dir":"/data/nsa/claims"})
curl https://contextbuilder-nsa.azurewebsites.net/api/health

# Claims API (should return JSON array of claims)
curl https://contextbuilder-nsa.azurewebsites.net/api/claims

# Auth check (should return 401 if not authenticated)
curl https://contextbuilder-nsa.azurewebsites.net/api/auth/me

# Logo/static files (should return PNG binary, not HTML)
curl -sI https://contextbuilder-nsa.azurewebsites.net/trueaim-logo.png | head -5
```

## Monitor & Troubleshoot

### View container logs

```powershell
# Stream live logs (Ctrl+C to stop)
az webapp log tail --name contextbuilder-nsa --resource-group azure-resource-group-claims-ai-prod

# Download logs as zip
az webapp log download --name contextbuilder-nsa --resource-group azure-resource-group-claims-ai-prod --log-file logs.zip
```

Docker logs are at `LogFiles/*_docker.log` inside the zip.

### Enable container stdout/stderr logging

This was already enabled, but if needed:

```powershell
az webapp log config --name contextbuilder-nsa --resource-group azure-resource-group-claims-ai-prod --docker-container-logging filesystem
```

### Check app status

```powershell
az webapp show --name contextbuilder-nsa --resource-group azure-resource-group-claims-ai-prod --query "{state:state, defaultHostName:defaultHostName}" -o json
```

### Common issues

| Symptom | Cause | Fix |
|---|---|---|
| 503 Service Unavailable | Container crashed on startup | Check docker logs. Common: CRLF line endings in entrypoint, missing env vars |
| Logo/images return HTML | SPA catch-all serving index.html | Static file serving bug in `main.py` — files must exist in `ui/dist/` |
| Container exit code 255 | Entrypoint script has CRLF `\r\n` | Dockerfile has `sed -i 's/\r$//'` safety net; rebuild with `--no-cache` if needed |
| Old code still served after push | App Service cached old image | Use `az webapp stop` + `az webapp start` instead of `restart` |
| Sync 403 Forbidden | SAS token expired or Azure AD auth | Script auto-generates SAS tokens; ensure `az login` is current |
| "Site blocked for 1 minute" | Container crashed multiple times | Wait for unblock period, then fix root cause and redeploy |

## Environment Variables

Configured in App Service (do not put secrets in code):

| Variable | Purpose |
|---|---|
| `WORKSPACE_PATH` | `/data/nsa` — points to Azure Files mount |
| `WEBSITES_PORT` | `8000` — tells App Service which port the container listens on |
| `CORS_EXTRA_ORIGINS` | `https://contextbuilder-nsa.azurewebsites.net` |
| `AZURE_OPENAI_API_KEY` | OpenAI API key for LLM calls |
| `AZURE_OPENAI_BASE_URL` | OpenAI endpoint URL |
| `AZURE_OPENAI_GPT_4_1_ENDPOINT` | GPT-4.1 specific endpoint |
| `AZURE_OPENAI_GPT_4_1_API_KEY` | GPT-4.1 specific key |
| `AZURE_DI_ENDPOINT` | Document Intelligence endpoint |
| `AZURE_DI_API_KEY` | Document Intelligence key |
| `PYTHONIOENCODING` | `utf-8` |
| `PYTHONUTF8` | `1` |

To update env vars:

```powershell
az webapp config appsettings set --name contextbuilder-nsa --resource-group azure-resource-group-claims-ai-prod --settings KEY=VALUE
```

## Auth Persistence

User credentials (`users.json`, `sessions.json`) are stored on Azure Files at `/data/nsa/.auth/`. The `docker-entrypoint.sh` symlinks them to `/app/.contextbuilder/` on container start so they persist across restarts.

To update auth files:

```powershell
# Copy local auth files into workspace
copy .contextbuilder\users.json workspaces\nsa\.auth\
copy .contextbuilder\sessions.json workspaces\nsa\.auth\

# Sync to Azure
.\scripts\sync-workspace.ps1

# Restart container to pick up new symlinks
az webapp restart --name contextbuilder-nsa --resource-group azure-resource-group-claims-ai-prod
```

## Docker Build Details

- **Multi-stage**: Node 20 builds React frontend, Python 3.11 runs backend
- **Frontend build**: `npx vite build` (skips TypeScript type checking — use `npm run build` locally to catch TS errors)
- **Entrypoint safety**: `sed -i 's/\r$//'` strips Windows CRLF before `chmod +x`
- **Context size**: ~22 MB (`.dockerignore` excludes workspaces, node_modules, tests, docs)
- **ACR admin**: Enabled for App Service to pull images

## Cost

~$19/month: App Service B1 ($13) + ACR Basic ($5) + Azure Files ($1)
