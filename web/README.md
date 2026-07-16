# TailoredResume frontend

This directory contains the Next.js 16 and React 19 dashboard for TailoredResume. Product architecture, environment configuration, backend setup, and safety notes are documented in the [project README](../README.md).

## Local development

Create `web/.env.local` when Clerk authentication is enabled:

```text
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
CLERK_SECRET_KEY=sk_test_...
NEXT_PUBLIC_API_URL=http://localhost:8001
```

Then run:

```powershell
npm ci
npm run dev
```

The dashboard is available at `http://localhost:3000`. Browser API calls are routed through the Next.js `/api/backend` rewrite to avoid cross-origin development issues.

## Required checks

```powershell
npm run lint
npm run typecheck
npm run build
```

Run all three checks with:

```powershell
npm run verify
```

Do not commit `.env.local`, `.next`, `node_modules`, exported resumes, or applicant data.
