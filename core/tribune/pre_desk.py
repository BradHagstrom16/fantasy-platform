"""The four Club Letters sent before the announce desk kept a copy.

Week 1 through Week 3 of 2026 went out through the plain-text announce
tool, which mailed and forgot: no ``Announcement`` row exists for them, so
The Tribune cannot file them from the database. Their text is kept here
verbatim, as members received it (copied from the delivered mail), with
the moment each went out.

They are rebuilt the way that tool rendered them: the body is plain text
(a blank line starts a paragraph, a newline is a ``<br>``), never the
announce markup, which would now read "- 11 lives lost" as a bullet and
"1) Open" as a numbered step. ``file_pre_desk_letters`` writes each as a
sent row with the mailed copy, the page copy and the filing week, the same
shape the desk stores at send; nothing is mailed. The recipient count was
never kept, so it stays empty. Idempotent: a letter already filed (same
subject, sent before the desk existed) is left alone.
"""
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select

from core.admin.announce import _cta
from extensions import db
from models.content import Announcement
from models.user import User
from utils.email_layout import (
    Letter,
    paragraphs_block,
    render_letter,
    render_letter_page,
)

# The recap desk (drafts, sent rows) shipped after this moment; every
# pre-desk letter was sent before it.
DESK_STARTED = datetime(2026, 9, 24, tzinfo=UTC)


@dataclass(frozen=True, slots=True)
class PreDeskLetter:
    subject: str
    sent_at: datetime
    body: str


PRE_DESK_LETTERS = (
    PreDeskLetter(
        subject='Yee-Haw Cowboy, We Have Pandemonium in Week 1',
        sent_at=datetime(2026, 9, 8, 20, 43, 7, tzinfo=UTC),
        body=(
            'Welcome to the CFB Survivor 2026 pool, and thank you for joining. There are 32 of us, and only one can be the final survivor. Week 1 delivered more than we could have ever asked for. Let’s dive into it. As always, I like to offer my kind-hearted condolences to all the lives lost each week.\n'
            '\n'
            '- 11 lives lost on Oklahoma State (-13.5). What in tarnation were the North Texas Mean Green Cowboys doing out there? Who gave this team a preseason AP vote? They turned the ball over on downs three times. I know Oklahoma is ranked in the bottom three states for education, but they should still be able to count to four. Add in four more turnovers, and you have a perfect recipe for a butt whoopin’. Tulsa defends their turf, 24-10, and rocks this survivor league in Week 1.\n'
            '\n'
            '- 2 lives lost on Georgia Tech (-6.5). What an ending. Colorado, who was wired, fired, and inspired, scored a miraculous TD late and then got one of the best jumps off the line to block the GT game-winning FG. Starting to think this Alberto Mendoza might only be a discount Fernando. Colorado wins 14-13 on the road.\n'
            '\n'
            'Congrats to those who picked Memphis, Ole Miss, New Mexico, JMU, LSU, Auburn, and UNLV. \n'
            'Week 2 selections are now available.\n'
            'As always, any feedback on the site is appreciated.'
        ),
    ),
    PreDeskLetter(
        subject='Week 2: 2 Casualties, an Underdog, and a New Feature',
        sent_at=datetime(2026, 9, 15, 0, 52, 6, tzinfo=UTC),
        body=(
            'Picking a 5.5-point underdog in a Survivor pool is maybe bonkers, but who am I to talk when it pays off? Let’s get into Week 2.\n'
            '\n'
            'We lost two comrades for good, and four others lost their first life. There are always 0-2 victims, and I was one of them my first year. I wouldn’t wish it upon my worst enemy.\n'
            '\n'
            'Illinois (-6) claimed 3 lives. I have to admit, I did not watch a second of this game, and I am slightly bummed because it seemed like a great one. 758 yards of total offense, 1 total turnover, and 1 total punt. This was largely an offensive clinic. Illinois threw the one INT, missed a FG, and turned the ball over on downs twice, which they could not overcome. Duke wins 31-27 in Urbana-Champaign.\n'
            '\n'
            'Oklahoma (-5.5) claimed 3 lives. Not quite an offensive clinic here. I am unsure if John Mateer ever practices throwing the football. He may have forgotten to work on it in the offseason, but it was atrocious, as he went 17/33 for 189 yards, 1 TD, and 1 INT. Michigan wins in a cleaner way than last week, 17-10.\n'
            '\n'
            '30 remain. Congrats to those who picked Iowa, Texas A&M, Utah, Pitt, Alabama, Michigan, Tulane, Tennessee, and Mizzou.\n'
            '\n'
            'New Feature: The Wire!\n'
            'cccfantasy.com now installs on your phone like an app, and a new push notification feature, The Wire, is live.\n'
            '\n'
            'On iPhone\n'
            '1) Open cccfantasy.com in Safari.\n'
            '2) Tap Share (the plus icon in the center of the bottom bar) → Add to Home Screen → Add.\n'
            'The icon is the badger, labeled CCC.\n'
            '3) Open CCC from the new icon and sign in again.\n'
            '4) Tap your name → Get on the Wire → Turn on the Wire → Allow.\n'
            'You’re in.\n'
            '\n'
            'On Android\n'
            'Chrome offers Install on its own. You do not have to install anything for The Wire to work, and the notifications work right in Chrome. Install it if you want the CCC icon and badge on your home screen.\n'
            '\n'
            'There are becoming fewer and fewer excuses to autopick. Don’t let it happen.\n'
            '\n'
            'See you on the Wire.\n'
            '- The Commish'
        ),
    ),
    PreDeskLetter(
        subject='New Feature: The Wire!',
        sent_at=datetime(2026, 9, 15, 0, 52, 53, tzinfo=UTC),
        body=(
            'New Feature: The Wire!\n'
            'cccfantasy.com now installs on your phone like an app, and a new push notification feature, The Wire, is live.\n'
            '\n'
            'On iPhone\n'
            '1) Open cccfantasy.com in Safari.\n'
            '2) Tap Share (the plus icon in the center of the bottom bar) → Add to Home Screen → Add.\n'
            'The icon is the badger, labeled CCC.\n'
            '3) Open CCC from the new icon and sign in again.\n'
            '4) Tap your name → Get on the Wire → Turn on the Wire → Allow.\n'
            'You’re in.\n'
            '\n'
            'On Android\n'
            'Chrome offers Install on its own. You do not have to install anything for The Wire to work, and the notifications work right in Chrome. Install it if you want the CCC icon and badge on your home screen.\n'
            '\n'
            'There are becoming fewer and fewer excuses to autopick. Don’t let it happen.\n'
            '\n'
            'See you on the Wire.\n'
            '- The Commish'
        ),
    ),
    PreDeskLetter(
        subject='Week 3 Recap + Reminder of How This Game Works',
        sent_at=datetime(2026, 9, 23, 15, 18, 18, tzinfo=UTC),
        body=(
            'Week 3 is in the books. Two more contestants have succumbed, while four total lives were claimed this week.\n'
            '\n'
            'South Carolina (-3) eliminates the South Carolinian. \n'
            'I applaud Wicks for sticking to his guns, but he may have been unaware of gunslinger Kamario Taylor. Taylor threw for four TDs down in Columbia to keep Mississippi State undefeated on the year. Miss. State might be a team to watch out for, as they beat the Gamecocks 41-34.\n'
            '\n'
            'Virginia (-10) seizes two lives. \n'
            'The border battle between West Virginia and Virginia was a shootout, and the Mountaineers came out on top 38-27. The ACC sucks yet again, so Virginia\'s season is still alive, but the two lives are still spent.\n'
            '\n'
            'LSU (-3) costs one life. \n'
            'This game is what college football is all about. A 24-year-old QB who started his college career in 2021. A coach who demonstrates morals and prioritizes his players’ and institution’s development over his personal image and bank account. This game delivered. Ole Miss looked like they were going to run away with this game, but LSU came back and tied it. The Rebels\' fourth-quarter TD proved to be enough to outlast the Tigers 32-24.\n'
            '\n'
            'A friendly reminder: You are picking a team to win outright. The spread is displayed only as a potential tiebreaker if two or more contestants pick the national champion and have the same number of lives remaining.\n'
            '\n'
            'Week 4 picks are open. Get them in.'
        ),
    ),
)


def pre_desk_letter(entry: PreDeskLetter) -> Letter:
    """The letter as the plain-text tool built it: the subject as the
    headline, the club eyebrow, the body as plain paragraphs, the lounge
    button."""
    return Letter(
        subject=entry.subject,
        headline=entry.subject,
        eyebrow='From the Commish',
        preheader='',
        extras=[paragraphs_block(entry.body)],
        cta=_cta('lounge'),
    )


def file_pre_desk_letters() -> int:
    """File every pre-desk letter not yet on the record as a sent row;
    returns how many were filed. Sends nothing. The rows are attributed to
    the first platform admin (the Commish)."""
    from core.tribune.services import filed_week

    filed_subjects = set(db.session.scalars(
        select(Announcement.subject)
        .where(Announcement.sent_at.is_not(None),
               Announcement.sent_at < DESK_STARTED)
    ))
    missing = [e for e in PRE_DESK_LETTERS if e.subject not in filed_subjects]
    if not missing:
        return 0
    commish = db.session.scalar(
        select(User).where(User.is_admin.is_(True)).order_by(User.id).limit(1))
    if commish is None:
        raise RuntimeError('No platform admin to file the pre-desk letters under.')
    for entry in missing:
        letter = pre_desk_letter(entry)
        plain, html = render_letter(letter)
        db.session.add(Announcement(
            subject=entry.subject,
            cta='lounge',
            audiences='',
            recipient_filter='all',
            body=entry.body,
            created_by_id=commish.id,
            created_at=entry.sent_at,
            updated_at=entry.sent_at,
            sent_at=entry.sent_at,
            sent_html=html,
            sent_plain=plain,
            sent_page_html=render_letter_page(letter),
            week_number=filed_week(entry.subject, None, entry.sent_at),
        ))
    db.session.commit()
    return len(missing)
