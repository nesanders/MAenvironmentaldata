"""Regression tests for assemble_db.py's entity-name normalization.

_normalize_entity groups spelling variants of the same lobbying firm/client
under one canonical key. Its main failure mode is the opposite problem:
over-aggressively stripping descriptive suffixes ("Associates", "Legislative
Services", "Policy Group", ...) can collapse genuinely DIFFERENT firms that
happen to share a surname into one group. Sister project MAPLE hit and fixed
the identical bug (codeforboston/maple#2280); these tests use their exact
real-world example, which is also present in AMEND's own data.

Run from get_data/: pytest tests/test_assemble_db_normalize.py -q
"""

import assemble_db as adb


def test_distinct_firms_sharing_a_surname_stay_distinct():
    """Delaney & Associates, Delaney Legislative Services, and Delaney Policy
    Group are three unrelated MA lobbying registrants (verified in AMEND's
    own production data) that must NOT normalize to the same bare "DELANEY"."""
    a = adb._normalize_entity('Delaney & Associates, Inc')
    b = adb._normalize_entity('Delaney Legislative Services')
    c = adb._normalize_entity('Delaney Policy Group')
    assert len({a, b, c}) == 3, f'distinct firms collapsed: {a!r}, {b!r}, {c!r}'
    for name in (a, b, c):
        assert name != 'DELANEY', f'normalization collapsed to a bare surname: {name!r}'


def test_spelling_variants_of_the_same_firm_still_merge():
    """The fix must not regress the normalizer's actual job: real spelling
    variants of ONE firm should still collapse to the same key."""
    variants = [
        'Delaney & Associates, INC',
        'Delaney & Associates, Inc',
        'Delaney & Associates, Inc.',
        'Delaney and Associates, INC',
        'Delaney and Associates, Inc',
    ]
    normalized = {adb._normalize_entity(v) for v in variants}
    assert len(normalized) == 1, f'spelling variants of one firm diverged: {normalized}'


def test_ampersand_is_spaced_not_glued():
    """'&' must expand to ' AND ' with surrounding spaces, not glue adjacent
    words together (e.g. "Morrison&Foerster" must not become
    "MORRISONANDFOERSTER")."""
    assert adb._normalize_entity('Morrison & Foerster LLP') == 'MORRISON AND FOERSTER'


def test_real_client_containing_total_or_associates_substring_untouched():
    """A real client/entity name that merely CONTAINS a normalized phrase as a
    substring (not a whole word) must not be mangled."""
    assert adb._normalize_entity('ADP TotalSource') == 'ADP TOTALSOURCE'


def test_glued_associates_gets_a_space():
    """A name with no space before a trailing 'ASSOCIATES' (observed as a
    portal data-entry artifact) is still recognized and space-separated
    before the descriptive-phrase-stripping safety check runs."""
    assert adb._normalize_entity('SmithAssociates') == 'SMITH ASSOCIATES'


def test_law_office_of_strips_to_two_or_more_words():
    result = adb._normalize_entity('The Law Office of Jane Doe')
    assert result == 'JANE DOE'


def test_non_string_input_passed_through():
    assert adb._normalize_entity(None) is None
    assert adb._normalize_entity(123) == 123
