"""
database.py
------------
All persistence for the TurfHub prototype lives here: schema creation,
Bangalore-flavoured mock data, and small query helper functions used by
the admin / manager / customer blueprints.

This is intentionally a single SQLite file with plain sqlite3 (no ORM)
so the whole data layer is easy to read, replace, or re-seed later.
"""

import sqlite3
import random
from datetime import date, timedelta, datetime

from config import DATABASE_PATH

# Hourly slots the platform sells, 6am to 11pm.
TIME_SLOTS = [f"{h:02d}:00 - {h+1:02d}:00" for h in range(6, 23)]

FACILITY_OPTIONS = [
    "Floodlights", "Parking", "Changing Room", "Washroom",
    "Drinking Water", "Seating", "Equipment Rental", "First Aid",
]

# Image handling: every turf gets a locally-generated photo (see
# scripts/generate_turf_images.py) named turf-01.jpg .. turf-10.jpg,
# matching turfs.id. FALLBACK_IMAGE is used in templates whenever a
# turf's `image` column is empty or the file can't be found, so the
# UI never shows a broken-image icon. GALLERY_IMAGES are the extra,
# unlabeled alternates a manager can switch their listing to.
FALLBACK_IMAGE = "placeholder.jpg"
GALLERY_IMAGES = [f"turf-gallery-{i}.jpg" for i in range(1, 5)]


def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
DROP TABLE IF EXISTS reviews;
DROP TABLE IF EXISTS blocked_slots;
DROP TABLE IF EXISTS bookings;
DROP TABLE IF EXISTS favourites;
DROP TABLE IF EXISTS turfs;
DROP TABLE IF EXISTS managers;
DROP TABLE IF EXISTS customers;

CREATE TABLE managers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL
);

CREATE TABLE customers (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT NOT NULL,
    joined_date TEXT NOT NULL
);

CREATE TABLE turfs (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    area TEXT NOT NULL,
    address TEXT NOT NULL,
    manager_id INTEGER REFERENCES managers(id),
    price_per_hour INTEGER NOT NULL,
    turf_type TEXT NOT NULL,          -- 5-a-side / 6-a-side / 7-a-side / 11-a-side
    surface_type TEXT NOT NULL,       -- Artificial Turf / Hybrid Grass / Natural Grass
    description TEXT NOT NULL,
    facilities TEXT NOT NULL,         -- comma separated
    opening_time TEXT NOT NULL,
    closing_time TEXT NOT NULL,
    rating REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',       -- active / pending / suspended
    verified INTEGER NOT NULL DEFAULT 0,
    image TEXT NOT NULL,
    phone TEXT NOT NULL,
    distance_km REAL NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE bookings (
    id INTEGER PRIMARY KEY,
    turf_id INTEGER REFERENCES turfs(id),
    customer_id INTEGER REFERENCES customers(id),
    booking_date TEXT NOT NULL,
    time_slot TEXT NOT NULL,
    players INTEGER NOT NULL,
    amount INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'confirmed',  -- confirmed / completed / cancelled
    created_at TEXT NOT NULL
);

CREATE TABLE blocked_slots (
    id INTEGER PRIMARY KEY,
    turf_id INTEGER REFERENCES turfs(id),
    block_date TEXT NOT NULL,
    time_slot TEXT NOT NULL
);

CREATE TABLE reviews (
    id INTEGER PRIMARY KEY,
    turf_id INTEGER REFERENCES turfs(id),
    customer_id INTEGER REFERENCES customers(id),
    pitch_quality INTEGER NOT NULL,
    lighting INTEGER NOT NULL,
    cleanliness INTEGER NOT NULL,
    maintenance INTEGER NOT NULL,
    facilities_rating INTEGER NOT NULL,
    value_for_money INTEGER NOT NULL,
    overall REAL NOT NULL,
    comment TEXT NOT NULL,
    review_date TEXT NOT NULL
);

CREATE TABLE favourites (
    id INTEGER PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    turf_id INTEGER REFERENCES turfs(id)
);
"""


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

MANAGERS = [
    ("Arjun Rao", "arjun.rao@turfmail.com", "9880011223"),
    ("Priya Nambiar", "priya.n@turfmail.com", "9880011224"),
    ("Suresh Gowda", "suresh.g@turfmail.com", "9880011225"),
    ("Farhan Sheikh", "farhan.s@turfmail.com", "9880011226"),
    ("Divya Shetty", "divya.s@turfmail.com", "9880011227"),
    ("Kiran Kumar", "kiran.k@turfmail.com", "9880011228"),
    ("Meera Iyer", "meera.i@turfmail.com", "9880011229"),
    ("Rohit Bhandari", "rohit.b@turfmail.com", "9880011230"),
    ("Sana Khan", "sana.k@turfmail.com", "9880011231"),
    ("Vikram Reddy", "vikram.r@turfmail.com", "9880011232"),
]

CUSTOMERS = [
    ("Rahul Verma", "rahul.verma@mail.com", "9900112233"),
    ("Ananya Pillai", "ananya.p@mail.com", "9900112234"),
    ("Karthik Subramani", "karthik.s@mail.com", "9900112235"),
    ("Neha Joshi", "neha.j@mail.com", "9900112236"),
    ("Aditya Menon", "aditya.m@mail.com", "9900112237"),
    ("Fatima Ansari", "fatima.a@mail.com", "9900112238"),
    ("Vivek Nair", "vivek.n@mail.com", "9900112239"),
    ("Sneha Kulkarni", "sneha.k@mail.com", "9900112240"),
]

# name, area, price, type, surface, facilities subset, rating, status, verified, distance
TURFS = [
    ("KickOff Arena", "HSR Layout", 1200, "7-a-side", "Artificial Turf",
     ["Floodlights", "Parking", "Changing Room", "Washroom", "Drinking Water"],
     4.6, "active", 1, 2.1),
    ("Striker's Den", "Koramangala", 1400, "6-a-side", "Artificial Turf",
     ["Floodlights", "Parking", "Seating", "Washroom", "First Aid"],
     4.5, "active", 1, 3.4),
    ("Green Pitch BTM", "BTM Layout", 900, "5-a-side", "Hybrid Grass",
     ["Floodlights", "Changing Room", "Drinking Water"],
     4.2, "active", 1, 3.8),
    ("Goal Line Turf", "Bannerghatta Road", 1000, "7-a-side", "Artificial Turf",
     ["Floodlights", "Parking", "Washroom", "Equipment Rental"],
     4.0, "active", 1, 5.6),
    ("JP Soccer Yard", "JP Nagar", 1100, "6-a-side", "Artificial Turf",
     ["Floodlights", "Parking", "Changing Room", "Seating"],
     4.3, "pending", 0, 4.9),
    ("EC Football Park", "Electronic City", 800, "5-a-side", "Artificial Turf",
     ["Floodlights", "Parking", "Drinking Water"],
     3.9, "active", 1, 9.2),
    ("Indiranagar Kickers Club", "Indiranagar", 1600, "7-a-side", "Natural Grass",
     ["Floodlights", "Parking", "Changing Room", "Washroom", "Seating", "First Aid"],
     4.7, "active", 1, 6.3),
    ("Whitefield Champions Turf", "Whitefield", 1300, "7-a-side", "Artificial Turf",
     ["Floodlights", "Parking", "Changing Room", "Equipment Rental"],
     4.4, "active", 1, 11.5),
    ("Marathahalli Matchday Ground", "Marathahalli", 950, "6-a-side", "Hybrid Grass",
     ["Floodlights", "Washroom", "Drinking Water", "Seating"],
     3.8, "pending", 0, 8.0),
    ("Sarjapur Sports Arena", "Sarjapur Road", 1150, "5-a-side", "Artificial Turf",
     ["Floodlights", "Parking", "Changing Room", "Washroom"],
     4.1, "suspended", 1, 10.4),
]

TURF_DESCRIPTIONS = {
    "KickOff Arena": "A well-maintained 7-a-side artificial turf tucked just off "
        "the main HSR Layout road, popular with weekday evening regulars.",
    "Striker's Den": "Premium turf with strong floodlighting, a favourite for "
        "corporate 6-a-side leagues in Koramangala.",
    "Green Pitch BTM": "A compact, budget-friendly hybrid grass pitch ideal for "
        "quick 5-a-side games after work.",
    "Goal Line Turf": "Spacious 7-a-side ground with easy two-wheeler and car "
        "parking, close to Bannerghatta Road.",
    "JP Soccer Yard": "Neighbourhood turf awaiting platform verification, run by "
        "a small local operator in JP Nagar.",
    "EC Football Park": "An affordable 5-a-side option for the Electronic City "
        "tech-park crowd, busiest on weekend mornings.",
    "Indiranagar Kickers Club": "Bangalore's rare natural-grass 7-a-side pitch, "
        "well-groomed with a dedicated maintenance crew.",
    "Whitefield Champions Turf": "Large 7-a-side artificial turf with equipment "
        "rental, serving the Whitefield IT corridor.",
    "Marathahalli Matchday Ground": "Newer hybrid-grass ground still building its "
        "review history, awaiting verification.",
    "Sarjapur Sports Arena": "A 5-a-side turf currently suspended while the "
        "management resolves a facilities complaint.",
}

REVIEW_COMMENTS = [
    "Great surface, ball roll was consistent all game.",
    "Lights could be a little brighter for a 9pm slot.",
    "Changing rooms were clean, would book again.",
    "Turf was a bit worn near the penalty box.",
    "Staff were helpful and check-in was quick.",
    "Best value pitch in the area for a weekday game.",
    "Parking filled up fast, arrive early.",
    "Solid pitch, minor puddling after the rain.",
]


def _rand_recent_date(days_back=30, days_fwd=3):
    offset = random.randint(-days_back, days_fwd)
    return (date.today() + timedelta(days=offset)).isoformat()


def seed_db():
    conn = get_db()
    conn.executescript(SCHEMA)

    for i, (name, email, phone) in enumerate(MANAGERS, start=1):
        conn.execute(
            "INSERT INTO managers (id, name, email, phone) VALUES (?,?,?,?)",
            (i, name, email, phone),
        )

    for i, (name, email, phone) in enumerate(CUSTOMERS, start=1):
        joined = (date.today() - timedelta(days=random.randint(20, 400))).isoformat()
        conn.execute(
            "INSERT INTO customers (id, name, email, phone, joined_date) VALUES (?,?,?,?,?)",
            (i, name, email, phone, joined),
        )

    for i, (name, area, price, ttype, surface, facilities, rating, status, verified, dist) in enumerate(TURFS, start=1):
        created = (date.today() - timedelta(days=random.randint(30, 300))).isoformat()
        conn.execute(
            """INSERT INTO turfs
               (id, name, area, address, manager_id, price_per_hour, turf_type, surface_type,
                description, facilities, opening_time, closing_time, rating, status, verified,
                image, phone, distance_km, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (i, name, area, f"{name}, {area}, Bangalore", i, price, ttype, surface,
             TURF_DESCRIPTIONS[name], ",".join(facilities), "06:00", "23:00", rating,
             status, verified, f"turf-{i:02d}.jpg", MANAGERS[i - 1][2].replace("@turfmail.com", ""),
             dist, created),
        )

    # Bookings: a healthy spread across turfs, customers and dates so
    # dashboards, "today's bookings" and reports all have something to show.
    booking_id = 1
    today_iso = date.today().isoformat()
    for turf_id in range(1, len(TURFS) + 1):
        num_bookings = random.randint(6, 12)
        for _ in range(num_bookings):
            b_date = _rand_recent_date()
            slot = random.choice(TIME_SLOTS)
            customer_id = random.randint(1, len(CUSTOMERS))
            players = random.choice([5, 6, 7, 8, 10, 12, 14])
            price = TURFS[turf_id - 1][2]
            status = random.choices(
                ["confirmed", "completed", "cancelled"], weights=[0.4, 0.5, 0.1]
            )[0]
            if b_date > today_iso:
                status = "confirmed"
            conn.execute(
                """INSERT INTO bookings
                   (id, turf_id, customer_id, booking_date, time_slot, players, amount, status, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (booking_id, turf_id, customer_id, b_date, slot, players, price, status,
                 f"{b_date}T09:00:00"),
            )
            booking_id += 1

    # Make sure "today" always has a few visible bookings for the demo.
    for turf_id in [1, 1, 2, 3, 7]:
        slot = random.choice(TIME_SLOTS)
        customer_id = random.randint(1, len(CUSTOMERS))
        price = TURFS[turf_id - 1][2]
        conn.execute(
            """INSERT INTO bookings
               (id, turf_id, customer_id, booking_date, time_slot, players, amount, status, created_at)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (booking_id, turf_id, customer_id, today_iso, slot, 10, price, "confirmed",
             f"{today_iso}T09:00:00"),
        )
        booking_id += 1

    # A couple of manager-blocked slots for the availability grid demo.
    conn.execute("INSERT INTO blocked_slots (turf_id, block_date, time_slot) VALUES (1, ?, ?)",
                 (today_iso, "13:00 - 14:00"))
    conn.execute("INSERT INTO blocked_slots (turf_id, block_date, time_slot) VALUES (1, ?, ?)",
                 (today_iso, "14:00 - 15:00"))

    # Reviews for the active, verified turfs.
    review_id = 1
    for turf_id in range(1, len(TURFS) + 1):
        if TURFS[turf_id - 1][7] != "active":
            continue
        for _ in range(random.randint(3, 6)):
            pitch, light, clean, maint, fac, value = [random.randint(3, 5) for _ in range(6)]
            overall = round((pitch + light + clean + maint + fac + value) / 6, 1)
            conn.execute(
                """INSERT INTO reviews
                   (id, turf_id, customer_id, pitch_quality, lighting, cleanliness, maintenance,
                    facilities_rating, value_for_money, overall, comment, review_date)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (review_id, turf_id, random.randint(1, len(CUSTOMERS)), pitch, light, clean,
                 maint, fac, value, overall, random.choice(REVIEW_COMMENTS), _rand_recent_date(60, -1)),
            )
            review_id += 1

    # A few favourites for the demo customer (id=1).
    for turf_id in [1, 7, 2]:
        conn.execute("INSERT INTO favourites (customer_id, turf_id) VALUES (1, ?)", (turf_id,))

    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Query helpers
# ---------------------------------------------------------------------------

def compute_slot_status(conn, turf_id, on_date):
    """Return list of (slot, status) for a turf on a given date."""
    booked = {
        row["time_slot"]
        for row in conn.execute(
            "SELECT time_slot FROM bookings WHERE turf_id=? AND booking_date=? AND status!='cancelled'",
            (turf_id, on_date),
        )
    }
    blocked = {
        row["time_slot"]
        for row in conn.execute(
            "SELECT time_slot FROM blocked_slots WHERE turf_id=? AND block_date=?",
            (turf_id, on_date),
        )
    }
    result = []
    for slot in TIME_SLOTS:
        if slot in booked:
            result.append((slot, "booked"))
        elif slot in blocked:
            result.append((slot, "blocked"))
        else:
            result.append((slot, "available"))
    return result


def turf_review_summary(conn, turf_id):
    row = conn.execute(
        """SELECT COUNT(*) as n, AVG(pitch_quality) pq, AVG(lighting) lt,
                  AVG(cleanliness) cl, AVG(maintenance) mt, AVG(facilities_rating) fc,
                  AVG(value_for_money) vf, AVG(overall) ov
           FROM reviews WHERE turf_id=?""",
        (turf_id,),
    ).fetchone()
    return row
