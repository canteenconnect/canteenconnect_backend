# Canteen Backend (Replaced)

This backend has been replaced with the Python polyglot stack in:
- `canteen_backend/polyglot_backend`

Frameworks now used together:
- FastAPI (core API)
- Flask + Socket.IO (gateway + realtime)
- Django (admin console)
- PostgreSQL

## Start
```powershell
cd C:\Users\APSSDC\Music\cannten_p\canteen_backend
copy polyglot_backend\.env.example polyglot_backend\.env
.\start.ps1
```

## Stop
```powershell
.\stop.ps1
```

## Status
```powershell
.\status.ps1
```