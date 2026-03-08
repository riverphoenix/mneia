from __future__ import annotations

from mneia.connectors.web_scraper import _TextExtractor, extract_text_from_html


def test_extract_text_simple():
    html = "<html><body><p>Hello world</p></body></html>"
    text = extract_text_from_html(html)
    assert "Hello world" in text


def test_extract_text_strips_scripts():
    html = (
        "<html><body>"
        "<script>var x = 1;</script>"
        "<p>Visible text</p>"
        "</body></html>"
    )
    text = extract_text_from_html(html)
    assert "Visible text" in text
    assert "var x" not in text


def test_extract_text_strips_styles():
    html = (
        "<html><body>"
        "<style>.foo { color: red; }</style>"
        "<p>Content</p>"
        "</body></html>"
    )
    text = extract_text_from_html(html)
    assert "Content" in text
    assert "color" not in text


def test_extract_text_strips_nav_footer():
    html = (
        "<html><body>"
        "<nav>Menu items</nav>"
        "<main><p>Main content here</p></main>"
        "<footer>Footer stuff</footer>"
        "</body></html>"
    )
    text = extract_text_from_html(html)
    assert "Main content" in text
    assert "Menu items" not in text
    assert "Footer stuff" not in text


def test_extract_text_headings_newlines():
    html = "<h1>Title</h1><p>Paragraph</p>"
    text = extract_text_from_html(html)
    assert "Title" in text
    assert "Paragraph" in text


def test_extract_text_list_items():
    html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
    text = extract_text_from_html(html)
    assert "Item 1" in text
    assert "Item 2" in text


def test_extract_text_empty():
    assert extract_text_from_html("") == ""


def test_extract_text_no_html():
    text = extract_text_from_html("Just plain text")
    assert "Just plain text" in text


def test_text_extractor_get_text():
    extractor = _TextExtractor()
    extractor.feed("<p>Hello</p><p>World</p>")
    text = extractor.get_text()
    assert "Hello" in text
    assert "World" in text
