---
paths: frontend/**/*.tsx
---

# Frontend React Development Rules

## Next.js App Router
- Use `'use client'` directive for client components
- Wrap `useSearchParams` in `<Suspense>` boundary
- Use `next/navigation` for routing, not `next/router`

## API Calls
- Use the `api` object from `@/lib/api` for all backend calls
- Handle loading and error states
- Show Macedonian error messages to users

## UI Components
- Use shadcn/ui components from `@/components/ui/`
- Follow existing patterns in the codebase
- Use Tailwind CSS for styling

## Macedonian Language
- All user-facing text should be in Macedonian
- Use "Се вчитува..." for loading states
- Use "Грешка" for error states

## State Management
- Use React hooks for local state
- Persist filter state across tab switches
- Debounce search inputs (300-500ms)

## Links
- External links: `target="_blank" rel="noopener noreferrer"`
- Internal navigation: Use Next.js `<Link>` component
- Pass search params via URL when navigating

## Build
- Run `npm run build` before committing to catch TypeScript errors
- Frontend auto-deploys to Vercel on git push
