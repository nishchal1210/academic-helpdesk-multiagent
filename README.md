# Multi-Agent Academic Helpdesk

**Autonomous Systems — Assignment 2**

| Team member | Roll number |
|---|---|
| Nishchal Badaya | B23CM1053 |
| Krish Jain | B23CM1019 |
| Shivam | B23EE1068 |

A local academic helpdesk for IIT Jodhpur. It answers questions about academic regulations,
curriculum, course contents and timetables, and drafts leave or makeup-examination emails to
verified instructors. Answers cite the supplied documents. Unsupported requests receive a refusal.

## Features

- Google ADK single-agent baseline and multi-agent orchestrator with policy, schedule and email specialists.
- Ollama-hosted Qwen3 8B and Qwen2.5 3B through the LiteLLM connector.
- Hybrid RAG using Nomic embeddings, persistent Chroma vectors, BM25 and reciprocal rank fusion.
- PDF, DOCX and XLSX ingestion with page, sheet, row and cell provenance; cached OCR for scanned pages.
- Exact course, instructor, elective-count and examination-schedule tools.
- Source-ID validation, exact source-passage attachment and a second LLM grounding check.
- Email drafts with verified recipients and placeholders for missing student details; no email sending.
- Local SQLite logging of unanswered questions and reproducible model evaluation.

## Run

From this directory, start Ollama in one terminal:

```bash
bash scripts/start_ollama.sh
```

In another terminal:

```bash
source .venv/bin/activate
helpdesk doctor
helpdesk chat --model qwen3:8b --mode multi
```

Type `/quit` to exit. Use `--model qwen2.5:3b` for the other model or `--mode single` for the baseline.
Each question is independent; include the course code in follow-up questions.

Examples:

```bash
helpdesk ask "What is the slot for the course Autonomous Systems?"
helpdesk ask "How many 400-level electives are offered by the Humanities department this semester?"
helpdesk ask "Write an email to the CSL7650 instructor requesting leave for 2 days."
helpdesk ask "What dining options are available on campus?"
```

Add `--json` to inspect source passages, routing and execution traces.

## Installation

Python 3.11 or later and Ollama are required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,report]'
cp .env.example .env
```

On systems without `ensurepip`, create the environment with `python3 -m venv --without-pip .venv`
and bootstrap it using an existing pip installation:
`/path/to/working/python -m pip --python .venv install pip`.

The startup script uses the existing local Ollama installation. Set `HELPDESK_OLLAMA_BIN` and
`OLLAMA_MODELS` when their paths differ. Download `qwen3:8b`, `qwen2.5:3b` and `nomic-embed-text`
with Ollama on a fresh installation. `requirements.lock.txt` records the tested Python dependency versions.

## Configuration and data

`.env` selects the data directory, state directory, models, academic term, programme, branch and
admission cohort. The supplied configuration uses B.Tech AI & DS, cohort 2023, term `2026-27-I`.

| File | Purpose |
|---|---|
| `data/college/manifest.json` | Source registry, applicability and policy-amendment precedence |
| `data/college/documents/` | 21 registered sources and source-hash-checked OCR sidecars |
| `data/college/courses.csv` | Course allocations, slots, departments, levels and source locators |
| `data/college/faculty.csv` | Instructor identities and verified email addresses |
| `data/college/examinations.csv` | Major/Minor schedules and confirmed or unconfirmed revisions |
| `.runtime/college/` | Generated vector index, catalogue and local question log |

Build or refresh the index after changing documents, CSVs, source metadata or the embedding model:

```bash
helpdesk ingest --strict
```

Changing the chat model does not require rebuilding the embedding index. Course counts require
verified completeness and elective classifications. Missing contacts are never guessed. The current
records establish CSL7650 as Autonomous Systems; they do not establish a current CSL7570 offering.

## Architecture

The scope gate checks the request, then evidence preflight retrieves applicable passages or exact table
results. In single mode one ADK agent receives all tools. In multi mode a deterministic ADK
orchestrator invokes the relevant specialist. The selected model returns claims and evidence IDs;
the application attaches original passages, validates citations and reviews semantic support.
The renderer produces the answer, source references and optional email draft.

## Evaluation

The recorded experiment contains **22 verified questions, two models, two agent modes and three
repetitions: 264 responses**. The final report is [REPORT.pdf](reports/REPORT.pdf), with editable source
in [REPORT.md](reports/REPORT.md).

| Artifact | Contents |
|---|---|
| `evaluation/questions.jsonl` | Verified questions, reference answers and source labels |
| `evaluation/results/results.jsonl` | Recorded answers, sources, traces and automatic checks |
| `evaluation/results/reviews.csv` | Assistant-reviewed accuracy and groundedness with per-response notes |
| `evaluation/results/summary.json` | Aggregated metrics and repeated-run changes |
| `evaluation/results/experiment.json` | Models, settings, package versions and provenance hashes |

Reproduce the experiment in a new output directory:

```bash
helpdesk evaluate --dataset evaluation/questions.jsonl \
  --models qwen3:8b qwen2.5:3b --modes single multi --runs 3 \
  --output evaluation/runs/reproduction
helpdesk summarize evaluation/results
helpdesk unanswered --output /tmp/unanswered.csv
```

Semantic accuracy, citation support, status correctness and keyword matches are separate measures.
The report documents both successful responses and observed failure cases.

## Validation and packaging

```bash
pytest -q
ruff check helpdesk scripts tests
python -m pip check
python scripts/build_report.py
python scripts/package_submission.py --include-college-data
```

Unit tests use isolated synthetic fixtures; the application defaults to the real college collection.
The package excludes environments, model weights, credentials, runtime logs and duplicate uploads.
Queries and source records are processed locally by the configured Ollama service.
