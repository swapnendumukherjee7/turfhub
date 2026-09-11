from datetime import date, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash

from database import get_db, compute_slot_status, turf_review_summary, TIME_SLOTS, FACILITY_OPTIONS, GALLERY_IMAGES

manager_bp = Blueprint("manager", __name__)

# No real auth in this prototype — the logged-in manager always manages this turf.
CURRENT_TURF_ID = 1


@manager_bp.route("/")
def dashboard():
    conn = get_db()
    turf = conn.execute("SELECT * FROM turfs WHERE id=?", (CURRENT_TURF_ID,)).fetchone()
    today_iso = date.today().isoformat()

    today_bookings = conn.execute(
        """SELECT bookings.*, customers.name as customer_name FROM bookings
           JOIN customers ON customers.id = bookings.customer_id
           WHERE turf_id=? AND booking_date=? AND status!='cancelled'
           ORDER BY time_slot""",
        (CURRENT_TURF_ID, today_iso),
    ).fetchall()

    upcoming_bookings = conn.execute(
        """SELECT bookings.*, customers.name as customer_name FROM bookings
           JOIN customers ON customers.id = bookings.customer_id
           WHERE turf_id=? AND booking_date>? AND status!='cancelled'
           ORDER BY booking_date LIMIT 8""",
        (CURRENT_TURF_ID, today_iso),
    ).fetchall()

    revenue_today = conn.execute(
        "SELECT COALESCE(SUM(amount),0) s FROM bookings WHERE turf_id=? AND booking_date=? AND status!='cancelled'",
        (CURRENT_TURF_ID, today_iso),
    ).fetchone()["s"]

    booked_count = len(compute_slot_status(conn, CURRENT_TURF_ID, today_iso))
    booked_today = sum(1 for _, s in compute_slot_status(conn, CURRENT_TURF_ID, today_iso) if s == "booked")
    occupancy = round((booked_today / len(TIME_SLOTS)) * 100) if TIME_SLOTS else 0

    recent_reviews = conn.execute(
        """SELECT reviews.*, customers.name as customer_name FROM reviews
           JOIN customers ON customers.id = reviews.customer_id
           WHERE turf_id=? ORDER BY review_date DESC LIMIT 4""",
        (CURRENT_TURF_ID,),
    ).fetchall()
    summary = turf_review_summary(conn, CURRENT_TURF_ID)
    conn.close()

    return render_template("manager/dashboard.html", turf=turf, today_bookings=today_bookings,
                            upcoming_bookings=upcoming_bookings, revenue_today=revenue_today,
                            occupancy=occupancy, recent_reviews=recent_reviews, summary=summary)


@manager_bp.route("/profile", methods=["GET", "POST"])
def profile():
    conn = get_db()
    turf = conn.execute("SELECT * FROM turfs WHERE id=?", (CURRENT_TURF_ID,)).fetchone()
    own_image = f"turf-{CURRENT_TURF_ID:02d}.jpg"
    allowed_images = set(GALLERY_IMAGES) | {own_image}

    if request.method == "POST":
        facilities = request.form.getlist("facilities")
        image = request.form.get("image", turf["image"])
        if image not in allowed_images:
            image = turf["image"]
        conn.execute(
            """UPDATE turfs SET name=?, area=?, address=?, description=?, turf_type=?, surface_type=?,
                      price_per_hour=?, facilities=?, opening_time=?, closing_time=?, phone=?, image=?
               WHERE id=?""",
            (request.form["name"], request.form["area"], request.form["address"],
             request.form["description"], request.form["turf_type"], request.form["surface_type"],
             request.form["price_per_hour"], ",".join(facilities), request.form["opening_time"],
             request.form["closing_time"], request.form["phone"], image, CURRENT_TURF_ID),
        )
        conn.commit()
        conn.close()
        flash("Turf profile updated.", "success")
        return redirect(url_for("manager.profile"))

    current_facilities = [f.strip() for f in turf["facilities"].split(",")]
    gallery_choices = [own_image] + GALLERY_IMAGES
    conn.close()
    return render_template("manager/profile.html", turf=turf, facility_options=FACILITY_OPTIONS,
                            current_facilities=current_facilities, gallery_choices=gallery_choices)


@manager_bp.route("/availability", methods=["GET", "POST"])
def availability():
    conn = get_db()
    q_date = request.args.get("date", date.today().isoformat())

    if request.method == "POST":
        slot = request.form["time_slot"]
        b_date = request.form["date"]
        action = request.form["action"]
        if action == "block":
            exists = conn.execute(
                "SELECT 1 FROM blocked_slots WHERE turf_id=? AND block_date=? AND time_slot=?",
                (CURRENT_TURF_ID, b_date, slot),
            ).fetchone()
            if not exists:
                conn.execute("INSERT INTO blocked_slots (turf_id, block_date, time_slot) VALUES (?,?,?)",
                             (CURRENT_TURF_ID, b_date, slot))
                conn.commit()
                flash(f"Blocked {slot} on {b_date}.", "success")
        elif action == "unblock":
            conn.execute(
                "DELETE FROM blocked_slots WHERE turf_id=? AND block_date=? AND time_slot=?",
                (CURRENT_TURF_ID, b_date, slot),
            )
            conn.commit()
            flash(f"Reopened {slot} on {b_date}.", "success")
        conn.close()
        return redirect(url_for("manager.availability", date=b_date))

    slots = compute_slot_status(conn, CURRENT_TURF_ID, q_date)
    bookings_by_slot = {
        row["time_slot"]: row["customer_name"]
        for row in conn.execute(
            """SELECT bookings.time_slot, customers.name as customer_name FROM bookings
               JOIN customers ON customers.id=bookings.customer_id
               WHERE turf_id=? AND booking_date=? AND status!='cancelled'""",
            (CURRENT_TURF_ID, q_date),
        )
    }
    conn.close()
    morning = [(s, st) for s, st in slots if int(s[:2]) < 15]
    evening = [(s, st) for s, st in slots if int(s[:2]) >= 15]
    next_7_days = [(date.today() + timedelta(days=i)).isoformat() for i in range(7)]
    return render_template("manager/availability.html", morning=morning, evening=evening,
                            q_date=q_date, next_7_days=next_7_days, bookings_by_slot=bookings_by_slot)


@manager_bp.route("/bookings")
def bookings():
    conn = get_db()
    status = request.args.get("status", "")
    query = """SELECT bookings.*, customers.name as customer_name, customers.phone as customer_phone
               FROM bookings JOIN customers ON customers.id = bookings.customer_id
               WHERE turf_id=?"""
    params = [CURRENT_TURF_ID]
    if status:
        query += " AND status=?"
        params.append(status)
    query += " ORDER BY booking_date DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return render_template("manager/bookings.html", bookings=rows, status=status)


@manager_bp.route("/reviews")
def reviews():
    conn = get_db()
    rows = conn.execute(
        """SELECT reviews.*, customers.name as customer_name FROM reviews
           JOIN customers ON customers.id = reviews.customer_id
           WHERE turf_id=? ORDER BY review_date DESC""",
        (CURRENT_TURF_ID,),
    ).fetchall()
    summary = turf_review_summary(conn, CURRENT_TURF_ID)
    conn.close()
    return render_template("manager/reviews.html", reviews=rows, summary=summary)
