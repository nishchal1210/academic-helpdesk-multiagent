"""Repeatable experiments with separate automatic checks and provenance-labelled semantic reviews."""
from collections import defaultdict
import csv
from dataclasses import replace
from datetime import datetime, timezone
from importlib import metadata
import json
import hashlib
from pathlib import Path
import statistics

from .corpus import atomic_json
from .service import ask


def load_cases(path: Path):
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    ids = [c["id"] for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Evaluation question IDs must be unique.")
    for c in cases:
        if c.get("expected_status") not in {"answered", "refused", "needs_clarification", None}:
            raise ValueError("Invalid expected status.")
    return cases


def proxy_checks(case, answer):
    expected = case.get("expected_status")
    content = (answer.answer + "\n" + (answer.draft or "")).casefold()
    facts = case.get("required_facts", [])
    # Each fact can be a string or a list of acceptable paraphrase alternatives.
    fact_results = [any(str(v).casefold() in content for v in (f if isinstance(f, list) else [f])) for f in facts]
    expected_docs = set(case.get("expected_document_ids", []))
    actual_docs = {s.document_id for s in answer.sources}
    return {
        "status_correct": answer.status == expected if expected is not None else None,
        "fact_match_proxy": all(fact_results) if facts and answer.status == "answered" else
                            False if facts else None,
        "expected_source_recall": len(expected_docs & actual_docs) / len(expected_docs) if expected_docs else None,
        "citation_structure_valid": answer.structural_grounding if answer.status == "answered" else None,
        "correct_out_of_scope_refusal": answer.status == "refused" and answer.reason == "out_of_scope"
            if case.get("category") == "out_of_scope" else None,
        "unsafe_answer": answer.status == "answered" if expected in {"refused", "needs_clarification"} else None,
    }


async def evaluate(settings, dataset, output_dir, models, modes, runs, backend="adk"):
    cases = load_cases(dataset)
    if backend == "adk" and any(c.get("expected_status") is None for c in cases):
        raise ValueError("Fill the gold answers/statuses before running the real benchmark.")
    output_dir.mkdir(parents=True, exist_ok=False)
    versions = {p: metadata.version(p) for p in ["google-adk", "litellm", "chromadb", "ollama"]}
    from .corpus import Registry
    registry = Registry(settings.data_dir)
    source_hash = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        source_hash.update(path.name.encode() + path.read_bytes())
    model_inventory = []
    if backend == "adk":
        import ollama
        client = ollama.Client(host=settings.host, timeout=10)
        model_inventory = [m.model_dump(mode="json") for m in client.list().models]
    atomic_json(output_dir / "experiment.json", {
        "created_utc": datetime.now(timezone.utc).isoformat(), "versions": versions,
        "settings": {k: str(v) if isinstance(v, Path) else v for k, v in settings.__dict__.items()},
        "corpus_fingerprint": registry.fingerprint(), "synthetic": registry.manifest.synthetic,
        "application_source_sha256": source_hash.hexdigest(), "ollama_model_inventory": model_inventory,
        "backend": backend, "models": models, "modes": modes, "runs": runs,
        "dataset": str(dataset), "cases": cases,
        "note": "No human semantic scores are inferred from automatic source/keyword checks."})
    rows = []
    with (output_dir / "results.jsonl").open("w") as f:
        for model in models:
            for mode in modes:
                for run in range(1, runs + 1):
                    for case in cases:
                        answer = await ask(replace(settings, model=model), case["question"], mode, backend)
                        row = {"case_id": case["id"], "category": case["category"], "run": run,
                               "model": model, "mode": mode, "question": case["question"],
                               "answer": answer.model_dump(), "checks": proxy_checks(case, answer)}
                        rows.append(row)
                        f.write(json.dumps(row, ensure_ascii=False) + "\n")
                        f.flush()
                        print(f"{model} {mode} run={run} {case['id']}: {answer.status}", flush=True)
    with (output_dir / "reviews.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["question_id", "accuracy", "groundedness", "reviewer", "notes"])
        for r in rows:
            writer.writerow([r["answer"]["question_id"], "", "", "", ""])
    summarize(output_dir)
    return rows


def summarize(output_dir):
    rows = [json.loads(line) for line in (output_dir / "results.jsonl").read_text().splitlines()]
    annotations = {}
    for filename, default_reviewer in [("human_review.csv", "human"), ("reviews.csv", "unspecified")]:
        review = output_dir / filename
        if review.exists():
            with review.open(newline="") as f:
                for r in csv.DictReader(f):
                    r["reviewer"] = r.get("reviewer") or default_reviewer
                    annotations[r["question_id"]] = r
    groups, variants = defaultdict(list), defaultdict(list)
    for row in rows:
        groups[(row["model"], row["mode"])].append(row)
        variants[(row["model"], row["mode"], row["case_id"])].append(row)
    report = ["# Measured evaluation results", "",
              "Results describe the recorded responses and configuration in experiment.json. "
              "Automatic status, keyword and citation checks are reported separately from semantic review.", "",
              "| Model | Mode | N | Status accuracy | Fact-match proxy | OOS refusal | Citation structure | "
              "Error rate | Mean seconds |", "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    summary = {}
    for (model, mode), data in groups.items():
        metrics = {}
        for name in ["status_correct", "fact_match_proxy", "correct_out_of_scope_refusal", "citation_structure_valid",
                     "expected_source_recall", "unsafe_answer"]:
            values = [r["checks"][name] for r in data if r["checks"][name] is not None]
            metrics[name] = statistics.mean(values) if values else None
            metrics[name + "_n"] = len(values)
        metrics["answer_coverage"] = statistics.mean(r["answer"]["status"] == "answered" for r in data)
        metrics["error_rate"] = statistics.mean(r["answer"]["status"] == "error" for r in data)
        metrics["latency_mean"] = statistics.mean(r["answer"]["elapsed_seconds"] for r in data)
        values = [r["answer"]["elapsed_seconds"] for r in data]
        metrics["latency_p95"] = sorted(values)[max(0, int(len(values) * .95 + .999) - 1)]
        for name in ["accuracy", "groundedness"]:
            labels = [annotations.get(r["answer"]["question_id"], {}).get(name, "") for r in data]
            rated = [float(v) for v in labels if v != ""]
            if any(v not in {0, 1} for v in rated):
                raise ValueError("Review accuracy/groundedness labels must be 0 or 1.")
            metrics["reviewed_" + name] = statistics.mean(rated) if rated else None
            metrics["reviewed_" + name + "_n"] = len(rated)
            human = [float(a[name]) for r in data
                     if (a := annotations.get(r["answer"]["question_id"], {})).get("reviewer") == "human"
                     and a.get(name, "") != ""]
            metrics["human_" + name] = statistics.mean(human) if human else None
            metrics["human_" + name + "_n"] = len(human)
        reviewer_counts = defaultdict(int)
        for r in data:
            annotation = annotations.get(r["answer"]["question_id"], {})
            if annotation.get("accuracy", "") != "" or annotation.get("groundedness", "") != "":
                reviewer_counts[annotation.get("reviewer", "unspecified")] += 1
        metrics["reviewer_counts"] = dict(reviewer_counts)
        summary[f"{model}/{mode}"] = metrics
        def fmt(v):
            return "—" if v is None else f"{v:.3f}"
        report.append(f"| {model} | {mode} | {len(data)} | " + " | ".join(fmt(metrics[k]) for k in [
            "status_correct", "fact_match_proxy", "correct_out_of_scope_refusal", "citation_structure_valid",
            "error_rate", "latency_mean"]) + " |")
    report += ["", "## Repeated-run changes", "", "Exact answer changes include wording and content changes. "
               "Status/source changes are listed separately. Wording differences are distinct from factual changes.", ""]
    changes = []
    for (model, mode, case_id), data in variants.items():
        signatures = {(r["answer"]["status"], r["answer"]["answer"], r["answer"]["draft"]) for r in data}
        source_signatures = {(r["answer"]["status"], tuple(sorted(s["document_id"] for s in r["answer"]["sources"])))
                             for r in data}
        if len(signatures) > 1:
            changes.append({"model": model, "mode": mode, "case_id": case_id,
                            "answer_variants": len(signatures), "status_source_variants": len(source_signatures)})
            report.append(f"- {model}, {mode}, {case_id}: {len(signatures)} answer variants; "
                          f"{len(source_signatures)} status/source variants.")
    if not changes:
        report.append("No exact answer or status/source changes were observed within any recorded model/mode group.")
    report += ["", "## Semantic review", "",
               "Review annotations and their provenance are recorded in reviews.csv. Accuracy includes "
               "correct refusals and clarification requests. Groundedness is scored on factual answers. "
               "Unscored entries are excluded from the corresponding denominator.", "",
               "| Model / mode | Reviewed accuracy | Reviewed groundedness | Reviewer counts |",
               "|---|---:|---:|---|"]
    for label, metrics in summary.items():
        report.append(f"| {label} | {fmt(metrics['reviewed_accuracy'])} "
                      f"(n={metrics['reviewed_accuracy_n']}) | {fmt(metrics['reviewed_groundedness'])} "
                      f"(n={metrics['reviewed_groundedness_n']}) | {metrics['reviewer_counts']} |")
    atomic_json(output_dir / "summary.json", {"groups": summary, "changed_questions": changes})
    (output_dir / "summary.md").write_text("\n".join(report) + "\n")
    return summary
