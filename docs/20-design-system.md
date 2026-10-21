# AgentOps Design System Specification (`docs/20-design-system.md`)

## 1. Design Philosophy & Visual Principles

The AgentOps design system is engineered specifically for an **auditable, high-reliability AI Agent Operations Platform**. It models a calm, professional, dense, and functional technical SaaS console suitable for engineering leadership, system architects, and technical analysts.

### Core Visual Principles
1. **Calm, High-Clarity Utility**: Avoid decorative gradients, glassmorphism, 3D gimmicks, or distracting kinetic animations. Prioritize legibility, contrast, and high-density information hierarchy.
2. **Information Hierarchy Over Visual Decoration**: Important execution states (running, blocked on human approval, failed, completed) and traceability links (evidence citations, audit events) must be instantly recognizable.
3. **Dual Encoding for Status (Accessibility First)**: Status is **never communicated by color alone**. Every status badge, alert, and card pairs high-contrast semantic color with an explicit text label and an accessible icon.
4. **Accessible by Default (WCAG 2.1 AA Compliance)**:
   - High-contrast text ratios (minimum 4.5:1 for normal text, 3:1 for large text).
   - High-visibility keyboard focus rings (`focus-visible:ring-2 focus-visible:ring-offset-2`).
   - Screen-reader friendly semantic HTML and ARIA roles (`role="status"`, `aria-live="polite"`, `aria-expanded`).
5. **Reduced-Motion Consideration**: All transition and animation durations respect `prefers-reduced-motion` using Tailwind's `motion-reduce:...` utilities.
6. **Data Honesty & Traceability**: No decorative fake sparklines, synthetic metrics, or fabricated execution numbers. When demo data is presented, it is clearly flagged as `[DEMO SEED]`.

---

## 2. Design Tokens

### 2.1 Color Tokens & Theming (Light & Dark)

The palette is built on neutral zinc/slate foundations with precision-tuned semantic tokens for operational states. Both light and dark modes are supported using CSS custom properties via `next-themes` (or standard class-based `dark` mode).

```css
:root {
  /* Canvas & Surface */
  --bg-canvas: #f8fafc;        /* slate-50 */
  --bg-surface: #ffffff;       /* white */
  --bg-surface-elevated: #ffffff;
  --bg-muted: #f1f5f9;         /* slate-100 */
  --bg-subtle: #e2e8f0;        /* slate-200 */

  /* Text & Content */
  --text-primary: #0f172a;     /* slate-900 */
  --text-secondary: #475569;   /* slate-600 */
  --text-muted: #64748b;       /* slate-500 */
  --text-disabled: #94a3b8;    /* slate-400 */

  /* Borders & Dividers */
  --border-default: #e2e8f0;   /* slate-200 */
  --border-subtle: #f1f5f9;    /* slate-100 */
  --border-strong: #cbd5e1;    /* slate-300 */
  --border-focus: #2563eb;     /* blue-600 */

  /* Interactive & Accent */
  --accent-primary: #2563eb;   /* blue-600 */
  --accent-primary-hover: #1d4ed8; /* blue-700 */
  --accent-primary-fg: #ffffff;
  --accent-secondary: #0f172a; /* slate-900 */

  /* Operational Status Colors (Dual-Encoded) */
  --status-neutral-bg: #f1f5f9;
  --status-neutral-text: #475569;
  --status-neutral-border: #cbd5e1;

  --status-info-bg: #eff6ff;   /* blue-50 */
  --status-info-text: #1e40af; /* blue-800 */
  --status-info-border: #93c5fd; /* blue-300 */

  --status-success-bg: #f0fdf4; /* emerald-50 */
  --status-success-text: #166534; /* emerald-800 */
  --status-success-border: #86efac; /* emerald-300 */

  --status-warning-bg: #fffbeb; /* amber-50 */
  --status-warning-text: #92400e; /* amber-800 */
  --status-warning-border: #fcd34d; /* amber-300 */

  --status-danger-bg: #fef2f2;  /* rose-50 */
  --status-danger-text: #991b1b; /* rose-800 */
  --status-danger-border: #fca5a5; /* rose-300 */
}

.dark {
  /* Canvas & Surface */
  --bg-canvas: #090d16;        /* very dark slate/navy */
  --bg-surface: #0f172a;       /* slate-900 */
  --bg-surface-elevated: #1e293b; /* slate-800 */
  --bg-muted: #1e293b;         /* slate-800 */
  --bg-subtle: #334155;        /* slate-700 */

  /* Text & Content */
  --text-primary: #f8fafc;     /* slate-50 */
  --text-secondary: #cbd5e1;   /* slate-300 */
  --text-muted: #94a3b8;       /* slate-400 */
  --text-disabled: #64748b;    /* slate-500 */

  /* Borders & Dividers */
  --border-default: #1e293b;   /* slate-800 */
  --border-subtle: #0f172a;    /* slate-900 */
  --border-strong: #334155;    /* slate-700 */
  --border-focus: #3b82f6;     /* blue-500 */

  /* Interactive & Accent */
  --accent-primary: #3b82f6;   /* blue-500 */
  --accent-primary-hover: #60a5fa; /* blue-400 */
  --accent-primary-fg: #0f172a;
  --accent-secondary: #f8fafc;

  /* Operational Status Colors (Dual-Encoded in Dark Mode) */
  --status-neutral-bg: #1e293b;
  --status-neutral-text: #94a3b8;
  --status-neutral-border: #334155;

  --status-info-bg: #172554;   /* blue-950 */
  --status-info-text: #93c5fd; /* blue-300 */
  --status-info-border: #1e40af; /* blue-800 */

  --status-success-bg: #064e3b; /* emerald-950 */
  --status-success-text: #6ee7b7; /* emerald-300 */
  --status-success-border: #047857; /* emerald-700 */

  --status-warning-bg: #451a03; /* amber-950 */
  --status-warning-text: #fcd34d; /* amber-300 */
  --status-warning-border: #b45309; /* amber-700 */

  --status-danger-bg: #4c0519;  /* rose-950 */
  --status-danger-text: #fda4af; /* rose-300 */
  --status-danger-border: #be123c; /* rose-700 */
}
```

---

### 2.2 Typography Scale

AgentOps uses a crisp system sans font stack (`Inter`, system UI fallback) paired with a high-legibility monospace stack (`JetBrains Mono`, `Fira Code`, monospace fallback) for IDs, UUIDs, parameters, and tokens:

| Token | Size | Line Height | Font Weight | Typical Usage |
|---|---|---|---|---|
| `text-xs` | 12px (0.75rem) | 16px (1.0rem) | Regular / Medium | Timestamps, metadata pills, table captions |
| `text-sm` | 14px (0.875rem) | 20px (1.25rem) | Regular / Medium / SemiBold | Primary UI labels, table body cells, form inputs |
| `text-base` | 16px (1.0rem) | 24px (1.5rem) | Regular / Medium | Reading text, body descriptions, narrative reports |
| `text-lg` | 18px (1.125rem) | 28px (1.75rem) | SemiBold | Card section headers, modal titles |
| `text-xl` | 20px (1.25rem) | 28px (1.75rem) | Bold | Subsection titles, primary card metrics |
| `text-2xl` | 24px (1.5rem) | 32px (2.0rem) | Bold | Main Page Headings (h1) |
| `font-mono` | - | - | Regular / Medium | UUIDs, Run IDs, tool parameters, JSON payload viewer |

---

### 2.3 Spacing Scale & Layout Grid

- **Base Unit**: 4px (0.25rem).
- **Scale**:
  - `space-1`: 4px
  - `space-2`: 8px
  - `space-3`: 12px
  - `space-4`: 16px
  - `space-6`: 24px
  - `space-8`: 32px
  - `space-12`: 48px
- **Layout Container**:
  - Max Width: `1440px` (`max-w-7xl`).
  - Desktop Shell: Fixed left sidebar (64px collapsed, 240px expanded) + Top Navigation Bar (56px) + Main Scrollable Canvas.
  - Mobile Shell: Off-canvas drawer with hamburger toggle + Sticky Header + Safe bottom margins.

---

### 2.4 Semantic Operational Status Mapping

| Backend Status | Semantic Meaning | Foreground / Background | Icon |
|---|---|---|---|
| `QUEUED` | Awaiting execution slot | Neutral Slate | `Clock` |
| `PLANNING` | Synthesizing execution DAG | Info Blue | `Cpu` / `Loader2` |
| `RUNNING` | Executing tool sequence | Info Blue | `PlayCircle` |
| `AWAITING_APPROVAL` | Blocked at human-in-the-loop gate | Warning Amber | `AlertTriangle` |
| `COMPLETED` | Execution finished with all evidence | Success Emerald | `CheckCircle2` |
| `COMPLETED_WITH_WARNINGS` | Finished with partial contradictions | Warning Amber | `AlertCircle` |
| `FAILED` | Terminal execution failure | Danger Rose | `XCircle` |
| `CANCELLED` | Operator explicitly cancelled | Neutral Slate | `Ban` |
| `ABORTED_BY_OPERATOR` | Rejected at approval checkpoint | Neutral Slate | `UserX` |

---

## 3. Reusable Component Catalog

The component library lives in `apps/web/components/ui/` and adheres to zero external heavyweight component libraries:

1. **Button (`components/ui/button.tsx`)**:
   - Variants: `primary`, `secondary`, `outline`, `ghost`, `danger`.
   - Sizes: `sm` (h-8), `md` (h-10), `lg` (h-12), `icon`.
   - States: default, hover, active, disabled, loading (with spinner).
2. **Badge (`components/ui/badge.tsx`)**:
   - Status badges with dual icon+label encoding for all 9 run states.
   - Evidence quality badges (`VERIFIED`, `CONTRADICTED`, `PENDING_VALIDATION`).
3. **Card (`components/ui/card.tsx`)**:
   - Structured containers with `CardHeader`, `CardTitle`, `CardDescription`, `CardContent`, `CardFooter`.
4. **Alert (`components/ui/alert.tsx`)**:
   - Operational notifications with `info`, `success`, `warning`, `danger` variants.
5. **Form Controls (`components/ui/input.tsx`, `components/ui/textarea.tsx`, `components/ui/select.tsx`)**:
   - Accessible labels, hint text, error states, and visible focus rings.
6. **Data Table (`components/ui/table.tsx`)**:
   - Dense operational table with sticky header, sorting indicators, monospace cell formatting, and responsive scroll.
7. **Dialog / Modal (`components/ui/dialog.tsx`)**:
   - Keyboard accessible (Escape to dismiss, trap focus, backdrop blur, ARIA dialog roles).
8. **Tabs (`components/ui/tabs.tsx`)**:
   - Horizontal tab list for switching views (Overview, Plan DAG, Evidence, Audit Log, Report).
9. **Breadcrumbs (`components/ui/breadcrumbs.tsx`)**:
   - Clear contextual location hierarchy (e.g. `Runs > run-84a1... > Execution Timeline`).
10. **Empty State (`components/ui/empty-state.tsx`)**:
    - Informative state with icon, heading, explanatory message, and optional primary call to action.
11. **Loading Skeletons (`components/ui/skeleton.tsx`)**:
    - Pulse animated structural placeholders matching card, table row, and timeline node geometries.
12. **Error & Retry State (`components/ui/error-view.tsx`)**:
    - Standardized error boundary container displaying correlation ID, error code, friendly explanation, and retry trigger.

---

## 4. Accessibility & Interaction Specifications

### Keyboard Navigation & Focus Ring
- Every interactive element (buttons, links, inputs, table rows) must render an unmistakable focus ring:
  ```css
  focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 focus-visible:ring-offset-2 dark:focus-visible:ring-blue-400 dark:focus-visible:ring-offset-slate-900
  ```
- Modals trap tab focus within dialog boundaries and return focus to the triggering element upon closing.
- Tables support keyboard row navigation and action activation via `Enter` or `Space`.

### Screen Reader Support
- Dynamic status changes (e.g. step running -> completed, approval notification received) announce via `aria-live="polite"` regions.
- Icons use `aria-hidden="true"` when accompanied by visible text, or require `aria-label` when used standalone.
