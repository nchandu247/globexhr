"""
Convert a DOCX file to PDF using LibreOffice headless.
LibreOffice is pre-installed on all Frappe Cloud (Ubuntu) servers.
"""
import os
import shutil
import subprocess
import tempfile


def docx_to_pdf_bytes(docx_path: str) -> bytes:
    """Run LibreOffice headless to convert a DOCX file to PDF; return PDF bytes."""
    out_dir = tempfile.mkdtemp()
    try:
        result = subprocess.run(
            [
                "libreoffice",
                "--headless",
                "--convert-to", "pdf",
                "--outdir", out_dir,
                docx_path,
            ],
            capture_output=True,
            timeout=60,
        )
        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace")[:400]
            raise RuntimeError(f"LibreOffice conversion failed: {stderr}")

        base = os.path.splitext(os.path.basename(docx_path))[0]
        pdf_path = os.path.join(out_dir, base + ".pdf")
        if not os.path.exists(pdf_path):
            raise RuntimeError(f"LibreOffice did not produce output at: {pdf_path}")

        with open(pdf_path, "rb") as f:
            return f.read()
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
