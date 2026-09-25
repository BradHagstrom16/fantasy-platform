"""The Club Desk: one email system for every game (ADR-065).

Two passes, both built on the ``games/gameday.py`` consumer shape: each
game contributes a consumer from its own services package, the desk lists
them in ``_reminder_consumers()`` / ``_paper_consumers()``, and adding a
game is one consumer plus one line. Games never import each other.

**The reminder desk** (``run_desk``). The unit is the send SLOT, not the
member path. Every active, unsent tier of every game named in ``anchors``
anchors a letter, keyed to its deadline and never to a weekday; the
nearest deadline owns the subject. Another game rides a slot only when the
slot is named in ``rides``, that game has an open obligation, and its own
matching tier is near (``covers``); riding pre-marks that tier. A dual
recipient gets the anchor's own reminder letter (byte-identical to the
legacy pass's) plus a footnote rider; a rider-only recipient gets that
game's own standalone reminder. Per-game delivered counters: a game's flag
latches only if a letter carrying that game's section was delivered, marks
are monotonic, and there is one commit at the end. A rider's failure
degrades the letter to the anchor's section and never aborts the pass.

**The Tuesday Paper** (``run_paper``). One run opens both games (the
Docket first: creating its week is the one job no other path recovers),
each in its own isolation, then sends one letter per member with
something to say: two or more sections wear club chrome, one section is
that game's own letter, and the latches (``picks_open_notified`` per game,
``record_notified`` on the Docket's previous week) are set after the send.
Any game not open at that moment is announced later by its existing
standalone path, unchanged.

**One clock.** The desk reads the clock once (``now``, aware) and passes
it to every consumer call; nothing reached from a run may read a clock
itself, which is what makes ``--dry-run --now`` truthful in production,
where the ``*_FAKE_NOW`` seams are off (``tests/test_club_desk.py``).

**Dry run** composes everything, prints what would go and what would
latch, and sends nothing and writes nothing. Locked by
``tests/test_club_desk_matrix.py`` (the written spec of who gets what)
and ``tests/test_club_desk.py``.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from extensions import db
from utils.email import send_platform_email
from utils.email_layout import (
    Letter,
    Section,
    format_deadline_short,
    render_letter,
    rider_block,
    section_block,
    tab_block,
)

logger = logging.getLogger(__name__)

# The named slots a rider may join: F and S are Survivor's two tiers, D the
# Docket's last. A tier outside this map anchors its own letter and never
# carries a rider (1A: a Docket-only week sends 48h, 24h and 2h on their
# own; the Docket's Sunday morning has nothing left to ride).
SLOTS = {'F': ('cfb', 'warning'), 'S': ('cfb', 'final'), 'D': ('docket', '2h')}
SLOT_OF = {pair: name for name, pair in SLOTS.items()}
ANCHOR_SLUGS = ('cfb', 'docket')


class DeskNoWork(Exception):
    """Nothing to do YET (out of season, week not imported, no open week):
    a quiet exit 0 under ``--scheduled``, a loud exit 1 typed by hand."""


@dataclass(frozen=True)
class ReminderConsumer:
    """One game's half of the reminder desk. Every callable takes the
    desk's ``now`` (aware) explicitly; none reads a clock.

    ``week(now)`` is the week this game answers for right now (None out of
    season, before the import, or with no open week). ``deadline(week)`` is
    that week's aware deadline. ``anchor_tier(week, now)`` is the game's
    active, UNSENT tier (None otherwise). ``covers(slot, week, now)`` is the
    tier of this game a ride on ``slot`` satisfies, only when that tier's
    target is within six hours of ``now``. ``recipients`` / ``letter`` /
    ``context`` are the game's shared reminder builders (the legacy pass
    calls the same ones); ``user`` reads the User off a recipient;
    ``section`` is the recipient's obligation as a :class:`Section`, the
    source of the rider line. ``tier_sent`` / ``mark_sent`` wrap the game's
    per-week flag; ``mark_sent`` stages only (monotonic, no commit).
    ``push`` buzzes the game's own recipients with its own tag.
    """
    slug: str
    week: Callable[[datetime], object | None]
    deadline: Callable[[object], datetime]
    anchor_tier: Callable[[object, datetime], str | None]
    covers: Callable[[str, object, datetime], str | None]
    recipients: Callable[[object, str, datetime], list]
    user: Callable[[object], object]
    section: Callable[[object, object, datetime], Section]
    context: Callable[[object, datetime], dict]
    letter: Callable[[object, dict, str], Letter]
    tier_sent: Callable[[object, str], bool]
    mark_sent: Callable[[object, str], None]
    push: Callable[[object, str, datetime, list], None]


@dataclass(frozen=True)
class PaperConsumer:
    """One game's half of the Tuesday Paper.

    ``open_week(now)`` opens the week WITHOUT announcing and returns the
    week to announce, or None (nothing to open, a failed or partial import,
    already announced). ``candidate(now)`` is the dry run's read-only
    counterpart: the week that is open right now, announced or not, or
    None. ``record_week(week)`` is the earlier week whose record this letter
    carries (the Docket), or None. ``sections(week, record_week, now)`` is
    one read for the whole roster: ``{user_id: Say}``. ``mark_announced``
    stages the latches after the send (no commit).
    """
    slug: str
    open_week: Callable[[datetime], object | None]
    candidate: Callable[[datetime], object | None]
    record_week: Callable[[object], object | None]
    sections: Callable[[object, object | None, datetime], dict]
    mark_announced: Callable[[object, object | None, bool, bool], None]


@dataclass(frozen=True)
class Say:
    """What one game says to one member in the Paper: the section, the
    short phrase for the preheader (``survived with Oregon``), and whether
    the section's record line came from a graded week (the Docket's
    ``record_notified`` latches only on those)."""
    user: object
    section: Section
    hook: str | None = None
    record: bool = False


def _reminder_consumers():
    """Imported lazily: each consumer module imports this one."""
    from games.cfb.services.desk import REMINDER as cfb
    from games.docket.services.desk import REMINDER as docket
    return (cfb, docket)


def _paper_consumers():
    """The Docket FIRST: creating its week is the one job no other path
    recovers (``docket-lines --scheduled`` stands down on a missing week);
    a CFB hang or failure must never stop it."""
    from games.cfb.services.desk import PAPER as cfb
    from games.docket.services.desk import PAPER as docket
    return (docket, cfb)


# ---------------------------------------------------------------------------
# The reminder desk
# ---------------------------------------------------------------------------

@dataclass
class Anchor:
    consumer: ReminderConsumer
    week: object
    tier: str
    deadline: datetime
    rider: Rider | None = None

    @property
    def slot(self):
        return SLOT_OF.get((self.consumer.slug, self.tier))


@dataclass
class Rider:
    consumer: ReminderConsumer
    week: object
    tier: str


@dataclass
class Composed:
    """One letter the desk would send, and which games it carries."""
    user: object
    letter: Letter
    games: tuple[str, ...]      # slugs whose section this letter carries
    anchor: str
    rider: str | None = None
    says: list = field(default_factory=list)   # the Paper: one Say per section


@dataclass
class DeskRun:
    now: datetime
    anchors: list[Anchor] = field(default_factory=list)
    skipped: dict = field(default_factory=dict)     # slug -> why (no week)
    composed: list[Composed] = field(default_factory=list)
    delivered: dict = field(default_factory=dict)   # slug -> letters delivered
    pushed: dict = field(default_factory=dict)      # slug -> user ids pushed
    latched: dict = field(default_factory=dict)     # slug -> tier
    recipients: dict = field(default_factory=dict)  # slug -> recipient count
    errors: list = field(default_factory=list)
    exit_code: int = 0
    dry_run: bool = False


def _rider_sentence(section: Section) -> str:
    """The rider's one sentence, from the riding game's own Section: its
    obligation line, then its deadline through the platform formatter."""
    first = section.lines[0]
    text = first.striptags() if hasattr(first, 'striptags') else str(first)
    return (f'{text} {section.deadline_label} '
            f'{format_deadline_short(section.deadline)}.')


def _find_anchors(consumers, anchors, now, run):
    for consumer in consumers:
        if consumer.slug not in anchors:
            continue
        week = consumer.week(now)
        if week is None:
            run.skipped[consumer.slug] = 'no week to answer for'
            continue
        tier = consumer.anchor_tier(week, now)
        if tier is None:
            continue
        run.anchors.append(Anchor(consumer=consumer, week=week, tier=tier,
                                  deadline=consumer.deadline(week)))
    run.anchors.sort(key=lambda a: a.deadline)


def _attach_riders(consumers, rides, now, run):
    """A rider joins the nearest letter whose slot is named in ``rides``.
    A game already anchoring in the same firing becomes that letter's
    rider instead of sending standalone (its tier is covered by
    definition); a game not anchoring rides only when ``covers`` names a
    near, unsent tier."""
    if not run.anchors:
        return
    lead = run.anchors[0]
    if lead.slot not in rides:
        return
    for consumer in consumers:
        if consumer is lead.consumer:
            continue
        week = consumer.week(now)
        if week is None:
            continue                       # quiet skip (rule 3)
        tier = consumer.covers(lead.slot, week, now)
        if tier is None or consumer.tier_sent(week, tier):
            continue                       # rule 2: dropped entirely
        lead.rider = Rider(consumer=consumer, week=week, tier=tier)
        run.anchors = [a for a in run.anchors if a.consumer is not consumer]
        return


def _rider_owes(rider, now, run):
    """``{user_id: (recipient, Section)}`` for the rider, in its own
    isolation: an exception logs at ERROR and degrades the letter to the
    anchor's section (rule 3)."""
    try:
        owes = {}
        for recipient in rider.consumer.recipients(rider.week, rider.tier, now):
            user = rider.consumer.user(recipient)
            owes[user.id] = (recipient, rider.consumer.section(
                recipient, rider.week, now))
        return owes
    except Exception as exc:
        logger.exception('Rider %s failed; sending anchor-only letters',
                         rider.consumer.slug)
        run.errors.append(f'rider {rider.consumer.slug}: {exc}')
        return {}


def _compose_slot(anchor, now, run):
    consumer = anchor.consumer
    context = consumer.context(anchor.week, now)
    recipients = consumer.recipients(anchor.week, anchor.tier, now)
    run.recipients[consumer.slug] = len(recipients)
    rider = anchor.rider
    owes = _rider_owes(rider, now, run) if rider else {}
    if rider:
        run.recipients[rider.consumer.slug] = len(owes)
    anchored_ids = set()
    for recipient in recipients:
        user = consumer.user(recipient)
        anchored_ids.add(user.id)
        letter = consumer.letter(recipient, context, anchor.tier)
        games = (consumer.slug,)
        rider_slug = None
        if user.id in owes:
            _, section = owes[user.id]
            letter.notes = [rider_block(rider.consumer.slug,
                                        _rider_sentence(section),
                                        section.button, section.url),
                            *letter.notes]
            games = (consumer.slug, rider.consumer.slug)
            rider_slug = rider.consumer.slug
        run.composed.append(Composed(user=user, letter=letter, games=games,
                                     anchor=consumer.slug, rider=rider_slug))
    if rider:
        rider_context = rider.consumer.context(rider.week, now)
        for user_id, (recipient, _section) in owes.items():
            if user_id in anchored_ids:
                continue
            letter = rider.consumer.letter(recipient, rider_context, rider.tier)
            run.composed.append(Composed(
                user=rider.consumer.user(recipient), letter=letter,
                games=(rider.consumer.slug,), anchor=rider.consumer.slug))
    return {consumer.slug: [consumer.user(r).id for r in recipients],
            **({rider.consumer.slug: list(owes)} if rider else {})}


def _send(run):
    for composed in run.composed:
        user = composed.user
        if not user.email:
            continue
        plain, html = render_letter(composed.letter)
        if send_platform_email(user.email, composed.letter.subject, plain, html):
            for slug in composed.games:
                run.delivered[slug] = run.delivered.get(slug, 0) + 1
        else:
            logger.warning('Desk letter to user %s was not accepted', user.id)


def run_desk(now, *, anchors=ANCHOR_SLUGS, rides=(), dry_run=False,
             scheduled=False) -> DeskRun:
    """One firing of the reminder desk at ``now`` (aware).

    ``anchors`` names the games the desk may lead for, ``rides`` the slots
    that may carry a rider (both live on the unit's ``ExecStart`` line in
    production). Returns the run record; ``exit_code`` is 1 when an active
    anchor with recipients delivered to nobody, or when nothing named in
    ``anchors`` has a week and the run was not ``scheduled``.
    """
    run = DeskRun(now=now, dry_run=dry_run)
    consumers = _reminder_consumers()
    _find_anchors(consumers, anchors, now, run)
    if not run.anchors and run.skipped and all(
            slug in run.skipped for slug in anchors):
        if not scheduled:
            run.exit_code = 1
        return run
    _attach_riders(consumers, rides, now, run)

    pushes = {}
    for anchor in run.anchors:
        pushes.update(_compose_slot(anchor, now, run))
    if dry_run:
        carried = _games_with_recipients(run)
        for anchor in run.anchors:
            for consumer, _week, tier in _parties(anchor):
                if consumer.slug in carried:
                    run.latched[consumer.slug] = tier
        return run

    _send(run)

    # Push rides on each game's own recipients regardless of the mail
    # outcome (a mail outage is exactly when push matters), with each
    # game's own tag.
    for anchor in run.anchors:
        for consumer, week, tier in _parties(anchor):
            ids = pushes.get(consumer.slug, [])
            if ids:
                consumer.push(week, tier, now, ids)
                run.pushed[consumer.slug] = ids

    # Latch G only if a letter carrying G's section was delivered
    # (rule 5); marks are monotonic and land in one commit.
    for anchor in run.anchors:
        for consumer, week, tier in _parties(anchor):
            if run.delivered.get(consumer.slug, 0) > 0:
                consumer.mark_sent(week, tier)
                run.latched[consumer.slug] = tier
    db.session.commit()

    for anchor in run.anchors:
        slug = anchor.consumer.slug
        if run.recipients.get(slug, 0) and not run.delivered.get(slug, 0):
            logger.error('%s %s reminder reached nobody (%s recipients)',
                         slug, anchor.tier, run.recipients[slug])
            run.exit_code = 1
    return run


def _parties(anchor):
    yield anchor.consumer, anchor.week, anchor.tier
    if anchor.rider:
        yield anchor.rider.consumer, anchor.rider.week, anchor.rider.tier


def _games_with_recipients(run):
    return {slug for c in run.composed for slug in c.games}


# ---------------------------------------------------------------------------
# The Tuesday Paper
# ---------------------------------------------------------------------------

HEADLINES = {
    frozenset({'cfb', 'docket'}): 'Both boards are open',
    frozenset({'docket'}): 'The docket is open',
    frozenset({'cfb'}): 'Picks are open',
}
OWN_SUBJECT = {'cfb': 'Picks are open: CFB Survivor, Week {n}',
               'docket': 'Picks are open: The Docket, Week {n}'}
OWN_HEADLINE = {'cfb': 'CFB Survivor, Week {n}: picks are open',
                'docket': 'The Docket, Week {n}: picks are open'}
PAPER_SUBJECT_MAX = 50


@dataclass
class PaperRun:
    now: datetime
    opened: dict = field(default_factory=dict)      # slug -> week
    announced: dict = field(default_factory=dict)   # slug -> already announced
    record_week: object | None = None
    composed: list[Composed] = field(default_factory=list)
    delivered: dict = field(default_factory=dict)   # slug -> sections delivered (with a button)
    record_delivered: int = 0
    latched: dict = field(default_factory=dict)
    errors: list = field(default_factory=list)
    exit_code: int = 0
    dry_run: bool = False


def _open_all(consumers, now, run, dry_run):
    for consumer in consumers:
        opener = consumer.candidate if dry_run else consumer.open_week
        try:
            week = opener(now)
        except Exception as exc:
            # Isolated: a CFB failure must never stop the Docket week
            # being created (or the reverse); the exit code takes the
            # worst result at the end.
            db.session.rollback()
            logger.exception('Paper: %s open failed', consumer.slug)
            run.errors.append(f'{consumer.slug}: {exc}')
            run.exit_code = 1
            continue
        if week is None:
            continue
        run.opened[consumer.slug] = week
        run.announced[consumer.slug] = bool(week.picks_open_notified)


def _week_label(week):
    """``Week 4`` from either game's week row."""
    return getattr(week, 'round_name', None) or f'Week {week.week_number}'


def _paper_letter(says: list[Say], state_slugs, week_number) -> Letter:
    """One member's Paper: club chrome over two or more sections, or the
    single game's own letter shape (its headline, accent, subject). The
    Paper's headline is its name and week; the state opens the lede (no
    eyebrow above a heading, ADR-066)."""
    says = sorted(says, key=lambda s: (s.section.deadline is None,
                                       s.section.deadline or datetime.max))
    hooks = [s.hook for s in says if s.hook]
    preheader = ('You ' + ' and '.join(hooks) + '.') if hooks else ''
    notes = [tab_block(s.section.nudge, s.section.slug)
             for s in says if s.section.nudge]
    if len(says) >= 2:
        state = HEADLINES[frozenset(state_slugs)]
        subject = f'The Morning Line, Week {week_number}: {state}'
        assert len(subject) <= PAPER_SUBJECT_MAX, subject
        return Letter(
            subject=subject,
            headline=f'The Morning Line, Week {week_number}',
            game_slug=None,
            preheader=preheader or 'Last week is in the books and this '
                                   'week\'s lines are posted.',
            lede=[f'{state}. Last week is in the books and this week\'s '
                  f'lines are posted.'],
            extras=[section_block(s.section) for s in says],
            cta=None,
            notes=notes,
        )
    say = says[0]
    section = say.section
    slug = section.slug
    return Letter(
        subject=OWN_SUBJECT[slug].format(n=week_number),
        headline=OWN_HEADLINE[slug].format(n=week_number),
        game_slug=slug,
        season=_season_of(slug),
        preheader=preheader or f'Deadline {format_deadline_short(section.deadline)}.',
        lede=list(section.lines),
        facts=[(section.deadline_label, format_deadline_short(section.deadline))],
        cta=(section.button, section.url),
        notes=notes,
    )


def _season_of(slug):
    if slug == 'cfb':
        from flask import current_app
        return current_app.config.get('CFB_SEASON_YEAR', 2026)
    from games.docket.services.weeks import SEASON_YEAR
    return SEASON_YEAR


def run_paper(now, *, dry_run=False, scheduled=False) -> PaperRun:
    """One Tuesday Paper at ``now`` (aware): open, compose, send, latch."""
    run = PaperRun(now=now, dry_run=dry_run)
    consumers = _paper_consumers()
    _open_all(consumers, now, run, dry_run)
    if not run.opened:
        if not scheduled and not run.errors:
            run.exit_code = 1
        return run

    by_slug = {c.slug: c for c in consumers}
    says_by_user: dict[int, list[Say]] = {}
    for slug, week in run.opened.items():
        consumer = by_slug[slug]
        record_week = consumer.record_week(week)
        if slug == 'docket':
            run.record_week = record_week
        for user_id, say in consumer.sections(week, record_week, now).items():
            says_by_user.setdefault(user_id, []).append(say)

    # "Week n" is the first section's week, nearest deadline first.
    for _user_id, says in sorted(says_by_user.items()):
        say_sorted = sorted(says, key=lambda s: (s.section.deadline is None,
                                                 s.section.deadline or datetime.max))
        if len(says) == 1 and says[0].section.button is None:
            continue        # a spectator alone gets no Paper (design 3A)
        week_number = run.opened[say_sorted[0].section.slug].week_number
        letter = _paper_letter(says, run.opened.keys(), week_number)
        run.composed.append(Composed(
            user=says[0].user, letter=letter,
            games=tuple(s.section.slug for s in say_sorted),
            anchor=say_sorted[0].section.slug, says=say_sorted))

    if dry_run:
        return run

    for composed in run.composed:
        user = composed.user
        if not user.email:
            continue
        plain, html = render_letter(composed.letter)
        if not send_platform_email(user.email, composed.letter.subject,
                                   plain, html):
            logger.warning('Paper to user %s was not accepted', user.id)
            continue
        for say in composed.says:
            slug = say.section.slug
            # Only a section with something to act on counts toward the
            # game's picks-open latch: an eliminated member's spectator
            # line is a mention, not an announcement.
            if say.section.button is not None:
                run.delivered[slug] = run.delivered.get(slug, 0) + 1
            if slug == 'docket' and say.record:
                run.record_delivered += 1

    for slug, week in run.opened.items():
        consumer = by_slug[slug]
        announced = run.delivered.get(slug, 0) > 0
        record = slug == 'docket' and run.record_delivered > 0
        consumer.mark_announced(week, run.record_week if slug == 'docket' else None,
                                announced, record)
        if announced:
            run.latched[slug] = 'picks_open_notified'
        if record:
            run.latched['docket-record'] = run.record_week.week_number
    db.session.commit()
    return run
