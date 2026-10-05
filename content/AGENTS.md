# Content instructions

- Preserve source inputs, expert notes, and feedback files.
- Apply human-approved, type-matched lessons from root `editorial-memory.yaml`;
  current source and expert notes remain authoritative.
- Keep generated artifacts outside `content/`.
- Never mark AI-created material approved or published.
- Read `STYLE_GUIDE.md` before drafting or substantially revising a question.
- Match depth to the expected interview duration.
- Treat the companion handbook as the source for foundational teaching. Apply
  the concept to the interview decision here and link the chapter by number and
  title instead of re-teaching it.
- Prefer primary technical specifications for claims that depend on a protocol,
  standard, language rule, or platform API. Never invent figures or citations.

## System design

- Draft with `$draft-system-design` and follow its chapter skeleton:
  short question with a bold crux, requirements with numbers, entities, API,
  a design built one requirement at a time with growing figures, "What is still
  broken", two or three deep dives, calibration, and follow-ups.
- Every chapter stands alone. Record `track_order`, `design_moves`, and
  `handbook_chapters` in metadata; introduce each move once in a callout; when
  reusing a move, re-explain it briefly and link the question by its title,
  never by number. Moves are defined in `taxonomy/design-moves.yaml`.
- Where the best design is non-obvious, show the simpler answers candidates give
  first and their costs before the refinement, and say when no option is perfect.
- Diagrams are Graphviz sources in `diagrams/*.dot` using the handbook palette
  roles (`new`, `warn`, `ok`, `store`, `ext`).
- `python -m tools.lint_readability` must report zero errors.
- Read the rendered chapter (`make sd-preview`) before declaring it done.

## Coding and fundamentals

- Coding answers include every declaration, member, header, and implementation
  step the candidate is expected to produce, without repeating what the prompt
  gives. Keep a coding chapter within six rendered pages.
- Limit improvements and follow-ups to the three most realistic items each.
- Fundamentals entries prioritise technical learning and runnable experiments;
  interview advice is supplemental.
