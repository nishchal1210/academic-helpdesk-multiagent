import re
from dataclasses import dataclass

COURSE = re.compile(r"\b([A-Z]{2,5})\s*[- ]?\s*(\d{3,5}[A-Z]?)\b", re.I)


def course_codes(text: str) -> list[str]:
    ordinary_words = {"FROM", "FOR", "DATE", "YEAR", "SINCE", "BATCH", "DEMO", "UNTIL",
                      "IN", "ON", "TO", "AND", "THE", "TERM", "CLASS", "LEVEL"}
    return list(dict.fromkeys(a.upper() + b.upper() for a, b in COURSE.findall(text)
                             if a.upper() not in ordinary_words))


@dataclass(frozen=True)
class Route:
    name: str
    reason: str = ""


def route_question(question: str) -> Route:
    """Conservative, reproducible routing; never uses general model knowledge as a fallback."""
    q = question.lower()
    if len(q.strip()) < 5:
        return Route("clarify", "Please give a complete academic question.")
    if len(q) > 6000:
        return Route("clarify", "Please keep the question below 6,000 characters.")
    outside = r"\b(dining|restaurant|cafeteria|canteen|weather|tourism|taxi|bus fare|city cent(?:er|re)|" \
              r"stock price|bitcoin|cricket|hostel food|wifi password|wi-fi password)\b"
    if re.search(outside, q) or re.search(r"\b(reach|travel|directions)\b.*\bcampus\b", q):
        return Route("out_of_scope", "This helpdesk covers academic matters and instructor email drafts.")
    if re.search(r"\b(send|deliver|dispatch)\b.*\b(email|mail)\b", q):
        return Route("out_of_scope", "I can draft an email for review, but I cannot send it.")
    if re.search(r"ignore (all |previous |your )*(instructions|rules)|reveal.*system prompt", q):
        return Route("out_of_scope", "I cannot follow requests to override the helpdesk's evidence rules.")
    if re.search(r"\b(email|e-mail|mail|draft|write.*instructor)\b", q):
        return Route("email")
    if (course_codes(question) and re.search(r"\b(major|minor)\b.*\b(exam|examination)\b", q)
            and re.search(r"\b(when|date|time|schedule)\b", q)
            and not re.search(r"make.?up|\bi[ -]grade\b", q)):
        return Route("schedule")
    if re.search(r"\b(slot|timetable|time table|schedule|floated|offered|400.level|instructor|teaches|teaching)\b", q):
        return Route("schedule")
    if re.search(r"\b(exam|exams|examination|makeup|make-up)\b", q):
        return Route("policy")
    if course_codes(question) and re.search(r"\b(when|where|who|time)\b", q):
        return Route("schedule")
    if re.search(r"\b(attendance|exam|exams|examination|major|minor|credit|credits|curriculum|course|courses|"
                 r"academic|degree|programme|program|elective|registration|register|withdraw|audit|"
                 r"semester|cgpa|sgpa|grade|grading|prerequisite|promotion|leave|policy|regulation|"
                 r"rule|rules|syllabus|syllabi|b\.?tech|m\.?tech|ph\.?d|fee deadline|pass mark)\b", q):
        return Route("policy")
    return Route("out_of_scope", "I do not have a supported academic interpretation of this question.")
