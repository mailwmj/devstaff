---
name: site-brief
description: Clarify a nontechnical user's core website task, scope, data ownership and high-impact unknowns. Use for new tasks or changed scope, not repeated questions on local edits.
---
# Task and scope discovery

Read the shared protocol at the sibling site-builder/references/AGENTS.md (installed), or ../AGENTS.md (source bundle). Apply its user-language guidance. 

Do not write product source. Clarify who uses the site, their one main task, observable completion and first-version exclusions. Use the user's real example before inventing an abstract data model.

For a new website the first user-visible reply is the questions, not a plan or a direction summary. List the unknowns that can change the first version, cross off what the user already stated, and ask the rest as one round of 3-5 questions with plain-language options and a recommendation, so one "use your recommendations" answers them all. "I can infer it" is not "the user stated it": brand name, contact/conversion channel, visual preference and first-version exclusions are asked or explicitly assumed, never silently inferred. Do not ask users to choose frameworks or databases. Details that cannot change the first version stay assumptions.

Record the result in `.site/brief.md` as a fenced `brief` block before confirming direction:

```brief
{
  "facts": {
    "audience":   {"value": "个人养猫用户", "source": "assumed", "asked": true},
    "main_task":  {"value": "看猫玩具并咨询下单", "source": "user"},
    "conversion": {"value": "加微信咨询", "source": "assumed", "asked": true}
  },
  "assumptions": ["购买入口按加微信处理"],
  "exclusions": ["首版不做在线支付"]
}
```

`source` is `user` (the user said it), `reused` (an earlier confirmed answer or existing material) or `assumed` (a disclosed default). An assumed fact requires `"asked": true` and at least one plain-language line in `assumptions` that you show the user when confirming direction. Schema revision 3 refuses `decide` without a valid block; `state.py migrate` seeds one for legacy projects.

Keep facts, confirmed decisions, assumptions and unresolved confirmations separate in `.site/brief.md`, with sources and stable BR IDs where helpful. Replay the scenario: actor, input, action, visible result, likely failure and recovery. Include where data comes from, who sees/changes it, whether reload or changing devices must preserve it and whether there are real external effects.

For marketing/content pages start with audience, action, promise and objections. A lead form still requires a recipient/storage/privacy boundary; the landing-page exception does not erase data risks. Never invent testimonials, metrics or customer logos.

Reuse existing reference URLs, screenshots, brand materials and answers. Research only facts affecting feasibility/scope/risk; external facts don't become user decisions. Visual reference analysis belongs to site-design. When blocked, return the gap to builder instead of invoking another skill.

Return one receipt: status ready/needs_user/blocked, summary, artifacts, evidence, limitations. The user sees only the useful question/result, not the internal receipt fields.
