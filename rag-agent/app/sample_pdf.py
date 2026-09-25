"""Build the sample refund-policy PDF used by the demo and the parser test.

The 30-day rule is on page 4 and nowhere else, so a correct citation names that page.
"""

from pathlib import Path

import pymupdf

PAGE_BODIES = [
    (
        "Returns introduction\n\n"
        "This page introduces how retail purchases can be sent back to the shop. "
        "Collect the receipt before reading the later page that states the deadline. "
        "No deadline is printed on this page."
    ),
    (
        "What to prepare\n\n"
        "Have the order number, the payment method, and a photo when goods arrived damaged. "
        "Agents can explain how to submit a request. This page does not state the deadline."
    ),
    (
        "How a request is reviewed\n\n"
        "The desk reviews complete requests in the order they arrive. "
        "Items should be unused aside from ordinary inspection. "
        "This page still does not state how many days a shopper has."
    ),
    (
        "Refund window\n\n"
        "Customers may request a refund within 30 days of the original purchase date. "
        "The refund period is 30 days. Requests submitted after that window are declined."
    ),
    (
        "Digital goods\n\n"
        "Opened digital downloads are not refundable once the download link has been used. "
        "An unused download license can still be returned inside the window described earlier."
    ),
]


def build_refund_policy_pdf() -> bytes:
    document = pymupdf.open()
    try:
        for body in PAGE_BODIES:
            page = document.new_page()
            page.insert_textbox(pymupdf.Rect(72, 72, 540, 720), body, fontsize=12, fontname="helv")
        return document.tobytes()
    finally:
        document.close()


def write_sample_pdf(path: Path | None = None) -> Path:
    target = path or Path(__file__).resolve().parents[1] / "sample_docs" / "refund-policy.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(build_refund_policy_pdf())
    return target


if __name__ == "__main__":
    written = write_sample_pdf()
    print(written)
