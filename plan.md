# Yash Dental Clinic — repair & completion plan

Repo: `https://gitlab.com/webapp-sales-type-shi/yashdentalclinic.git`
Stack: Next.js 15 App Router · TypeScript · Tailwind 4 · Firebase Auth (Google) ·
Supabase Postgres · Resend · web-push · Razorpay.

## Runtime layout in this environment

- The whole Next.js project lives in `/app/frontend` (supervisor runs `yarn start`
  → `next dev -H 0.0.0.0 -p 3000`).
- `/app/backend/server.py` is a thin FastAPI reverse proxy: the platform ingress
  sends `/api/*` to port 8001, and the proxy forwards it verbatim to Next.js on
  port 3000. No application logic lives there.
- Secrets are in `/app/frontend/.env.local` (git-ignored), taken from the user's
  `ENV_FOR_VERCEL.txt`, with `NEXT_PUBLIC_SITE_URL` pointed at the preview URL.
- `/api/health` reports supabase, firebaseAdmin, firebaseWeb, email, razorpay and
  maps all configured and reachable.

## Hard constraint discovered

Only the Supabase **service-role REST key** is available — there is no Postgres
password, so **no DDL can be run from here**. Everything is therefore built
against the schema already deployed (migrations 0001–0003 are applied). A new
`supabase/migrations/0004_hardening.sql` is committed for the user to paste into
the Supabase SQL editor; it is an optimisation, not a requirement.

## Phases

### Phase 1 — foundation & backend (auth, data, APIs)
- Rewrite `lib/auth.ts`: local session-cookie verification (no per-request
  round-trip to Google), per-request `cache()` dedupe, 30 s profile cache,
  permission helpers. This is the root cause of slow login/logout and of the
  dashboard "application error" on re-entry.
- `lib/settings.ts` + `lib/site-content.ts`: admin-editable clinic settings and
  website content stored in the `settings` table with config fallback.
- `lib/notify.ts`: single source for in-app notifications + web push + the
  once-per-appointment email claim (tracked in `audit_logs`).
- `lib/email.ts`: exactly one patient email per appointment, ever. No welcome
  email, no clinic alert email, no reminder email.
- APIs: profile, appointments (staff + patient self-service), availability,
  patients, doctors, staff, settings, content, holidays, notifications,
  invoices/payments, razorpay order + webhook, cron reminders + no-show sweep.
- Fix `middleware.ts` (it guarded routes that do not exist and redirected to a
  `/sign-in` page that does not exist).
- Fix `treatment_id` never being written on booking.

### Phase 2 — patient experience
- `/signin` (separate journey) and `/book` (login required, name + phone required).
- `/account`: overview, appointments (reschedule/cancel), profile editor,
  notifications, treatment history.
- Notification bell with unread count; browser push opt-in.

### Phase 3 — staff & admin
- Reception dashboard: today's queue, calendar, walk-in booking, patient records,
  check-in/attendance, missed appointments, visit notes, payments.
- Dentist management and per-appointment assignment.
- Super admin: staff accounts (dentist Google accounts, receptionists,
  permissions), clinic settings, website content editor, notifications, payments,
  audit log.

### Phase 4 — public site wiring & polish
- Homepage/FAQ/why sections driven by the admin content editor.
- Clinic contact + hours driven by settings via a client context.
- Responsiveness, loading/error states, empty states.

## Status

- [x] Repo cloned, dependencies installed, app running, env wired, health green
- [x] Phase 1
- [x] Phase 2
- [x] Phase 3
- [x] Phase 4
