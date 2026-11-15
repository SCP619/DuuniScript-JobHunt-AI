# DuuniScript frontend

React and TypeScript web app for DuuniScript (Vite, TanStack Start/Router, React Query, Tailwind).
It talks only to the local DuuniScript API on `http://127.0.0.1:8000`.

```powershell
npm install
$env:VITE_USE_MOCKS = "false"; npm run dev -- --port 8080   # real local API
npm run dev -- --port 8080                                  # sample data only
npx vitest run                                              # tests
npx tsc --noEmit -p .                                       # type check
```

Normally you don't run this by hand: `scripts\start_duuniscript.ps1` (or the DuuniScript
shortcut) starts the backend and this app together. Design notes: `DEVELOPMENT.md`.
