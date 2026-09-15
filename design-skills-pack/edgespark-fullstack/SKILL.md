---
name: edgespark-fullstack
description: Use when building and deploying a full-stack site on EdgeSpark inside Bloome — creating the Bloome EdgeSpark binding, implementing the booking backend (auth/db/storage/notifications), building the customer-facing public website that ships at the project's public URL, and shipping a working preview.
---

# EdgeSpark Full-Stack Build (Bloome control-plane flow)

> 🎯 **The deliverable is a public, shareable website** — a real URL (e.g. `https://<alias>.edgespark.app`, later a custom domain) that a customer can open in any browser **without logging into Bloome**, and complete the core flow (e.g. booking) there. This is what a "build me a site" merchant is paying for. A Bloome in-app widget is, at most, a secondary convenience surface — it is **never** the whole deliverable. **A project whose public root returns "Service Unavailable" / only serves `/api/*` is NOT delivered.** (See §5 and §7.)

> **Authoritative source of truth:** the bundled `bloome` skill's `references/edgespark.md` (the "EdgeSpark App Surface Guide") plus the official `building-edgespark-apps` and `edgespark-frontend-design` skills. **Read those before building.** This skill orchestrates that flow for a site/booking project — it does NOT replace those command references. If anything here ever disagrees with `references/edgespark.md`, follow `references/edgespark.md`. Canonical commands (`bloome-cli edgespark`, `widget create --edgespark`, `secret call`) come from the Bloome runtime's built-in `bloome` skill at `references/edgespark.md` (readable by the agent inside Bloome). When executing, use the exact commands given in `nextSteps`; run `--help` first to confirm subcommand names rather than guessing from the name alone. EdgeSpark serves a **full-stack** project's `web/` build output at the project root as the public site; a **server-only** project has no public site (root is unavailable) — so this build is **always full-stack** (see §1).

## When to Trigger

Mira routes here when the project enters build phase: a confirmed brief and Iris's design spec are ready. Also for adding a backend feature (new booking flow, auth, notifications) to an existing EdgeSpark-backed widget.

## Command Surface — keep these separate (critical)

- **Bloome control-plane (use this to create/track):** `bloome-cli edgespark project create/list/info/verify/delete`. If you only have a Bloome tool (not shell), pass the command body, e.g. `edgespark project create --alias <alias>`.
- **Official EdgeSpark CLI (only AFTER the Bloome binding exists, usually shown in `nextSteps`):** raw `edgespark pull` / `edgespark deploy`, plus the schema / type / app-implementation commands returned in `nextSteps`. (Use the exact commands `nextSteps` gives you — don't guess subcommand names.)
- 🚫 **Never run raw `edgespark project create` / standalone `edgespark init` for creation** — that hits the official CLI and prompts the human to log in instead of creating the Bloome binding. Creation always goes through `bloome-cli edgespark project create --alias`.

## Build Sequence

### 1. Create the Bloome EdgeSpark binding (first, always) — and make it FULL-STACK

```bash
bloome-cli edgespark project create --alias <alias>
```

This also generates the local `edgespark/<alias>/` scaffold. Use that directory; do not hand-create a parallel project or replace it with an empty `edgespark.toml`.

**Confirm the project is full-stack before building** (this is what makes the public site exist):

- Read `edgespark.toml`. A full-stack project has a `[web]` section (e.g. `path = "web"`, `output_path = "web/dist"`) alongside `[server]`. The default EdgeSpark template is full-stack.
- If the scaffold came up **server-only** (only `server/`, no `web/` and no `[web]` in `edgespark.toml`), follow `references/edgespark.md` / the `building-edgespark-apps` skill to enable the web surface (add the `web/` app) **before** writing feature code. Do not proceed server-only — a server-only project ships no public website.
- Keep server code in `server/` and the customer-facing site in `web/`; don't move files out of either.

### 2. Install official EdgeSpark skills + CLI if `nextSteps` asks

```bash
npx skills add edgesparkhq/agent-skills --yes
npm install -g @edgespark/cli@latest
```

Then read both before writing any EdgeSpark code:
`skills/building-edgespark-apps/SKILL.md` and `skills/edgespark-frontend-design/SKILL.md`.

### 3. Read the brief, scope the build

Parse `booking_config` (slot intervals, capacity, cutoff, form fields, confirmation/cancellation, notify targets, admin view) and the `must_have` list — every must_have is in v1 scope. Flag ambiguity to **Mira** (not the user) before building.

### 4. Backend (EdgeSpark `server/`) — auth / db / storage / notifications

- Backend-required workflows (bookings, list CRUD, ownership, "my/all" views, durable collections, queries, permissions, secrets, webhooks) are **EdgeSpark-backed by default** — do NOT build these on `ResonWidget.state` (state is only for tiny conversation-scoped JSON).
- Expose backend behavior on **public routes under `/api/public/<resource>`** (the Bloome bridge calls these). Example: `POST /api/public/bookings`, `GET /api/public/bookings/:id`, `PATCH /api/public/bookings/:id`.
- DB (Drizzle ORM via EdgeSpark): bookings table (slot, contact_ref, party_size, status, created_at) + brief extensions. **No PII in logs.** Validate + escape all user input before storing/templating (injection).
- Auth: minimum scopes; the Bloome viewer identity arrives via the `/api/public/_bloome/silent-sign-in` bridge — follow `references/edgespark.md` for the contract.
- Notifications: **sandbox/test mode first**; real sends only after Mira confirms with the user.

### 5. Frontend — build the PUBLIC website (primary), widget optional

Build the site to Iris's design spec (tokens for color/type/spacing; match layout; functional & faithful over pixel-perfect). There are two possible surfaces, and for web_studio the order is **not** negotiable:

- **① Standalone public EdgeSpark web app — DEFAULT and MANDATORY.** This is the customer-facing site that ships at the project's public URL (`https://<alias>.edgespark.app`, later a custom domain). It lives in `web/`, is a full-stack EdgeSpark app's frontend, and calls the backend with the `@edgespark/web` browser SDK — **not** the Bloome bridge, **not** bare `fetch`:

  ```ts
  // web/src/lib/edgespark.ts — one app-level singleton, import everywhere
  import { createEdgeSpark } from '@edgespark/web';
  import '@edgespark/web/styles.css';
  export const client = createEdgeSpark();
  ```

  ```ts
  // anywhere in the public site
  import { client } from "@/lib/edgespark";
  const res = await client.api.fetch("/api/public/bookings", { method: "POST", body: ... });
  ```

  Follow the `edgespark-frontend-design` and `building-edgespark-apps` skills for the exact `@edgespark/web` interface (`client.api.fetch`, `client.authUI.mount`, `client.auth`). Read `node_modules/@edgespark/web/dist/index.d.ts` for the real contract — don't guess.

- **② Bloome in-app widget — OPTIONAL, secondary.** Only build this _in addition_ when the brief explicitly wants an in-Bloome preview/management surface. It is never a substitute for ① and never the whole deliverable. The widget calls the **same** `/api/public/*` backend, but **only** via the injected bridge:
  ```javascript
  await ResonWidget.edgespark.fetch('/api/public/bookings', { method: 'POST', body: ... });
  ```

🚫 **Surface discipline (do not mix the two clients):** in the public web app use `client.api.fetch` (the `@edgespark/web` singleton); in a Bloome widget use `ResonWidget.edgespark.fetch`. **Never** hardcode the EdgeSpark host and **never** call bare `fetch('https://...edgespark.app/...')` in either. The `ResonWidget` bridge exists only inside a widget bound with `--edgespark <alias>`; the `@edgespark/web` client only works in the deployed web app served at the project root.

> Why ① is mandatory: a server-only project, or a widget-only delivery, leaves the public root returning "Service Unavailable" — the merchant has no link to put on 大众点评 / 名片 / 朋友圈. That fails the core promise. The public site is the deliverable; the widget is a bonus.

### 5b. Owner admin backend (`/admin`) — standard deliverable

Every project that collects submissions (bookings, leads, orders) **ships a private owner backend at `/admin`** — a route in the same `web/` app, so it lives at `https://<alias>.edgespark.app/admin`. This is part of "done," not an optional extra: the merchant needs somewhere to see what their customers submitted.

- **Single operator, no public registration.** Do **not** wire EdgeSpark's managed multi-user auth / sign-up for this. The admin credentials come from EdgeSpark **secrets** `ADMIN_USERNAME` / `ADMIN_PASSWORD`, with safe code fallbacks (`admin` / `edgespark`) so a fresh build works immediately. Declare the keys in `defs/runtime.ts` and read them server-side with `secret.get(...)`.
- **Auth = a signed, httpOnly session cookie.** The login route checks username + password (constant-time compare) and sets the cookie; every admin data route verifies it. Put admin routes under **`/api/public/admin/*`** and **self-guard each one** (reject when the cookie is missing/invalid) — the `/api/*` managed-auth gate is for end-customer login, not this operator. From the browser, call admin routes with `credentials: 'include'` so the cookie is sent (a wrapper SDK that omits credentials will 401).
- **What it shows:** every submission (newest first) with the key fields + basic status, and a **CSV export**. Brand-consistent — reuse the site's design tokens (same dark/accent palette + display font); it must not look like a generic admin template.
- **Changing the credentials is owner-only and agent-blind.** Never hardcode a real password or print one in chat. To change the admin username/password, register the secret keys so EdgeSpark returns a **secure browser URL where the owner types the new value** — the value never passes through the CLI, terminal, or any agent context (see the secret flow in `references/edgespark.md`). The code already reads from the secret, so changing it needs no code edit.

### 6. Payments (if in brief)

Sandbox/test keys only during build. Wire the intent/webhook flow. Document the live-key env var names but **do not insert live keys** — switching to production needs Mira → user confirmation.

### 7. Deploy, verify the PUBLIC URL, (optionally) bind widget

- Deploy with the official EdgeSpark CLI commands from `nextSteps` — during build/preview phases, deploy to the default or preview environment (do **not** set `EDGESPARK_PROJECT_ENVIRONMENT=production` at this stage). The typical flow is `edgespark pull` then `edgespark deploy` (which builds the `web/` frontend and serves it at the project root), run wrapped in the Bloome `secret call` that injects `EDGESPARK_API_KEY` (follow `references/edgespark.md` for the exact wrapper). **Production environment cutover is a Gate 5 (launch authorization) action only** — wait for Mira to confirm the user's explicit written authorization before switching to production (see Gate 5 in web-pm-orchestration).
- Verify the Bloome binding:
  ```bash
  bloome-cli edgespark project verify <alias>
  ```
- ✅ **VERIFY THE PUBLIC SITE IS ACTUALLY LIVE (required — do not skip, do not hand off without this).** After deploy, fetch the **public root URL** and confirm it serves the website, not an API error:
  ```bash
  curl -sS -o /dev/null -w "%{http_code}\n" https://<alias>.edgespark.app/   # expect 200, NOT 503 "Service Unavailable"
  curl -sS https://<alias>.edgespark.app/ | head -40                          # expect the site's HTML (title, hero), NOT a bare JSON/error
  ```
  Then confirm a core action works end-to-end on the **public** site (e.g. POST a test booking via `/api/public/...` from the deployed origin and read it back). If the root is 503 / blank / API-only, the build is **not** done — the project is likely server-only or the web build didn't deploy: go back to §1 (make it full-stack) and §5 (build the `web/` app), then redeploy. Never report a project as built while its public root is unavailable.
- **(Optional) Bind a Bloome widget — only if surface ② was requested** (see §5). The public site does not need this:
  ```bash
  widget create --title "<Site>" --html-file widgets/<name>.html --edgespark <alias>
  ```
- If any Bloome EdgeSpark command or `widget create/update --edgespark` returns `EDGESPARK_DISABLED`: **stop the EdgeSpark path**, do not retry raw EdgeSpark CLI, do not create an untracked external project. Tell the user (via Mira) backend support is temporarily unavailable.

### 8. Handoff to Mira

Lead with the **public shareable URL** — `https://<alias>.edgespark.app/` (the customer-facing site), confirmed returning 200 with the real page at the root (per §7). That URL is the headline deliverable; everything else is supporting detail. Then return: the booking flow confirmed end-to-end **on the public site**, the optional widget (only if built), env vars the user must set for production, what's built, v1 scope constraints, and key flows for Nova to test. If you cannot produce a working public URL, say so explicitly and report the blocker — do not present a widget-only result as a finished site.

## Boundaries

- Payments / real sends / production cutover require Mira → user confirmation. Never flip unilaterally.
- Out-of-`must_have` features are out of v1 scope — flag additions to Mira.
- Never store/log PII, credentials, or tokens — env vars / EdgeSpark secrets only.
- Complex systems beyond a typical site (full ERP, multi-tenant SaaS, financial transaction engines) are out of v1 — describe a realistic v1 and flag the rest to Mira.
