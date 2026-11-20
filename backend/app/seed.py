"""Bundled demo data: one clearly-labelled sample lecture so the app is explorable
before any YouTube URL is pasted.

The transcript below is ORAYA-authored demo content (not fetched from YouTube) and is
marked source="sample" in the database and in the UI.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Lecture, Topic, User
from .security import hash_password
from .services import transcript as transcript_svc
from .services.lecture_service import store_segments

DEMO_EMAIL = "demo@oraya.app"
DEMO_PASSWORD = "oraya-demo-1"

_SAMPLE_TITLE = "Forces and Newton's Laws — sample lecture"
_SAMPLE_CHANNEL = "ORAYA Sample"

# (start, end, text) — 10s cadence
_SAMPLE: list[tuple[float, float, str]] = [
    (0, 10, "Welcome back. Today we are looking at forces and how they change the motion of objects."),
    (10, 20, "A force is a push or a pull exerted on an object, and it is measured in newtons."),
    (20, 30, "Remember that forces are vectors, which means they have both a magnitude and a direction."),
    (30, 40, "When several forces act on the same object, we add them as vectors to get the net force."),
    (40, 50, "The net force is what actually determines the acceleration of the object."),
    (50, 60, "Newton's first law says that an object at rest stays at rest unless a net force acts on it."),
    (60, 70, "The same law says that a moving object keeps moving at a constant velocity without a net force."),
    (70, 80, "This tendency to resist a change in motion is called inertia, and it depends on mass."),
    (80, 90, "Now we reach Newton's second law, which is written as F equals m times a."),
    (90, 100, "In that equation, F is the net force in newtons, m is the mass in kilograms, and a is acceleration."),
    (100, 110, "So if you double the net force on an object, its acceleration doubles as well."),
    (110, 120, "And if you double the mass while keeping the force constant, the acceleration is halved."),
    (120, 130, "Let's work through an example. A cart of mass 4 kilograms is pushed with a net force of 12 newtons."),
    (130, 140, "Using F equals m times a, the acceleration is 12 divided by 4, which is 3 metres per second squared."),
    (140, 150, "Notice that we always use the net force, not just one of the forces acting on the cart."),
    (150, 160, "If a friction force of 4 newtons opposed the push, the net force would be 8 newtons instead."),
    (160, 170, "In that case the acceleration would be 8 divided by 4, giving 2 metres per second squared."),
    (170, 180, "Newton's third law says that every action has an equal and opposite reaction."),
    (180, 190, "That means if the ground pushes up on you with a normal force, you push down on the ground equally."),
    (190, 200, "The action and reaction pair never cancel each other, because they act on different objects."),
    (200, 210, "Weight is a good example. Gravity pulls down on you, and you pull up on the Earth."),
    (210, 220, "Your weight is your mass times the acceleration due to gravity, about 9.8 metres per second squared."),
    (220, 230, "Mass stays the same everywhere, but your weight would change on the Moon."),
    (230, 240, "On the Moon the gravitational acceleration is about 1.6 metres per second squared."),
    (240, 250, "So a 60 kilogram student weighs about 588 newtons on Earth and about 96 newtons on the Moon."),
    (250, 260, "Friction is another force we meet daily, and it always acts opposite to the direction of motion."),
    (260, 270, "Static friction holds an object in place, while kinetic friction slows a sliding object down."),
    (270, 280, "The force of friction equals the coefficient of friction times the normal force."),
    (280, 290, "A rough surface has a larger coefficient of friction than a smooth polished surface."),
    (290, 300, "When you sketch a free body diagram, you draw the object and every force acting on it."),
    (300, 310, "Label each force with its direction, then resolve the forces into components if needed."),
    (310, 320, "Free body diagrams are the single most useful tool for solving force problems."),
    (320, 330, "To summarise: forces are vectors, the net force sets the acceleration, and forces come in pairs."),
    (330, 340, "Next time we will apply these ideas to projectiles and circular motion. Thanks for watching."),
]


def seed_demo_data(db: Session) -> None:
    user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
    if user is None:
        user = User(
            email=DEMO_EMAIL,
            password_hash=hash_password(DEMO_PASSWORD),
            name="Demo Student",
            grade="Grade 11",
            language="English",
            subjects=["Physics"],
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    existing = db.scalar(select(Lecture).where(Lecture.user_id == user.id, Lecture.source == "sample"))
    if existing is not None:
        return

    lecture = Lecture(
        user_id=user.id,
        video_id="",
        url="",
        title=_SAMPLE_TITLE,
        channel=_SAMPLE_CHANNEL,
        thumbnail="",
        duration=_SAMPLE[-1][1],
        source="sample",
        transcript_status="missing",
    )
    db.add(lecture)
    db.commit()
    db.refresh(lecture)

    parsed = [transcript_svc.ParsedSegment(s, e, t) for s, e, t in _SAMPLE]
    store_segments(db, lecture, parsed, source="sample")
