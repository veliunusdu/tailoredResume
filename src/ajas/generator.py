import os

import pypandoc
from jinja2 import Environment, FileSystemLoader

from ajas.logger import log


def render_cv(cv_data: dict, template_path: str = "prompts/cv_template.md.j2") -> str:
    """Render CV data into Markdown using Jinja2."""
    template_dir = os.path.dirname(template_path)
    template_name = os.path.basename(template_path)

    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(template_name)

    return template.render(**cv_data)


def compile_outputs(md_content: str, output_base: str):
    """Generate both PDF and DOCX from Markdown content."""
    # Ensure directory exists
    os.makedirs(os.path.dirname(output_base), exist_ok=True)

    # Always save the intermediate markdown as a fallback/source
    md_path = f"{output_base}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    log.info(f"Saved Markdown source: {md_path}")

    try:
        # Convert to PDF
        log.info(f"Generating PDF: {output_base}.pdf")
        pypandoc.convert_text(
            md_content,
            "pdf",
            format="md",
            outputfile=f"{output_base}.pdf",
            extra_args=["--pdf-engine=pdflatex"],
        )
    except Exception as e:
        log.error(f"Failed to generate PDF: {e}")
        # Try to save the tex file if it failed
        try:
            pypandoc.convert_text(
                md_content, "latex", format="md", outputfile=f"{output_base}.tex"
            )
            log.info(f"Saved LaTeX source to {output_base}.tex for debugging.")
        except Exception:
            pass

    try:
        # Convert to DOCX
        log.info(f"Generating DOCX: {output_base}.docx")
        pypandoc.convert_text(
            md_content, "docx", format="md", outputfile=f"{output_base}.docx"
        )
    except Exception as e:
        log.error(f"Failed to generate DOCX: {e}")
