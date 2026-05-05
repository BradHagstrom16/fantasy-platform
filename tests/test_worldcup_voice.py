"""Tests for games.worldcup.services.voice.

State-keyed copy module. Tests verify the structure (every state has the
expected sub-keys), not the wording (which is allowed to evolve without
breaking tests).
"""
import pytest

from games.worldcup.services.voice import HUB_COPY, hub_copy, rank_tier


def test_hub_copy_has_all_four_states():
    assert set(HUB_COPY.keys()) == {'out', 'pre', 'live', 'post'}


def test_out_state_has_all_four_cta_variants():
    """Per spec section 9: 'guest' / 'unenrolled_pre' / 'unenrolled_live' /
    'unenrolled_post' (the last added in Plan 4 brainstorm to fill the
    spec gap)."""
    assert set(HUB_COPY['out'].keys()) == {
        'guest', 'unenrolled_pre', 'unenrolled_live', 'unenrolled_post',
    }


def test_pre_state_has_submitted_and_unsubmitted_variants():
    assert set(HUB_COPY['pre'].keys()) == {'submitted', 'unsubmitted'}


def test_live_state_has_four_rank_tier_variants():
    assert set(HUB_COPY['live'].keys()) == {'leader', 'chasing', 'mid', 'tail'}


def test_post_state_has_four_rank_tier_variants():
    assert set(HUB_COPY['post'].keys()) == {'champion', 'top_3', 'mid', 'tail'}


def test_every_leaf_dict_has_eyebrow_headline_subhead():
    """Every state/sub-state combo has the same 3 keys — partials rely
    on this structure."""
    for state, branches in HUB_COPY.items():
        for branch_key, leaf in branches.items():
            assert isinstance(leaf, dict), f'{state}/{branch_key} is not a dict'
            assert 'eyebrow' in leaf, f'{state}/{branch_key} missing eyebrow'
            assert 'headline' in leaf, f'{state}/{branch_key} missing headline'
            assert 'subhead' in leaf, f'{state}/{branch_key} missing subhead'


def test_hub_copy_accessor_returns_correct_leaf():
    leaf = hub_copy('out', 'guest')
    assert isinstance(leaf, dict)
    assert 'eyebrow' in leaf


def test_hub_copy_accessor_raises_on_unknown_state():
    with pytest.raises(KeyError):
        hub_copy('mystery', 'guest')


def test_hub_copy_accessor_raises_on_unknown_branch():
    with pytest.raises(KeyError):
        hub_copy('out', 'mystery')


@pytest.mark.parametrize('rank,total,expected', [
    (1, 10, 'leader'),
    (2, 10, 'chasing'),
    (3, 10, 'chasing'),
    (5, 10, 'mid'),
    (8, 10, 'tail'),
    (10, 10, 'tail'),
    (1, 1, 'leader'),
])
def test_rank_tier_buckets(rank, total, expected):
    """Rank tier mapping for live/post states.
    - 1 -> leader
    - 2-3 -> chasing
    - bottom 1/3 (rank > total * 2/3) -> tail
    - else -> mid
    """
    assert rank_tier(rank, total) == expected
