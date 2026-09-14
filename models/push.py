"""
Fantasy Sports Platform - Web Push Subscription Model
======================================================
One row per (member, device). A browser hands us a push *subscription* — an
endpoint URL at the member's push service plus two crypto keys — when they tap
"Turn on the buzz" on /app. We store it against the User and send Web Push to it
from the same systemd timers that send email (utils/push.py). Push is additive:
a dead token here can never cost a member an email.

    OWNERSHIP-FOLLOWING UPSERT (shared-device leak guard)
    -----------------------------------------------------
    The browser returns the SAME endpoint for the installed app no matter who is
    logged in. If member A subscribes on a shared iPad, then A logs out (GET
    /logout) and B logs in and opens the app, B's upsert must NOT inherit A's
    verdict pushes. So an incoming (user, endpoint) re-points the endpoint's row
    to the current user and deletes any row with that endpoint under anyone else.

        incoming (user=B, endpoint=E)
          ├── row(E) exists under A  → delete it, then insert/point to B
          ├── row(E) exists under B  → touch last_seen_at
          └── no row(E)              → insert under B

    EVICTION (cap 5 per user, oldest last_seen_at first)
    ----------------------------------------------------
    A member with 6 devices is a member who replaced phones; the stalest row is
    the one to drop. Insert past the cap evicts the oldest last_seen_at BEFORE
    the insert so the cap is never exceeded even for one statement.
"""
from datetime import UTC, datetime

from extensions import db

# Per-member device cap. Insert past this evicts the oldest last_seen_at.
MAX_DEVICES_PER_USER = 5


class PushSubscription(db.Model):
    """A single browser push subscription owned by one member."""
    __tablename__ = 'push_subscription'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'),
                        nullable=False, index=True)
    # The push-service delivery URL. Unique across the platform: one physical
    # device has one endpoint, and it belongs to whoever most recently armed it.
    endpoint = db.Column(db.String(512), unique=True, nullable=False)
    # ECDH public key + auth secret the push service needs to encrypt to.
    p256dh = db.Column(db.String(255), nullable=False)
    auth = db.Column(db.String(255), nullable=False)
    user_agent = db.Column(db.String(400), nullable=True)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    # Bumped on every app open (upsert). Also the eviction key.
    last_seen_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

    user = db.relationship('User', backref=db.backref('push_subscriptions',
                                                      lazy='dynamic'))

    @classmethod
    def upsert(cls, user_id, endpoint, p256dh, auth, user_agent=None):
        """Ownership-following upsert (see module diagram). Idempotent.

        Adds the row to the session and flushes; the CALLER commits. Never
        commits on its own so it composes inside a request handler.
        """
        now = datetime.now(UTC)
        existing = db.session.scalar(
            db.select(cls).filter_by(endpoint=endpoint))
        if existing is not None:
            if existing.user_id != user_id:
                # Re-point a shared device to the member using it right now.
                existing.user_id = user_id
            existing.p256dh = p256dh
            existing.auth = auth
            existing.user_agent = user_agent
            existing.last_seen_at = now
            db.session.flush()
            return existing

        cls._evict_over_cap(user_id)
        row = cls(user_id=user_id, endpoint=endpoint, p256dh=p256dh,
                  auth=auth, user_agent=user_agent,
                  created_at=now, last_seen_at=now)
        db.session.add(row)
        db.session.flush()
        return row

    @classmethod
    def _evict_over_cap(cls, user_id):
        """Delete oldest-seen rows so a subsequent insert stays within the cap."""
        rows = db.session.scalars(
            db.select(cls).filter_by(user_id=user_id)
            .order_by(cls.last_seen_at.asc())
        ).all()
        # Leave room for the one about to be inserted.
        overflow = len(rows) - (MAX_DEVICES_PER_USER - 1)
        for row in rows[:max(0, overflow)]:
            db.session.delete(row)

    def __repr__(self):
        return f'<PushSubscription user={self.user_id} id={self.id}>'
