# Before and after

Real passages from the October 2026 pilot drafts, and how the same content was
rewritten. The "before" text is technically correct. It fails the reader.

---

## 1. The question introduction

**Before** (notification system, 4 paragraphs, ~390 words before the first requirement):

> Design a notification system that lets an application tell a user about something that needs their attention. For example, Maya comments on a document owned by Leo. Leo should find the notification in the application and, if his preferences allow it, receive email and mobile push alerts.
>
> I want to begin with what "notify" means to Leo. An inbox item remains available when he next opens the application; email and push try to draw his attention outside it. Those are different promises, even though they start with the same comment. We will interpret the open-ended prompt as **in-app, email, and mobile push**. Before choosing infrastructure, settle who chooses recipients, whether occasional duplicate alerts are acceptable, and whether delivery has a deadline. …
>
> For this walkthrough, we assume each request names one recipient, the calling application chooses that recipient, and messages are informational. … The caller retries unacknowledged requests. The notification system takes responsibility once it accepts a request; … These are illustrative assumptions, not requirements supplied by the original prompt.
>
> A complete platform with bulk campaigns, scheduling, and multiple regions exceeds one interview. … To keep capacity decisions concrete, use an illustrative busy workload of 1,000 notifications/s …

**What is wrong:** the reader meets retry ownership, scope cuts, and workload
numbers before learning what the system is for or what makes it hard. "Illustrative"
appears three times. There is no crux.

**After** (~110 words, then requirements):

> Inside a trading firm, the notification system is the internal platform other services call when a person needs to know something. A desk breached its loss limit. The overnight reconciliation failed. …
>
> Most days it is quiet. Then a venue's feed drops at the open and fifty services alert at once.
>
> **The crux: keep urgent alerts fast while bulk traffic surges, and never lose one.**

**Rule:** what it is, who uses it, the crux. Everything else moves to Requirements.

---

## 2. A paragraph that carries five ideas

**Before** (134 words, one paragraph):

> For the worker, those saved delivery rows are already a durable queue. A separate broker would provide dedicated dispatch capacity, but would also require reliable transfer from the database into the broker. Querying due work through an index on state and next-attempt time, in bounded batches, gives us a starting dispatcher without loading the whole backlog. This shares database resources with the inbox; measuring contention and pending age will tell us when that compromise stops working. The worker loads saved content and destinations, makes provider calls with finite timeouts, and writes outcomes or retry times back to the delivery rows. …

**After** — the same decision as a labelled option, a code block, a short
explanation, a comparison table, and one bolded verdict:

> **Good: the database is the queue.** In one transaction, the API writes the notification and its `PENDING` deliveries, then returns `202`. A pool of dispatcher workers picks up due deliveries:
>
> ```sql
> … FOR UPDATE SKIP LOCKED …
> ```
>
> `SKIP LOCKED` lets many workers poll at once without blocking on each other's rows. …
>
> | | Database as queue | Broker + outbox |
> |---|---|---|
> | Atomic acceptance | One transaction | Needs the outbox relay |
> | … | … | … |
>
> **At this scale the database is the right queue. Say so out loud, and name the number that would make you switch.**

**Rule:** one idea per paragraph. When a paragraph compares options, it wants to
be a table. When it describes steps, it wants to be a numbered list.

---

## 3. Caveats instead of claims

**Before:**

> These are workload assumptions, not measured database or provider capacities. Even one day at that rate creates 86.4 million inbox items, so retention and measured storage capacity matter; a single database is a starting layout, not an unlimited scaling claim.

**After:**

> Assume our providers together accept about 500 sends per second; contracts and rate limits set that ceiling.

**Rule:** label an assumption once, where it is introduced. Then use it. Do not
re-qualify it in every later sentence.

---

## 4. Telling instead of breaking

**Before** (risk limits):

> The tempting design is "publish updates through a broker and retry".

**After:** the tempting design is built in the high-level design, then the running
scenario is run through it until it fails at a named step:

> At 10:31:04 Maya's change commits as version 42. … The agent's thread stalls after reading the delta and before touching the table. S7's next 400-share buy passes the old check, and S7 reaches 5,300 shares. Every dashboard says the change was delivered.

**Rule:** derive the fix from a concrete failure. A reader who watched the naive
design break can rebuild the answer; a reader who was told the answer can only
recognise it.

---

## 5. Architecture as a final diagram

**Before:** a long prose walkthrough, then one diagram of the finished system.

**After:** one `###` step per functional requirement, each with a numbered flow and
a figure that adds components (new ones highlighted), ending in "What is still
broken". The reader holds a working system after every step.

---

## 6. Presenting the expert answer as the obvious one

**Before** (news feed, first draft of the reset):

> One adapter per source converts to a canonical model at entry, and the original bytes are kept for audit and reprocessing.

The design is good — a small common core, vendor extensions, and the raw bytes —
but the chapter presented it as a given. An average candidate does not start
there, and the reader never learns why it beats the simpler options.

**After:** a deep dive that starts with the two answers candidates actually give,
says what each costs, and only then reaches the hybrid:

> **Option A: one uniform schema.** Every adapter must fill the same fixed fields. Strategies love it … Then Wire B sends a "flash" urgency level that has no place in the schema …
>
> **Option B: keep every vendor's own schema.** Nothing is lost … and every consumer now writes five parsers.
>
> | | Uniform | Per-vendor | Core + extensions |
> |---|---|---|---|
> | Information lost | … | … | … |
>
> There is no perfect answer here. **Pick the core from what your consumers filter and join on; keep everything else, unmapped, next to it.**

**Rule:** show the progression from the first defensible answers to the refinement,
say what each option costs, and say when the requirements — not the design —
decide.

---

## 7. Question numbers and "as we saw earlier"

**Before:**

> That is the [queue buys time](../sd-notification-system/question.md) arithmetic from Q1 again.

**After:**

> A buffer only buys time: size it for the longest stall it must survive (drain time = backlog ÷ spare capacity), the arithmetic [Design a Notification System](../sd-notification-system/question.md) works through for an alert storm.

**Rule:** each chapter stands alone. Re-explain a reused move in a sentence, then
link the question that develops it by its title.

---

## 8. Links as navigation, not teaching

**Before:**

> The handbook's [pre-trade risk chapter](../../../release1/handbook-markdown/chapters/e3-pretrade-risk-engine/chapter.md) develops that separate control boundary.

**After:**

> The release store and the acquire load pair up: an order thread that sees the new index also sees every field written before it. That is the publish-data-then-flag pattern from [Handbook Ch 9 — *What the Other Thread Can See*](../../../release1/handbook-markdown/chapters/b1-cpp-memory-model/chapter.md).

**Rule:** name the chapter by number and title, say what the reader will find
there, and apply it to this design in the same paragraph.

---

## 9. A refinement justified by a strawman

**Before** (task scheduler, first draft):

> The claim query asks for rows that are due *and* best by priority. No single index serves both.

An expert reviewer replied in one line: with four priority levels, a partial index
on `(priority, due_at)` probed once per priority never touches a future row. The
argument for the refinement collapsed, and with it the reader's trust.

**After:**

> **Option A: keep one table and tune it.** With four priority levels, a partial index on `(priority, due_at)` over `QUEUED` rows, probed once per priority, finds due work without touching a single future row. … It is a good answer, and you should say so.
>
> It has one real limit: **the policy is whatever an index can sort** — priority, then age. The third deep dive needs shares per class and quotas per team, and no `ORDER BY` expresses those.

**Rule:** steelman the simple option, concede what it handles at this scale, and
argue the refinement on what it still cannot do.

