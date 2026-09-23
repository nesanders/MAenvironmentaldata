"""Regression + format-change tests for the MA lobbying disclosure parser.

The SoS portal HTML has four distinct format eras and the parser is the most
likely thing to silently break when the portal changes its markup. These tests
parse committed fixture pages (one per era, entity + individual) and assert the
known-correct compensation totals, client/bill counts, era detection, and the
specific bug fixes (the "Total amount" summary-row artifact; the "H73;"
semicolon bill separator). If the portal changes format and the parser starts
returning different numbers, these fail loudly.

Fixtures live in tests/fixtures/*.html.gz (gzipped real disclosure + summary
pages). Run from get_data/:  pytest tests/ -q
"""

import gzip
from pathlib import Path

import pytest
from bs4 import BeautifulSoup

import get_MA_lobbying as g

FIXTURES = Path(__file__).parent / 'fixtures'


def _soup(name: str) -> BeautifulSoup:
    with gzip.open(FIXTURES / f'{name}.html.gz', 'rt', encoding='utf-8') as fh:
        return BeautifulSoup(fh.read(), 'html.parser')


def _comp_total(detail: dict) -> float:
    return sum(c['amount'] for c in detail['compensation'] if c['amount'])


# (fixture, year, expected_comp, n_clients, n_bills, era_label)
DISCLOSURE_CASES = [
    ('2007e', 2007, 112_500.00, 1, 2, 'legacy 4-col -> _total_salary_'),
    ('2011e', 2011, 641_243.0, 23, 4, 'legacy 6-col -> per-client comp'),
    ('2016e', 2016, 990_474.00, 30, 1357, 'hybrid -> Panel1 totals'),
    ('2024e', 2024, 115_000.00, 5, 22, 'modern -> grdvClientPaidToEntity'),
    ('2024i', 2024, 1_095_200.0, 17, 135, 'modern individual'),
    ('2011i', 2011, 18_518.00, 1, 0, 'legacy individual'),
]


@pytest.mark.parametrize('fix,year,exp_comp,n_clients,n_bills,era', DISCLOSURE_CASES)
def test_disclosure_compensation_and_bills(fix, year, exp_comp, n_clients, n_bills, era):
    d = g.parse_disclosure_detail(_soup(f'{fix}_disc'), year)
    assert _comp_total(d) == pytest.approx(exp_comp, abs=1.0), f'{fix} ({era}) comp total'
    assert len(d['compensation']) == n_clients, f'{fix} ({era}) client count'
    assert len(d['bills']) == n_bills, f'{fix} ({era}) bill count'


@pytest.mark.parametrize('fix,year,_c,_n,_b,_e', DISCLOSURE_CASES)
def test_no_total_amount_artifact(fix, year, _c, _n, _b, _e):
    """The legacy summary row (client_name == 'Total amount') must never be
    captured as a real client — that bug inflated 2010-2013 by ~4,000 rows."""
    d = g.parse_disclosure_detail(_soup(f'{fix}_disc'), year)
    bad = [c for c in d['compensation'] if c['client_name'] in ('Total amount', 'Total', '')]
    assert not bad, f'{fix} produced summary-row artifacts: {bad}'


def test_legacy_2007_uses_total_salary_placeholder():
    """2005-2008 has no per-client comp column; comp falls back to the entity
    salary total under the placeholder client name."""
    d = g.parse_disclosure_detail(_soup('2007e_disc'), 2007)
    assert [c['client_name'] for c in d['compensation']] == ['_total_salary_']


def test_legacy_2011_is_per_client_not_placeholder():
    """2009-2013 has a per-client 'Compensation received' column, so comp is
    per real client — never the _total_salary_ placeholder."""
    d = g.parse_disclosure_detail(_soup('2011e_disc'), 2011)
    names = [c['client_name'] for c in d['compensation']]
    assert '_total_salary_' not in names
    assert len(names) == len(set(names)), 'per-client comp should be deduped'


def test_semicolon_bill_separator_parsed():
    """Legacy bill tokens may use 'H73; Title' (semicolon) instead of a space;
    the bill number must still be captured."""
    d = g.parse_disclosure_detail(_soup('2011e_disc'), 2011)
    house_numbers = {b['bill_number'] for b in d['bills'] if b['chamber'] == 'House Bill'}
    assert '73' in house_numbers, 'H73 (semicolon-separated) should be parsed'


def test_modern_individual_captures_per_client_comp():
    """Individual (Lobbyist) registrants in the modern era report per-client
    compensation that the old grdvClientPaidToEntity-only parser missed."""
    d = g.parse_disclosure_detail(_soup('2024i_disc'), 2024)
    assert _comp_total(d) > 0
    assert all(c['client_name'] not in ('Total amount', '') for c in d['compensation'])


# (fixture, entity_name, year, reg_type, n_disc_urls)
SUMMARY_CASES = [
    ('2007e_summ', 'Ventry Associates, LLP', 2007, 'Lobbyist Entity', 2),
    ('2011e_summ', 'ML Strategies, LLC', 2011, 'Lobbyist Entity', 7),
    ('2024e_summ', '21c, LLC', 2024, 'Lobbyist Entity', 2),
    ('2024i_summ', 'Anthony Arthur Abdelahad', 2024, 'Lobbyist', 2),
    ('2011i_summ', 'Aaron Judd Agulnek', 2011, 'Lobbyist', 4),
]


@pytest.mark.parametrize('fix,name,year,reg_type,n_urls', SUMMARY_CASES)
def test_summary_metadata(fix, name, year, reg_type, n_urls):
    m = g.parse_summary(_soup(fix))
    assert m['entity_name'] == name
    assert m['year'] == year
    assert m['reg_type'] == reg_type
    assert len(m['disclosure_urls']) == n_urls
    assert all('CompleteDisclosure' in u for u in m['disclosure_urls'])


def test_parse_amount():
    assert g._parse_amount('$1,234.56') == 1234.56
    assert g._parse_amount('$0.00') == 0.0
    assert g._parse_amount('') is None
    assert g._parse_amount('N/A') is None


def test_year_to_general_court():
    # GC183 convened Jan 2003; each GC spans two calendar years.
    assert g._year_to_general_court(2003) == 183
    assert g._year_to_general_court(2004) == 183
    assert g._year_to_general_court(2005) == 184
    assert g._year_to_general_court(2023) == 193
    assert g._year_to_general_court(2025) == 194


# ── Offline-parsed fields (campaign contributions, salaries, mapping, purpose) ──

# (fixture, n_contributions, total_amount) — Date|Lobbyist|Recipient|Office|Amount
CAMPAIGN_CASES = [
    ('2007e_disc', 14, 2_630.0),
    ('2011e_disc', 93, 13_225.0),
    ('2016e_disc', 160, 28_825.0),
    ('2024e_disc', 6, 1_200.0),
    ('2024i_disc', 14, 2_800.0),
]


@pytest.mark.parametrize('fix,n,total', CAMPAIGN_CASES)
def test_campaign_contributions(fix, n, total):
    cc = g.parse_campaign_contributions(_soup(fix))
    assert len(cc) == n, f'{fix} contribution count'
    assert sum(c['amount'] for c in cc if c['amount']) == pytest.approx(total, abs=1.0)
    # required fields present and no header/placeholder rows leaked
    for c in cc:
        assert c['recipient_name'] and 'No campaign' not in c['date']


def test_salaries():
    sal = g.parse_salaries(_soup('2011e_disc'))
    assert len(sal) == 10
    assert sum(s['salary'] for s in sal if s['salary']) == pytest.approx(663_175.0, abs=1.0)
    assert all('Total' not in s['lobbyist_name'] for s in sal)


def test_employment_edges_individual_page():
    """Individual summary lists employing entities (RptEntity)."""
    edges = g.parse_employment_edges(_soup('2024i_summ'))
    assert len(edges) == 1
    assert edges[0]['entity_name'] == 'Ventry Associates, LLP'
    assert edges[0]['lobbyist_name'] is None  # registrant side filled by driver
    assert edges[0]['salary'] == pytest.approx(167_348.50, abs=1.0)


def test_employment_edges_entity_page():
    """Entity summary lists employed lobbyists (RptLobbyistInfo)."""
    edges = g.parse_employment_edges(_soup('2011e_summ'))
    assert len(edges) == 10
    assert all(e['entity_name'] is None and e['lobbyist_name'] for e in edges)


def test_client_purposes():
    cp = g.parse_client_purposes(_soup('2024e_summ'))
    assert len(cp) == 5
    assert sum(c['amount'] for c in cp if c['amount']) == pytest.approx(132_500.0, abs=1.0)
    by_name = {c['client_name']: c for c in cp}
    assert 'Amplify Education, Inc.' in by_name
    assert 'K-12 education' in by_name['Amplify Education, Inc.']['purpose']


def test_expenses_all_three_types():
    ex = g.parse_expenses(_soup('2024i_disc'))
    types = {e['expense_type'] for e in ex}
    assert types == {'operating', 'meals_entertainment_travel', 'additional'}
    assert all(e['amount'] > 0 for e in ex), 'blank $0 template rows must be filtered'
    assert sum(e['amount'] for e in ex) == pytest.approx(127_923.0, abs=5.0)


def test_expenses_filters_zero_template_rows():
    """The standard blank category template ('Advertising $0.00', etc.) must not
    appear; only actual reported expenses with amount > 0."""
    ex = g.parse_expenses(_soup('2011e_disc'))
    assert len(ex) == 2
    assert sum(e['amount'] for e in ex) == pytest.approx(414_750.0, abs=1.0)


# ── Reporting period + true registrant (nesanders/MAenvironmentaldata#126) ──────
# The Summary page's own lblYear only ever gives a bare year, which collided an
# entity's H1 and H2 filings under the same dedup key. And the discovering
# Summary page's registrant name is not reliably who actually filed a given
# disclosure — a single filing is cross-listed from every affiliated lobbyist's
# own Summary page too (e.g. 2024i_disc below: discovered via individual
# lobbyist Anthony Arthur Abdelahad's Summary page, per SUMMARY_CASES above, but
# actually filed by his employer entity "Ventry Associates, LLP").

# (fixture, year, period_start, period_end)
PERIOD_CASES = [
    ('2007e_disc', 2007, '2007-01-01', '2007-06-30'),
    ('2011e_disc', 2011, '2011-01-01', '2011-06-30'),
    ('2016e_disc', 2016, '2016-01-01', '2016-06-30'),
    ('2024e_disc', 2024, '2024-01-01', '2024-06-30'),
    ('2024i_disc', 2024, '2024-07-01', '2024-12-31'),
    ('2011i_disc', 2011, '2011-01-01', '2011-06-30'),
]


@pytest.mark.parametrize('fix,year,start,end', PERIOD_CASES)
def test_disclosure_period(fix, year, start, end):
    assert g.parse_disclosure_period(_soup(fix)) == (start, end)
    d = g.parse_disclosure_detail(_soup(fix), year)
    assert (d['period_start'], d['period_end']) == (start, end)


# (fixture, true_registrant_name, true_registrant_type)
REGISTRANT_CASES = [
    ('2007e_disc', 'Ventry Associates, LLP', 'Lobbyist Entity'),
    ('2011e_disc', 'ML Strategies, LLC', 'Lobbyist Entity'),
    ('2016e_disc', 'Murphy Donoghue Partners', 'Lobbyist Entity'),
    ('2024e_disc', '21c, LLC', 'Lobbyist Entity'),
    # Discovered via individual lobbyist Anthony Arthur Abdelahad's Summary page
    # (see SUMMARY_CASES) but actually filed by his employer entity — exactly
    # the misattribution this parser exists to catch.
    ('2024i_disc', 'Ventry Associates, LLP', 'Lobbyist Entity'),
    ('2011i_disc', 'Aaron Judd Agulnek', 'Lobbyist'),
]


@pytest.mark.parametrize('fix,name,reg_type', REGISTRANT_CASES)
def test_disclosure_registrant(fix, name, reg_type):
    assert g.parse_disclosure_registrant(_soup(fix)) == (name, reg_type)
    d = g.parse_disclosure_detail(_soup(fix), 2024)
    assert (d['registrant_name'], d['registrant_type']) == (name, reg_type)


def test_disclosure_registrant_falls_back_to_none_when_unparseable():
    """A page with neither registrant template (e.g. a Summary page, or a
    malformed fetch) must return (None, None) so callers fall back to the
    discovering Summary page's entity_name rather than silently keying on
    a wrong or empty value."""
    assert g.parse_disclosure_registrant(_soup('2024i_summ')) == (None, None)
    assert g.parse_disclosure_period(_soup('2024i_summ')) == (None, None)
