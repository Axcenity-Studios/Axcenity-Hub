"""Browser checks for the Home's motion that only a real layout and scroll can show.

`open_home` is in tests/conftest.py; it needs the built stylesheet.
"""

import os

import pytest

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

pytestmark = pytest.mark.browser

PLAYING = (
    "() => [...document.querySelectorAll('#facts .motif')].map(m => m.dataset.on !== undefined)"
)


def test_motifs_play_in_view_and_again_after_scrolling_away_and_back(open_home):
    page, errors = open_home()
    assert page.evaluate(PLAYING) == [False] * 4
    page.evaluate("document.getElementById('facts').scrollIntoView({block: 'center'})")
    page.wait_for_function(f"({PLAYING})().every(Boolean)")
    page.evaluate("scrollTo(0, 0)")
    page.wait_for_function(f"!({PLAYING})().some(Boolean)")
    page.evaluate("document.getElementById('facts').scrollIntoView({block: 'center'})")
    page.wait_for_function(f"({PLAYING})().every(Boolean)")
    assert errors == []


def test_motifs_rest_drawn_under_reduced_motion(open_home):
    page, _ = open_home(reduced_motion="reduce")
    assert page.evaluate("document.documentElement.dataset.motifs") is None
    page.evaluate("document.getElementById('facts').scrollIntoView({block: 'center'})")
    assert page.evaluate("getComputedStyle(document.querySelector('.stat-motif')).opacity") == "1"


@pytest.mark.parametrize("width", [360, 640, 768, 1024, 1279, 1280])
def test_motifs_sit_beside_their_numerals_and_titles_without_overflowing(open_home, width):
    page, _ = open_home(width=width)
    overflow = page.evaluate(
        """() => [...document.querySelectorAll('.stat-title, .flow-head')].filter(row => {
            const column = row.parentElement.getBoundingClientRect().right;
            return [...row.children, row].some(part => part.getBoundingClientRect().right > column + 0.5);
          }).map(row => row.textContent.trim())"""
    )
    assert overflow == []
    beside = page.evaluate(
        """() => [...document.querySelectorAll('.stat-title, .flow-head')].every(row => {
            const icon = row.querySelector('.motif').getBoundingClientRect();
            const text = (row.querySelector('.flow-num') || row).getBoundingClientRect();
            const middle = icon.top + icon.height / 2;
            return middle > text.top && middle < text.bottom;
          })"""
    )
    assert beside
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
