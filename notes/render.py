import markdown
import nh3
import pymdownx.superfences


NH3_ALLOWED_ATTRIBUTES = {
    "*": {"class", "id"},
    "a": {"href", "title"},
    "img": {"src", "alt", "title"},
    "th": {"align"},
    "td": {"align"},
    "input": {"type", "checked", "disabled"},  # for pymdownx.tasklist
    "math": {"xmlns", "display"},  # Fallback if Arithmatex uses MathML
}

NH3_URL_SCHEMES = {"http", "https", "mailto"}

MARKDOWN_EXTENSIONS = [
    "tables",
    "sane_lists",
    "footnotes",
    "admonition",
    "attr_list",
    "def_list",
    "pymdownx.superfences",  # Mermaid and custom fences
    "pymdownx.highlight",  # Syntax highlighting (Pygments)
    "pymdownx.tasklist",  # Checkboxes
    "pymdownx.tilde",  # Strikethrough
    "pymdownx.emoji",  # Emojis
    "pymdownx.arithmatex",  # Math
]

MARKDOWN_EXTENSION_CONFIGS = {
    "pymdownx.highlight": {
        "css_class": "highlight",
        "use_pygments": True,
        "pygments_style": "friendly",  # must match the CSS you generate in step 3
    },
    "pymdownx.tasklist": {
        "custom_checkbox": True,
    },
    "pymdownx.arithmatex": {
        "generic": True,  # emits <span class="arithmatex">\(...\)</span>, not tied to MathJax specifically
    },
    "pymdownx.superfences": {
        "custom_fences": [
            {
                "name": "mermaid",
                "class": "mermaid",
                "format": pymdownx.superfences.fence_div_format,
            }
        ]
    },
}

NH3_ALLOWED_TAGS = {
    "a",
    "abbr",
    "b",
    "blockquote",
    "code",
    "em",
    "i",
    "li",
    "ol",
    "strong",
    "ul",
    "p",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "br",
    "hr",
    "pre",
    "div",
    "span",
    "img",
    "del",
    "s",
    "input",
    "dl",
    "dt",
    "dd",
    "sup",
    "sub",
    "section",
    "math",
    "semantics",
    "mrow",
    "mi",
    "mo",
    "mn",
    "ms",
    "mspace",
    "mtext",
    "details",
    "summary",
    "label",
}


def markdown_to_html(raw_markdown: str) -> str:
    """Render markdown to HTML.

    Args:
        raw_content (str): Markdown source.

    Returns:
        HTML (str): Rendered HTML.
    """
    return markdown.markdown(
        raw_markdown,
        extensions=MARKDOWN_EXTENSIONS,
        extension_configs=MARKDOWN_EXTENSION_CONFIGS,
    )


def sanitize_html(html: str) -> str:
    """Sanitize HTML using NH3.

    Args:
        content (str): HTML input

    Returns:
        HTML (str): Sanitized HTML safe for rendering
    """
    return nh3.clean(
        html,
        tags=NH3_ALLOWED_TAGS,
        attributes=NH3_ALLOWED_ATTRIBUTES,
        url_schemes=NH3_URL_SCHEMES,
    )


def render_markdown(raw_markdown: str) -> str:
    """
    Render raw Markdown into sanitized HTML.

    The Markdown is rendered using Python-Markdown with the configured
    extensions and then sanitized using NH3 before being returned.

    Args:
        raw_markdown: Raw Markdown.

    Returns:
        Sanitized HTML safe for rendering.
    """
    if not raw_markdown.strip():
        return ""

    html: str = markdown_to_html(raw_markdown)
    return sanitize_html(html)
