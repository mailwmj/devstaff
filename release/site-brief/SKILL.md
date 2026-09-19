---
name: site-brief
description: Clarify a nontechnical user's core website task, scope, data ownership and high-impact unknowns. Use for new tasks or changed scope, not repeated questions on local edits.
---
# Task and scope discovery

Read the shared protocol at the sibling site-builder/references/AGENTS.md (installed), or ../AGENTS.md (source bundle). Apply its user-language guidance. 

Do not write product source. Clarify who uses the site, their one main task, observable completion and first-version exclusions. Use the user's real example before inventing an abstract data model.

Ask only questions whose answers affect the first version, costly rework or risk. Ask up to 3-5 independent questions when needed, fewer when enough is known; give plain-language options and a recommendation. Do not ask users to choose frameworks or databases. Record reversible defaults as assumptions. Stop when remaining questions would not change the task.

Keep facts, confirmed decisions, assumptions and unresolved confirmations separate in `.site/brief.md`, with sources and stable BR IDs where helpful. Replay the scenario: actor, input, action, visible result, likely failure and recovery. Include where data comes from, who sees/changes it, whether reload or changing devices must preserve it and whether there are real external effects.

For marketing/content pages start with audience, action, promise and objections. A lead form still requires a recipient/storage/privacy boundary; the landing-page exception does not erase data risks. Never invent testimonials, metrics or customer logos.

Reuse existing reference URLs, screenshots, brand materials and answers. Research only facts affecting feasibility/scope/risk; external facts don't become user decisions. Visual reference analysis belongs to site-design. When blocked, return the gap to builder instead of invoking another skill.

Return one receipt: status ready/needs_user/blocked, summary, artifacts, evidence, limitations. The user sees only the useful question/result, not the internal receipt fields.
