# A visible experiment for one unresolved question

Use the retained preview-shell.html for quick, self-contained experiments. It provides neutral tokens, simple components and optional variant controls, not the information architecture. Existing approved visuals take priority over the shell's defaults.

## Choose only the necessary experiment

A structure experiment compares organization while holding real content and base visual language constant. A style experiment preserves task and information architecture while exploring typography, rhythm, color roles, material and image treatment. An interaction experiment compares controls/feedback with the same business outcome. Declare comparison_type. A new surface or changed core structure always shows at least two structure variants before any visual work. The visual step shows one reference-aligned version when the user supplied a reference, otherwise at least two style variants. Two style variants are two answers, not two tints: task, structure and content stay identical while at least two visible mechanisms differ enough to survive the exchange check. Local edits and inherited design systems keep their confirmed direction without a new comparison.

Describe the tradeoff in ordinary language and recommend one. Keep the preview switch labels as 方案 A / 方案 B so candidates stay comparable. Shared DOM, reusable components and theme tokens are valid for style alternatives, but a pair whose only difference is those tokens is one direction, not two: unify the palettes or strip color and the two candidates must still be easy to tell apart. Two dark/light extremes are not obligatory. The same assets/content must be used so quality differences do not bias the comparison.

## Lightweight construction

Show enough of the first screen, representative content and key state to resolve the question. Use real content or clearly marked synthetic records. No production database, real sending, payment or fake connected service. Make controls real only when testing interaction. Check basic rendering and navigation; avoid full production testing before the decision is stable.

Keep readable Chinese system fonts, coherent icon use, keyboard access, meaningful focus and bounded long text. Pure expressions such as radius/shadow/animation are design choices, not universally mandatory values. Use the craft reference as a context-aware review, not a recipe gate.

## Deliver a visible version

Both choice stages — the two structure skeletons first, the style candidates later — are delivered as a page opened in a browser, not as a path the user has to open. Render each candidate yourself first and look at the actual layout and the 方案 A / 方案 B switch before describing it. When the runtime is on the user's own machine, open the page for the user with the host's browser or system open command. If the host has no browser at all, say so and use the visible fallback below.

Before a style handover, run `design.py check-preview --file <preview> --summary` and fix what it blocks: a pair that differs only in colour, or in a single mechanism axis, is one direction with two palettes. When it reports the preview as not scoped, judge the exchange check on the render itself and say what differed; "not applicable" is not a pass.

Coordinate with builder to register the artifact/version/audience using project.py preview. Prefer the host's actual embedded surface, then an authorized accessible URL or usable file. Screenshots are a fallback; state that interaction has not been experienced. Opening a page shows what you saw; it is not evidence that a remote user can reach it, so an OS open command and an agent-local localhost URL do not establish user access. No private-data upload to solve access without authorization.

Stop only when a material decision needs the user's answer. Reuse references already provided. Do not mechanically ask another reference question or regenerate a stage already decided. A user may accept the recommendation. Record the decision object and its version, not a requirement for unique wording.

## Inherit, then productionize

Preserve selected tokens, layout relationships, content and visual behavior. Keep an explicit inventory of real/simulated/missing capabilities. Experimental DOM glue, hardcoded data and fake success do not become production logic unchanged. Capture requested adjustments as observable acceptance targets. Return one receipt to builder; do not orchestrate another skill.
