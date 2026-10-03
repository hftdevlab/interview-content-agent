# Content instructions

- Preserve source inputs and expert notes.
- Apply human-approved, type-matched lessons from root `editorial-memory.yaml`;
  current source and expert notes remain authoritative.
- Keep generated artifacts outside `content/`.
- Never mark AI-created material approved or published.
- Read `STYLE_GUIDE.md` before drafting or substantially revising a question.
- Treat the question templates as coverage guidance, not a reason to force
  every answer into the same checklist.
- Teach the reasoning behind the solution. For system design, follow the current
  STYLE_GUIDE progression: question/clarifications, functional/non-functional
  requirements, entities, useful interfaces, architecture, then focused deep
  dives. Develop one design; comparisons, improvements, and follow-ups are
  optional. Do not force an invariant-led specification or evaluator rubric.
- Use a first-person instructor voice for system-design tutorials, not a
  candidate answer script. Teach how and why we develop the design. Derive
  central choices rather than stacking conclusions: motivate entities, explain
  data flow before the architecture diagram, and connect workload to interface
  and storage choices. Keep scope focused without hiding defining challenges
  behind artificially small assumptions. See STYLE_GUIDE for teaching criteria.
- Teach for hedge-fund, trading, and finance engineers. Explain material domain
  differences at the decisions they affect without changing the raw prompt or
  treating every internal system as a trading hot path. State priorities and
  assumptions; availability must not imply accepting unsafe financial state.
- Tag the reusable system-design challenges using `design_patterns` from the
  controlled taxonomy, and explain their application where they affect a choice.
- Match answer depth to the expected interview duration.
- Keep a coding chapter within six rendered pages. Keep a typical system-design
  chapter within ten pages and an unusually complex one within fourteen.
- Limit improvements and follow-ups to the three most realistic items each.
- Coding answers must include every material declaration, class member, header,
  and implementation step the candidate is expected to produce, but do not
  repeat headers or types already given in the prompt.
- For oversized system-design prompts, state the whole-system boundary and
  explicitly agree on a small number of deep dives. Do not prescribe a
  minute-by-minute answer schedule.
- Treat the companion handbook as the default source for foundational teaching.
  Apply those concepts to the interview decision here; link to the relevant
  handbook chapter or a primary external source instead of re-teaching it.
- Fundamentals entries should prioritize technical learning and runnable
  experiments; interview advice is supplemental.
- Prefer primary technical specifications for claims that depend on a protocol,
  standard, language rule, or platform API.
