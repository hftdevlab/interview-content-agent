# C++ Quant Developer Interview Content Factory 

Project Goal and Codex Implementation Plan 

## 1. Executive summary 

#### The goal is to build a **human-curated, AI-assisted production system for high-quality C+ + quant developer interview preparation content** . 

The product is not merely a collection of AI-generated answers. Its value should come from: 

- Realistic questions selected from genuine interview experience and high-frequency interview patterns. 

- Clear separation between an answer that is merely sufficient and one that demonstrates exceptional engineering judgment. 

- Interviewer-focused annotations: what is being tested, where candidates commonly fail, how follow-up questions evolve, and what distinguishes different performance levels. 

- Consistent taxonomy, difficulty ratings, cross-references, and answer structure. 

- Runnable C++ practice environments rather than static explanations alone. 

- Continuous correction and expansion based on human feedback. 

The system should treat AI as a **content production and engineering assistant** , while the human remains the: 

- Domain editor. 

- Final quality judge. 

- Source of real interview context. 

- Owner of difficulty and importance rankings. 

- Final publishing authority. 

The initial implementation should be deliberately simple: 

- One Git repository. 

- Markdown and YAML as the source of truth. 

- A command-line workflow. 

- Deterministic PDF generation. 

- A shared C++ build and test environment. 

- Codex skills for repeated content workflows. 

- Mandatory human approval before publication. 

The initial version should **not** require a database, vector store, complex website, autonomous multi-agent service, or LeetCode-style online judge. 

## 2. Product deliverables 

### 2.1 System Design Interview Guide 

A continuously updated PDF focused on system design and open-ended engineering questions relevant to C++ quant developers. 

The catalog should group questions by categories such as: 

- Market data systems. 

- Data pipelines and stream processing. 

- Trading systems and order management. 

- Exchange connectivity and gateways. 

- Storage, logging, replay, and recovery. 

- Low-latency architecture. 

- Reliability and fault tolerance. 

- Testing and deployment. 

- Monitoring and performance diagnosis. 

- Distributed coordination and consistency. 

Each question should contain: 

1. **Question description** 

2. **Clarifying questions** 

3. **Requirements and assumptions** 

4. **Good solution** 

5. **Great solution** 

6. **Key trade-offs** 

7. **Failure scenarios** 

8. **Common pitfalls** 

9. **Follow-up questions** 

10. **Expected points for each follow-up** 

11. **Evaluation rubric** 

12. **Tags** 

13. **Similar or prerequisite questions** 

#### 14. **Architecture and sequence diagrams** 

The distinction between the two solution levels should be explicit: 

- **Good solution:** A coherent, practical design likely to pass an ordinary interview. 

- **Great solution:** Improvements demonstrating stronger prioritization, latency awareness, operational maturity, failure reasoning, and domain-specific judgment. 

The great solution should normally be expressed as a set of improvements over the good solution rather than repeating the full answer. 

### 2.2 Coding Interview Guide 

A continuously updated PDF containing coding and C++ API-design questions, ordered by difficulty. 

Each question should contain: 

1. **Interview-ready problem statement** 

2. **Input, output, and API contract** 

3. **Constraints and examples** 

4. **Expected clarification questions** 

5. **Primary solution** 

6. **Time and space complexity** 

7. **Optional alternative approaches** 

8. **Optional improvements** 

9. **Common implementation mistakes** 

10. **Follow-up questions** 

11. **Related C++ knowledge** 

12. **Relevant object-oriented or API design patterns** 

#### 13. **(TODO later) Link to the runnable practice package** 

The document should prioritize questions that resemble real C++ and quant developer interviews rather than attempting to reproduce the entire LeetCode question universe. 

Images should be rare. Small state diagrams or memory-layout illustrations can be included only when they materially improve the explanation. 

### 2.3 C++ Systems and Low-Latency Knowledge Guide 

A third continuously updated PDF covering: 

- C++ language internals. 

- Concurrency. 

- Operating systems. 

- Networking. 

- CPU and memory behavior. 

- Low-latency engineering. 

- Performance analysis. 

- Lock-free and wait-free techniques. 

- Production debugging. 

- Intentionally tricky or adversarial interview questions. 

Each entry should contain: 

1. **Question** 

2. **Concise interview answer** 

3. **Deeper explanation** 

4. **Pass-level answer framework** 

5. **Strong-answer improvements** 

6. **Examples or code snippets** 

7. **Common misconceptions** 

8. **Typical traps** 

9. **Follow-up questions** 

#### 10. **Related concepts** 

#### 11. **Runnable experiment when appropriate** 

This guide should resemble the system design guide structurally but use fewer diagrams. 

### 2.4 Runnable Practice Repository 

A repository containing runnable versions of: 

- Every coding question. 

- Every fundamentals question for which a practical experiment is useful. 

- Selected system-design components when implementation practice adds value. 

Each runnable question should include: 

- A minimal starter template. 

- A reference implementation. 

- Public test cases. 

- Build instructions. 

- Required environment configuration. 

- A short question-specific README. 

- Commands for building and running that question. 

- Optional sanitizer or stress-test configurations. 

The initial environment should use: 

- C++20. 

- CMake. 

- Ninja or Make. 

- Clang and GCC compatibility where practical. 

- CTest or a very small shared test harness. 

- Docker for a reproducible environment. 

A complex browser-based coding platform is outside the initial scope. 

Overall, the solutions provided for all type of questions should be clear, concise and use natural human languages tone. It should resemble a realistic interviewee answer as much as possible instead of being like lengthy AI generated with unnecessary details. 

Each question should be tagged with a recommended finish time. The system design questions usually range from 30-60mins, coding questions 20-50mins, while random questions can be from 5-30mins. This tag can be recommended by AI but finally determined by human. The answer content for the question should be related to the time. For example for a 5mins question, usually one plain answer and knowledge explanation is enough. For a 60mins design question, the full spectrum comparison, follow up and linked knowledge should be provided. 

## 3. Core product differentiation 

Generic AI can already produce acceptable explanations for many questions. Therefore, the defensible product value should be concentrated in the following layers. 

### 3.1 Interview calibration 

Every answer should explain not only what is technically possible, but: 

- What the interviewer is trying to measure. 

- Which parts should be discussed first. 

- Which improvements are valuable only after the baseline is correct. 

- What an average candidate usually misses. 

- Which claims invite dangerous follow-ups. 

- How much detail is appropriate for a 30-, 45-, or 60-minute interview. 

### 3.2 Good-versus-great differentiation 

The great answer should not merely be longer. 

It should demonstrate improvements such as: 

- Better prioritization. 

- Stronger requirement clarification. 

- Better latency and throughput reasoning. 

- More realistic failure handling. 

- Better separation of critical and non-critical paths. 

- Operational observability. 

- Testability. 

- Replay and recovery. 

- Capacity estimates. 

- Clearer trade-offs. 

- Domain-specific insights. 

### 3.3 Human expert annotations 

The highest-value human input will be: 

- Why the question is asked. 

- What a strong interviewer expects. 

- Common candidate mistakes. 

- Real follow-up sequences. 

- Scoring criteria. 

- Which topics are genuinely high-frequency. 

- Whether an answer sounds technically impressive but is unrealistic. 

- How much depth is appropriate for different interview levels. 

### 3.4 Cross-question knowledge structure 

Questions should form a connected learning system rather than an isolated list. 

Examples: 

- A market-data-feed design question links to sequence numbers, gap recovery, packet loss, multicast, replay, backpressure, and lock-free queues. 

- A thread-safe queue coding problem links to condition variables, memory ordering, shutdown semantics, spurious wakeups, and bounded queues. 

- A sequence lock question links to memory models, reader starvation, consistency, version counters, and cache-line behavior. 

## 4. Source-of-truth principle 

The PDFs must never be the primary editable content. 

The source of truth should be: 

- Markdown. 

- YAML metadata. 

- Mermaid diagram source. 

- C++ source code. 

- Test files. 

- Expert notes. 

- Review status. 

- Git history. 

Generated outputs should include: 

- system-design-guide.pdf 

- coding-interview-guide.pdf 

- cpp-systems-guide.pdf 

- Optional HTML previews. 

- Generated catalog files. 

- Release manifests and checksums. 

The anti-piracy document platform should eventually act as a **distribution layer** , not the authoring system. 

Generated files under dist/ should never be edited manually. 

## 5. Human and AI responsibility split 

### 5.1 Human responsibilities 

The human editor should control: 

- Whether a question belongs in the product. 

- Whether the question reflects a real interview pattern. 

- Final category and difficulty. 

- Final correctness judgment. 

- Interviewer expectations. 

- Expert tips and real follow-ups. 

- Confidentiality and sanitization. 

- Final publication approval. 

- Whether a solution qualifies as good or great. 

### 5.2 AI responsibilities 

AI agents should handle: 

- Transcribing text from an image. 

- Rewriting rough input into a clear interview prompt. 

- Identifying ambiguities. 

- Producing an initial structured solution. 

- Suggesting categories and tags. 

- Suggesting similar questions. 

- Drafting good and great solutions. 

- Drafting pitfalls and follow-ups. 

- Creating Mermaid diagrams. 

- Formatting Markdown. 

- Generating starter code, solutions, and tests. 

- Reviewing content against a checklist. 

- Checking cross-document consistency. 

- Updating generated catalogs. 

- Building and validating PDFs. 

- Compiling and testing runnable exercises. 

### 5.3 Deterministic tooling responsibilities 

Ordinary scripts, rather than language models, should perform: 

- Schema validation. 

- ID validation. 

- Sorting and catalog generation. 

- Broken-link checks. 

- Related-question validation. 

- Markdown linting. 

- Diagram rendering. 

- PDF generation. 

- C++ compilation. 

- Test execution. 

- Release packaging. 

- File hashing. 

- Status enforcement. 

No AI-generated question should be automatically published without human approval. 

## 6. Content lifecycle 

Each question should move through an explicit lifecycle: 

inbox -> normalized 

-> drafted -> agent-reviewed -> human-review-required -> approved -> published -> revised or deprecated 

Recommended status values: 

status **: -** inbox **-** normalized **-** draft **-** agent_reviewed **-** needs_human_review **-** approved **-** published **-** deprecated 

The publishing script must include only questions with an approved or published status. 

## 7. Question identity and metadata 

Question IDs must remain stable even if: 

- The title changes. 

- The difficulty changes. 

- The question moves to another category. 

- The PDF ordering changes. 

Do not encode the current question number or difficulty into the permanent ID. 

Good IDs: 

sd-market-data-feed sd-order-routing-gateway code-multi-source-stream-merger code-bounded-blocking-queue 

fund-sequence-lock fund-tcp-nagle-delayed-ack 

#### Common metadata should include: 

schema_version **:** 1 id **:** sd-market-data-feed type **:** system_design title **:** Design a Low-Latency Market Data Feed System 

status **:** draft **:** 4 difficulty 

categories **:** 

- market-data 

- data-pipeline 

- low-latency 

tags **:** 

- multicast 

- sequencing 

- gap-recovery 

- replay 

- normalization 

prerequisites **:** 

- fund-udp-multicast 

- fund-sequence-numbers 

related_questions **:** 

- sd-market-data-replay 

- code-multi-source-stream-merger 

source **:** input_type **:** image confidentiality **:** sanitized_real_interview original_company_removed **:** true 

review **:** 

human_reviewed **:** false technical_accuracy_reviewed **:** false interview_realism_reviewed **:** false 

last_updated **:** 2026-07-29 

Useful confidentiality values: 

public sanitized_real_interview private_reference 

#### Private-reference content should never be included in distributable artifacts. 

## 8. Standard content templates 

### 8.1 System design question template 

# Question title 

## Interview prompt 

## What the interviewer is testing 

## Clarifying questions 

## Assumptions and requirements 

### Functional requirements 

### Non-functional requirements ## Good solution 

### High-level architecture ### Core data flow 

### Data model and interfaces 

### Failure handling ### Trade-offs 

## Great solution improvements 

### Improvement 1 

### Improvement 2 

### Improvement 3 

## Capacity and latency discussion 

## Failure scenarios 

## Common pitfalls 

## Follow-up questions 

### Follow-up 1 Expected answer points: ### Follow-up 2 Expected answer points: ## Evaluation rubric ## Similar questions ## Tags 8.2 Coding question template # Question title ## Interview prompt 

## API contract ## Constraints ## Examples 

## Clarifications a candidate should ask 

## Primary approach 

## Reference solution ## Complexity analysis 

## Alternative approaches 

## Common mistakes 

## Optional improvements 

## Follow-up questions 

## Related C++ knowledge 

## Related design patterns 

## Practice repository 

### 8.3 Fundamentals question template 

# Question 

## Concise interview answer 

## Deep explanation 

## Good answer framework 

## Great answer improvements 

## Example 

## Common misconception 

## Interview trap 

## Follow-up questions 

## Related concepts 

## Runnable experiment 

## 9. Proposed repository structure 

quant-dev-interview-content/ ├── AGENTS.md 

├── README.md ├── PROJECT_PLAN.md ├── Makefile ├── pyproject.toml ├── Dockerfile ├── docker-compose.yml │ ├── .agents/ │└── skills/ │ ├── ingest-question/ │ │├── SKILL.md │ │├── references/ │ │└── scripts/ │ ├── draft-system-design/ │ │└── SKILL.md │ ├── draft-coding-question/ │ │└── SKILL.md │ ├── draft-fundamentals-question/ │ │└── SKILL.md │ ├── review-question/ │ │└── SKILL.md │ ├── build-practice-question/ │ │└── SKILL.md │ └── publish-guides/ │ └── SKILL.md │ ├── schemas/ │├── common.schema.json │├── system-design.schema.json │├── coding.schema.json │└── fundamentals.schema.json │ ├── taxonomy/ │├── categories.yaml │├── tags.yaml │├── difficulty.yaml │└── ordering.yaml │ ├── inbox/ │└── .gitkeep │ ├── content/ │├── AGENTS.md 

│├── system-design/ ││└── sd-market-data-feed/ ││ ├── metadata.yaml ││ ├── question.md ││ ├── expert-notes.md ││ ├── review.yaml ││ ├── source/ ││ │├── original.txt ││ │└── input-image.png ││ ├── diagrams/ ││ │├── architecture.mmd ││ │└── recovery-sequence.mmd ││ └── assets/ ││ │├── coding/ ││└── code-stream-merger/ ││ ├── metadata.yaml ││ ├── question.md ││ ├── expert-notes.md ││ ├── review.yaml ││ └── source/ ││ │└── fundamentals/ │ └── fund-sequence-lock/ │ ├── metadata.yaml │ ├── question.md │ ├── expert-notes.md │ ├── review.yaml │ └── source/ │ ├── practice/ │├── AGENTS.md │├── CMakeLists.txt │├── common/ ││├── include/ ││└── test/ │└── questions/ │ ├── code-stream-merger/ │ │├── README.md │ │├── metadata.yaml │ │├── CMakeLists.txt │ │├── starter/ │ ││├── stream_merger.hpp 

│ ││└── stream_merger.cpp │ │├── solution/ │ ││├── stream_merger.hpp │ ││└── stream_merger.cpp │ │└── tests/ └── │ │ stream_merger_test.cpp │ └── fund-sequence-lock/ │ ├── prompts/ │├── normalize-question.md │├── system-design-draft.md │├── coding-draft.md │├── fundamentals-draft.md │├── reviewer.md │└── refine-with-expert-notes.md │ ├── tools/ │├── ingest.py │├── validate.py │├── generate_catalog.py │├── build_guides.py │├── render_diagrams.py │├── create_practice_question.py │└── release.py │ ├── templates/ │├── system-design/ │├── coding/ │├── fundamentals/ │├── practice/ │└── pdf/ │ ├── generated/ │├── catalogs/ │├── markdown/ │└── diagrams/ │ ├── dist/ │├── system-design-guide.pdf │├── coding-interview-guide.pdf │├── cpp-systems-guide.pdf │└── manifest.json │ 

└── .github/ └── workflows/ ├── validate.yml ├── practice-tests.yml └── build-guides.yml 

Codex reads project instructions from AGENTS.md, including more specific instructions in nested directories. Repository-scoped reusable skills can be stored under .agents/skills, with each skill containing a required SKILL.md and optional scripts, references, and assets. 

## 10. Input workflow 

The human should be able to add a question through either text or images. 

Example commands: 

python -m tools.ingest \ --type system-design \ 

--input inbox/market-data-question.png 

- python -m tools.ingest \ --type coding \ 

- --input inbox/stream-merger.txt 

The ingestion workflow should: 

1. Preserve the original input. 

2. Extract or transcribe the question. 

3. Remove company-specific or confidential identifiers. 

4. Rewrite it into clear interview English. 

5. Identify missing or ambiguous information. 

6. Suggest a stable ID. 

7. Suggest categories, tags, and difficulty. 

8. Create the standard question directory. 

9. Generate an initial draft. 

- 10.Set the status to needs_human_review. 

The original source should never be silently modified or deleted. 

## 11. Human feedback workflow 

Human feedback should be stored separately from generated prose. 

Example expert-notes.md: 

# Expert notes 

- The interviewer primarily cared about gap recovery, not the parser design. 

- A candidate should ask whether recovery may block the real-time path. 

- Mention per-channel sequence numbers before discussing global ordering. 

- Avoid claiming exactly-once processing. 

- The strongest follow-up was how to recover without delaying live traffic. 

- Difficulty should be 4 rather than 3. 

A refinement command should read the current content and these notes: 

python -m tools.refine --id sd-market-data-feed 

The refinement process should: 

- Preserve the original source. 

- Preserve the expert notes. 

- Show a Git diff. 

- Modify only the relevant answer sections. 

- Explain which notes were incorporated. 

- Return the question to needs_human_review. 

Human edits must take priority over AI suggestions. 

## 12. Diagram strategy 

Technical diagrams should use an editable text-based format whenever possible. 

Recommended initial format: 

- Mermaid source in diagrams/*.mmd. 

- SVG as the generated PDF asset. 

- PNG only for imported screenshots or source images. 

The agent may generate Mermaid source, but deterministic tools should render it. 

Each diagram should include: 

- A caption. 

- Descriptive alt text. 

- A stable filename. 

- A reference from the question Markdown. 

- Readable labels at PDF scale. 

Useful diagram types include: 

- Architecture diagrams. 

- Data-flow diagrams. 

- Sequence diagrams. 

- State machines. 

- Recovery workflows. 

- Thread-interaction diagrams. 

Do not use decorative AI-generated illustrations for technical content. 

## 13. PDF publishing strategy 

A straightforward initial toolchain is: 

1. Generate catalog and combined Markdown with Python. 

2. Render Mermaid files to SVG. 

3. Convert Markdown into styled HTML with Pandoc. 

4. Convert HTML into PDF using WeasyPrint or headless Chromium. 

5. Run PDF validation. 

6. Write version metadata and hashes to dist/manifest.json. 

Example commands: 

make validate make diagrams make guides make practice-test make all 

Expected outputs: 

dist/system-design-guide.pdf dist/coding-interview-guide.pdf dist/cpp-systems-guide.pdf dist/manifest.json 

Catalogs should be generated from metadata. Adding a question must not require manually editing a table of contents or question index. 

Recommended sorting rules: 

- System design: category, then difficulty, then title. 

- Coding: difficulty, then topic, then title. 

- Fundamentals: domain, then difficulty, then title. 

Each release should display: 

- Product version. 

- Build date. 

- Number of questions. 

- Recently added questions. 

- Recently revised questions. 

## 14. Practice-repository design 

Each practice question should contain both starter and reference implementations. 

practice/questions/code-stream-merger/ 

├── README.md ├── metadata.yaml ├── CMakeLists.txt 

├── starter/ ├── solution/ └── tests/ 

### Starter requirements 

The starter version should: 

- Compile where practical. 

- Expose the required API. 

- Contain clear TODO markers. 

- Avoid revealing the complete solution. 

- Fail relevant behavioral tests until implemented. 

### Reference solution requirements 

The reference version should: 

- Compile without warnings under the supported configuration. 

- Pass all tests. 

- Match the explanation in the PDF. 

- Include complexity and design notes. 

- Avoid unnecessary production-framework code. 

### Test requirements 

Tests should cover: 

- Normal cases. 

- Boundary cases. 

- Empty input. 

- Invalid input where relevant. 

- Shutdown or lifecycle behavior. 

- Ordering behavior. 

- Duplicate or stale data. 

- Concurrency behavior where practical. 

Concurrency tests should be designed to minimize flakiness. 

Separate test modes can include: 

unit stress asan ubsan tsan benchmark 

The initial MVP only requires unit tests and optional sanitizer support. 

### Shared commands 

cmake -S practice -B build -G Ninja cmake --build build ctest --test-dir build --output-on-failure 

Question-specific command: 

./tools/run-question code-stream-merger --variant solution 

CI should require: 

- All reference solutions to compile and pass. 

- Starter templates to compile where intended. 

- Metadata links to valid content questions. 

- Every runnable question to have a README and tests. 

## 15. Agent design for the initial version 

Do not begin with a large autonomous agent framework. 

The first version should use: 

- Codex. 

- Repository instructions. 

- Focused Codex skills. 

- Python scripts. 

- Git diffs. 

- Human approval. 

#### Recommended conceptual agents: 

### 15.1 Ingestion agent 

Input: 

- Image or text. 

- Question type. 

- Optional human note. 

#### Output: 

- Original source archive. 

- Normalized prompt. 

- Metadata draft. 

- Ambiguity list. 

### 15.2 Content drafting agent 

Input: 

- Normalized prompt. 

- Question schema. 

- Existing related questions. 

- Expert notes. 

#### Output: 

- Structured question draft. 

- Good and great solutions where applicable. 

- Pitfalls. 

- Follow-ups. 

- Suggested relationships. 

### 15.3 Diagram agent 

Input: 

- Approved or near-approved system design answer. 

#### Output: 

- Mermaid source. 

- Captions. 

- Alt text. 

### 15.4 Practice agent 

Input: 

- Coding or runnable fundamentals question. 

#### Output: 

- Starter implementation. 

- Reference implementation. 

- Tests. 

- CMake configuration. 

- README. 

### 15.5 Reviewer agent 

#### Input: 

- Full question package. 

#### Output: 

- Structured review report. 

- Correctness concerns. 

- Missing trade-offs. 

- Good-versus-great overlap. 

- Unclear wording. 

- Unsupported claims. 

- Test gaps. 

- Suggested review status. 

### 15.6 Publisher 

The publisher should be deterministic code, not an LLM agent. 

It should: 

- Validate. 

- Sort. 

- Generate catalogs. 

- Render diagrams. 

- Build PDFs. 

- Run tests. 

- Package releases. 

## 16. Codex configuration 

### 16.1 Root AGENTS.md 

The root instructions should include rules such as: 

# Repository purpose 

This repository produces human-reviewed C++ quant developer interview materials and runnable practice exercises. 

# Source of truth 

- Edit Markdown, YAML, Mermaid, C++, and tests. 

- Never manually edit files under generated/ or dist/. 

- Preserve original source inputs. 

- Expert notes override AI suggestions. 

# Content rules 

- Never invent interview provenance. 

- Remove employer-specific identifiers. 

- Do not mark content approved or published. 

- Clearly distinguish good solutions from great improvements. 

- Prefer realistic engineering trade-offs over generic completeness. 

- Use stable IDs and validate all related-question references. 

##### # Engineering rules 

- Run **_`make validate`_** after content changes. 

- Run **_`make practice-test`_** after C++ changes. 

- Run **_`make guides`_** after renderer changes. 

- Add or update tests for deterministic tooling. 

- Summarize modified files and validation results. 

# Completion criteria 

A task is complete only when required validation and tests pass. 

### 16.2 Nested instructions 

content/AGENTS.md should focus on: 

- Interview writing quality. 

- Schemas. 

- Expert-note handling. 

- Confidentiality. 

- Review status. 

practice/AGENTS.md should focus on: 

- C++ conventions. 

- Build commands. 

- Test requirements. 

- Sanitizers. 

- Starter-versus-solution separation. 

### 16.3 Codex skills 

Create focused skills rather than one very large skill: 

$ingest-question $draft-system-design $draft-coding-question $draft-fundamentals-question $review-question $build-practice-question $link-interview-foundations $publish-guides 

A skill should describe: 

- When it should run. 

- Required inputs. 

- Files it may modify. 

- Files it must preserve. 

- Exact output format. 

- Validation commands. 

- Conditions for completion. 

OpenAI’s current guidance recommends keeping each skill focused on one job, using explicit inputs and outputs, and using scripts where deterministic behavior is required. 

## 17. Validation and quality gates 

### 17.1 Structural validation 

Automated checks should verify: 

- Required files exist. 

- YAML matches the schema. 

- IDs are unique. 

- Related IDs exist. 

- Tags and categories are valid. 

- Required headings exist. 

- Published questions have completed review fields. 

- No private-reference material enters generated PDFs. 

- No unresolved placeholders remain. 

Examples of forbidden placeholders: 

TODO TBD INSERT ANSWER NEEDS DIAGRAM UNKNOWN COMPLEXITY 

### 17.2 Content review 

The reviewer agent should check: 

- Does the prompt sound like a real interview question? 

- Is the baseline solution actually sufficient? 

- Is the great solution materially better rather than merely longer? 

- Are trade-offs explicit? 

- Are failure modes realistic? 

- Are follow-ups answerable from the material? 

- Are latency claims justified? 

- Are C++ claims consistent with the language rules? 

- Is domain terminology used correctly? 

- Is the answer too broad for the expected interview duration? 

### 17.3 Code validation 

Automated checks should include: 

- Formatting. 

- Compilation. 

- Unit tests. 

- Warning checks. 

- Optional sanitizer runs. 

- Consistency between documented APIs and actual code. 

- Confirmation that the reference solution passes. 

- Confirmation that the starter does not accidentally contain the answer. 

### 17.4 Diagram validation 

Automated checks should verify: 

- Mermaid source renders. 

- Generated SVG exists. 

- Referenced diagrams exist. 

- No missing captions. 

- No broken asset paths. 

### 17.5 PDF validation 

Checks should include: 

- All three PDFs are generated. 

- Table of contents exists. 

- Question catalog is populated. 

- No missing images. 

- No empty question sections. 

- Page count is non-zero. 

- PDF metadata contains version and build date. 

## 18. Implementation milestones 

## Milestone 0: Establish the gold standard 

Before building broad automation, manually select approximately six representative questions: 

- Two system design questions. 

- Two coding questions. 

- Two fundamentals questions. 

Suggested initial examples: 

- Design a market data feed and normalization system. 

- Design market data replay and gap recovery. 

- Merge multiple ordered input streams. 

- Implement a bounded blocking queue. 

- Explain and implement a sequence lock. 

- Diagnose latency caused by TCP buffering behavior. 

These examples should establish: 

- Writing style. 

- Expected answer depth. 

- Good-versus-great distinction. 

- Difficulty scale. 

- Diagram style. 

- Coding repository structure. 

- Review rubric. 

**Done when:** The six examples are accepted as templates for future content. 

## Milestone 1: Repository and deterministic build 

Implement: 

- Repository structure. 

- Schemas. 

- Taxonomy. 

- Sample question fixtures. 

- Catalog generator. 

- Diagram renderer. 

- PDF builder. 

- Shared C++ environment. 

- Basic CI. 

- make all. 

#### **Done when:** 

make all 

successfully: 

- Validates content. 

- Builds all diagrams. 

- Builds all three PDFs. 

- Compiles reference solutions. 

- Runs tests. 

No AI workflow is required yet. 

## Milestone 2: Text and image ingestion 

Implement: 

- Text input. 

- Image input. 

- Source preservation. 

- Normalized question output. 

- Metadata suggestions. 

- Initial directory creation. 

- Draft review status. 

**Done when:** A raw text file and an image can each be converted into a valid draft question package without manually creating directories or metadata files. 

## Milestone 3: Content-generation skills 

Implement the Codex skills for: 

- System design drafting. 

- Coding drafting. 

- Fundamentals drafting. 

- Question review. 

- Refinement from expert notes. 

**Done when:** Codex can take a normalized question package and produce a schema-valid draft while preserving source material and setting the correct review status. 

## Milestone 4: Runnable-question generation 

Implement: 

- Practice-question scaffolding. 

- Starter code. 

- Reference solution. 

- Tests. 

- Question README. 

- Root build registration. 

**Done when:** A coding question can be converted into a complete practice directory whose reference solution compiles and passes its tests. 

## Milestone 5: Human review and controlled publishing 

Implement: 

- Review checklist. 

- Review-status enforcement. 

- Expert-note refinement. 

- Approved-only publishing. 

- Revision history. 

- Release manifest. 

**Done when:** Draft content cannot appear in a published PDF, and approved content can be added without manually editing catalogs. 

## Milestone 6: Pilot question bank 

Build a first usable release containing approximately: 

- 10 system design questions. 

- 20 coding questions. 

- 20 fundamentals questions. 

- Runnable packages for all 20 coding questions. 

- Runnable packages for selected fundamentals questions. 

The purpose of this milestone is to reveal where the workflow becomes slow or inconsistent. 

## 19. Ordered Codex backlog 

Each item should be implemented as a separate Codex task or pull request. 

Official Codex guidance recommends structuring tasks with a clear goal, relevant context, constraints, and an explicit definition of done. It also recommends requiring tests and review rather than accepting generated changes without validation. 

Task 1: Initialize the repository 

#### **Goal** 

Create the directory structure, build files, placeholder documentation, and initial developer commands. 

#### **Constraints** 

- No database. 

- No web application. 

- Python for tooling. 

- C++20 and CMake for practice. 

- Generated files must be isolated. 

#### **Done when** 

- Repository structure exists. 

- make help works. 

- Empty validation and build commands execute successfully. 

- README explains local setup. 

### Task 2: Define schemas and taxonomy 

#### **Goal** 

Create machine-validatable schemas for all three question types. 

#### **Context** 

Use the templates in this plan. 

#### **Constraints** 

- Stable IDs. 

- Explicit status. 

- Confidentiality metadata. 

- Related-question references. 

- Difficulty independent of IDs. 

#### **Done when** 

- Valid fixtures pass. 

- Invalid fixtures fail with useful errors. 

- Duplicate IDs are rejected. 

### Task 3: Add gold-standard fixtures 

#### **Goal** 

Add one fully completed example of each question type and at least one runnable coding question. 

#### **Constraints** 

- Examples must exercise most schema fields. 

- System design example must contain diagrams. 

- Coding example must link to the practice directory. 

#### **Done when** 

- Fixtures validate. 

- Diagrams render. 

- Reference code passes tests. 

### Task 4: Build the catalog generator 

#### **Goal** 

Generate categorized question catalogs from metadata. 

#### **Constraints** 

- No manually maintained question list. 

- Stable ordering. 

- Links must target generated document anchors. 

#### **Done when** 

- All three catalogs are generated. 

- Category and difficulty counts are shown. 

- Broken related-question IDs fail validation. 

### Task 5: Build the document renderer 

#### **Goal** 

Produce the three PDF guides from approved content. 

#### **Constraints** 

- Markdown is the source. 

- Mermaid source renders to SVG. 

- Styling is shared but each guide may have a distinct cover. 

- Draft questions must be excluded. 

#### **Done when** 

- Three non-empty PDFs are created. 

- Table of contents and catalogs are present. 

- Diagrams render correctly. 

### Task 6: Build the C++ practice harness 

#### **Goal** 

Create a shared CMake project and one complete example question. 

#### **Constraints** 

- Starter and reference code must remain separate. 

- Tests should not require a complex external service. 

- The environment should be reproducible through Docker. 

#### **Done when** 

- Local and Docker builds succeed. 

- The solution passes. 

- The starter builds but does not pass the solution tests. 

- Question-specific commands are documented. 

### Task 7: Implement validation 

#### **Goal** 

Create a single validation command covering content, assets, metadata, diagrams, and practice links. 

#### **Done when** 

##### make validate 

detects: 

- Missing files. 

- Invalid schemas. 

- Duplicate IDs. 

- Broken references. 

- Invalid status. 

- Unrenderable diagrams. 

- Missing practice directories. 

- Unresolved placeholders. 

### Task 8: Write AGENTS.md files 

#### **Goal** 

Encode repository-wide and directory-specific Codex instructions. 

#### **Done when** 

- Root instructions cover source-of-truth and completion rules. 

- Content instructions cover interview quality. 

- Practice instructions cover C++ and tests. 

- Codex can summarize the loaded instructions correctly. 

### Task 9: Add repository skills 

#### **Goal** 

Create the initial focused Codex skills under .agents/skills. 

#### **Initial skills** 

- ingest-question 

- draft-system-design 

- draft-coding-question 

- draft-fundamentals-question 

- review-question 

- build-practice-question 

- link-interview-foundations 

- publish-guides 

#### **Done when** 

- Every skill defines inputs and outputs. 

- Every skill states which files it may edit. 

- Every skill includes validation commands. 

- Skills preserve source files and human notes. 

### Task 10: Implement text ingestion 

#### **Goal** 

Turn a text file into a standardized draft question package. 

#### **Done when** 

- Source is archived. 

- Metadata is created. 

- Question is normalized. 

- Status is set correctly. 

- Package passes structural validation. 

### Task 11: Implement image ingestion 

#### **Goal** 

Turn a screenshot or photograph into the same standardized draft package. 

#### **Constraints** 

- Preserve the source image. 

- Keep uncertain transcription visible for review. 

- Do not silently guess unreadable constraints. 

#### **Done when** 

- Image input produces a valid package. 

- Uncertain text is flagged. 

- Original image remains linked in the review package. 

### Task 12: Implement expert-note refinement 

#### **Goal** 

Update a draft based on expert-notes.md. 

#### **Constraints** 

- Human notes are authoritative. 

- Preserve the notes. 

- Never publish automatically. 

- Produce a reviewable diff. 

#### **Done when** 

- Relevant sections change. 

- Unrelated sections remain stable. 

- The output returns to human-review-required status. 

### Task 13: Implement runnable-question generation 

#### **Goal** 

Generate the starter, solution, tests, CMake files, and README for a coding question. 

#### **Done when** 

- Reference code passes. 

- Starter code is usable. 

- PDF links resolve. 

- Build registration is automatic. 

### Task 14: Add CI 

#### **Goal** 

Validate every change and build release previews. 

#### **Checks** 

- Python tests. 

- Schema validation. 

- Markdown lint. 

- Diagram rendering. 

- C++ compilation. 

- Unit tests. 

- PDF generation. 

#### **Done when** 

A pull request cannot merge when any required check fails. 

### Task 15: Add release packaging 

#### **Goal** 

Create versioned release artifacts. 

#### **Outputs** 

- Three PDFs. 

- Practice repository archive. 

- Manifest. 

- Change summary. 

- File hashes. 

#### **Done when** 

One release command produces all distributable artifacts from a clean checkout. 

## 20. Initial commands 

The repository should eventually support a workflow similar to: 

_# Add a raw question_ python -m tools.ingest \ --type system-design \ 

--input inbox/market-data.png 

_# Validate one question_ 

python -m tools.validate \ --id sd-market-data-feed 

_# Refine using human notes_ python -m tools.refine \ --id sd-market-data-feed 

_# Generate a practice package_ python -m tools.create_practice_question \ --id code-stream-merger 

_# Run all checks_ make validate make practice-test 

_# Build guides_ make guides 

_# Build everything_ make all 

_# Package a release_ python -m tools.release --version 0.1.0 

## 21. MVP acceptance criteria 

The first meaningful MVP is complete when all of the following are true: 

1. A text description can create a new question package. 

2. An image can create a new question package. 

3. Original inputs are preserved. 

4. All questions use stable metadata and schemas. 

5. The system generates three PDFs. 

6. The system-design PDF contains rendered diagrams. 

7. Catalogs are generated automatically. 

8. Coding questions link to runnable directories. 

9. Reference C++ solutions compile and pass tests. 

- 10.Human notes can refine an answer. 

- 11.Draft questions cannot be published. 

- 12.Broken IDs, assets, or diagrams fail validation. 

- 13.A clean checkout can reproduce all outputs. 

- 14.One command can build and test the entire project. 

- 15.Git clearly shows every content and code revision. 

## 22. Features intentionally postponed 

The following should not be part of the first implementation: 

- LeetCode-style web editor. 

- Browser execution sandbox. 

- User accounts. 

- Payment system. 

- Anti-piracy delivery integration. 

- Question recommendation engine. 

- Vector database. 

- Automatic web scraping. 

- Fully autonomous continuous research. 

- Company-specific question databases. 

- Multi-model routing. 

- Fine-tuning. 

- Automated difficulty decisions. 

- Automatic publication. 

- Adaptive mock interviews. 

- Student analytics. 

These features should be considered only after the repository workflow produces consistently strong content. 

## 23. Later-stage architecture 

After the question bank and workflow mature, the project can add: 

### 23.1 Similarity and deduplication 

Use embeddings or structured similarity to detect: 

- Duplicate prompts. 

- Questions testing the same core concept. 

- Slight variants that should become follow-ups. 

- Missing links between related questions. 

### 23.2 Parallel agent review 

Separate agents can independently review: 

- Technical correctness. 

- Interview realism. 

- C++ correctness. 

- Low-latency claims. 

- Writing quality. 

- Test coverage. 

Codex supports supervising separate agents and isolated worktrees, but parallelism should be introduced only after individual workflows and quality gates are stable. 

### 23.3 Adaptive interview practice 

A later interview agent could: 

- Present a question. 

- Track the candidate’s assumptions. 

- Ask realistic follow-ups. 

- Score the response against the rubric. 

- Recommend prerequisite material. 

- Link to runnable exercises. 

### 23.4 Delivery platform 

The anti-piracy platform can eventually consume: 

- Versioned PDFs. 

- Per-user watermarks. 

- HTML content. 

- Question-level access. 

- Practice-repository archives. 

- Release manifests. 

The content repository should remain independent of the delivery platform. 

## 24. Final implementation principle 

The project should begin as a **content compiler with human review** , not as an autonomous education platform. 

The correct initial sequence is: 

Define quality 

- -> standardize content 

- -> make builds deterministic 

- -> generate runnable exercises 

- -> add human review 

- -> scale the question bank 

- -> automate repeated workflows 

- -> build distribution and interactive products 

The most important early success metric is not the number of generated questions. 

It is the percentage of generated drafts that, after a small amount of human editing, become material that an experienced C++ quant developer would genuinely trust for final interview preparation. 
