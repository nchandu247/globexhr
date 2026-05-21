"""
Pre-flight check for the WeasyPrint PDF rendering pipeline.

Verifies that WeasyPrint imports cleanly and that the C system libraries
it depends on (libcairo2, libpango, libgdk-pixbuf) are available on the
host. Surfaces results through health_check so we can confirm the bench
is ready BEFORE we switch the offer-letter handler over to the HTML path.

Pure Python, no Frappe dependencies — testable offline.
"""
import ctypes.util


def check_pdf_dependencies() -> dict:
    """
    Return availability status of the PDF rendering stack.

    Keys returned:
      weasyprint_installed       (bool)
      weasyprint_version         (str | None)
      weasyprint_error           (str, only if import failed)
      libcairo_available         (bool)
      libpango_available         (bool)
      libgdk_pixbuf_available    (bool)
    """
    result = {
        "weasyprint_installed": False,
        "weasyprint_version": None,
        "libcairo_available": False,
        "libpango_available": False,
        "libgdk_pixbuf_available": False,
    }

    try:
        import weasyprint
        result["weasyprint_installed"] = True
        result["weasyprint_version"] = getattr(weasyprint, "__version__", "unknown")
    except Exception as exc:
        result["weasyprint_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"

    # ctypes.util.find_library returns the library name if found, else None.
    # Probe multiple common naming variants per library.
    result["libcairo_available"] = any(
        ctypes.util.find_library(name) for name in ("cairo", "cairo-2")
    )
    result["libpango_available"] = any(
        ctypes.util.find_library(name) for name in ("pango-1.0", "pango")
    )
    result["libgdk_pixbuf_available"] = any(
        ctypes.util.find_library(name) for name in ("gdk_pixbuf-2.0", "gdk-pixbuf-2.0")
    )

    return result
