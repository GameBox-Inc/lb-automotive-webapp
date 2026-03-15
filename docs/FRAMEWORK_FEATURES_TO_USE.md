# Framework Features to Use for Enhancement

This doc lists **functions and assets from your current web stack** that are either unused or underused and would improve the app: reliability, accessibility, UX, and consistency.

**Stack:** React 18, React Router 7, Vite 7, Tailwind 4, Redux Toolkit, @headlessui/react (installed), react-hot-toast, date-fns, Lucide.

---

## 1. React

### 1.1 Error boundaries (not used)

- **What:** A component that catches JavaScript errors in its child tree and shows a fallback UI instead of a blank crash.
- **Why:** Today, any uncaught error in a page (e.g. in CaseDetails or Appointments) can take down the whole app. An error boundary keeps the rest of the UI (e.g. sidebar) and shows “Something went wrong” with a retry or link home.
- **How:** Implement a class component with `static getDerivedStateFromError` and `componentDidCatch`, or use a small library (e.g. `react-error-boundary`). Wrap `<Suspense>` and route content in `main.tsx` or `App.tsx` so route-level errors are contained.

### 1.2 `useId()` (not used)

- **What:** React 18 hook that generates a stable unique ID per component instance (safe for SSR).
- **Why:** You have linter warnings about “form label must be associated with a control.” Using `htmlFor={id}` and `id={useId()}` on inputs/labels fixes that and avoids ID collisions.
- **Where:** Any form with a `<label>` and `<input>`/`<select>` (CaseDetails, CheckIn, Appointments, AdminCustomers, AdminStaff, Login, Settings).

### 1.3 `useTransition` (optional, alongside existing `startTransition`)

- **What:** Hook that exposes `isPending` and `startTransition` for non-urgent UI updates.
- **Why:** You already use `startTransition` for navigations. For heavy lists (e.g. filtering appointments or repairs), wrapping the state update in `useTransition` lets you show a subtle “updating” state and keep the UI responsive.
- **Where:** Appointments (filter/sort), StaffDashboard (filters), any page with client-side filter/sort of large lists.

---

## 2. @headlessui/react (installed but unused)

The package is in `package.json` but not imported anywhere. Using it would improve **accessibility and behavior** of overlays and lists.

### 2.1 `Dialog` for modals

- **What:** Accessible modal: focus trap, Escape to close, `aria-modal`, focus return on close.
- **Why:** Current modals are `<div className="fixed inset-0 ...">` with no focus trap or Escape handling. Headless UI’s Dialog gives that out of the box.
- **Where:** Add Customer/Edit Customer (AdminCustomers), Add Appointment (Appointments), Add/Edit Service (Services), Report modal (ReportModal), any “fixed overlay” modal.

### 2.2 `Listbox` or `Combobox` for dropdowns

- **What:** Accessible select/autocomplete: keyboard nav, aria attributes, optional search.
- **Why:** Native `<select>` is fine for simple lists; for “search then choose” (e.g. customer search in Appointments) or custom-styled dropdowns, Listbox/Combobox is a better fit and keeps behavior consistent.
- **Where:** Customer search in Add Appointment; any custom dropdown that isn’t a plain `<select>`.

### 2.3 `Tab` for tabbed UIs

- **What:** Tab panels with correct roles (`tab`, `tabpanel`) and keyboard navigation.
- **Why:** Case Details (Notes / Parts / History / Sign) and Admin IVR (Config / Analytics) use custom tab buttons. Headless UI Tab gives proper semantics and arrow-key navigation.
- **Where:** CaseDetails tabs, AdminIVR config vs analytics.

### 2.4 `Transition` for enter/leave animations

- **What:** Declarative show/hide with optional duration and unmount-after-leave.
- **Why:** So modals, toasts, or dropdowns can fade/slide instead of popping in/out.
- **Where:** Modal open/close, optional for toast (react-hot-toast may have its own).

---

## 3. React Router (v7)

You use `BrowserRouter`, `Routes`, `Route`, `Link`, `useNavigate`, `useLocation`. Router’s **data and layout** features are not used.

### 3.1 Loaders + `useLoaderData` (optional but high impact)

- **What:** Route-level async loaders that run when the route is matched; data is available on first paint via `useLoaderData()`.
- **Why:** Today many pages do `useEffect` + `useState` to fetch on mount, which causes a loading spinner flash. Loaders let the router fetch in parallel with navigation so you can show data (or a route-level skeleton) sooner.
- **How:** Migrate to `createBrowserRouter` / `RouterProvider` and add `loader` to routes that need data (e.g. Appointments, CaseDetails, StaffDashboard, AdminCustomers). Keep using your existing `apiClient` inside loaders.

### 3.2 Layout routes + `Outlet`

- **What:** Parent route that renders an `<Outlet />` so the sidebar (and any shared chrome) wraps only once; child routes render into the outlet.
- **Why:** Today the sidebar and header are inside `App` and repeated in the same tree. With a layout route, the layout is declared once and route elements are the “page” only.
- **Benefit:** Clearer structure, easier to add route-specific data or error boundaries later.

### 3.3 `errorElement` on routes

- **What:** Per-route error UI when a loader or action throws or when a child throws and an error boundary is used with the router.
- **Why:** Combined with an error boundary, you can show “Failed to load this case” with a retry or “Back to list” instead of a blank screen.

---

## 4. Vite

### 4.1 `import.meta.env` (already used)

- You use `VITE_API_URL` and `import.meta.env.DEV`. No change needed; keep using env for any other config (e.g. feature flags, analytics IDs).

### 4.2 Lazy loading (already used)

- Routes are lazy-loaded with `lazy(() => import(...))` and wrapped in `<Suspense>`. That’s good; optional improvement is to add a route-level `loading` or a skeleton in `Suspense fallback` for key routes.

### 4.3 Assets

- **What:** `import img from './asset.png'` or place in `public/` for static assets.
- **Why:** If you add more images (e.g. logos, empty-state illustrations), using Vite’s asset handling keeps hashing and paths correct. No change required until you add assets.

---

## 5. Tailwind CSS (v4)

### 5.1 Design tokens in `theme.extend`

- **What:** Your `index.css` defines CSS variables (`--lb-red-primary`, etc.). You can mirror those in `tailwind.config.js` under `theme.extend.colors` so you use `bg-lb-red-primary` instead of `bg-[#B91C1C]` everywhere.
- **Why:** One source of truth for brand colors and spacing; easier to change theme later and to keep contrast/accessibility in one place.

### 5.2 `@tailwindcss/forms` (optional)

- **What:** Plugin that adds a minimal reset and better defaults for form elements.
- **Why:** Slightly more consistent look for inputs/selects across browsers; less custom override needed. Optional if you’re happy with current form styling.

### 5.3 Container queries (Tailwind 4)

- **What:** `@container` and size-based utilities so components adapt to their container width, not only viewport.
- **Where:** Cards or lists that should reflow (e.g. appointment cards, repair cards) when the container is narrow, e.g. in a sidebar or a resizable panel.

---

## 6. Redux Toolkit

### 6.1 RTK Query (not used)

- **What:** `createApi` with `endpoints` for each API call; auto caching, deduplication, loading/error state, optional optimistic updates.
- **Why:** You currently use a single `apiClient` with manual `useState`/`useEffect` in each page. RTK Query would centralize “how we call the API” and reduce duplicate loading/error handling and duplicate requests (e.g. two components asking for the same case).
- **Trade-off:** Migration is non-trivial (many pages touch the API). Consider for a next phase or for the most critical flows (e.g. appointments, case details) first.

### 6.2 Keep current approach

- If you prefer to keep the existing `apiClient` + hooks, you can still add a **thin cache layer** (e.g. in-memory by key + stale-while-revalidate) in `supabase.ts` to avoid refetching the same resource in a short window. That’s a smaller change than full RTK Query.

---

## 7. Other libraries you already use

- **react-hot-toast:** Already used; position and usage are consistent. No change needed unless you want a different position or style.
- **date-fns:** You use it for formatting; consider using it for all date math (e.g. “today”, “start of day”) so timezone and DST are handled in one place.
- **Lucide:** You use it for icons; the UX/UI report covers icon consistency. No extra “framework” feature here.

---

## Suggested order of adoption

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| 1 | Error boundary around app/route content | Low | High (reliability) |
| 2 | Headless UI `Dialog` for one or two key modals | Low | High (a11y, UX) |
| 3 | `useId()` for form label/control association | Low | Medium (a11y, lint) |
| 4 | Headless UI `Tab` for CaseDetails (and optionally AdminIVR) | Low | Medium (a11y) |
| 5 | Tailwind theme.extend for LB brand colors | Low | Medium (consistency) |
| 6 | React Router layout routes + `Outlet` | Medium | Medium (structure) |
| 7 | Headless UI for remaining modals | Medium | Medium (a11y) |
| 8 | Loaders for 1–2 heavy pages (e.g. Appointments, CaseDetails) | Medium | High (perceived perf) |
| 9 | RTK Query or small API cache layer | High | High (long-term) |

If you tell me which of these you want to adopt first (e.g. error boundary + Headless Dialog, or loaders), I can outline concrete steps and code changes in the repo.
