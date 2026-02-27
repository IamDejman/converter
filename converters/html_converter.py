"""HTML to Markdown conversion logic."""
import html2text


def html_to_markdown(html_text: str) -> str:
    """Convert an HTML string to Markdown."""
    h = html2text.HTML2Text()
    h.body_width = 0  # don't wrap lines
    h.unicode_snob = True
    return h.handle(html_text)
