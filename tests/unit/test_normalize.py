"""Company and role normalization (research R8)."""

import pytest

from applytrail.normalize import make_key, norm_company, norm_role


@pytest.mark.parametrize("name", ["Acme", "ACME Inc.", "Acme Corporation", "Acme, Inc"])
def test_company_variants_share_key(name):
    assert norm_company(name) == "acme"


def test_ampersand_becomes_and():
    assert norm_company("Johnson & Johnson") == "johnson and johnson"


def test_punctuation_becomes_space_and_suffix_dropped():
    assert norm_company("Co-op Ltd") == "co op"


def test_suffix_only_name_keeps_last_word():
    assert norm_company("Company") == "company"


def test_repeated_suffixes_dropped():
    assert norm_company("Globex Pvt. Ltd.") == "globex"


def test_whitespace_collapsed():
    assert norm_company("  Initech   Systems  ") == "initech systems"


def test_role_trimmed_casefolded_and_end_punctuation_stripped():
    assert norm_role("  Backend Engineer. ") == "backend engineer"


def test_role_inner_whitespace_collapsed():
    assert norm_role("Senior   Data\tEngineer") == "senior data engineer"


@pytest.mark.parametrize("role", [None, ""])
def test_role_missing_gives_empty(role):
    assert norm_role(role) == ""


def test_make_key():
    assert make_key("acme", "") == "acme|"
    assert make_key("acme", "backend engineer") == "acme|backend engineer"
