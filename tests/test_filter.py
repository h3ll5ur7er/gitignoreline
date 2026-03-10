"""Tests for the core filter logic."""

import pytest

from gitignoreline.filter import filter_content, filter_text, scan_markers
from gitignoreline.markers import (
    C_BLOCK_COMMENT,
    DOUBLE_SLASH,
    HASH,
    HTML_COMMENT,
)


class TestFilterContentHash:
    """Test filtering with hash (#) comment style."""

    def test_single_line_removal(self) -> None:
        lines = [
            "normal = 1\n",
            "secret = 'abc'  # gitignore\n",
            "also_normal = 2\n",
        ]
        result = filter_content(lines, HASH)
        assert result == ["normal = 1\n", "also_normal = 2\n"]

    def test_standalone_marker_line(self) -> None:
        lines = [
            "normal = 1\n",
            "# gitignore\n",
            "also_normal = 2\n",
        ]
        result = filter_content(lines, HASH)
        assert result == ["normal = 1\n", "also_normal = 2\n"]

    def test_block_removal(self) -> None:
        lines = [
            "keep_this = True\n",
            "# gitignore-start\n",
            "secret_a = 'aaa'\n",
            "secret_b = 'bbb'\n",
            "# gitignore-end\n",
            "keep_this_too = True\n",
        ]
        result = filter_content(lines, HASH)
        assert result == ["keep_this = True\n", "keep_this_too = True\n"]

    def test_mixed_markers(self) -> None:
        lines = [
            "a = 1\n",
            "b = 2  # gitignore\n",
            "c = 3\n",
            "# gitignore-start\n",
            "d = 4\n",
            "e = 5\n",
            "# gitignore-end\n",
            "f = 6\n",
        ]
        result = filter_content(lines, HASH)
        assert result == ["a = 1\n", "c = 3\n", "f = 6\n"]

    def test_no_markers_passthrough(self) -> None:
        lines = ["a = 1\n", "b = 2\n", "c = 3\n"]
        result = filter_content(lines, HASH)
        assert result == lines

    def test_empty_input(self) -> None:
        assert filter_content([], HASH) == []

    def test_all_lines_marked(self) -> None:
        lines = [
            "secret_a = 1  # gitignore\n",
            "secret_b = 2  # gitignore\n",
        ]
        result = filter_content(lines, HASH)
        assert result == []

    def test_entire_file_in_block(self) -> None:
        lines = [
            "# gitignore-start\n",
            "everything = 'secret'\n",
            "# gitignore-end\n",
        ]
        result = filter_content(lines, HASH)
        assert result == []

    def test_multiple_blocks(self) -> None:
        lines = [
            "keep_1\n",
            "# gitignore-start\n",
            "secret_1\n",
            "# gitignore-end\n",
            "keep_2\n",
            "# gitignore-start\n",
            "secret_2\n",
            "# gitignore-end\n",
            "keep_3\n",
        ]
        result = filter_content(lines, HASH)
        assert result == ["keep_1\n", "keep_2\n", "keep_3\n"]

    def test_indented_markers(self) -> None:
        lines = [
            "def func():\n",
            "    secret = 'x'  # gitignore\n",
            "    normal = 'y'\n",
            "    # gitignore-start\n",
            "    hidden_a = 1\n",
            "    hidden_b = 2\n",
            "    # gitignore-end\n",
            "    return normal\n",
        ]
        result = filter_content(lines, HASH)
        assert result == [
            "def func():\n",
            "    normal = 'y'\n",
            "    return normal\n",
        ]

    def test_unclosed_block_removes_rest(self) -> None:
        """An unclosed block start removes everything after it."""
        lines = [
            "keep = 1\n",
            "# gitignore-start\n",
            "lost_1 = 2\n",
            "lost_2 = 3\n",
        ]
        result = filter_content(lines, HASH)
        assert result == ["keep = 1\n"]

    def test_normal_comments_preserved(self) -> None:
        lines = [
            "# This is a normal comment\n",
            "x = 1  # normal inline comment\n",
            "y = 2  # gitignore\n",
        ]
        result = filter_content(lines, HASH)
        assert result == [
            "# This is a normal comment\n",
            "x = 1  # normal inline comment\n",
        ]


class TestFilterContentDoubleSlash:
    """Test filtering with // comment style."""

    def test_js_single_line(self) -> None:
        lines = [
            'const url = "https://api.example.com";\n',
            'const key = "sk-abc123"; // gitignore\n',
            "console.log(url);\n",
        ]
        result = filter_content(lines, DOUBLE_SLASH)
        assert result == [
            'const url = "https://api.example.com";\n',
            "console.log(url);\n",
        ]

    def test_js_block(self) -> None:
        lines = [
            "const config = {\n",
            "// gitignore-start\n",
            '  apiKey: "secret",\n',
            '  apiSecret: "also-secret",\n',
            "// gitignore-end\n",
            '  appName: "MyApp",\n',
            "};\n",
        ]
        result = filter_content(lines, DOUBLE_SLASH)
        assert result == [
            "const config = {\n",
            '  appName: "MyApp",\n',
            "};\n",
        ]


class TestFilterContentHTML:
    """Test filtering with HTML comment style."""

    def test_html_line(self) -> None:
        lines = [
            "<div>public content</div>\n",
            "<div>secret content</div> <!-- gitignore -->\n",
            "<div>more public</div>\n",
        ]
        result = filter_content(lines, HTML_COMMENT)
        assert result == [
            "<div>public content</div>\n",
            "<div>more public</div>\n",
        ]

    def test_html_block(self) -> None:
        lines = [
            "<header>Public</header>\n",
            "<!-- gitignore-start -->\n",
            "<section>Secret stuff</section>\n",
            "<!-- gitignore-end -->\n",
            "<footer>Also public</footer>\n",
        ]
        result = filter_content(lines, HTML_COMMENT)
        assert result == [
            "<header>Public</header>\n",
            "<footer>Also public</footer>\n",
        ]


class TestFilterContentCSS:
    """Test filtering with CSS block comment style."""

    def test_css_line(self) -> None:
        lines = [
            "body { color: black; }\n",
            ".secret { display: none; } /* gitignore */\n",
            "h1 { font-size: 2em; }\n",
        ]
        result = filter_content(lines, C_BLOCK_COMMENT)
        assert result == [
            "body { color: black; }\n",
            "h1 { font-size: 2em; }\n",
        ]

    def test_css_block(self) -> None:
        lines = [
            "body { margin: 0; }\n",
            "/* gitignore-start */\n",
            ".debug { border: 1px solid red; }\n",
            "/* gitignore-end */\n",
            "footer { padding: 1em; }\n",
        ]
        result = filter_content(lines, C_BLOCK_COMMENT)
        assert result == [
            "body { margin: 0; }\n",
            "footer { padding: 1em; }\n",
        ]


class TestFilterText:
    """Test the text-level filter function."""

    def test_preserves_final_newline(self) -> None:
        text = "a = 1\nb = 2  # gitignore\nc = 3\n"
        result = filter_text(text, HASH)
        assert result == "a = 1\nc = 3\n"

    def test_empty_string(self) -> None:
        assert filter_text("", HASH) == ""

    def test_all_removed_returns_empty(self) -> None:
        text = "a = 1  # gitignore\n"
        result = filter_text(text, HASH)
        assert result == ""

    def test_no_markers(self) -> None:
        text = "normal line\n"
        assert filter_text(text, HASH) == "normal line\n"


class TestScanMarkers:
    """Test marker scanning / inventory."""

    def test_scan_single_line(self) -> None:
        lines = ["normal\n", "secret  # gitignore\n", "normal\n"]
        findings = scan_markers(lines, HASH)
        assert len(findings) == 1
        assert findings[0]["line_number"] == 2
        assert findings[0]["marker_type"] == "line"

    def test_scan_block(self) -> None:
        lines = [
            "keep\n",
            "# gitignore-start\n",
            "hidden_a\n",
            "hidden_b\n",
            "# gitignore-end\n",
            "keep\n",
        ]
        findings = scan_markers(lines, HASH)
        assert len(findings) == 4
        types = [f["marker_type"] for f in findings]
        assert types == ["block_start", "block_content", "block_content", "block_end"]
        assert findings[0]["line_number"] == 2
        assert findings[3]["line_number"] == 5

    def test_scan_mixed(self) -> None:
        lines = [
            "a\n",
            "b  # gitignore\n",
            "# gitignore-start\n",
            "c\n",
            "# gitignore-end\n",
        ]
        findings = scan_markers(lines, HASH)
        assert len(findings) == 4
        assert findings[0]["marker_type"] == "line"
        assert findings[1]["marker_type"] == "block_start"

    def test_scan_no_markers(self) -> None:
        lines = ["normal_a\n", "normal_b\n"]
        assert scan_markers(lines, HASH) == []
