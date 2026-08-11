# Phase 1 validator specification

Deterministic checks, specified from **observed defects** rather than from theory. Each entry names the run that produced it.

Principle from C0-11: a defect that a careful prose reviewer misses but a script catches for free is exactly what belongs here. Prose review is expensive and inconsistent; scripts are neither.

---

## V-01 · Callback markers present
**Source:** C0-11 F-1 (major)
**Check:** if the chapter has prerequisites in `curriculum.yaml` and its body references any of them, at least one `<!-- CALLBACK: [id] -->` marker must be present. All marker IDs must exist in `curriculum.yaml`.
**Severity:** major. **Why mechanical:** a prose reviewer reads for meaning and does not notice absent comments.

## V-02 · Normative claims have resolved references
**Source:** C0-11 F-4 (minor, silent)
**Check:** every `normative` claim in the brief maps to a reference entry containing no placeholder marker (`*(Stage 1...)*`, `TODO`, `pending`).
**Severity:** major once a source pack exists; warning until then.
**Why mechanical:** the draft reads as authoritative either way — this is the failure mode most likely to survive review.

## V-03 · Empirical claims have an experiment or a label
**Source:** plan §5, `c5` trap design
**Check:** every `empirical` claim either maps to an artifact of type `benchmark`/`test`, or the body contains an explicit statement that the quantity is unmeasured here.
**Additional heuristic:** flag numeric latency/ratio patterns (`Nx slower`, `N ns`, `N%`) appearing within an `empirical` claim's scope with no linked artifact. Review, not auto-fail — quoted vendor figures are legitimate when cited.
**Severity:** blocker.

## V-04 · Focus share
**Source:** plan §4.1
**Check:** word count of sections tagged as focus ≥ 40% of prose; no other single section > 20%.
**Severity:** warning — heuristic, and section tagging is imperfect. Triage signal, not a gate.

## V-05 · Unresolved markers
**Check:** no `[VERIFY]`, `[TODO]`, `[AUTHOR]` in a chapter proposed for publication. `<!-- CALLBACK: -->` is exempt (it is a deferred-work marker, not an unresolved one).
**Severity:** blocker.

## V-06 · Cross-reference integrity
**Check:** every `[id]` reference resolves to `curriculum.yaml`. Every prerequisite listed in the header appears there. No chapter references a prerequisite that comes later in publication order.
**Severity:** blocker.

## V-07 · Section order and required sections
**Source:** contract §2
**Check:** required sections present, in order, with conditional sections in their specified positions. Conditional sections present if and only if their brief switch is set.
**Severity:** major.

## V-08 · Quiz format
**Source:** round 3 feedback (3.1)
**Check:** if `include_quizzes`, exactly two quizzes; no italic `*Testing:*` line between the heading and the question; each answer in a blockquote.
**Severity:** minor.

## V-09 · Prose length band
**Source:** contract §4
**Check:** prose word count within the band for the chapter's difficulty. Worked traces, quizzes, and code blocks excluded.
**Severity:** warning.

## V-10 · Code artifacts build
**Source:** plan §9
**Check:** every artifact typed `compile`, `runnable`, `test`, or `benchmark` extracts and builds. `test` artifacts pass. `illustrative` artifacts are exempt from building but must carry a banner.
**Severity:** blocker.

## V-11 · Sequencing hazards written out
**Source:** C0-11 F-2, author decision round 4
**Check:** every `sequencing_hazards` entry in the brief appears in the chapter as an **ordered list** (not prose), with the violation failure described. Heuristic: locate an ordered list containing the declared step terms within the same section as the hazard's subject.
**Severity:** major.
**Why mechanical:** the C0-11 draft included the hazard by inference. Inference is unstable output — the point of the field is that the same brief produces the same chapter on every run.

## V-12 · Venue-specific content placement
**Source:** author decision round 4
**Check:** if `venue_specific_content.include`, the material sits in an `optional`-layer section or appendix, never in `core`. Every venue-specific claim maps to a resolved (non-placeholder) source. Simplified illustrations carry a "simplified" label.
**Severity:** major.

## V-13 · Figures exist and resolve
**Source:** round 11
**Check:** no `> **Figure fig-...**` placeholder blockquotes remain in a chapter proposed for publication. Every markdown image reference resolves to a file that exists and parses as XML. Every SVG carries the three comment fields from `standards/diagram-style.md`.
**Severity:** blocker for publication, warning in draft.
**Why mechanical:** a chapter with a missing figure reads as complete, so prose review does not notice the absence.

## V-15 · Figure text fits
**Source:** round 12
**Check:** `build/lint_figures.py` — no text overflows the viewBox given its anchor, none falls below the bottom edge, none is under 10.5px.
**Severity:** blocker.
**Why mechanical:** the SVG is valid and parses cleanly with the text clipped; the defect only appears in rendered output. 37 instances existed in the first figure pass.

## V-14 · No formulaic openers
**Source:** round 11, contract §3.7
**Check:** flag any sentence of 8+ words appearing verbatim at the start of the same section in three or more chapters.
**Severity:** minor.
**Why mechanical:** repetition across chapters is invisible when reviewing one chapter at a time — the same blind spot as the module-level findings.

---

## Deliberately not automated

- **Whether the derivation is correct.** V-04 counts words; it cannot tell whether the reasoning is sound.
- **Whether a quiz tests the right thing.** Format is checkable, pedagogy is not.
- **Whether the opening scenario is imaginable.** The failure mode is an abstract statement wearing concrete nouns, which no regex detects.
- **Whether the relevance filter was applied.** Judgment, and per C0-11 F-3 the rule itself is not yet fully specified.

These stay with human and model review. The validators exist to stop reviewers spending attention on things a script does better.
