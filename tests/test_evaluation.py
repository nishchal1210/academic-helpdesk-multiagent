import json

from helpdesk.evaluation import load_cases, proxy_checks, summarize
from helpdesk.schemas import Answer


def test_error_is_not_scored_as_correct_refusal():
    case = {"expected_status": "refused", "category": "out_of_scope"}
    answer = Answer(status="error", answer="Service unavailable", route="policy", mode="single", model="x")
    checks = proxy_checks(case, answer)
    assert checks["status_correct"] is False
    assert checks["correct_out_of_scope_refusal"] is False


def test_missing_gold_facts_are_unrated_not_successful():
    answer = Answer(status="answered", answer="A response", route="policy", mode="single", model="x")
    checks = proxy_checks({"category": "policy"}, answer)
    assert checks["fact_match_proxy"] is None and checks["status_correct"] is None


def test_reference_questions_meet_assignment_size():
    from pathlib import Path
    path = Path(__file__).parents[1] / "evaluation/questions.jsonl"
    assert 20 <= len(load_cases(path)) <= 30


def test_assistant_review_is_not_reported_as_human_review(tmp_path):
    answer = Answer(status="answered", answer="A supported response", route="policy", mode="multi",
                    model="x", question_id="response-1", structural_grounding=True)
    row = {"case_id": "P01", "model": "x", "mode": "multi", "run": 1,
           "answer": answer.model_dump(), "checks": proxy_checks(
               {"expected_status": "answered", "category": "policy"}, answer)}
    (tmp_path / "results.jsonl").write_text(json.dumps(row) + "\n")
    (tmp_path / "reviews.csv").write_text(
        "question_id,accuracy,groundedness,reviewer,notes\nresponse-1,1,1,assistant,Source checked\n")
    result = summarize(tmp_path)["x/multi"]
    assert result["reviewed_accuracy"] == 1
    assert result["reviewed_groundedness"] == 1
    assert result["human_accuracy"] is None
    assert result["reviewer_counts"] == {"assistant": 1}


def test_summary_reports_repeat_changes_and_missing_human_ratings(tmp_path):
    rows = []
    for run, text in [(1, "First wording"), (2, "Different wording")]:
        answer = Answer(status="answered", answer=text, route="policy", mode="multi", model="x",
                        question_id=f"run-{run}", elapsed_seconds=1, structural_grounding=True)
        rows.append({"case_id": "P01", "model": "x", "mode": "multi", "run": run,
                     "answer": answer.model_dump(), "checks": proxy_checks(
                         {"expected_status": "answered", "category": "policy"}, answer)})
    (tmp_path / "results.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    summarize(tmp_path)
    report = json.loads((tmp_path / "summary.json").read_text())
    assert len(report["changed_questions"]) == 1
    assert report["groups"]["x/multi"]["human_accuracy"] is None
