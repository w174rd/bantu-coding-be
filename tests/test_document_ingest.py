import pytest

from app.services.documents import extract_text

MAX_BYTES = 1024


def test_markdown_is_decoded():
    assert extract_text("problem.md", b"# Bug\n\nIt crashes.", MAX_BYTES) == "# Bug\n\nIt crashes."


def test_plain_text_is_decoded():
    assert extract_text("log.txt", "traceback".encode(), MAX_BYTES) == "traceback"


def test_suffix_check_is_case_insensitive():
    assert extract_text("NOTES.MD", b"content", MAX_BYTES) == "content"


def test_other_file_types_are_rejected():
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_text("report.pdf", b"%PDF-1.7", MAX_BYTES)


def test_missing_filename_is_rejected():
    with pytest.raises(ValueError, match="no filename"):
        extract_text(None, b"content", MAX_BYTES)


def test_oversized_file_is_rejected():
    with pytest.raises(ValueError, match="larger than"):
        extract_text("big.txt", b"x" * (MAX_BYTES + 1), MAX_BYTES)


def test_file_exactly_at_the_limit_is_accepted():
    assert extract_text("edge.txt", b"x" * MAX_BYTES, MAX_BYTES) == "x" * MAX_BYTES


def test_non_utf8_is_rejected():
    with pytest.raises(ValueError, match="not valid UTF-8"):
        extract_text("latin1.txt", b"caf\xe9", MAX_BYTES)


def test_empty_file_is_rejected():
    with pytest.raises(ValueError, match="empty"):
        extract_text("blank.md", b"   \n\t ", MAX_BYTES)


def test_filename_is_never_treated_as_a_path():
    # An upload naming a traversal path is still just a .md upload; nothing here
    # touches the filesystem, so the name only has to survive the suffix check.
    assert extract_text("../../etc/passwd.md", b"content", MAX_BYTES) == "content"
