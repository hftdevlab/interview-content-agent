# Expert notes

No expert notes were supplied during ingestion.

## Human feedback 20260814T064547Z

## Diagnosis  
The chapter reads like a **specification**, not a tutorial. Almost every sentence is in normative voice ("The service acknowledges acceptance only after that version is committed…"). Specs are written for someone who already knows the design and needs the exact rules; tutorials are written for someone constructing the design in their head for the first time. The section header says "Candidate reasoning," but the prose underneath is conclusions, not reasoning.  
Concretely, six things are going wrong:  
**1. No physical anchor.** The nouns are all abstract — authority, generation, scope, materializer, dispatcher. The reader has nothing to hold. Compare the market-data chapter, which is markedly easier to read for exactly one reason: its nouns are physical. Packets, NICs, cores, A and B lines. You can picture them. "Fenced version authority" you cannot picture. The fix isn't fewer abstractions, it's attaching each one to something that exists on a machine.  
**1. No physical anchor.** The nouns are all abstract — authority, generation, scope, materializer, dispatcher. The reader has nothing to hold. Compare the market-data chapter, which is markedly easier to read for exactly one reason: its nouns are physical. Packets, NICs, cores, A and B lines. You can picture them. "Fenced version authority" you cannot picture. The fix isn't fewer abstractions, it's attaching each one to something that exists on a machine.  
**2. No running example, anywhere.** There is never a moment like: *at 10:31:04 a risk manager cuts strategy S7's AAPL position limit from 10,000 to 5,000 shares; S7 currently holds 8,200 and has working orders.* One such scenario, referenced throughout, would let every subsequent rule land. "The gate reads either version v or v+1, never a mixture" is abstract; "the gate must never see the new max position paired with the old max notional" is immediate.  
**3. The instruction to stay symbolic leaked from the contract into the exposition.** The prompt says *don't invent a fixed latency, scale, or stale-limit action* — correct, those are clarification questions. But the model generalized that to "never use a number for anything," which is why sizing appears as U * p * N * S and nothing else. Plugging in illustrative values would teach the most important thing in the chapter and currently doesn't: 1,000 strategies × 50 updates/sec × 200 bytes ≈ 10 MB/s. This system is **not** bandwidth-constrained. Every hard part is correctness and tail behavior. That reframing is invisible right now.  
**4. The naive design is dismissed in two sentences instead of being executed and broken.** "The tempting design is 'publish updates through a broker and retry'" is the seed of what should be the chapter's best section: draw it, walk a scenario through it, watch it fail in a specific way, and let the invariant fall out of the wreckage. Deriving the answer from a failure is how a reader learns to derive answers. Being handed the answer teaches them to recognize one.  
**4. The naive design is dismissed in two sentences instead of being executed and broken.** "The tempting design is 'publish updates through a broker and retry'" is the seed of what should be the chapter's best section: draw it, walk a scenario through it, watch it fail in a specific way, and let the invariant fall out of the wreckage. Deriving the answer from a failure is how a reader learns to derive answers. Being handed the answer teaches them to recognize one.  
**5. Terminology arrives before definition.** The first architecture diagram is eight component names, and roughly seven contain a term the reader hasn't met — *fenced*, *materializer*, *generation*, *epoch*. A reader who doesn't already know the answer can't parse the diagram, which means the diagram serves only readers who don't need it.  
**5. Terminology arrives before definition.** The first architecture diagram is eight component names, and roughly seven contain a term the reader hasn't met — *fenced*, *materializer*, *generation*, *epoch*. A reader who doesn't already know the answer can't parse the diagram, which means the diagram serves only readers who don't need it.  
**6. Uniform density.** Every sentence carries the same informational weight. Readable technical writing alternates: a dense claim, then a lighter restatement or example, then the next claim. Twenty pages at constant maximum density is exhausting regardless of how correct it is.  
**6. Uniform density.** Every sentence carries the same informational weight. Readable technical writing alternates: a dense claim, then a lighter restatement or example, then the next claim. Twenty pages at constant maximum density is exhausting regardless of how correct it is.  
One more, worth calling out separately: **the best idea in the chapter is buried.** "Freshness is separate from change frequency — a scope may receive no changes for hours while its limits remain valid" is the insight that distinguishes a strong candidate from a passing one, and it appears mid-paragraph in deep dive 2. Same for "sent is not applied." These are the load-bearing ideas and they're delivered as asides.  
One more, worth calling out separately: **the best idea in the chapter is buried.** "Freshness is separate from change frequency — a scope may receive no changes for hours while its limits remain valid" is the insight that distinguishes a strong candidate from a passing one, and it appears mid-paragraph in deep dive 2. Same for "sent is not applied." These are the load-bearing ideas and they're delivered as asides.  
Also: the chapter contains far more than 45 minutes of material with no signal about what's core versus extension. A reader can't tell while reading which parts are Pass-tier and which are Exceptional-tier. The rubric knows the difference; the body doesn't mark it.  
## Generalizable feedback for the generator  
These are written as rules that apply to any chapter, not just this one:  
1. **Open with a concrete scenario before any architecture.** 3–5 sentences, named entities, real numbers, and a stated stake — what specifically goes wrong in the world if this system fails. Reference that same scenario throughout the chapter rather than introducing new ones.  
2. **Symbolic contract, concrete exposition.** Keeping latency targets and policy decisions unspecified is correct. Refusing to use illustrative numbers in explanation is not. Use plugged-in values marked "illustrative," and follow each with what the number *teaches* (which resource is actually scarce).  
3. **Prefer physical nouns.** When you introduce an abstract component, immediately name what it is on a machine — a process, a thread, a file, a queue, a shared-memory region. "A materializer builds immutable snapshots" → "a background process reads the log and writes a complete limit table to a file, one per version."  
4. **Break the naive design in full before presenting the good one.** Draw it, run the scenario through it, show the exact step where it produces a wrong outcome. The invariant should read as the *conclusion* of that trace, not as a premise.  
5. **Lead each section with its thesis, then the mechanism, then why the mechanism is sufficient.** Currently the sharpest formulations arrive mid-paragraph, after the supporting detail. A useful check: read only the first sentence of each paragraph in sequence. If those sentences don't form a coherent argument on their own, the theses are buried.  
6. **Define on first use, in plain language, before the term enters a diagram or a list.** One clause is enough: "a fencing token — a number that increments on every leader change, so an old leader's writes are rejected."  
7. **Vary density deliberately.** After each dense normative paragraph, add a lighter one: an example, a restatement in different words, or the failure it prevents. Uniform density is the main reason this reads as unapproachable rather than as difficult.  
8. **Show forks, not only verdicts.** Where two designs are defensible, present both and adjudicate. The paragraph arguing why durable append precedes the success response is the strongest in the chapter precisely because it argues rather than asserts — that paragraph is the model for the rest.  
9. **Diagrams need edges and failure annotations.** The flat node lists in this chapter carry no information a sentence didn't already carry. The reconnect sequence diagram in deep dive 3 does work, because it has a timeline and shows a state transition. Make all diagrams do that, or drop them.  
10. **Tier the content inline.** Mark sections as core / deep dive / stretch so a reader can calibrate against the 45-minute budget. Right now the rubric at the end is the only place that distinguishes Pass from Exceptional, and by then it's too late to have read differently.

## Human feedback 20260814T095144Z

The tutorial rewrite is a substantial improvement and its core technical direction should be preserved. Address these remaining reader-facing issues:

1. The rendered invariant leaks literal `>` blockquote markers into the PDF. The publisher now supports blockquotes; keep the invariant readable and verify the generated PDF rather than only the Markdown.
2. The context diagram combines the already-explained naive path with the derived architecture, creating crossing arrows and a very wide, shallow graph. The prose already executes the naive failure. Make this diagram show only the physical good path, with labeled edges for command, quorum commit, committed-log tail, authority proof, bounded delivery, atomic publication, and the failure action when proof or queue bounds expire.
3. Put each diagram after the complete reasoning unit it explains. In particular, place the good-path diagram after the receiver publication mechanism and place the recovery sequence after the paragraph that completes recovery. Avoid leaving a half-empty portrait page immediately before a forced landscape diagram.
4. Keep normal 13-point body leading. Trim repetition if needed to stay within the ten-page budget; do not make the prose denser merely to pass the numeric gate.
5. In the freshness protocol, keep the authority-originated proof and make the anti-replay boundary explicit: a challenge nonce or equivalent strictly fresh proof identity must prevent a dispatcher from stockpiling old proofs and extending freshness after authority isolation.

Do not add another diagram or expand the scope. Keep improvements and follow-ups at three each.

## Human feedback 20260814T101645Z

The technical review otherwise passes. Make only these final presentation fixes:

1. Page 7 is mostly empty before the good-path landscape diagram. Condense repetition within `Build the minimal correct path`, `Version the command`, and `Publish at the enforcement point` so the entire core good-path explanation ends on the preceding portrait page. Preserve every decision, but merge repeated statements about acceptance, atomicity, and `SENT` versus `APPLIED`. Keep normal body leading.
2. Use a normal paragraph beginning `**Derived invariant.**` rather than a blockquote for this chapter. The publisher supports blockquotes globally, but this short invariant does not need a bordered callout and the current page transition obscures the next page's running furniture.
3. Narrow the recovery sequence to the authority-isolation claim. Show the receiver's fresh `n902` challenge, the dispatcher forwarding it to the sequencer, and that request failing because the authority link is down; then show watchdog expiry. Remove reconnect/snapshot steps from this diagram because recovery is already explained in prose. Update the caption and alt text to match the narrower claim.
4. Rebuild and visually inspect every page. The running header and complete footer must be visible on every portrait and landscape page. The publisher now keeps short tables together to prevent the split seen at the bottom of the failure table.

Do not add concepts, diagrams, improvements, or follow-ups.

## Human feedback 20260814T113820Z

The chapter content and diagrams pass the last technical review. The remaining running-furniture finding was a viewer-side crop, not a PDF defect: the source raster files have identical populated header regions on every portrait page, and `pypdf` locates the full guide title at the correct top coordinate and the full footer at the correct bottom coordinate on every non-cover page.

The publisher now paints running furniture after page content and `validate_pdfs` enforces its positioned presence on every page. Do not change the chapter or compress it further. Rebuild, run the deterministic PDF validator, and re-review the actual PDF evidence. Do not report a crop in an inspection surface as missing PDF content when the raster pixels and positioned text prove otherwise.

## Human feedback 20260814T120141Z

No chapter or diagram change is requested. The prior automated review was interrupted while attempting unavailable display tooling. The controller and parent-level PDF workflow have completed raster QA, and the deterministic PDF validator passes page budgets plus positioned running furniture on every page.

Run the independent review using the existing PDF with pypdf/pdfplumber, generated SVGs, and deterministic gate results. Do not invoke browser, image, screenshot, or raster-rendering tools from the read-only review sandbox. A display-tool limitation is not a content failure.
