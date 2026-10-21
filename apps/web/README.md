# AgentOps Web Frontend (`apps/web`)

Next.js 14+ application providing the operational dashboard for AgentOps.

## Directory Layout

- `app/`: Next.js App Router pages and layout entrypoints.
- `components/`: Shared React presentational components.
- `components/ui/`: Atomic UI primitives (buttons, inputs, cards, dialogs).
- `features/`: Feature-scoped components (run-submission, plan-inspector, hitl-modal, evidence-drawer, report-viewer).
- `lib/`: API clients, formatting utilities, and constants.
- `hooks/`: Reusable React hooks for polling, state management, and SSE streams.
- `public/`: Static assets and icons.
- `tests/`: Unit and component test suites.
- `tests/e2e/`: Playwright end-to-end integration tests.

## Development

```bash
cd apps/web
npm install
npm run dev
```
