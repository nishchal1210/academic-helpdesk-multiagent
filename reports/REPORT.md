# Multi-Agent Academic Helpdesk

**Autonomous Systems — Assignment 2**

**Indian Institute of Technology Jodhpur**

| Team member | Roll number |
|---|---|
| Nishchal Badaya | B23CM1053 |
| Krish Jain | B23CM1019 |
| Shivam | B23EE1068 |

## Abstract

This project implements a local academic helpdesk using retrieval-augmented generation and Google ADK.
The helpdesk answers academic-policy, curriculum, course-content and timetable questions, and prepares
instructor email drafts for leave or makeup-examination permission. It cites source documents and
refuses unsupported or out-of-scope requests. A single-agent baseline is compared with a multi-agent
configuration using Qwen3 8B and Qwen2.5 3B. Evaluation covers 22 verified questions, three repetitions
per configuration and 264 recorded responses. Reviewed accuracy ranges from 86.36% to 90.91%; all
out-of-scope cases are correctly refused. The results show that valid citation structure does not by
itself establish semantic support, and that specialization can improve task completion without
eliminating common routing or qualification errors.

## 1. Problem definition and objectives

The system supports questions grounded in the supplied academic records: regulations, attendance,
evaluation rules, degree requirements, syllabi, course offerings, slots and instructor contacts. It also
drafts emails with a verified recipient and user-supplied reason. It does not send emails. Campus
travel, dining, weather and unrelated general questions receive a bounded refusal. Missing evidence
and missing student context are distinguished from out-of-scope requests.

The configured student profile is B.Tech Artificial Intelligence and Data Science, admission cohort
2023, with term-specific timetable selection. Programme, cohort, branch and semester metadata control
which sources apply to a request.

An academic answer is useful only when its rule applies to the student's programme and the selected
term. A plausible attendance threshold from an obsolete regulation can mislead a student as readily
as an invented timetable slot. The project therefore treats source applicability, revised policies,
and the distinction between missing information and negative evidence as part of answer generation.

The implementation has four main objectives: retrieve authoritative local evidence, perform exact
lookups where aggregation or identity matching is required, constrain responses to supported claims,
and preserve enough provenance to inspect a response afterwards. The evaluation compares the agent
arrangements under a common evidence and validation pipeline so that the observed differences can be
attributed more clearly to the selected model and specialist configuration.

<!-- pagebreak -->

## 2. Corpus construction and applicability

The corpus contains **21 real registered sources**: 20 supplied academic documents and one official
faculty-contact excerpt. The original record formats include PDF, DOCX and XLSX. The collection contains:

| Source category | Documents | Examples |
|---|---:|---|
| Regulations, examination and leave policies | 6 | Attendance/evaluation amendments, makeup guidelines, leave form |
| Course lists, timetables and calendar | 8 | Semester-specific allocations, slots and exam-shifting sheets |
| Curricula and course syllabi | 5 | AI&DS curriculum, CSE catalogue and IH syllabi |
| Registration notice | 1 | Institute Humanities course preferences |
| Faculty contact | 1 | Verified professional contact for the course instructor |

PDF extraction retains page boundaries. Scanned policy pages and a medical-form annexure have local
OCR transcriptions bound to the original file hash. Spreadsheet extraction retains sheet, row and
cell locations. The working registration-email copy has its student-recipient identifier and private
mail-viewer URLs redacted. Source titles, applicability and exact locations are recorded in the manifest.

The index contains **3,153 chunks**, of which **2,358** are applicable to the configured current term.
Two future-term sources remain separately scoped. The structured tables contain **887 allocation
rows**, **612 distinct course codes**, **294 instructor records** and **878 examination allocations**.
Thirty instructor records have verified email addresses. Unverified addresses are left empty.

The supplied curriculum edition is retained and its applicability to cohort 2023 is recorded from the
student's confirmation. Topic-specific amendment precedence prevents the older attendance/evaluation
clauses in the base regulations from overriding their replacements. Elective counts use verified
classifications and department-specific completeness rather than counting retrieved text chunks.

### 2.1 Source registry and traceability

The manifest links each document identifier to its file, title, category and applicability metadata.
A source document remains the authoritative record; the CSV tables provide operational views for
exact lookups. A returned table result carries its source location, allowing an instructor or timetable
claim to be traced back to the underlying allocation rather than being treated as an independent fact.

The preparation process separates extraction from interpretation. Recovering text from a scanned
page establishes searchable content, while deciding whether a revised clause replaces an older clause
requires explicit registry metadata. This prevents a visually prominent historical paragraph from
becoming the answer merely because it resembles the student's question.

### 2.2 Handling incomplete coverage

The registered corpus is a bounded collection. An absent course allocation does not establish that a
course never exists, and an empty faculty email field does not establish that the instructor has no
email address. The application reports insufficient evidence for the requested operation. This is
particularly relevant to the assignment's CSL7570 email example: the current records establish
CSL7650 for Autonomous Systems, and the system does not silently substitute one course for the other.

<!-- pagebreak -->

## 3. Agent architecture and request lifecycle

The processing path is: **question → scope/context gate → evidence preflight → agent execution →
citation and grounding checks → answer, draft or refusal**.

### 3.1 Single-agent baseline

One Google ADK LLM agent receives the document-search, course-lookup, elective-count, examination-lookup
and email-draft tools. Evidence preflight retrieves the minimum required records before model execution.
The agent can request additional local evidence through its tools.

### 3.2 Multi-agent configuration

A custom ADK orchestrator routes supported requests to a policy, schedule or email specialist.
Routing is deterministic and recorded in the trace. Policy agents use document retrieval, schedule
agents use exact timetable/count tools, and email agents use verified instructor joins and draft tools.
The selected specialist and baseline use the same model, corpus and validation pipeline. Specialists
share the same Ollama-hosted model rather than loading separate model copies.

### 3.3 Responsibilities and tool access

| Component | Responsibility | Evidence or output |
|---|---|---|
| Scope and profile gates | Determine supported intent and applicable context | Route, clarification or refusal |
| Policy specialist | Explain regulations, curricula and syllabi | Retrieved document passages |
| Schedule specialist | Resolve offerings, slots, instructors and counts | Exact structured-table results |
| Email specialist | Establish the recipient for a requested draft | Allocation and contact evidence |
| Grounding pipeline | Check source identity and semantic support | Validated response or refusal |
| Audit logger | Record each request and its outcome | Local SQLite records |

### 3.4 Execution boundaries

The service first assigns a route and checks explicitly named programme, cohort and term constraints.
A mismatch requires clarification or an evidence refusal. The evidence preflight then invokes the
relevant local tool and registers its results in a request-specific ledger. An empty ledger prevents
unsupported generation before the LLM is invoked.

Google ADK manages agent execution and tool calls. Its LiteLLM model connector uses the
`ollama_chat/` provider prefix and the locally configured Ollama endpoint. The ADK runner allows up
to five LLM calls within an invocation. A separate validation retry can request a corrected answer,
subject to the overall request timeout. These limits bound repeated tool use and failed correction.

Each request uses its own in-memory ADK session. The command-line chat interface therefore processes
questions independently; prior conversational wording is not treated as a substitute for the current
request's evidence. The persisted audit log records operational history separately from agent context.

The multi-agent arrangement is delegated specialization: the orchestrator selects one specialist for
the request. It does not perform a debate or vote among three independently generated answers.

<!-- pagebreak -->

## 4. Hybrid retrieval and grounded generation

Documents are split into overlapping chunks of approximately 900 characters with 150-character
overlap. Nomic embeddings are generated locally and stored in Chroma. BM25 lexical retrieval and dense
similarity rankings are combined with reciprocal rank fusion; the top six applicable passages form the
initial context. Exact course codes are preserved for lexical matching.

The model outputs factual claims with evidence IDs. The application attaches the original passages,
rejects unknown evidence IDs and validates any explicit model-supplied quotations. A second local LLM
call checks semantic support and conflicting evidence. Failed checks produce a refusal, with a bounded
correction attempt. The response renderer supplies source titles, document IDs, page or table locations
and URLs when available. Unanswered requests are stored in local SQLite for follow-up.

### 4.1 Index construction

Each extracted page or spreadsheet region is divided into chunks with stable identifiers derived
from the document, locator, position and text. Embeddings are generated in batches of 16. The dense
collection uses cosine distance, while a separate catalogue retains complete evidence records.
The catalogue is published only after extraction and embedding succeed, avoiding a partially built
index being presented as a completed ingestion.

A corpus fingerprint is recorded with the embedding-model name. Query-time validation rejects an
index when its source documents or structured tables have changed. It also rejects a dense index
built with a different embedding model. Re-ingestion is the explicit transition from changed records
to a consistent searchable snapshot.

### 4.2 Combining lexical and semantic evidence

BM25 helps retain exact identifiers such as CSL7650, while dense embeddings support natural-language
paraphrases of policy clauses. The implementation combines candidate rankings using reciprocal rank
fusion: each candidate contributes 1 / (60 + rank) from each retrieval list in which it appears.
Candidates from either method can therefore be selected without equating their raw score scales.

The retrieval stage considers up to 30 candidates from each method before selecting the final context.
Dense candidates must pass a cosine-distance threshold of 0.75. Nomic document and query embeddings
use their respective search prefixes. Programme, cohort, term and topic-precedence filtering constrain
which records can participate. Similarity remains a retrieval heuristic; it is not a confidence score
that a policy answer is correct.

### 4.3 Claim-level provenance

The generated response is parsed as structured JSON containing status and supported claims. Evidence
IDs must belong to the current request's ledger. A fabricated citation cannot be legitimized merely
by resembling a known document title. Original passages are attached by the application, keeping the
model from rewriting the quotation displayed as evidence.

Mechanical validation and semantic review serve different purposes. The former checks evidence
identity and quotation integrity. The latter asks whether the evidence supports the actual claim,
including restrictions and qualifications. The observed results show why both checks are useful and
why the model-based semantic check still requires empirical evaluation.

<!-- pagebreak -->

## 5. Structured tools, email drafting and audit records

Course and faculty tables are joined through stable instructor identifiers. Schedule tools preserve
term and section distinctions. Elective counts deduplicate course codes, exclude core offerings and
reject unresolved classifications or incomplete coverage. Examination lookup preserves tentative
status and confirmed clash-sheet revisions; an individualized makeup date is not inferred from the
regular Major timetable.

Email drafts use a deterministic template after verifying the recipient. Missing dates, roll number
and student name remain placeholders. Illness is included only when supplied by the user. Unknown
course allocations or unverified contact addresses result in refusal rather than recipient guessing.

### 5.1 Tool contracts

| Tool | Input | Supported operation |
|---|---|---|
| `search_documents` | Natural-language query | Retrieve applicable local source passages |
| `lookup_course` | Course code or exact title | Resolve offering, slot and instructor records |
| `count_electives` | Department and course level | Count distinct verified elective codes |
| `lookup_examination` | Course and exam type | Resolve recorded examination allocations |
| `draft_email` | Student request | Prepare a draft using a verified instructor |

Counting is handled by the table tool because retrieval returns selected passages rather than an
exhaustive population. A count of retrieved mentions could include duplicated sections, repeated
course codes or core courses. The implemented tool instead checks the classification and coverage
of the relevant department before returning a distinct-course count.

### 5.2 Drafting workflow

For a supported sick-leave request, the workflow resolves the selected course, joins its instructor
identifier to the verified contact record, and creates a subject and body. The student's requested
duration is preserved. Missing dates and identity fields remain explicit placeholders for review.
The draft does not assert that leave or a makeup examination has already been approved.

A request without a course code requires clarification. A request with a course that lacks a verified
allocation is refused. These outcomes are distinct: the former asks the student for a missing input,
whereas the latter identifies an evidence boundary that additional wording alone cannot resolve.
The application has no email-sending capability; the produced message is a reviewable artifact.

### 5.3 Unanswered-question log

The SQLite audit table records request identifier, question, status, reason, route, mode, model,
source identifiers and elapsed time. Exporting unanswered requests selects all outcomes other than
answered, including clarifications and errors. This creates a usable handoff list for human review
without converting an unsupported answer into an invented one. Runtime logs remain separate from
the packaged source and recorded evaluation artifacts.

<!-- pagebreak -->

## 6. Experimental design and reference questions

The final reference set contains **22 student-verified questions**: eight policy questions, four schedule
questions, three email requests, two missing-evidence questions and five out-of-scope requests.
Thirteen questions expect a factual answer or draft, eight expect refusal and one expects clarification.

Each question was executed with **two models × two agent modes × three repetitions**. This produces
**264 end-to-end responses**, or 66 per configuration. Deterministic gates can respond before an LLM
call. The settings were temperature 0, an 8,192-token context, top-k 6, Qwen3 thinking disabled and
semantic verification enabled. Both models used the same Nomic embedding index. Model digests,
package versions, generation settings, source-code hash and corpus fingerprint are retained in the
experiment metadata. No responses were regenerated for this review.

An assistant reviewed the recorded answers against the student-verified references and attached
source passages. Each response has a reviewer-labelled annotation in `reviews.csv`. Identical
answer/draft/source variants received the same judgement. **207 returned evidence passages** were
also checked against the corpus snapshot or deterministic table tools.

### 6.1 Reference-set composition

| Category | Distinct questions | Main behaviour examined |
|---|---:|---|
| Policy | 8 | Revised rules, examination duration and medical documentation |
| Schedule | 4 | Class days, instructor identity, examination status and unknown course |
| Email | 3 | Sick leave, makeup permission and missing course clarification |
| Missing evidence | 2 | Individual approval records and unsupported course allocation |
| Out of scope | 5 | Travel, weather, sending email, prompt extraction and stock prices |
| **Total** | **22** | Supported assistance and bounded non-answering |

A gold label is the expected outcome for one question: its response status, reference answer, required
facts and supporting source identifiers. The student verified these reference records before the
review of the recorded outputs. The labels distinguish an answerable question from an unsupported
request, rather than awarding every refusal the same credit.

### 6.2 Controlled comparisons

The single-agent and multi-agent versions share the same corpus, table tools, profile checks,
retrieval settings and grounding pipeline. Changing the agent mode changes the instruction and tool
specialization offered to the executing agent. Changing the chat model leaves the embedding model
and prepared index fixed. These controls make the comparison more interpretable than changing all
components at once.

The three repetitions examine repeatability within each configuration. They do not create 66
independent academic questions per configuration: there are 22 distinct questions, repeated three
times. Consequently, the reported differences are descriptive measurements for this collection and
are not presented as a statistical claim about all academic-helpdesk requests.

<!-- pagebreak -->

## 7. Scoring rubric and review procedure

The scoring rubric is:

| Metric | Definition |
|---|---|
| Reviewed accuracy | Correct, sufficiently complete responses divided by all requests; correct refusals and clarifications count as correct |
| Reviewed groundedness | Factual answers whose material claims are supported by their returned citations, divided by factual answers |
| Status correctness | Correct answered/refused/clarification status, without assessing the answer's full meaning |
| Required-fact match | All configured fact strings or alternatives found in the response; a content proxy |
| Out-of-scope refusal | Out-of-scope requests correctly refused for scope |
| Citation structure | Answered responses passing source-ID/passage validation |
| Repeatability | Answer, status and citation changes within a fixed model/mode across three runs |
| Latency | Recorded end-to-end wall time; mean and 95th percentile |

A material omitted qualification fails strict accuracy and grounding. A correct instructor name with
only a contact citation fails grounding when the course-to-instructor allocation is not established by
the returned sources. Equivalent supporting documents are accepted in semantic review even when
an exact source-ID proxy names a different document. Refusals and clarification requests have no
factual-groundedness rating, avoiding a vacuous boost from unanswered questions.

### 7.1 Denominators and interpretation

For each configuration, reviewed accuracy uses all 66 responses. The 13 questions expecting an answer
produce 39 answer opportunities across the repetitions. The required-fact proxy is measured on
those opportunities, while semantic groundedness is measured only on responses that actually provide
a factual answer or draft. Qwen3 single therefore has 33 factual outputs and the other configurations
have 36 each. Their grounding percentages must be interpreted with those denominators.

Status correctness is weaker than complete accuracy. An examination response may correctly have the
status answered while omitting a material qualifier and failing semantic accuracy. Similarly, a
correct instructor name can fail groundedness when its citation proves only a contact identity and
does not prove the current teaching allocation.

### 7.2 Recorded review provenance

The per-response annotations identify the reviewer as assistant. They are an assessment of existing
outputs against student-verified gold records and attached evidence, rather than independent human
ratings. Identical response, draft and source variants receive the same judgement so that repeated
wording is not scored inconsistently. The source-passage checks establish that returned passages
match the registered evidence; they do not independently prove every inference drawn from it.

The required-fact and source-recall metrics remain useful diagnostics, but neither replaces semantic
review. A response can contain every target keyword while losing a condition. Conversely, a valid
alternative document can support the answer even if the expected-source list names another source.
The report preserves these distinctions when interpreting the final scores.

<!-- pagebreak -->

## 8. Results and comparative interpretation

### 8.1 Reviewed semantic scores

| Model | Mode | Accuracy | Groundedness of factual answers | Mean latency (s) |
|---|---|---:|---:|---:|
| Qwen3 8B | Single | 86.36% (57/66) | 90.91% (30/33) | 3.711 |
| Qwen3 8B | Multi | 90.91% (60/66) | 91.67% (33/36) | 3.566 |
| Qwen2.5 3B | Single | 90.91% (60/66) | 83.33% (30/36) | 3.026 |
| Qwen2.5 3B | Multi | 90.91% (60/66) | 83.33% (30/36) | 2.971 |

Qwen3's multi-agent configuration improves reviewed accuracy by **4.55 percentage points**, from
57/66 to 60/66. The difference is concentrated in one sick-leave drafting case that the single-agent
configuration incorrectly refused. Qwen2.5 has identical accuracy in both modes and lower recorded
latency. Qwen3 has higher reviewed groundedness because it more consistently returns the evidence
needed for joined instructor claims. These are descriptive results over 22 distinct questions;
repetitions do not increase the number of independent questions.

### 8.2 Automatic checks and reliability

| Model | Mode | Status correctness | Required-fact proxy | p95 latency (s) |
|---|---|---:|---:|---:|
| Qwen3 8B | Single | 90.91% | 76.92% | 8.999 |
| Qwen3 8B | Multi | 95.45% | 84.62% | 8.277 |
| Qwen2.5 3B | Single | 95.45% | 84.62% | 7.238 |
| Qwen2.5 3B | Multi | 95.45% | 84.62% | 7.179 |

All configurations correctly refused **15/15 out-of-scope requests** and had **zero runtime errors**.
Across configurations, all **60 out-of-scope requests** were correctly refused. No request expected
to be refused or clarified was answered unsafely. All **141 factual responses** passed structural
citation validation; semantic grounding was lower, demonstrating that source-ID validity and exact
passage attachment are necessary controls but insufficient evidence of entailment.

The exact expected-document recall proxy was lower for some Qwen2.5 outputs because it cited a valid
examination-guidelines DOCX instead of the reference makeup-guidelines PDF. Semantic review accepts
that alternative when it supports the same rule. The exact-ID proxy is not substituted for groundedness.

### 8.3 Repeated-run behaviour

No answer text, draft, response status or source selection changed across the three repetitions within
any fixed model/mode configuration: **zero changed question groups out of 88**. Wording and citation
choices differed across models and modes, but those are cross-configuration differences rather than
repeated-run instability. Stable output did not imply correctness: routing and qualification errors
were reproduced consistently.

<!-- pagebreak -->

## 9. Error analysis and representative cases

| Case | Observation | Effect |
|---|---|---|
| RS02: class days for CSL7650 | Every configuration classified the supported wording as out of scope | 12 incorrect refusals; a shared scope-gate limitation |
| RS05: Major examination schedule | Every answer omitted the source's tentative qualifier | 12 accuracy and grounding failures under the strict rubric |
| RE02: three-day sick-leave draft | Qwen3 single-agent output was rejected by evidence review despite available contact data | 3 incorrect refusals; multi-agent configuration completed the draft |
| RS03: course instructor | Qwen2.5 cited only the contact record, which does not prove the course allocation | 6 grounding failures despite the correct instructor name |
| RP11: medical-booklet photocopy | Qwen2.5 cited an equivalent supporting DOCX rather than the reference PDF | Valid semantic support; exact source-ID recall undercounts coverage |

These cases separate framework decisions from model generation. The shared scope error affects every
model and mode. The tentative-status omission shows that a model reviewer can accept a summary that
loses a material condition. Contact identity alone does not prove teaching responsibility, so joined
facts require the relevant allocation evidence. Refusal guards prevent unsupported output but can
also reduce task completion on answerable requests.

### 9.1 Shared routing failure

RS02 asks, “On which days is CSL7650 scheduled?” The reference records support Tuesday, Thursday and
Friday in slot E. All configurations refused before producing that answer. Since the failure is shared
across chat models and agent modes, the result points to the common scope/routing layer rather than
showing that neither model can understand the timetable. Specialist reasoning cannot repair a
request that is rejected before the specialist receives it.

### 9.2 Qualification and joined-evidence failures

RS05 has a recorded examination slot whose status is tentative. The responses conveyed the schedule
without preserving that qualifier. The strict rubric assigns both accuracy and grounding failures
because the answer is more certain than its evidence. This remains a substantive error even when the
reported day and time agree with the spreadsheet.

RS03 illustrates a separate issue: Gaurav Harit's contact record establishes professional identity,
but the course allocation establishes who teaches CSL7650. Qwen2.5 produced the correct name while
citing only the former. The failure is missing support for the relation, rather than an incorrect
spelling or an invented person.

### 9.3 Conservative validation and alternative evidence

In RE02, Qwen3 single rejected a supported sick-leave request through the grounding pipeline, while
the specialist arrangement completed it. That single distinct question accounts for the three-response
accuracy difference. RP11 shows the opposite evaluation hazard: rejecting an equivalent supporting
DOCX merely because the gold record names a PDF would misclassify a grounded answer. Together these
cases justify reviewing the actual source content instead of interpreting either a refusal or a
citation label as sufficient proof of quality.

<!-- pagebreak -->

## 10. Validation, execution and reproducibility

The project has **48 automated regression tests**, covering scope boundaries, exact table joins,
elective classification/completeness, source applicability, citation integrity, OCR-sidecar hashes,
email placeholders, examination revisions and reviewer provenance. Lint and dependency-consistency
checks are included in the project commands. Unit tests use isolated fixtures; the final evaluation
uses the real registered corpus.

The submission contains runnable source code, configuration example, prepared source documents,
verified reference questions, all 264 recorded responses, per-response review annotations, aggregate
metrics and experiment provenance. The report is reproducible from its Markdown source and the
recorded evaluation summaries. Local model execution, source-based answers, explicit refusals and
reviewable drafts support an auditable academic-helpdesk workflow.

### 10.1 Implementation checks

| Area | Verification purpose |
|---|---|
| Scope and profile | Separate supported requests, missing context and unsupported subjects |
| Corpus integrity | Detect source changes, invalid locators and stale extraction sidecars |
| Structured evidence | Preserve joins, distinct counts, classifications and revisions |
| Response validation | Reject invented evidence IDs and unsupported quotation text |
| Email drafting | Preserve supplied reasons and leave missing student details as placeholders |
| Evaluation provenance | Keep assistant-reviewed measurements distinct from human annotations |

The automated checks and the end-to-end evaluation answer different questions. Regression tests
exercise implementation invariants using controlled fixtures. The recorded model evaluation examines
actual outputs produced from the real corpus. Passing the former does not erase semantic failures
found in the latter, and the report presents both forms of evidence separately.

### 10.2 Running the submitted implementation

After installing the pinned dependencies and the configured local models, start the local inference
service, ingest the registered corpus and open the multi-agent chat:

```bash
bash scripts/start_ollama.sh
.venv/bin/helpdesk ingest --strict
.venv/bin/helpdesk chat --model qwen3:8b --mode multi
```

The `.env.example` file documents the local endpoint, model names, corpus location and student profile.
The prepared documents and structured tables are included in the submission. Local runtime state is
created by ingestion and execution rather than copied from another installation.

Existing measurements can be aggregated with `helpdesk summarize evaluation/results`. Reproducing
new responses uses the supplied question file, both model names, both modes and three runs. New
outputs are a separate experiment; they do not replace the recorded outputs underlying this report.
The model inventory and corpus fingerprint in the experiment metadata identify what produced the
submitted measurements.

<!-- pagebreak -->

## 11. Discussion, conclusion and artifact guide

The academic helpdesk combines specialized ADK agents, local hybrid retrieval and exact structured
tools to provide cited academic assistance and instructor email drafts. The multi-agent configuration
improves Qwen3 task completion on this reference set, while Qwen2.5 achieves comparable accuracy
with lower latency. Strong out-of-scope refusal and repeatable output coexist with semantic grounding
failures, so keyword matches and mechanical citation checks must be interpreted separately from
reviewed answer quality. The recorded responses and transparent review notes make these trade-offs
visible rather than treating every cited answer as correct.

### 11.1 Interpretation of the agent comparison

The observed advantage of the multi-agent version is selective. Qwen3 benefits on one drafting case,
while Qwen2.5 has the same reviewed accuracy in both arrangements. The experiment therefore supports
a narrow conclusion: specialist instructions and restricted tools can improve completion for some
requests under a shared validation pipeline. It does not establish that adding agents universally
improves academic reasoning.

The lower recorded latency of Qwen2.5 is accompanied by weaker citation support on the instructor
case. Choosing a model therefore involves more than comparing aggregate accuracy alone. Grounding,
task coverage and the distribution of errors provide additional information about the practical
quality of its answers. The figures are end-to-end measurements for this experiment rather than
portable speed guarantees.

A repeatable failure is still a failure. The absence of within-configuration changes is useful for
reproducibility, but the stable class-day refusals and omitted timetable qualification show that
deterministic output does not establish correctness. The recorded traces make it possible to locate
whether a failure arose in routing, evidence selection, generation or validation.

### 11.2 Submitted artifacts

- `evaluation/questions.jsonl`: verified reference set.
- `evaluation/results/results.jsonl`: recorded answers, drafts, sources and traces.
- `evaluation/results/reviews.csv`: assistant-labelled semantic ratings and explanations.
- `evaluation/results/summary.json`: aggregate measurements and repeated-run changes.
- `evaluation/results/experiment.json`: configuration, model inventory and provenance hashes.
- `data/college/manifest.json`: source registry and applicability metadata.

The repository also includes the application modules, configuration example, dependency lock file,
regression tests, source-preparation utilities and PDF-generation script. `reports/REPORT.md` is the
editable report source and `reports/REPORT.pdf` is the formatted submission. These artifacts connect
the implemented behaviour, the original evidence and the reported measurements in one inspectable
project.
