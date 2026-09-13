from datetime import date, timedelta

from flask import Blueprint, render_template, request, redirect, url_for, flash

from database import get_db, compute_slot_status, turf_review_summary, TIME_SLOTS, FACILITY_OPTIONS

customer_bp = Blueprint("customer", __name__)


CURRENT_CUSTOMER_ID = 1


def _turf_facilities(row):
    return [f.strip() for f in row["facilities"].split(",") if f.strip()]


@customer_bp.route("/")
def home():
    conn = get_db()
    featured = conn.execute(
        "SELECT * FROM turfs WHERE status='active' ORDER BY rating DESC LIMIT 6"
    ).fetchall()
    areas = [r["area"] for r in conn.execute("SELECT DISTINCT area FROM turfs ORDER BY area")]
    conn.close()
    return render_template("customer/home.html", featured=featured, areas=areas,
                            facilities_list=_prep(featured))


def _prep(rows):
    return {row["id"]: _turf_facilities(row) for row in rows}


@customer_bp.route("/find")
def find():
    conn = get_db()
    area = request.args.get("area", "")
    turf_type = request.args.get("turf_type", "")
    facility = request.args.get("facility", "")
    price_max = request.args.get("price_max", "")
    rating_min = request.args.get("rating_min", "")
    sort = request.args.get("sort", "rating")
    q_date = request.args.get("date", date.today().isoformat())

    query = "SELECT * FROM turfs WHERE status='active'"
    params = []
    if area:
        query += " AND area=?"
        params.append(area)
    if turf_type:
        query += " AND turf_type=?"
        params.append(turf_type)
    if facility:
        query += " AND facilities LIKE ?"
        params.append(f"%{facility}%")
    if price_max:
        query += " AND price_per_hour<=?"
        params.append(price_max)
    if rating_min:
        query += " AND rating>=?"
        params.append(rating_min)

    sort_map = {
        "rating": "rating DESC",
        "price_low": "price_per_hour ASC",
        "price_high": "price_per_hour DESC",
        "distance": "distance_km ASC",
    }
    query += f" ORDER BY {sort_map.get(sort, 'rating DESC')}"

    turfs = conn.execute(query, params).fetchall()
    areas = [r["area"] for r in conn.execute("SELECT DISTINCT area FROM turfs ORDER BY area")]
    turf_types = [r["turf_type"] for r in conn.execute("SELECT DISTINCT turf_type FROM turfs")]
    conn.close()

    return render_template(
        "customer/find.html", turfs=turfs, areas=areas, turf_types=turf_types,
        facility_options=FACILITY_OPTIONS, facilities_list=_prep(turfs),
        filters=dict(area=area, turf_type=turf_type, facility=facility,
                     price_max=price_max, rating_min=rating_min, sort=sort, date=q_date),
    )


@customer_bp.route("/compare")
def compare():
    ids = request.args.get("ids", "")
    id_list = [int(i) for i in ids.split(",") if i.strip().isdigit()][:3]
    conn = get_db()
    turfs = []
    if id_list:
        placeholders = ",".join("?" * len(id_list))
        turfs = conn.execute(f"SELECT * FROM turfs WHERE id IN ({placeholders})", id_list).fetchall()
    all_active = conn.execute("SELECT id, name, area FROM turfs WHERE status='active' ORDER BY name").fetchall()
    conn.close()
    return render_template("customer/compare.html", turfs=turfs, facilities_list=_prep(turfs),
                            all_active=all_active, selected_ids=id_list)


@customer_bp.route("/turf/<int:turf_id>")
def turf_detail(turf_id):
    conn = get_db()
    turf = conn.execute("SELECT * FROM turfs WHERE id=?", (turf_id,)).fetchone()
    if not turf:
        conn.close()
        return render_template("404.html"), 404
    manager = conn.execute("SELECT * FROM managers WHERE id=?", (turf["manager_id"],)).fetchone()
    q_date = request.args.get("date", date.today().isoformat())
    slots = compute_slot_status(conn, turf_id, q_date)
    reviews = conn.execute(
        """SELECT reviews.*, customers.name as customer_name FROM reviews
           JOIN customers ON customers.id = reviews.customer_id
           WHERE turf_id=? ORDER BY review_date DESC LIMIT 10""",
        (turf_id,),
    ).fetchall()
    summary = turf_review_summary(conn, turf_id)
    is_favourite = conn.execute(
        "SELECT 1 FROM favourites WHERE customer_id=? AND turf_id=?",
        (CURRENT_CUSTOMER_ID, turf_id),
    ).fetchone() is not None
    conn.close()

    next_7_days = [(date.today() + timedelta(days=i)).isoformat() for i in range(7)]

    return render_template(
        "customer/turf_detail.html", turf=turf, manager=manager, slots=slots,
        selected_date=q_date, next_7_days=next_7_days, reviews=reviews, summary=summary,
        facilities=_turf_facilities(turf), is_favourite=is_favourite,
    )


@customer_bp.route("/book/<int:turf_id>", methods=["GET", "POST"])
def book(turf_id):
    conn = get_db()
    turf = conn.execute("SELECT * FROM turfs WHERE id=?", (turf_id,)).fetchone()
    if not turf:
        conn.close()
        return render_template("404.html"), 404

    if request.method == "POST":
        b_date = request.form["date"]
        slot = request.form["time_slot"]
        players = int(request.form.get("players", 10))

        already = conn.execute(
            "SELECT 1 FROM bookings WHERE turf_id=? AND booking_date=? AND time_slot=? AND status!='cancelled'",
            (turf_id, b_date, slot),
        ).fetchone()
        blocked = conn.execute(
            "SELECT 1 FROM blocked_slots WHERE turf_id=? AND block_date=? AND time_slot=?",
            (turf_id, b_date, slot),
        ).fetchone()
        if already or blocked:
            flash("That slot was just taken — please pick another.", "error")
            conn.close()
            return redirect(url_for("customer.turf_detail", turf_id=turf_id, date=b_date))

        cur = conn.execute(
            """INSERT INTO bookings (turf_id, customer_id, booking_date, time_slot, players, amount, status, created_at)
               VALUES (?,?,?,?,?,?, 'confirmed', datetime('now'))""",
            (turf_id, CURRENT_CUSTOMER_ID, b_date, slot, players, turf["price_per_hour"]),
        )
        conn.commit()
        booking_id = cur.lastrowid
        conn.close()
        return redirect(url_for("customer.confirmation", booking_id=booking_id))

    q_date = request.args.get("date", date.today().isoformat())
    slot = request.args.get("slot", "")
    conn.close()
    return render_template("customer/booking.html", turf=turf, q_date=q_date, slot=slot)


@customer_bp.route("/booking/confirmation/<int:booking_id>")
def confirmation(booking_id):
    conn = get_db()
    booking = conn.execute(
        """SELECT bookings.*, turfs.name as turf_name, turfs.area, turfs.address, turfs.image
           FROM bookings JOIN turfs ON turfs.id = bookings.turf_id WHERE bookings.id=?""",
        (booking_id,),
    ).fetchone()
    conn.close()
    return render_template("customer/confirmation.html", booking=booking)


@customer_bp.route("/my-bookings")
def my_bookings():
    conn = get_db()
    bookings = conn.execute(
        """SELECT bookings.*, turfs.name as turf_name, turfs.area, turfs.image
           FROM bookings JOIN turfs ON turfs.id = bookings.turf_id
           WHERE customer_id=? ORDER BY booking_date DESC""",
        (CURRENT_CUSTOMER_ID,),
    ).fetchall()
    conn.close()
    today_iso = date.today().isoformat()
    upcoming = [b for b in bookings if b["booking_date"] >= today_iso and b["status"] == "confirmed"]
    past = [b for b in bookings if not (b["booking_date"] >= today_iso and b["status"] == "confirmed")]
    return render_template("customer/my_bookings.html", upcoming=upcoming, past=past)


@customer_bp.route("/booking/<int:booking_id>/cancel", methods=["POST"])
def cancel_booking(booking_id):
    conn = get_db()
    conn.execute("UPDATE bookings SET status='cancelled' WHERE id=?", (booking_id,))
    conn.commit()
    conn.close()
    flash("Booking cancelled.", "success")
    return redirect(url_for("customer.my_bookings"))


@customer_bp.route("/favourites")
def favourites():
    conn = get_db()
    turfs = conn.execute(
        """SELECT turfs.* FROM favourites JOIN turfs ON turfs.id = favourites.turf_id
           WHERE favourites.customer_id=?""",
        (CURRENT_CUSTOMER_ID,),
    ).fetchall()
    conn.close()
    return render_template("customer/favourites.html", turfs=turfs, facilities_list=_prep(turfs))


@customer_bp.route("/favourites/toggle/<int:turf_id>", methods=["POST"])
def toggle_favourite(turf_id):
    conn = get_db()
    existing = conn.execute(
        "SELECT id FROM favourites WHERE customer_id=? AND turf_id=?",
        (CURRENT_CUSTOMER_ID, turf_id),
    ).fetchone()
    if existing:
        conn.execute("DELETE FROM favourites WHERE id=?", (existing["id"],))
        flash("Removed from favourites.", "success")
    else:
        conn.execute("INSERT INTO favourites (customer_id, turf_id) VALUES (?,?)",
                     (CURRENT_CUSTOMER_ID, turf_id))
        flash("Added to favourites.", "success")
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for("customer.home"))


@customer_bp.route("/profile")
def profile():
    conn = get_db()
    customer = conn.execute("SELECT * FROM customers WHERE id=?", (CURRENT_CUSTOMER_ID,)).fetchone()
    total_bookings = conn.execute(
        "SELECT COUNT(*) n FROM bookings WHERE customer_id=?", (CURRENT_CUSTOMER_ID,)
    ).fetchone()["n"]
    conn.close()
    return render_template("customer/profile.html", customer=customer, total_bookings=total_bookings)
