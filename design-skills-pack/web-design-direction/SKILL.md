---
name: web-design-direction
description: Use when a client site needs a visual direction set and a complete design deliverable produced — covering style direction, clickable HTML mockup, page structure, design tokens, responsive breakpoints, component states, copy sourcing, asset mapping, and visual acceptance criteria. The output is packaged for Mira to pass to Mike so he can build to visual spec.
---

# Web Design Direction

## Upstream

- pbakaus/impeccable (SKILL.md): systematic instructions for high-finish design language — makes "looks professional" repeatable and principled.
- nextlevelbuilder/ui-ux-pro-max-skill (SKILL.md): 50+ style presets, color systems, and type pairing library for UI/UX work.
- edgespark-frontend-design: edgespark-specific, anti-generic frontend art direction. **Bundled directly in this workspace at `skills/edgespark-frontend-design/`** so it is guaranteed available at design time (it is also part of the EdgeSpark agent-skills bundle Mike uses at build).
- impeccable + ui-ux-pro-max are vendored via skills-lock.json; edgespark-frontend-design is bundled in-workspace. All three are used in combination, not in isolation.

## When to Trigger

- A new client project needs a visual direction before Mike starts building.
- The client has content and structure but the site has no defined look and feel yet.
- A redesign is needed and the visual direction must be re-established from scratch.
- Mira needs a complete design spec package to hand to engineering.

## How to Use

1. **Gather context first.** Understand the site's purpose, target audience, industry vertical, and any existing brand assets (logo, colors, fonts, existing site). If assets exist, extract and respect them. If not, build from principled defaults.

2. **Draw on the design skills in combination (mandatory — this is what prevents cookie-cutter output).**
   - **`impeccable`** — establish the design language baseline: finish level, visual density, typographic hierarchy. (Always vendored.)
   - **`ui-ux-pro-max`** — select a concrete style direction and type pairing appropriate to the client's vertical and tone, from its 50+ presets. (Always vendored.)
   - **`edgespark-frontend-design`** — apply edgespark-specific, anti-generic art direction (visual thesis, one unforgettable move, anti-pattern bans, motion). **It is bundled in this workspace at `skills/edgespark-frontend-design/` — so you MUST load and apply it at design time, every time.** Read its `SKILL.md` and the relevant sections of `references/design-principles.md`, and bake its anti-generic doctrine into the directions. There is no "not available at design time" excuse anymore — it ships with you.
   - **Always state which design skills you applied** in the deliverable (expect all three: impeccable + ui-ux-pro-max + edgespark-frontend-design). Only if a bundled file were genuinely missing would you note it and proceed on the other two — but never silently produce default-template output.

3. **Offer 1–2 distinct style directions.** Each direction should have a name, a one-sentence tonal description, and a rationale for why it fits this client. Give the client a real choice — not minor variations on the same approach.

   **Deliver each mockup as a clickable Bloome widget for review.** Post the self-contained HTML mockup so it renders inline in the chat as a widget the owner can click through immediately — this is the cheapest, fastest way to validate the _feel_ before any build. The widget here is a **design-review preview only**; it is NOT the final deliverable. The shipped product is still a standalone public web app served at the EdgeSpark project root (Mike builds that from your spec — see edgespark-fullstack §5). Don't let the review-widget's styling constrain the real build.

4. **Once direction is confirmed, produce the full deliverable** (see Output section below).

## Output: Complete Design Deliverable

This package is the visual spec packaged for Mira to pass to Mike for implementation. It must be complete enough that engineering can build without guessing at design intent.

### 1. Style Direction Summary

- Chosen direction name and tonal description.
- Rationale: why this style fits the client's audience and product.
- Reference aesthetic (3–5 descriptive words, e.g., "editorial, airy, high-contrast").

### 2. Clickable HTML Mockup

- A self-contained HTML file (inline CSS, no external dependencies) demonstrating the actual visual feel.
- Shows: headline typography at size, body text in context, primary color in use, spacing rhythm, at least one interactive state (hover or active).
- Purpose: to validate the feel before Mike writes production code. Not a wireframe — it should look close to the finished site.

### 3. Page Map

- Ordered list of all pages in the site (e.g., Home, About, Pricing, Blog, Contact).
- For each page: one-line purpose statement and conversion priority (primary / secondary / utility).

### 4. Section Inventory

- For each page: ordered list of sections with name, content type, and layout pattern.
- Example: `[Hero] — headline + subhead + primary CTA + product screenshot, full-width, centered`.
- Flag any sections that require dynamic data or CMS content.

### 5. Design Tokens

- **Color**: Primary, secondary, accent, background, surface, text (primary/secondary/disabled), error, success, warning — each with hex value and usage note.
- **Typography**: Font families (heading / body / mono if applicable), scale (size + line-height + weight for each level: Display, H1–H4, Body, Caption, Label), and letter-spacing where relevant.
- **Spacing**: Base unit and scale (e.g., 4px base: 4, 8, 12, 16, 24, 32, 48, 64, 96).
- **Border radius**: Standard values per component tier (button, card, input, modal).
- **Shadow**: Elevation levels (flat, low, mid, high) with CSS values.

### 6. Responsive Breakpoints

- Defined breakpoints with pixel values and layout behavior at each (e.g., single-column vs. grid, nav collapse, hero text size).
- Minimum: mobile (≤ 640px), tablet (641–1024px), desktop (≥ 1025px).
- Flag any sections with significantly different mobile layout vs. desktop.

### 7. Component States

For each interactive component type present in the design (buttons, inputs, links, cards, nav items):

- Default, hover, active/pressed, focus, disabled.
- Error and empty states for form inputs.
- Loading state for any section that fetches data.
- Skeleton/placeholder pattern for async content.

### 8. Copy Source

- For each section: specify whether copy is (a) provided by client, (b) placeholder to be replaced, or (c) AI-drafted for client review.
- Flag any sections where copy length significantly affects layout (e.g., hero headline, pricing card descriptions).
- Provide character/word count targets for placeholder zones.

### 9. Asset Map

- Table mapping each image/media element to its section and slot.
- For each asset: slot name, section, expected dimensions, source (client-provided / stock / AI-generated / icon library), and format.
- Flag missing assets that block layout completion.

### 10. Visual Acceptance Criteria

- Checklist Mike and Nova use to verify the build matches the spec.
- Covers: color accuracy (hex match), type scale match, spacing match, responsive behavior at each breakpoint, interactive state rendering, accessibility (WCAG AA contrast minimum), and asset resolution.

## Anti-Generic Litmus (run before every handoff to Mira)

The whole point of this team's design step is that each client's site looks like _theirs_, not like an AI template. Before handing the deliverable to Mira, the mockup must pass all of these — if any fails, redo the direction, don't ship it:

- **Not the default skeleton.** It is NOT the reflexive "gradient hero + 3-up feature cards + testimonial row + CTA band" in that order unless the brief genuinely calls for it.
- **Not the default typeface/accent.** Not Inter-on-white with a `#6366f1`/generic-purple accent. Type and color are chosen for _this_ brand/vertical/tone.
- **A concrete direction, named.** The chosen direction is a specific extreme (editorial / luxury / industrial / playful / organic / brutalist / retro-futuristic / …) tied to the brief — not "clean modern".
- **Brand/spec signal is visible.** The look reflects something specific from the brief (industry, audience, existing brand assets, tone). Pull the relevant signals from `intake-brief`; if they're thin, ask Mira for more before designing rather than inventing a generic look.
- **The swap test.** If you could drop a different client's name/logo onto this mockup and it would look equally at-home, it's too generic — push the direction further.
- **No emoji as UI or decoration.** Emoji used as icons, bullets, stat markers, or hero accents read cheap and amateur — banned in the mockup and the shipped build. Use a real icon set, typography, and imagery instead.
- **Real placeholder imagery, never empty boxes.** Where client photos are missing, **search for representative stock/placeholder images** that fit the vertical and the slot, sized to the real content, so the mockup looks like a finished site — not gray rectangles, lorem-only blocks, or emoji stand-ins. Record each in the Asset Map with its source.

State in the deliverable which design skills were actually applied (impeccable / ui-ux-pro-max / edgespark-frontend-design) so Mira and Nova can confirm the anti-generic pipeline ran.

## Boundaries

- Design direction and visual spec only. Backend architecture, API design, and infrastructure are Mike's domain — do not cross into them.
- Final style decisions rest with the client. Present with reasoning; do not override their preference.
- If brand assets or content are missing, use clearly labeled principled placeholders. Do not invent brand colors or assume a logo exists.
- Handoff goes to Mira, who coordinates with Mike. Do not assign implementation tasks directly.
