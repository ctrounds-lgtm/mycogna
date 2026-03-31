"""Generate a PDF version of the Christopher support workflow."""

from fpdf import FPDF
import textwrap

INPUT_MARKDOWN = "outputs/Christopher-support-workflow.md"
OUTPUT_PDF = "outputs/Christopher-support-workflow.pdf"


def to_latin1(text: str) -> str:
    """Convert text to Latin-1, replacing unsupported characters."""
    return text.encode("latin1", "replace").decode("latin1")


def main():
    with open(INPUT_MARKDOWN, "r", encoding="utf-8") as f:
        lines = f.readlines()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    pdf.set_font("Helvetica", "", 12)

    in_code_block = False

    for raw in lines:
        line = raw.rstrip("\n")
        line = to_latin1(line)

        if line.startswith("# "):
            pdf.set_font("Helvetica", "B", 18)
            pdf.cell(0, 10, line[2:].strip(), ln=True)
            pdf.ln(2)
            pdf.set_font("Helvetica", "", 12)
            continue

        if line.startswith("## "):
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(0, 8, line[3:].strip(), ln=True)
            pdf.ln(1)
            pdf.set_font("Helvetica", "", 12)
            continue

        if line.startswith("### "):
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 7, line[4:].strip(), ln=True)
            pdf.set_font("Helvetica", "", 12)
            continue

        if line.startswith("```"):
            in_code_block = not in_code_block
            if in_code_block:
                pdf.set_font("Courier", "", 10)
                pdf.set_text_color(50, 50, 50)
                pdf.set_fill_color(240, 240, 240)
                pdf.multi_cell(0, 6, "")
            else:
                pdf.set_font("Helvetica", "", 12)
                pdf.set_text_color(0, 0, 0)
            continue

        if in_code_block:
            pdf.multi_cell(0, 6, line)
            continue

        if line.strip() == "":
            pdf.ln(3)
            continue

        prefix = ""
        stripped = line.lstrip()
        if stripped.startswith("- "):
            prefix = "- "
            line = stripped[2:]

        wrapped = textwrap.wrap(line, width=95)
        if not wrapped:
            pdf.ln(3)
            continue

        for i, part in enumerate(wrapped):
            if i == 0:
                pdf.cell(5 if prefix else 0, 6, "", ln=False)
                pdf.multi_cell(0, 6, (prefix + part) if prefix else part)
            else:
                pdf.cell(5 if prefix else 0, 6, "", ln=False)
                pdf.multi_cell(0, 6, part)

    pdf.output(OUTPUT_PDF)
    print(f"Wrote PDF: {OUTPUT_PDF}")


if __name__ == "__main__":
    main()
