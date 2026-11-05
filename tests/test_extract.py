from ingest.extract import clean_text, _join_spans
from ingest.chunker import heading_level
from ingest.extract import Line


def test_broken_ligatures_fixed():
    assert clean_text("speciĤed ĥoater oĦce suģering ﬁnal") == "specified floater office suffering final"


def test_ligature_in_own_span_is_glued():
    assert clean_text(_join_spans(["speci", "Ĥ", "ed by the ", "Company"])) == "specified by the Company"
    assert _join_spans(["Room", "Rent"]) == "Room Rent"


def _line(text, bold=True, size=10.0):
    return Line(text=text, page=1, size=size, bold=bold, y=100, page_height=800)


def test_heading_rules():
    assert heading_level(_line("•"), 10.0) == 0                        # bullet is not a heading
    assert heading_level(_line("Schedule then the CB to be carried", bold=False), 10.0) == 0
    assert heading_level(_line("Section 56() of the said Act"), 10.0) != 1
    assert heading_level(_line("Annexure-A"), 10.0) == 1
    assert heading_level(_line("Co-payment"), 10.0) == 2


def test_rupee_backtick():
    assert clean_text("maximum of ` 5,000/- per day and `2000") == "maximum of ₹5,000/- per day and ₹2000"
