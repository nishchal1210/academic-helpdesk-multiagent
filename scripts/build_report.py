"""Build the submission PDF from its Markdown source."""
from pathlib import Path

from markdown_it import MarkdownIt
import pymupdf


def main():
    root = Path(__file__).resolve().parents[1]
    source = root / "reports/REPORT.md"
    output = root / "reports/REPORT.pdf"
    temporary = output.with_suffix(".building.pdf")
    html = MarkdownIt("commonmark").enable("table").render(source.read_text())
    # Explicit section breaks keep the Markdown and submission PDF aligned.
    html = html.replace('<!-- pagebreak -->',
                        '<div style="page-break-before: always"></div>')
    css = """
    body { font-family: sans-serif; font-size: 10.5pt; line-height: 1.35; color: #172234; }
    h1 { font-size: 24pt; color: #12365b; margin-bottom: 8pt; }
    h2 { font-size: 14pt; color: #12365b; margin-top: 18pt; margin-bottom: 7pt; }
    h3 { font-size: 11.5pt; margin-top: 12pt; }
    p { margin-top: 5pt; margin-bottom: 7pt; }
    table { border-collapse: collapse; width: 100%; margin-top: 8pt; margin-bottom: 10pt; font-size: 9pt; }
    th { color: #12365b; text-align: left; padding: 5pt; border: 0.5pt solid #b8c5d4; }
    td { padding: 5pt; border: 0.5pt solid #cbd5df; vertical-align: top; }
    code { font-family: monospace; font-size: 9pt; }
    a { color: #174d80; }
    """
    story = pymupdf.Story(html=html, user_css=css)
    media = pymupdf.paper_rect("a4")
    content = pymupdf.Rect(42, 42, media.width - 42, media.height - 45)
    writer = pymupdf.DocumentWriter(str(temporary))
    story.write(writer, lambda _number, _filled: (media, content, None))
    writer.close()
    with pymupdf.open(temporary) as document:
        for i, page in enumerate(document):
            page.insert_text((42, media.height - 22),
                             f"Autonomous Systems | Assignment 2                                      {i + 1}",
                             fontsize=8, color=(.3, .36, .43))
        document.set_metadata({"title": "Multi-Agent Academic Helpdesk — Assignment 2",
            "author": "Nishchal Badaya; Krish Jain; Shivam", "subject": "Autonomous Systems",
            "creationDate": "", "modDate": ""})
        document.save(output, garbage=4, deflate=True)
    temporary.unlink()
    print(output)


if __name__ == "__main__":
    main()
