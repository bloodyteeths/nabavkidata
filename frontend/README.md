# nabavkidata.com Frontend

Next.js 14 frontend for Macedonian Tender Intelligence Platform

## Stack

- **Next.js 14** (App Router)
- **TypeScript**
- **Tailwind CSS**
- **shadcn/ui**
- **Zustand** (state management)
- **Recharts** (analytics)

## Setup

```bash
npm install
```

## Environment

Create `.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Development

```bash
npm run dev
```

Open http://localhost:3000

## Structure

```
app/
  layout.tsx          - Root layout with sidebar
  page.tsx            - Personalized dashboard
  tenders/            - Tender explorer
  competitors/        - Competitor intelligence
  inbox/              - Email digests
  chat/               - AI assistant
  settings/           - User preferences

components/
  ui/                 - shadcn base components
  dashboard/          - Dashboard widgets
  tenders/            - Tender components
  chat/               - Chat interface

lib/
  api.ts              - API client
  utils.ts            - Utilities
```

## Features

✅ Personalized Dashboard
✅ Tender Search & Filter
✅ AI-Powered Insights
✅ Competitor Tracking
✅ RAG Chat Assistant
✅ User Preferences

## API Integration

All endpoints from backend:
- `/api/tenders`
- `/api/personalized/dashboard`
- `/api/rag/query`
- `/api/personalization/preferences`

See `lib/api.ts` for full client.

## Build

```bash
npm run build
npm start
```
