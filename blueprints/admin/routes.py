from datetime import date, timedelta
from collections import Counter

from flask import Blueprint, render_template, request, redirect, url_for, flash

from database import get_db

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/")
def dashboard():
    conn = get_db()
    stats = {
        "total_turfs": conn.execute("SELECT COUNT(*) n FROM turfs").fetchone()["n"],
        "active_turfs": conn.execute("SELECT COUNT(*) n FROM turfs WHERE status='active'").fetchone()["n"],
        "pending_turfs": conn.execute("SELECT COUNT(*) n FROM turfs WHERE status='pending'").fetchone()["n"],
        "total_customers": conn.execute("SELECT COUNT(*) n FROM customers").fetchone()["n"],
    }
    today_iso = date.today().isoformat()
    stats["bookings_today"] = conn.execute(
        "SELECT COUNT(*) n FROM bookings WHERE booking_date=? AND status!='cancelled'", (today_iso,)
    ).fetchone()["n"]
    stats["revenue_today"] = conn.execute(
        "SELECT COALESCE(SUM(amount),0) s FROM bookings WHERE booking_date=? AND status!='cancelled'",
        (today_iso,),
    ).fetchone()["s"]
    stats["avg_rating"] = conn.execute(
        "SELECT ROUND(AVG(rating),2) a FROM turfs WHERE status='active'"
    ).fetchone()["a"] or 0

    pending_turfs = conn.execute(
        """SELECT turfs.*, managers.name as manager_name FROM turfs
           JOIN managers ON managers.id = turfs.manager_id
           WHERE turfs.status='pending'"""
    ).fetchall()

    recent_bookings = conn.execute(
        """SELECT bookings.*, turfs.name as turf_name, customers.name as customer_name
           FROM bookings
           JOIN turfs ON turfs.id = bookings.turf_id
           JOIN customers ON customers.id = bookings.customer_id
           ORDER BY bookings.created_at DESC LIMIT 8"""
    ).fetchall()

    top_turfs = conn.execute(
        """SELECT turfs.name, turfs.area, COUNT(bookings.id) n
           FROM bookings JOIN turfs ON turfs.id=bookings.turf_id
           WHERE bookings.status!='cancelled'
           GROUP BY turfs.id ORDER BY n DESC LIMIT 5"""
    ).fetchall()

    conn.close()
    return render_template("admin/dashboard.html", stats=stats, pending_turfs=pending_turfs,
                            recent_bookings=recent_bookings, top_turfs=top_turfs)


@admin_bp.route("/turfs")
def turfs():
    conn = get_db()
    status = request.args.get("status", "")
    query = """SELECT turfs.*, managers.name as manager_name,
                      (SELECT COUNT(*) FROM bookings WHERE bookings.turf_id = turfs.id) as booking_count
               FROM turfs JOIN managers ON managers.id = turfs.manager_id"""
    params = []
    if status:
        query += " WHERE turfs.status=?"
        params.append(status)
    query += " ORDER BY turfs.status='pending' DESC, turfs.name"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return render_template("admin/turfs.html", turfs=rows, status=status)


@admin_bp.route("/turfs/<int:turf_id>")
def turf_detail(turf_id):
    conn = get_db()
    turf = conn.execute(
        """SELECT turfs.*, managers.name as manager_name, managers.email as manager_email,
                  managers.phone as manager_phone
           FROM turfs JOIN managers ON managers.id = turfs.manager_id WHERE turfs.id=?""",
        (turf_id,),
    ).fetchone()
    bookings = conn.execute(
        """SELECT bookings.*, customers.name as customer_name FROM bookings
           JOIN customers ON customers.id = bookings.customer_id
           WHERE turf_id=? ORDER BY booking_date DESC LIMIT 10""",
        (turf_id,),
    ).fetchall()
    conn.close()
    return render_template("admin/turf_detail.html", turf=turf, bookings=bookings,
                            facilities=[f.strip() for f in turf["facilities"].split(",")])


@admin_bp.route("/turfs/<int:turf_id>/<action>", methods=["POST"])
def turf_action(turf_id, action):
    mapping = {"approve": "active", "reject": "suspended", "suspend": "suspended", "activate": "active"}
    conn = get_db()
    if action in mapping:
        verified = 1 if action == "approve" else None
        if verified is not None:
            conn.execute("UPDATE turfs SET status=?, verified=1 WHERE id=?", (mapping[action], turf_id))
        else:
            conn.execute("UPDATE turfs SET status=? WHERE id=?", (mapping[action], turf_id))
        conn.commit()
        flash(f"Turf {action}d.", "success")
    conn.close()
    return redirect(request.referrer or url_for("admin.turfs"))


@admin_bp.route("/customers")
def customers():
    conn = get_db()
    rows = conn.execute(
        """SELECT customers.*, COUNT(bookings.id) as booking_count,
                  COALESCE(SUM(CASE WHEN bookings.status!='cancelled' THEN bookings.amount ELSE 0 END),0) as total_spend
           FROM customers LEFT JOIN bookings ON bookings.customer_id = customers.id
           GROUP BY customers.id ORDER BY booking_count DESC"""
    ).fetchall()
    conn.close()
    return render_template("admin/customers.html", customers=rows)


@admin_bp.route("/bookings")
def bookings():
    conn = get_db()
    status = request.args.get("status", "")
    query = """SELECT bookings.*, turfs.name as turf_name, customers.name as customer_name
               FROM bookings
               JOIN turfs ON turfs.id = bookings.turf_id
               JOIN customers ON customers.id = bookings.customer_id"""
    params = []
    if status:
        query += " WHERE bookings.status=?"
        params.append(status)
    query += " ORDER BY bookings.booking_date DESC LIMIT 100"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return render_template("admin/bookings.html", bookings=rows, status=status)


@admin_bp.route("/reports")
def reports():
    conn = get_db()
    since = (date.today() - timedelta(days=13)).isoformat()
    raw = conn.execute(
        "SELECT booking_date, COUNT(*) n FROM bookings WHERE booking_date>=? AND status!='cancelled' GROUP BY booking_date",
        (since,),
    ).fetchall()
    by_day = {r["booking_date"]: r["n"] for r in raw}
    days = [(date.today() - timedelta(days=i)).isoformat() for i in range(13, -1, -1)]
    bookings_over_time = [{"date": d, "count": by_day.get(d, 0)} for d in days]

    most_booked = conn.execute(
        """SELECT turfs.name, COUNT(bookings.id) n FROM bookings
           JOIN turfs ON turfs.id = bookings.turf_id
           WHERE bookings.status != 'cancelled'
           GROUP BY turfs.id ORDER BY n DESC LIMIT 6"""
    ).fetchall()

    popular_areas = conn.execute(
        """SELECT turfs.area, COUNT(bookings.id) n FROM bookings
           JOIN turfs ON turfs.id = bookings.turf_id
           WHERE bookings.status != 'cancelled'
           GROUP BY turfs.area ORDER BY n DESC"""
    ).fetchall()

    avg_ratings = conn.execute(
        "SELECT area, ROUND(AVG(rating),2) avg_r FROM turfs WHERE status='active' GROUP BY area ORDER BY avg_r DESC"
    ).fetchall()
    conn.close()
    max_day = max([d["count"] for d in bookings_over_time] + [1])
    max_turf = max([t["n"] for t in most_booked] + [1])
    max_area = max([a["n"] for a in popular_areas] + [1])
    return render_template("admin/reports.html", bookings_over_time=bookings_over_time,
                            most_booked=most_booked, popular_areas=popular_areas,
                            avg_ratings=avg_ratings, max_day=max_day, max_turf=max_turf, max_area=max_area)


@admin_bp.route("/reviews")
def reviews():
    conn = get_db()
    rows = conn.execute(
        """SELECT reviews.*, turfs.name as turf_name, customers.name as customer_name
           FROM reviews
           JOIN turfs ON turfs.id = reviews.turf_id
           JOIN customers ON customers.id = reviews.customer_id
           ORDER BY review_date DESC LIMIT 50"""
    ).fetchall()
    conn.close()
    return render_template("admin/reviews.html", reviews=rows)


@admin_bp.route("/settings")
def settings():
    return render_template("admin/settings.html")
