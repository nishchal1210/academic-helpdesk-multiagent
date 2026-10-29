import asyncio
import re
import time
import uuid

from .audit import AuditLog
from .corpus import CorpusError, Registry
from .grounding import GroundingError, render, validate_answer, verify_semantics
from .retrieval import Retriever
from .schemas import Answer
from .scope import route_question
from .tools import AcademicTools, EvidenceLedger, NeedClarification, NoEvidence


async def ask(settings, question: str, mode="multi", backend="adk") -> Answer:
    start = time.monotonic()
    request_id = uuid.uuid4().hex
    route = route_question(question)
    trace = [{"agent": "scope_gate", "route": route.name}]
    result = Answer(status="refused", answer="I don't know based on the available academic records.",
                    route=route.name, mode=mode, model=settings.model if backend == "adk" else "extractive",
                    question_id=request_id)
    try:
        if route.name == "out_of_scope":
            result.answer = "I don't know. I can help with academic programmes, rules, courses, schedules, and instructor email drafts."
            result.reason = "out_of_scope"
        elif route.name == "clarify":
            result.status, result.answer, result.reason = "needs_clarification", route.reason, "incomplete_question"
        else:
            asked_programmes = re.findall(r"\b[BM]\.?Tech\b", question, re.I)
            profile = re.sub(r"[^a-z]", "", settings.programme.lower())
            if any(re.sub(r"[^a-z]", "", p.lower()) != profile for p in asked_programmes):
                raise NeedClarification("The question names a different programme. Select that programme and its applicable sources first.")
            cohorts = re.findall(r"\b(?:batch|cohort|admission year)\s*(?:of\s*)?(20\d{2})\b", question, re.I)
            if cohorts and any(c != settings.cohort for c in cohorts):
                raise NeedClarification("Select the admission cohort named in your question before using its curriculum.")
            terms = re.findall(r"\b\d{4}-\d{2}-(?:I|II)\b", question, re.I)
            if terms and any(t.upper() != settings.semester.upper() for t in terms):
                raise NoEvidence("The requested academic term is different from the configured term.")
            registry = Registry(settings.data_dir)
            result.synthetic = registry.manifest.synthetic
            retriever = Retriever(settings, registry)
            ledger = EvidenceLedger()
            tools = AcademicTools(settings, registry, retriever, ledger)
            draft = None
            if route.name == "policy":
                tools.search_documents(question)
            elif route.name == "schedule":
                tools.schedule_for_question(question)
            elif route.name == "email":
                draft = tools.draft_email(question)
            if not ledger.items:
                raise NoEvidence("No applicable source was retrieved for this question.")
            trace.append({"agent": "evidence_preflight", "evidence_ids": list(ledger.items)})
            if backend == "extractive":
                # Explicit non-LLM ablation, useful for checking data and provenance offline.
                result.answer = "\n\n".join(f"{e.text} [S{i}]" for i, e in enumerate(ledger.items.values(), 1))
                result.sources = list(ledger.items.values())
                result.status, result.structural_grounding = "answered", True
            else:
                from .agents import run_agent
                feedback = ""
                async with asyncio.timeout(settings.timeout):
                    for attempt in range(2):
                        raw = await run_agent(settings, tools, question, route.name, mode, trace,
                                              request_id + f"_{attempt}", feedback)
                        try:
                            parsed = validate_answer(raw, ledger, question)
                            if settings.verify and parsed.status == "answered":
                                await asyncio.to_thread(verify_semantics, settings, parsed, ledger, question)
                                trace.append({"agent": "grounding_reviewer", "supported": True})
                            break
                        except GroundingError as exc:
                            if attempt == 1:
                                raise
                            feedback = str(exc) + " Correct this failure; return the factual answer with valid supporting quotations."
                            trace.append({"agent": "grounding_gate", "retry": True, "detail": str(exc)})
                if parsed.status == "needs_clarification":
                    raise NeedClarification("Please specify the applicable programme, admission cohort, term or course section.")
                if parsed.status != "answered":
                    raise NoEvidence("The sources did not establish an unambiguous answer.")
                result.answer, result.sources = render(parsed, ledger)
                result.status, result.structural_grounding = "answered", True
            result.draft = draft
            if draft:
                cited = {s.id for s in result.sources}
                result.sources.extend(e for e in ledger.items.values() if e.id not in cited)
    except NeedClarification as exc:
        result.status, result.answer, result.reason = "needs_clarification", str(exc), "missing_context"
    except NoEvidence as exc:
        result.reason = "missing_evidence"
        trace.append({"agent": "evidence_gate", "detail": str(exc)})
    except GroundingError as exc:
        result.reason = "grounding_check_failed"
        trace.append({"agent": "grounding_gate", "detail": str(exc)})
    except (CorpusError, OSError, ValueError, TimeoutError) as exc:
        result.status, result.reason = "error", "configuration_or_runtime_error"
        result.answer = "The helpdesk could not complete this request. Check the local diagnostics and try again."
        trace.append({"agent": "runtime", "error": type(exc).__name__, "detail": str(exc)[:500]})
    except Exception as exc:
        # API failures must never become invented answers. Preserve the exception type for diagnosis.
        result.status, result.reason = "error", "model_or_tool_error"
        result.answer = "The local model or a tool is unavailable. Check helpdesk doctor."
        trace.append({"agent": "runtime", "error": type(exc).__name__, "detail": str(exc)[:500]})
    result.trace = trace
    result.elapsed_seconds = round(time.monotonic() - start, 3)
    AuditLog(settings.state_dir).record(question, result)
    return result
