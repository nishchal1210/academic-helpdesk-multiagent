"""Prepare the supplied IITJ bundle without deleting or modifying its originals.

This importer records uncertainties instead of inventing publication dates, emails or course types.
OCR sidecars are bound to source hashes. Re-run ingestion after running this script.
"""
import csv
from collections import Counter
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import pymupdf
from openpyxl import load_workbook

from helpdesk.schemas import CourseRow, ExaminationRow, FacultyRow

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs_for_assignment"
DATA = ROOT / "data/college"
DEST = DATA / "documents"
OCR_ROOT = ROOT / ".runtime/tools/ocr/root"
TERM = "2026-27-I"

SOURCES = [
    ("exam-guidelines-2024", "1. New Guidelines for Institute Examination (2024).docx", "policy", "General Guidelines for Institute Examination (2024)", []),
    ("minor-timetable-2026-i", "2. Time Table, Minor Exam (S1, 26-27, Sep 26).xlsx", "schedule", "Minor examination timetable, Semester I 2026-27", [TERM]),
    ("major-timetable-2026-i", "3. Time Table - Major Exam (S1, 26-27, Nov 26).xlsx", "schedule", "Major examination timetable, Semester I 2026-27", [TERM]),
    ("major-clashes-2026-i", "5. Exam Clash Sheet (Major, S1, AY 26-27).xlsx", "schedule", "Major examination clash and shifting sheet, Semester I 2026-27", [TERM]),
    ("attendance-amendment-2024", "7.1_Circular_51Circular-No.-IITJOAACircular2024-2551682-dated-08-July-2024.pdf", "policy", "Attendance policy amendment, Circular 51, 8 July 2024", []),
    ("examination-amendment-2024", "7.2_Circular_52Circular-No.-IITJOAACircular2024-2552683-dated-08-July-2024.pdf", "policy", "Examination evaluation amendment, Circular 52, 8 July 2024", []),
    ("btech-leave-form", "A-15 B.Tech Leave Form-1.pdf", "policy", "A-15 B.Tech leave application form", []),
    ("slots-2026-ii", "AY 2026-27_Semester II_Slot System (2nd Year onwards).xlsx", "schedule", "Slot system and contacts, Semester II 2026-27", ["2026-27-II"]),
    ("slots-2026-i", "AY 2026-27_Semester I_Slot System (2nd Year onwards).xlsx", "schedule", "Slot system and classroom allocation, Semester I 2026-27", [TERM]),
    ("academic-regulations-base", "Academic Regulations _ Office of Academics Affairs _ IIT Jodhpur.pdf", "policy", "Academic Regulations, IIT Jodhpur (website printout)", []),
    ("academic-calendar-2026", "Academic-Calendar-AY-2026-27-639178076336417495.pdf", "schedule", "Academic calendar, academic year 2026-27", [TERM, "2026-27-II"]),
    ("cse-course-catalogue", "CSE-Courses-Details.pdf", "curriculum", "CSE course catalogue and syllabi", []),
    ("cse-specializations", "CSE-Specializations-and-DualDegree.pdf", "curriculum", "CSE specializations and dual degree programmes", []),
    ("aids-curriculum-2020", "Curriculum-BTech-AIDS.pdf", "curriculum", "B.Tech AI and DS curriculum, edition AY 2020-21", []),
    ("course-list-2026-i", "Finalized courses list_sem1.xlsx", "schedule", "Finalized departmental course lists, Semester I 2026-27", [TERM]),
    ("course-list-2026-ii", "Finalized courses list_sem2.xlsx", "schedule", "Departmental course lists, Semester II 2026-27", ["2026-27-II"]),
    ("ih-preferences-2026-i", "Indian Institute of Technology Jodhpur Mail - [IMPORTANT]_ Course preferences for IH category Courses for Semester 1, AY 2026-27.pdf", "registration", "Registration Cell IH2 and IH3 course preferences, Semester I 2026-27", [TERM]),
    ("makeup-guidelines", "Makeup & I Grade Exam Guidelines.pdf", "policy", "Makeup and I Grade examination guidelines and forms", []),
    ("ih2-syllabi-2026-i", "Syllabus for IH2 courses offered for AY2026-27 Sem 1.pdf", "curriculum", "IH2 course syllabi, Semester I 2026-27", [TERM]),
    ("ih3-syllabi-2026-i", "Syllabus for IH3 courses offered for AY2026-27 Sem 1.pdf", "curriculum", "IH3 course syllabi, Semester I 2026-27", [TERM]),
]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normal_name(name):
    return re.sub(r"[^a-z]", "", re.sub(r"\b(dr|prof|professor)\.?", "", name.lower()))


def ocr_image(image):
    executable = shutil.which("tesseract") or str(OCR_ROOT / "usr/bin/tesseract")
    env = os.environ.copy()
    if not shutil.which("tesseract"):
        env["LD_LIBRARY_PATH"] = str(OCR_ROOT / "usr/lib/x86_64-linux-gnu")
        env["TESSDATA_PREFIX"] = str(OCR_ROOT / "usr/share/tesseract-ocr/5/tessdata")
    result = subprocess.run([executable, str(image), "stdout", "-l", "eng", "--psm", "3"],
                            env=env, check=True, capture_output=True, text=True)
    return result.stdout


def pdf_sidecar(path, source_id):
    sidecar = path.with_suffix(path.suffix + ".extraction.json")
    if sidecar.exists():
        cached = json.loads(sidecar.read_text())
        if cached.get("source_sha256") == digest(path):
            return len(cached["pages"])
    pages = {}
    with pymupdf.open(path) as document, tempfile.TemporaryDirectory() as temp:
        for i, page in enumerate(document, 1):
            text = page.get_text()
            if len(text.strip()) < 30:
                image = Path(temp) / f"page-{i}.png"
                page.get_pixmap(dpi=250).save(image)
                text = ocr_image(image)
                if len(text.strip()) < 30:
                    raise ValueError(f"OCR did not recover {path.name} page {i}")
                pages[str(i)] = text
        if source_id == "attendance-amendment-2024":
            # The signed circular quotes its historical policy before its replacement. Preserve the
            # original PDF; omit only that explicitly historical paragraph in the retrieval sidecar.
            text = pages["1"]
            text = re.sub(r"Existing policy:.*?(?=Revised Policy:)",
                          "[Historical policy quotation omitted here; see original PDF page 1.]\n\n",
                          text, flags=re.S | re.I)
            pages["1"] = text
    if pages:
        sidecar.write_text(json.dumps({"source_sha256": digest(path), "method": "Tesseract 5 English OCR",
            "notes": "English body text; verify OCR against original scans. Historical attendance quotation excluded from retrieval, original preserved.",
            "pages": pages}, indent=2))
    return len(pages)


def redact_student_header(path):
    temporary = path.with_suffix(".redacted.pdf")
    count = 0
    with pymupdf.open(path) as doc:
        for page in doc:
            for line in page.get_text().splitlines():
                if re.search(r"\b[bmp]\d{2}[a-z]{1,4}\d{3,5}\b", line, re.I) or "mail.google.com/mail/" in line:
                    for rect in page.search_for(line.strip()):
                        page.add_redact_annot(rect, text="Student recipient redacted", fontsize=7)
                        count += 1
            page.apply_redactions()
        doc.save(temporary, garbage=4, deflate=True)
    temporary.replace(path)
    return count


def prepare_documents():
    DEST.mkdir(parents=True, exist_ok=True)
    confirmation_path = DATA / "applicability_confirmations.json"
    confirmations = json.loads(confirmation_path.read_text()) if confirmation_path.exists() else {}
    documents, inventory = [], []
    for source_id, original, category, title, semesters in SOURCES:
        source = SOURCE / original
        path = DEST / (source_id + source.suffix.lower())
        shutil.copy2(source, path)
        redactions = redact_student_header(path) if source_id == "ih-preferences-2026-i" else 0
        notes = "Supplied local source; exact publication/effective date is not stated unless recorded."
        status = "current"
        if source_id == "aids-curriculum-2020":
            status = "pending_review"
            notes = "Cover says AY 2020-21. Applicability to admission batch 2023 is unconfirmed; excluded from answers until confirmed."
            if source_id in confirmations:
                status = "current"
                notes = ("Source edition is AY 2020-21. The student explicitly confirmed on "
                         + confirmations[source_id]["confirmed_on"]
                         + " that this curriculum also applies to admission batch 2023.")
        if source_id == "academic-regulations-base":
            notes = "Base regulations include historical clauses. Attendance and examination evaluation amendments of 8 July 2024 take precedence for those topics."
        if "timetable" in source_id:
            notes = "The workbook explicitly calls this timetable tentative. Course-specific confirmed shifting entries take precedence."
        if source_id == "attendance-amendment-2024":
            notes = "Revised policy replaces the quoted historical policy; use only Revised Policy and its continuation on page 2. Exam performance is no longer linked to attendance."
        doc = {"id": source_id, "file": "documents/" + path.name, "title": title, "category": category,
               "authority": "IIT Jodhpur, supplied official academic record", "effective_date":
               "2024-07-08" if "amendment-2024" in source_id else None, "status": status,
               "semesters": semesters, "notes": notes, "synthetic": False}
        if source_id == "aids-curriculum-2020":
            doc["branches"] = ["Artificial Intelligence and Data Science"]
            doc["programmes"] = ["B.Tech"]
            if source_id in confirmations:
                doc["cohorts"] = confirmations[source_id]["cohorts"]
        ocr_pages = pdf_sidecar(path, source_id) if path.suffix == ".pdf" else 0
        documents.append(doc)
        inventory.append({"id": source_id, "original": original, "prepared_file": str(path.relative_to(DATA)),
                          "original_sha256": digest(source), "prepared_sha256": digest(path),
                          "ocr_pages": ocr_pages, "student_header_redactions": redactions, "status": status})
    return documents, inventory


def slot_map(path):
    wb = load_workbook(path, data_only=True)
    ws = wb["Slot System"]
    result = {}
    for row in list(ws)[2:13]:
        timing = str(row[0].value or "").strip()
        for col, day in [(2, "Monday"), (4, "Tuesday"), (6, "Wednesday"), (8, "Thursday"), (10, "Friday")]:
            value = str(row[col - 1].value or "").strip()
            if re.fullmatch(r"[A-Z]{1,2}\d?", value):
                result.setdefault(value, []).append((day, timing, f"Slot System!{row[col-1].coordinate}; time A{row[0].row}"))
    return result


def known_contacts():
    wb = load_workbook(DEST / "slots-2026-i.xlsx", data_only=True)
    result = {}
    for row in list(wb["Time Table Committee Members"])[2:]:
        name, email = str(row[2].value or ""), str(row[3].value or "").strip()
        if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            result[normal_name(name)] = (email, "slots-2026-i", f"Time Table Committee Members!C{row[0].row}:D{row[0].row}")
    # Captured from the official public faculty profile and stored as a separate, cited source.
    if (DEST / "gaurav-harit-contact.txt").exists():
        result[normal_name("Gaurav Harit")] = ("gharit@iitj.ac.in", "gaurav-harit-contact", "faculty profile contact excerpt")
    return result


def write_csv(path, cls, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(cls.model_fields))
        writer.writeheader()
        writer.writerows(cls.model_validate(r).model_dump() for r in rows)


def prepare_courses():
    slots = slot_map(DEST / "slots-2026-i.xlsx")
    contacts, faculty, courses, omissions = known_contacts(), {}, [], []
    wb = load_workbook(DEST / "slots-2026-i.xlsx", data_only=True)
    ws = wb["Classroom Allocation"]
    raw = []
    for row in list(ws)[1:]:
        code = re.sub(r"\s+", "", str(row[0].value or "")).upper()
        if not re.fullmatch(r"[A-Z]{2,5}\d{3,5}[A-Z]?", code):
            omissions.append({"row": row[0].row, "reason": "missing or placeholder course code"})
            continue
        raw.append((row[0].row, code, [c.value for c in row]))
    counts = Counter(code for _, code, _ in raw)
    for rownum, code, values in raw:
        title, slot = str(values[1] or "not specified").strip(), str(values[4] or "not specified").strip()
        department = str(values[5] or "not specified").strip()
        if "liberal" in department.lower():
            department = "Humanities"
        names = [n.strip() for v in values[6:8] if v for n in re.split(r",|;|\n|\s+and\s+|\s+&\s+", str(v)) if n.strip()]
        if not names:
            names = ["Instructor not specified in the supplied allocation"]
        for name in dict.fromkeys(names):
            key = normal_name(name) + (code if name.startswith("Instructor not") else "")
            faculty_id = "F_" + hashlib.sha256(key.encode()).hexdigest()[:12]
            email, source_id, locator = contacts.get(normal_name(name), ("", "slots-2026-i", f"Classroom Allocation!G{rownum}:H{rownum}"))
            faculty.setdefault(faculty_id, {"instructor_id": faculty_id, "name": name, "email": email,
                                           "source_document_id": source_id, "source_locator": locator})
            meetings = slots.get(slot, [])
            kind = "elective" if code in {"LAL4070", "LAL4850"} else "unknown"
            course = {"course_code": code, "title": title, "department": department,
                "level": int(re.search(r"\d", code).group()) * 100, "course_type": kind,
                "slot": slot, "days": ", ".join(dict.fromkeys(d for d, _, _ in meetings)) or "not specified",
                "time": "; ".join(f"{d}: {t} (as printed)" for d, t, _ in meetings) or "not specified",
                "semester": TERM, "section": f"allocation-row-{rownum}" if counts[code] > 1 else "",
                "instructor_id": faculty_id, "source_document_id": "slots-2026-i",
                "source_locator": f"Classroom Allocation!A{rownum}:H{rownum}",
                "slot_document_id": "slots-2026-i" if meetings else "",
                "slot_locator": "; ".join(loc for _, _, loc in meetings)}
            if kind == "elective":
                course.update(type_document_id="ih3-syllabi-2026-i", type_locator="page 6" if code == "LAL4070" else "page 5")
            courses.append(course)
    write_csv(DATA / "courses.csv", CourseRow, courses)
    write_csv(DATA / "faculty.csv", FacultyRow, faculty.values())
    return courses, list(faculty.values()), omissions


def prepare_examinations(courses):
    result = []
    shifts = {}
    for kind, source, sheet_name in [("major", "major-clashes-2026-i", "Sheet1"),
                                      ("minor", "minor-timetable-2026-i", "Clash Sheet")]:
        ws = load_workbook(DEST / (source + ".xlsx"), data_only=True)[sheet_name]
        for row in list(ws)[3:]:
            values = [c.value for c in row]
            code = re.sub(r"\s+", "", str(values[1] or "")).upper()
            if re.fullmatch(r"[A-Z]{2,5}\d{3,5}[A-Z]?", code) and values[7]:
                approved = str(values[10] or "").strip().lower() == "done"
                shifts[kind, code] = (values[7], values[8], "revised" if approved else "unconfirmed_change",
                                     source, f"{sheet_name}!B{row[0].row}:K{row[0].row}")
    for kind, source in [("major", "major-timetable-2026-i"), ("minor", "minor-timetable-2026-i")]:
        ws = load_workbook(DEST / (source + ".xlsx"), data_only=True).worksheets[0]
        slot_times = {}
        for row in list(ws)[6:]:
            date_value = row[1].value
            if not date_value or not re.search(r"20\d{2}", str(date_value)):
                continue
            for cell in row[2:7]:
                if cell.value:
                    for slot in re.split(r"\s*\+\s*", str(cell.value).strip()):
                        if re.fullmatch(r"[A-Z]{1,3}\d?", slot):
                            slot_times[slot] = (date_value, ws.cell(5, cell.column).value,
                                "tentative", source, f"{ws.title}!B{row[0].row},{cell.coordinate}; time {ws.cell(5, cell.column).coordinate}")
        seen = set()
        for course in courses:
            code, slot = course["course_code"], course["slot"]
            data = shifts.get((kind, code)) or slot_times.get(slot)
            if not data or (code, str(data)) in seen:
                continue
            seen.add((code, str(data)))
            day, timing, status, doc, locator = data
            result.append({"course_code": code, "examination": kind, "semester": TERM,
                           "date": day.isoformat()[:10] if isinstance(day, datetime) else str(day),
                           "time": str(timing or "not specified"), "status": status,
                           "source_document_id": doc, "source_locator": locator + "; course slot from " + course["source_locator"]})
    write_csv(DATA / "examinations.csv", ExaminationRow, result)
    return result


def main():
    documents, inventory = prepare_documents()
    contact = DEST / "gaurav-harit-contact.txt"
    if contact.exists():
        documents.append({"id": "gaurav-harit-contact", "file": "documents/" + contact.name,
            "title": "Gaurav Harit — official IIT Jodhpur faculty contact excerpt", "category": "contacts",
            "authority": "IIT Jodhpur, Computer Science and Engineering faculty profile", "effective_date": None,
            "source_url": "https://iitj.ac.in/People/Profile/fea43e72-3cd7-4948-8475-65ededbcc375?ln=en",
            "notes": "Public professional contact captured on 2026-10-29; the supplied allocation separately establishes teaching responsibility."})
    courses, faculty, omissions = prepare_courses()
    exams = prepare_examinations(courses)
    manifest = {"institution": "IIT Jodhpur", "synthetic": False, "documents": documents,
        "complete_course_semesters": [], "complete_department_semesters": {TERM: ["Humanities"]},
        "topic_overrides": [
            {"keywords": ["attendance", "absent", "absence", "de-registration", "deregistration"],
             "preferred_document_ids": ["attendance-amendment-2024"], "excluded_document_ids": ["academic-regulations-base"]},
            {"keywords": ["minor", "major", "evaluation", "examination", "exam", "weightage"],
             "preferred_document_ids": ["examination-amendment-2024"], "excluded_document_ids": ["academic-regulations-base"]}]}
    (DATA / "manifest.json").write_text(json.dumps(manifest, indent=2))
    config = ROOT / ".env"
    config.write_text(re.sub(r"^HELPDESK_SEMESTER=.*$", "HELPDESK_SEMESTER=" + TERM, config.read_text(), flags=re.M))
    report = {"supplied_documents": len(SOURCES), "registered_documents": len(documents), "inventory": inventory,
        "term": TERM, "course_rows": len(courses), "distinct_courses": len({c['course_code'] for c in courses}),
        "faculty_records": len(faculty), "faculty_without_verified_email": sum(not f['email'] for f in faculty),
        "examination_rows": len(exams), "allocation_omissions": omissions,
        "department_completeness_basis": "Complete SoLA/Classroom Allocation records reconciled against the Registration Cell IH3 list. LAL4070 and LAL4850 are explicitly elective in IH3 syllabus pages 6 and 5. Full institute-wide course/elective completeness is NOT asserted.",
        "coverage_notes": (["Curriculum applicability to admission batch 2023 is unconfirmed."]
            if next(d for d in documents if d['id']=='aids-curriculum-2020')['status']=='pending_review' else []) + [
            "Instructor records without verified contacts have empty email fields; no email pattern is guessed.",
            "CSL7570 current-term offering is not established by these records.",
            "Semester II files are registered for their term; exact CSV lookups currently cover Semester I."]}
    (DATA / "preparation_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k not in {"inventory", "allocation_omissions"}}, indent=2))


if __name__ == "__main__":
    main()
