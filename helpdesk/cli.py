import argparse
import asyncio
from dataclasses import replace
import json
import logging
from pathlib import Path
import sys

from .config import Settings


def settings_for(args):
    settings = Settings.from_env()
    if getattr(args, "demo", False):
        settings = replace(settings, data_dir=Path("data/demo"), state_dir=Path(".runtime/demo"),
                           semester="DEMO-2026-I", programme="B.Tech", cohort="2023", branch="")
    for attr in ["data_dir", "state_dir", "model", "semester", "cohort", "branch", "temperature"]:
        value = getattr(args, attr, None)
        if value is not None:
            settings = replace(settings, **{attr: value})
    return settings


def print_answer(answer, as_json=False):
    if as_json:
        print(answer.model_dump_json(indent=2))
        return
    if answer.synthetic:
        print("SYNTHETIC DEMO DATA — these are not official IIT Jodhpur answers.\n")
    print(answer.answer)
    if answer.draft:
        print("\nDRAFT ONLY — review placeholders before using:\n\n" + answer.draft)
    if answer.sources:
        print("\nSources:")
        for i, source in enumerate(answer.sources, 1):
            print(f"[S{i}] {source.title}; {source.locator}; document ID: {source.document_id}")
            if source.source_url:
                print("     " + source.source_url)
    print(f"\n[{answer.status}; route={answer.route}; mode={answer.mode}; {answer.elapsed_seconds:.2f}s]")
    if answer.status == "error":
        print("Run with --json to inspect the diagnostic trace.")


def doctor(settings):
    from importlib import metadata
    report = {"python": sys.version, "model": settings.model, "embedding_model": settings.embed_model,
              "host": settings.host, "data_dir": str(settings.data_dir), "term": settings.semester,
              "programme": settings.programme, "admission_cohort": settings.cohort or "NOT SET",
              "branch": settings.branch or "NOT SET"}
    for package in ["google-adk", "litellm", "chromadb", "ollama", "pypdf", "python-docx", "rank-bm25"]:
        try:
            report[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            report[package] = "MISSING"
    try:
        import ollama
        client = ollama.Client(host=settings.host, timeout=5)
        import httpx
        version = httpx.get(settings.host + "/api/version", timeout=5)
        version.raise_for_status()
        report["ollama_version"] = version.json()["version"]
        report["available_models"] = [m.model for m in client.list().models]
        for role, model in [("chat", settings.model), ("embedding", settings.embed_model)]:
            try:
                info = client.show(model)
                report[role + "_capabilities"] = info.capabilities
            except Exception as e:
                report[role + "_model_error"] = str(e)
    except Exception as e:
        report["ollama_error"] = str(e)
    try:
        from .corpus import Registry
        r = Registry(settings.data_dir)
        report["documents"] = len(r.docs)
        report["synthetic"] = r.manifest.synthetic
        report["submission_document_count_ok"] = not r.manifest.synthetic and 20 <= len(r.docs) <= 30
        report["course_rows"], report["faculty_rows"] = len(r.courses), len(r.faculty)
        report["faculty_with_verified_email"] = sum(bool(f.email) for f in r.faculty)
        report["examination_rows"] = len(r.examinations)
        report["pending_review_documents"] = [d.id for d in r.docs.values() if d.status == "pending_review"]
        report["applicable_documents"] = sum(r.applicable(d, settings.semester, settings.programme,
                                                         settings.cohort, settings.branch) for d in r.docs)
        from .retrieval import Retriever
        report["index_chunks_applicable"] = len(Retriever(settings, r).records)
    except Exception as e:
        report["corpus_error"] = str(e)
    print(json.dumps(report, indent=2))


def main():
    logging.basicConfig(level=logging.WARNING)
    parser = argparse.ArgumentParser(description="Local academic helpdesk: ADK + Ollama + hybrid RAG")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ["doctor", "ingest", "ask", "chat", "evaluate", "unanswered"]:
        p = commands.add_parser(name)
        p.add_argument("--demo", action="store_true", help="Use clearly labelled synthetic test data")
        p.add_argument("--data-dir", type=Path)
        p.add_argument("--state-dir", type=Path)
        p.add_argument("--model")
        p.add_argument("--semester")
        p.add_argument("--cohort")
        p.add_argument("--branch")
        p.add_argument("--temperature", type=float)
        if name == "ingest":
            p.add_argument("--lexical-only", action="store_true", help="Explicit no-vector ablation")
            p.add_argument("--strict", action="store_true", help="Require 20–30 real documents")
        if name in {"ask", "chat"}:
            p.add_argument("--mode", choices=["single", "multi"], default="multi")
            p.add_argument("--backend", choices=["adk", "extractive"], default="adk")
            p.add_argument("--json", action="store_true")
        if name == "ask":
            p.add_argument("question")
        if name == "evaluate":
            p.add_argument("--dataset", type=Path, required=True)
            p.add_argument("--output", type=Path, required=True)
            p.add_argument("--models", nargs="+")
            p.add_argument("--modes", nargs="+", choices=["single", "multi"], default=["single", "multi"])
            p.add_argument("--runs", type=int, default=3)
            p.add_argument("--backend", choices=["adk", "extractive"], default="adk")
        if name == "unanswered":
            p.add_argument("--output", type=Path, default=Path("unanswered.csv"))
    p = commands.add_parser("summarize")
    p.add_argument("directory", type=Path)
    args = parser.parse_args()
    settings = settings_for(args)
    try:
        if args.command == "doctor":
            doctor(settings)
        elif args.command == "ingest":
            from .retrieval import ingest
            print(json.dumps(ingest(settings, args.lexical_only, args.strict), indent=2))
        elif args.command in {"ask", "chat"}:
            from .service import ask
            if args.command == "ask":
                answer = asyncio.run(ask(settings, args.question, args.mode, args.backend))
                print_answer(answer, args.json)
                if answer.status == "error":
                    return 1
            else:
                print("Enter a complete question each time; sessions are independent. Type /quit to exit.")
                while True:
                    try:
                        question = input("\nYou: ").strip()
                    except EOFError:
                        break
                    if question.lower() in {"/quit", "/exit"}:
                        break
                    if question:
                        print_answer(asyncio.run(ask(settings, question, args.mode, args.backend)), args.json)
        elif args.command == "evaluate":
            if args.runs < 1:
                raise ValueError("--runs must be positive.")
            from .evaluation import evaluate
            asyncio.run(evaluate(settings, args.dataset, args.output, args.models or [settings.model],
                                 args.modes, args.runs, args.backend))
            print(f"Results: {args.output / 'summary.md'}")
        elif args.command == "summarize":
            from .evaluation import summarize
            summarize(args.directory)
        elif args.command == "unanswered":
            from .audit import AuditLog
            AuditLog(settings.state_dir).export_unanswered(args.output)
            print(f"Exported unanswered questions to {args.output}")
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
