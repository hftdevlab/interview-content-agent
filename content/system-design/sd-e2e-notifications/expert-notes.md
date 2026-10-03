# Expert notes

This is a foundational system-design readability trial, not an advanced flagship question. Assume in-app, email, and mobile push notifications, and label this interpretation explicitly. Enrich missing requirements with clearly labeled illustrative assumptions. Keep the passing interview answer small; advanced extensions are optional.

## Human feedback 20260929T032840Z

The system design solution you provided skills reads like a series of spec output rather than a tutorial and a realistic interview answers. Read the two similar tutorials written by human experts to learn the style that better suits teaching purpose. Let's reframe the content into 1. Question descriptions and clarifications 2. Functional requirements and non-functional requirements 3. Core Entities 4. API and Data Schema(variants depends on topics, some may not need API design or schema discussion) 5. High level Architecture with at least one diagram 6. Some lower level details or deep dive. The bad vs good vs great solutions are optional and typically appear in this section. We usually don't need to provide two completely different solution as comparison. 7. Optional follow up or pitfalls. Also to help learning, we can categories key challenges of system design into a few expandable design patterns tailored for trading domain such as: Scale Read, Scale Write, Real-time Updates, Multi-steps workflows, Data Transactions, Low-latency, High reliability and error-proof, Network techniques, Fan-out write, Time-series system... Mention and tag those design patterns in the tutorial. The current reference to the handbook topics is good and should be kept. Review these feedback and rewrite these example questions

## Human feedback 20260930T025122Z

The overall structure works now but the writing style is still very off from a reader friendly tutorial. The major issue: you are stacking up a bunch of conclusions at every steps without showing any logical thinking, reasoning steps and reuse-able knowledge and skills. We should write with first person tone for all system design questions. Read the human written material for the log collection system for example, it explains why we need "Label", "Metric" and "Series" and their relationships in very natural and human-readable words, then accurately define them. Before giving the high level architecture, it explains the data flow within the system thoroughly. And in the API Inference section, it explains why we need JSON and when to use protobufs format. It also discuss the high throughout requirements for ingestion and design choice which is very important for this question.

## Human feedback 20261003T232039Z

# Instructor-led finance-engineering tutorial feedback

## Editor request

your improvements are on the right direction. I manually updated the ./agent/skills/draft-system-design/SKILL.md to give more detailed instructions on how to control the content quality. The key decision is: write the content as tutorial for interview at the instructor's first person tone, but not the candidate's answer itself. Try regenerating the example questions based on the latest SKILL.md. Also keep in mind we are writing a tutorial books for hedge fund/trading/finance engineers specifically. So highly the difference between traditional tech system design interviews when there is a good distinction

## Editor-authored skill snapshot

The edited file was found at `.agents/skills/draft-system-design/SKILL.md` in
the editor's original checkout. The following is its verbatim content at the
time of this revision, preserved as human input. The active generation skill
reconciles it with the later workflow safeguards and teaching criteria.

```markdown
---
name: draft-system-design
description: "Draft or substantially revise a normalized system-design interview question with an invariant-led good solution, focused deep dives, diagrams, trade-offs, and realistic follow-ups. Use for content/system-design packages that need an interview-ready answer before human review."
---

# Draft System Design Question

Write as an interview tutorial in the instructor's first person tone, not for schema completion.
The finished content should read like a tutorial mapping to real interview answer, not as the answer itself.

## Inputs

- The package's `metadata.yaml`, `question.md`, `expert-notes.md`, and `source/`.
- `content/STYLE_GUIDE.md`, relevant taxonomy, and related questions.
- Relevant foundations selected with `$link-interview-foundations`.

Human notes and original source are authoritative. Flag contradictions rather
than resolving them silently.

## Workflow

1. Requirements: the goal of the requirements section is to get a clear understanding and boundary of the system you are being asked to design. We almost always break down into two sections: Functional requirements and Non-functional requirements.
2. For functional requirements, state prominently when the full platform is too large for one interview;
   sketch it, then offer a few likely deep dives for agreement. For Non-functional requirements, the typical CAP Theorem still applies, but in the trading/finance area, usually availability, testability and fault tolerant are more important than scalability. Latency, throughput and low-level system & network techniques will come into the design consideration earlier than higher level architecture. We should speak loud to students when making such assumptions though.
3. As an optional step, explain what is tested and develop the candidate's reasoning toward a
   minimal correct design.
4. Next you should take a moment to identity and list the core entities of your system, which your API will exchange and that your system will persist in a Data model.
5. Depending on the specific question, we may need a detailed data model discussion. This usually come with questions when underlying format, schema and scalability of data matter. It may also be combined naturally with step 6. For example, we need to design the timestamp columns for back-testing system and that come together with how it was queried.
6. API or system interface: Next you will define the contract between your system and its users. Usually you will map to your functional requirements above. The typical default choices for providing CRUD operations to users is RESTful APIs. Use RPC for action-oriented protocols and when service-to-service communication is performance critical. For trading/finance domain,however, we sometimes may provide interface as simple as
a dashbroad, an interal data query platform. Leave the detailed data model design into next sections though.
7. Describe the Data Flow as an optional step. For some data-processing system, the core problem can be solved by clarifying how data is written into the system, processed by the system and delivered as outputs. Usually a diagram is useful for this section.
8. Next we can come up with the high level architecture. Name the design pattern, common tools and platforms at this step. A diagram is almost very needed. Make sure you describe a complete solution for every functional requirements before diving into complex components. Add improvements such as caching and partitions only with reasons back it.
9. Finally, we may choose 1-3 topics to deep dive. This should usually map to non-functional requirements. It may be a good vs great solution improvements on an existing solution, edge cases discussions or a lower-level probe for a established tool, such as OS or network level details. Manage this section considering the whole size of the solution.
10 Set status to `needs_human_review`; set only `agent_reviewed` true and leave
   all human review flags false.

A typical chapter must fit ten rendered pages. A genuinely complex flagship
question may use up to fourteen when the extra pages contain interview-relevant
decisions rather than prerequisite tutorials.

## Outputs and edit boundary

Edit only `question.md`, `metadata.yaml`, `review.yaml`, and `diagrams/*.mmd`
inside the selected package. Preserve `source/` and `expert-notes.md`. Do not
edit rendered SVGs, catalogs, PDFs, or other generated artifacts by hand.

## Validation

Run:

```bash
python -m tools.validate --id <id>
make diagrams
make pdf-preview
```

Inspect the rendered chapter for page count, diagram legibility, and density.
Finish with `make all` after a substantial revision.
```
