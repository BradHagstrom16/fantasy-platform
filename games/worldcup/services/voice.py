"""State-keyed voice copy for the WC hub.

Spec C Plan 4 introduces a 4-state hub (out/pre/live/post) with branching
sub-states inside each. Centralizing the strings here keeps partials free
of hardcoded text and makes copy revisable in one place.

Structure:
    HUB_COPY[state][branch] = {'eyebrow', 'headline', 'subhead'}

The 'out' state has 4 cta_state branches (guest, unenrolled_{pre,live,post}).
'pre' has 2 (submitted, unsubmitted). 'live' and 'post' have 4 rank-tier
branches each — see rank_tier() for the bucket boundaries.

Tone: Commish voice (the CCC house pattern — see Spec A's voice doctrine).
Sentence-case eyebrows are optional; uppercase happens in CSS via
.wc-eyebrow's text-transform.
"""

HUB_COPY = {
    'out': {
        'guest': {
            'eyebrow': 'The Pool Is Open',
            'headline': 'Pick 9 nations. Chase the trophy.',
            'subhead': 'Sign up to swear the Oath before the deadline.',
        },
        'unenrolled_pre': {
            'eyebrow': 'Picks Open',
            'headline': 'Join the pool. The deadline is approaching.',
            'subhead': 'Pick 9 teams across 5 tiers. The Commish keeps score.',
        },
        'unenrolled_live': {
            'eyebrow': 'Tournament Underway',
            'headline': 'Registration is closed. Watch the action.',
            'subhead': 'See the leaderboard, browse rosters, follow recent results.',
        },
        'unenrolled_post': {
            'eyebrow': 'Pool Closed',
            'headline': 'The Oath is fulfilled. Meet your champion.',
            'subhead': 'See the final podium and the winning roster.',
        },
    },
    'pre': {
        # Hero collapse (S-Hub-PreCritique): drop the subhead to two-beat
        # hero per impeccable copy law. Headline carries the Tribune voice;
        # the lead card carries the action and the live countdown.
        # Plain-spoken middle (Hub coherence pass): eyebrow drops the
        # archaic "Tribute Window" framing so Casual-default readers don't
        # pay a metaphor-unpack cost above the fold; the Tribune voice
        # still lives in H1 ("The Tribune") and the CTAs ("Seal/Amend the
        # Oath"). Cross-tab parity: leaderboard.html mirrors this string.
        'unsubmitted': {
            'eyebrow': 'Picks Open',
            'headline': 'The Pool locks at first whistle.',
            'subhead': '',
        },
        'submitted': {
            'eyebrow': 'Sealed. Still Editable.',
            'headline': 'Your Oath is on file.',
            'subhead': '',
        },
    },
    'live': {
        'leader': {
            'eyebrow': 'You Lead The Pool',
            'headline': 'The Commish takes notes.',
            'subhead': 'Hold the line.',
        },
        'chasing': {
            'eyebrow': 'In The Hunt',
            'headline': 'You are within striking distance.',
            'subhead': 'A few results away from the top.',
        },
        'mid': {
            'eyebrow': 'Mid-Pack',
            'headline': 'The Commish is watching.',
            'subhead': 'A run of green can change the picture quickly.',
        },
        'tail': {
            'eyebrow': 'Long Road Ahead',
            'headline': 'Underdogs make the season.',
            'subhead': 'Keep the faith.',
        },
    },
    'post': {
        'champion': {
            'eyebrow': 'Champion of the Pool',
            'headline': 'You won. The Oath is paid.',
            'subhead': 'See your final roster and the season recap.',
        },
        'top_3': {
            'eyebrow': 'Podium Finish',
            'headline': 'The Commish raises a glass.',
            'subhead': 'You finished on the podium.',
        },
        'mid': {
            'eyebrow': 'Season Closed',
            'headline': 'The Oath is fulfilled.',
            'subhead': 'See your final roster and the champion.',
        },
        'tail': {
            'eyebrow': 'Season Closed',
            'headline': 'There is always next cycle.',
            'subhead': 'See the champion and start plotting your return.',
        },
    },
}


def hub_copy(state: str, branch: str) -> dict:
    """Return the {eyebrow, headline, subhead} leaf for a state/branch path.

    Raises KeyError on unknown state or branch — fail loud per CLAUDE.md.
    """
    return HUB_COPY[state][branch]


def rank_tier(rank: int, total: int) -> str:
    """Bucket a rank into one of the live/post sub-state keys.

    - rank 1                     -> 'leader' (or 'champion' for post — caller
                                    swaps when state == 'post')
    - rank 2 or 3                -> 'chasing' (or 'top_3' for post)
    - bottom third (rank > total * 2 / 3)  -> 'tail'
    - everything else            -> 'mid'

    For 'post' state, the caller maps 'leader' -> 'champion' and
    'chasing' -> 'top_3' since the labels differ.
    """
    if rank == 1:
        return 'leader'
    if rank in (2, 3):
        return 'chasing'
    if total > 0 and rank > (total * 2) // 3:
        return 'tail'
    return 'mid'
