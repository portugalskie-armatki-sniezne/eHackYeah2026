"""replace mock users, reports, and discussions in Kraków for application demos."""

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import math
import os
from pathlib import Path
import random
import sys
import unicodedata
from uuid import UUID, uuid4

import psycopg
from psycopg import sql

import mock_data
from mock_data import CITY_OFFICE, TOPICS


EMAIL_DOMAIN = "mock.ehackyeah.pl"
# argon2 hash of the shared demo password "mock_demo_password", made with the API's pwdlib.
PASSWORD_HASH = "$argon2id$v=19$m=65536,t=3,p=4$C8q6FsWpZaniVoEJX31lrQ$JWM5uG3q1fbVayRB47gk2OZs033HC/81zuhGOqxvdQU"
PHOTO_DIR = Path(__file__).resolve().parent / "mock_photos"
GENERATED_MASTERS = 140
HISTORY_DAYS = 90
# reports about one issue lie within the API matching radius of 50 meters.
REPORT_SPREAD_M = 25
PLACE_SPREAD_M = 150
# the API matching lock, so reports created meanwhile do not join removed masters.
MATCHING_LOCK_KEY = 20260001
POINT = sql.SQL("ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography")
STATUSES = ("created", "reported", "inprogress", "finished")


@dataclass
class User:
    id: UUID
    first_name: str
    last_name: str
    email: str
    role: str
    created_at: datetime


@dataclass
class Report:
    id: UUID
    user: User
    title: str
    description: str
    longitude: float
    latitude: float
    created_at: datetime
    photo: str | None


@dataclass
class Comment:
    id: UUID
    user: User
    content: str
    created_at: datetime
    likes: list[User]


@dataclass
class Master:
    id: UUID
    topic: str
    title: str
    description: str
    longitude: float
    latitude: float
    status: str
    created_at: datetime
    edited_at: datetime
    response: str | None
    reports: list[Report] = field(default_factory=list)
    comments: list[Comment] = field(default_factory=list)


def email_name(text: str) -> str:
    # ł has no Unicode decomposition, so it is replaced before removing accents.
    text = unicodedata.normalize("NFKD", text.lower().replace("ł", "l"))
    return "".join(char for char in text if char.isascii() and char.isalnum())


def build_users(rng: random.Random, now: datetime) -> dict[str, list[User]]:
    def user(name: str, first_name: str, last_name: str, role: str) -> User:
        created_at = now - timedelta(days=rng.uniform(HISTORY_DAYS + 5, HISTORY_DAYS + 30))
        return User(uuid4(), first_name, last_name, f"{name}@{EMAIL_DOMAIN}", role, created_at)

    demo = {name: user(name, first, last, role) for name, first, last, role in mock_data.DEMO_ACCOUNTS}
    citizens = [user(f"{email_name(first)}.{email_name(last)}", first, last, "user")
                for first, last in mock_data.CITIZENS]
    return {"demo": [demo["user"]], "office": [demo["office"]], "admin": [demo["admin"]],
            "citizens": citizens}


def move(longitude: float, latitude: float, rng: random.Random, max_m: float) -> tuple[float, float]:
    """return a random point within max_m meters, accurate enough for a city."""
    distance, angle = max_m * math.sqrt(rng.random()), rng.uniform(0, 2 * math.pi)
    meters_per_degree = 111_320
    return (round(longitude + distance * math.cos(angle)
                  / (meters_per_degree * math.cos(math.radians(latitude))), 6),
            round(latitude + distance * math.sin(angle) / meters_per_degree, 6))


def generated_status(rng: random.Random, age_days: float) -> str:
    # older issues move further through the funnel.
    if age_days < 7:
        weights = (70, 30, 0, 0)
    elif age_days < 30:
        weights = (25, 40, 30, 5)
    elif age_days < 60:
        weights = (10, 25, 35, 30)
    else:
        weights = (0, 15, 30, 55)
    return rng.choices(STATUSES, weights)[0]


def new_master(rng: random.Random, now: datetime, topic_name: str, title: str, description: str,
               longitude: float, latitude: float, age_days: float, status: str) -> Master:
    topic = TOPICS[topic_name]
    created_at = now - timedelta(days=age_days)
    edited_at = created_at if status == "created" else created_at + (now - created_at) * rng.uniform(0.3, 0.9)
    response = {"inprogress": topic.in_progress_response, "finished": topic.finished_response}.get(status)
    return Master(uuid4(), topic_name, title, description, longitude, latitude, status, created_at,
                  edited_at, response)


def add_reports(rng: random.Random, now: datetime, master: Master, count: int, place: str,
                users: list[User], first_user: User | None = None) -> None:
    """add the report that created the master and later reports about the same issue."""
    topic = TOPICS[master.topic]
    authors = rng.sample([user for user in users if user is not first_user], count)
    if first_user is not None:
        authors[0] = first_user
    for index, author in enumerate(authors):
        if index == 0:
            title, description = master.title, master.description
            longitude, latitude, created_at = master.longitude, master.latitude, master.created_at
            with_photo = rng.random() < 0.8
        else:
            title = f"{rng.choice(topic.titles)}, {place}"
            description = rng.choice(topic.descriptions)
            longitude, latitude = move(master.longitude, master.latitude, rng, REPORT_SPREAD_M)
            later = min(now - master.created_at, timedelta(days=21)) * rng.random()
            created_at = master.created_at + later
            with_photo = rng.random() < 0.35
        photo = rng.choice(topic.photos) if topic.photos and with_photo else None
        master.reports.append(Report(uuid4(), author, title, description, longitude, latitude,
                                     created_at, photo))
    master.reports.sort(key=lambda report: report.created_at)


def add_comments(rng: random.Random, now: datetime, master: Master, users: dict[str, list[User]]) -> None:
    topic = TOPICS[master.topic]
    voices = users["citizens"] + users["demo"]
    pool = mock_data.ISSUE_COMMENTS if topic.category == "issue" else mock_data.IMPROVEMENT_COMMENTS
    count = min(len(pool), rng.randint(0, 3) + len(master.reports))
    for content in rng.sample(pool, count):
        created_at = master.created_at + (now - master.created_at) * rng.random()
        master.comments.append(Comment(uuid4(), rng.choice(voices), content, created_at, []))
    if master.status in mock_data.OFFICE_COMMENTS and rng.random() < 0.6:
        master.comments.append(Comment(uuid4(), users["office"][0],
                                       rng.choice(mock_data.OFFICE_COMMENTS[master.status]),
                                       master.edited_at, []))
    for comment in master.comments:
        fans = [user for user in voices if user is not comment.user]
        comment.likes = rng.sample(fans, min(len(fans), int(rng.triangular(0, 9, 1))))
    master.comments.sort(key=lambda comment: comment.created_at)


def build_masters(rng: random.Random, now: datetime, users: dict[str, list[User]]) -> list[Master]:
    citizens, demo_user = users["citizens"], users["demo"][0]
    masters = []
    for scenario in mock_data.SCENARIOS:
        master = new_master(rng, now, scenario.topic, scenario.title, scenario.description,
                            scenario.longitude, scenario.latitude, scenario.days_ago, scenario.status)
        add_reports(rng, now, master, scenario.report_count, scenario.place, citizens + [demo_user],
                    demo_user if scenario.by_demo_user else None)
        masters.append(master)

    pairs = rng.sample([(topic, place) for topic in TOPICS for place in mock_data.PLACES], GENERATED_MASTERS)
    for topic_name, (place, place_longitude, place_latitude) in pairs:
        topic = TOPICS[topic_name]
        age_days = rng.uniform(0.2, HISTORY_DAYS)
        longitude, latitude = move(place_longitude, place_latitude, rng, PLACE_SPREAD_M)
        master = new_master(rng, now, topic_name, f"{rng.choice(topic.titles)}, {place}",
                            rng.choice(topic.descriptions), longitude, latitude, age_days,
                            generated_status(rng, age_days))
        add_reports(rng, now, master, rng.choices((1, 2, 3, 4), (35, 35, 20, 10))[0], place, citizens)
        masters.append(master)

    for master in masters:
        add_comments(rng, now, master, users)
    return masters


def responsible_parties(connection: psycopg.Connection) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    """return ids of categories, statuses, and responsible parties, which earlier imports provide."""
    categories = dict(connection.execute("SELECT name, id FROM report_categories").fetchall())
    statuses = dict(connection.execute("SELECT name, id FROM master_report_statuses").fetchall())
    keys = {topic.responsible for topic in TOPICS.values()}
    parties = dict(connection.execute(
        "SELECT source_key, id FROM service_entities WHERE source_key = ANY(%s)", (list(keys),)
    ).fetchall())
    office = connection.execute(
        "SELECT id FROM local_government_offices WHERE teryt_code = %s", (CITY_OFFICE.split(":")[1],)
    ).fetchone()
    if office is not None:
        parties[CITY_OFFICE] = office[0]
    missing = sorted(keys - parties.keys()) + sorted({"issue", "improvement"} - categories.keys()) \
        + sorted(set(STATUSES) - statuses.keys())
    if missing:
        raise ValueError(f"Missing reference data, run db-seeder first: {', '.join(missing)}")
    return categories, statuses, parties


def delete_mocks(connection: psycopg.Connection) -> list[str]:
    """delete mock users and their content, return storage keys of their photos."""
    users = sql.SQL("SELECT id FROM users WHERE email LIKE %(pattern)s")
    params = {"pattern": f"%@{EMAIL_DOMAIN}"}
    storage_keys = [row[0] for row in connection.execute(sql.SQL(
        "SELECT p.storage_key FROM report_photos p JOIN reports r ON r.id = p.report_id "
        "WHERE r.user_id IN ({})"
    ).format(users), params)]
    masters = [row[0] for row in connection.execute(sql.SQL(
        "SELECT DISTINCT master_report_id FROM reports WHERE user_id IN ({}) AND master_report_id IS NOT NULL"
    ).format(users), params)]
    for statement in (
        "DELETE FROM master_report_comment_likes WHERE user_id IN ({})",
        "DELETE FROM master_report_comments WHERE user_id IN ({})",
        "DELETE FROM reports WHERE user_id IN ({})",
    ):
        connection.execute(sql.SQL(statement).format(users), params)
    # masters keep reports of real users, the others go with their comments.
    connection.execute(
        "DELETE FROM master_reports m WHERE m.id = ANY(%s) "
        "AND NOT EXISTS (SELECT 1 FROM reports r WHERE r.master_report_id = m.id)", (masters,)
    )
    connection.execute(sql.SQL("DELETE FROM users WHERE id IN ({})").format(users), params)
    return storage_keys


def delete_reports(connection: psycopg.Connection) -> list[str]:
    """delete every remaining report with its master, return storage keys of their photos."""
    storage_keys = [row[0] for row in connection.execute("SELECT storage_key FROM report_photos")]
    # reports reference their master with RESTRICT, while photos, comments, and likes go with cascades.
    connection.execute("DELETE FROM reports")
    connection.execute("DELETE FROM master_reports")
    return storage_keys


def insert_mocks(connection: psycopg.Connection, users: list[User], masters: list[Master],
                 parties: tuple[dict[str, int], dict[str, int], dict[str, int]]) -> list[tuple[str, str]]:
    """insert users and masters, return storage keys and source files of report photos."""
    categories, statuses, responsible = parties
    photos = []
    with connection.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO users (id, first_name, last_name, email, password_hash, role, edited_at, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            [(user.id, user.first_name, user.last_name, user.email, PASSWORD_HASH, user.role,
              user.created_at, user.created_at) for user in users],
        )
        for master in masters:
            topic = TOPICS[master.topic]
            party = responsible[topic.responsible] if master.status != "created" else None
            is_office = topic.responsible == CITY_OFFICE
            cursor.execute(sql.SQL(
                "INSERT INTO master_reports (id, report_category_id, status_id, responsible_office_id, "
                "responsible_service_entity_id, title, description, location, response, edited_at, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, {}, %s, %s, %s)"
            ).format(POINT), (
                master.id, categories[topic.category], statuses[master.status],
                party if is_office else None, None if is_office else party, master.title, master.description,
                master.longitude, master.latitude, master.response, master.edited_at, master.created_at,
            ))
            cursor.executemany(sql.SQL(
                "INSERT INTO reports (id, user_id, master_report_id, report_category_id, title, description, "
                "location, edited_at, created_at) VALUES (%s, %s, %s, %s, %s, %s, {}, %s, %s)"
            ).format(POINT), [
                (report.id, report.user.id, master.id, categories[topic.category], report.title,
                 report.description, report.longitude, report.latitude, report.created_at, report.created_at)
                for report in master.reports
            ])
            for report in master.reports:
                if report.photo is not None:
                    photo_id = uuid4()
                    storage_key = f"reports/{report.id}/{photo_id}.{report.photo.rsplit('.', 1)[-1]}"
                    cursor.execute(
                        "INSERT INTO report_photos (id, report_id, storage_key, created_at) VALUES (%s, %s, %s, %s)",
                        (photo_id, report.id, storage_key, report.created_at),
                    )
                    photos.append((storage_key, report.photo))
            cursor.executemany(
                "INSERT INTO master_report_comments (id, master_report_id, user_id, content, created_at) "
                "VALUES (%s, %s, %s, %s, %s)",
                [(comment.id, master.id, comment.user.id, comment.content, comment.created_at)
                 for comment in master.comments],
            )
            cursor.executemany(
                "INSERT INTO master_report_comment_likes (comment_id, user_id, created_at) VALUES (%s, %s, %s)",
                [(comment.id, fan.id, comment.created_at) for comment in master.comments for fan in comment.likes],
            )
    return photos


def give_to_owner(path: Path, upload_dir: Path) -> None:
    # as root in a container, new files get the owner of the directory above the upload directory.
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        owner = upload_dir.parent.stat()
        os.chown(path, owner.st_uid, owner.st_gid)


def make_dir(path: Path, upload_dir: Path) -> None:
    if not path.is_dir():
        path.mkdir()
        give_to_owner(path, upload_dir)


def save_photos(upload_dir: Path, photos: list[tuple[str, str]], saved: list[Path]) -> None:
    make_dir(upload_dir, upload_dir)
    make_dir(upload_dir / "reports", upload_dir)
    for storage_key, source in photos:
        path = upload_dir / storage_key
        make_dir(path.parent, upload_dir)
        saved.append(path)
        path.write_bytes((PHOTO_DIR / source).read_bytes())
        give_to_owner(path, upload_dir)


def delete_photos(paths: list[Path]) -> None:
    for path in paths:
        path.unlink(missing_ok=True)
        try:
            path.parent.rmdir()
        except OSError:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upload_dir", type=Path, help="the API UPLOAD_DIR, for example apps/api/uploads")
    parser.add_argument("--seed", type=int, default=2026, help="random seed of generated content")
    parser.add_argument("--replace-all", action="store_true",
                        help="also delete the reports of real users, leaving only the mock data")
    args = parser.parse_args()

    rng, now = random.Random(args.seed), datetime.now(timezone.utc)
    user_groups = build_users(rng, now)
    users = [user for group in user_groups.values() for user in group]
    masters = build_masters(rng, now, user_groups)
    saved: list[Path] = []
    try:
        missing = sorted({photo for topic in TOPICS.values() for photo in topic.photos
                          if not (PHOTO_DIR / photo).is_file()})
        if missing:
            raise ValueError(f"Missing mock photos: {', '.join(missing)}")
        if not args.upload_dir.parent.is_dir():
            raise ValueError(f"Parent of the upload directory does not exist: {args.upload_dir.parent}")
        with psycopg.connect(connect_timeout=10) as connection, connection.transaction():
            connection.execute("SELECT pg_advisory_xact_lock(%s)", (MATCHING_LOCK_KEY,))
            parties = responsible_parties(connection)
            old_photos = delete_mocks(connection)
            # the mock users go first, so only the reports of real users are left to delete.
            if args.replace_all:
                old_photos += delete_reports(connection)
            photos = insert_mocks(connection, users, masters, parties)
            save_photos(args.upload_dir, photos, saved)
    except (OSError, ValueError) as error:
        delete_photos(saved)
        print(f"Mock import failed: {error}", file=sys.stderr)
        return 1
    except psycopg.Error as error:
        delete_photos(saved)
        print(f"Mock import failed: database error ({error.sqlstate or 'connection failure'})", file=sys.stderr)
        return 1
    # old files go only after the commit, so a failed run keeps the previous photos.
    delete_photos([args.upload_dir / storage_key for storage_key in old_photos])

    reports = [report for master in masters for report in master.reports]
    comments = [comment for master in masters for comment in master.comments]
    print(f"Imported {len(users)} mock users, {len(masters)} master reports, {len(reports)} reports, "
          f"{len(photos)} photos, {len(comments)} comments, and "
          f"{sum(len(comment.likes) for comment in comments)} likes.")
    print(f"Demo accounts: user@, office@, and admin@{EMAIL_DOMAIN} with the password mock_demo_password.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
