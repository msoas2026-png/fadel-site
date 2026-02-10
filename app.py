import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.utils import secure_filename
import db

app = Flask(__name__)
app.secret_key = "change-this-secret"

SITE_NAME = "مجمع فاضل البديري"
UPLOAD_DIR = os.path.join(app.root_path, "static", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ---------- Helpers ----------
def admin_required():
    return session.get("admin_logged_in") is True


def user_required():
    return session.get("user_logged_in") is True


def current_admin_id():
    return session.get("admin_id")


def current_user_id():
    return session.get("user_id")


# ---------- Init DB + seed super admin ----------
def bootstrap():
    db.init_db()
    con = db.connect()
    row = con.execute("SELECT id FROM admins WHERE email=?", ("admin@example.com",)).fetchone()
    if not row:
        con.execute(
            "INSERT INTO admins(email, password, role) VALUES (?,?,?)",
            ("admin@example.com", "123456", "super")
        )
        con.commit()
    con.close()


bootstrap()


# ---------- Admin Auth ----------
@app.get("/admin/login")
def admin_login():
    return render_template("admin_login.html", site_name=SITE_NAME)


@app.post("/admin/login")
def admin_login_post():
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "").strip()

    con = db.connect()
    row = con.execute("SELECT * FROM admins WHERE email=?", (email,)).fetchone()
    con.close()

    if row and row["password"] == password:
        session["admin_logged_in"] = True
        session["admin_id"] = row["id"]
        session["admin_role"] = row["role"]
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_login.html", site_name=SITE_NAME, error="بيانات الدخول غير صحيحة")


@app.get("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


# ---------- Admin Dashboard ----------
@app.get("/admin")
def admin_dashboard():
    if not admin_required():
        return redirect(url_for("admin_login"))

    con = db.connect()
    tech_count = con.execute("SELECT COUNT(*) c FROM technicians").fetchone()["c"]
    gifts_available = con.execute("SELECT COUNT(*) c FROM gifts WHERE is_active=1").fetchone()["c"]
    points_total = con.execute("SELECT COALESCE(SUM(points_added),0) s FROM points_tx").fetchone()["s"]
    best = con.execute("SELECT name FROM technicians ORDER BY points DESC LIMIT 1").fetchone()
    con.close()

    stats = {
        "technicians_count": tech_count,
        "gifts_available": gifts_available,
        "points_total": points_total,
        "best_performance": best["name"] if best else "غير متوفر",
        "db_status": "قاعدة البيانات متصلة",
    }
    return render_template("admin_dashboard.html", site_name=SITE_NAME, stats=stats)


# ---------- Admin: Technicians ----------
@app.get("/admin/techs")
def admin_techs():
    if not admin_required():
        return redirect(url_for("admin_login"))
    con = db.connect()
    techs = con.execute("SELECT * FROM technicians ORDER BY id DESC").fetchall()
    con.close()
    return render_template("admin_techs.html", site_name=SITE_NAME, techs=techs)


@app.get("/admin/techs/new")
def admin_tech_new():
    if not admin_required():
        return redirect(url_for("admin_login"))
    return render_template("admin_tech_form.html", site_name=SITE_NAME, mode="new")


@app.post("/admin/techs/new")
def admin_tech_new_post():
    if not admin_required():
        return redirect(url_for("admin_login"))

    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    password = request.form.get("password", "").strip()
    specialty = request.form.get("specialty", "").strip()

    if not (name and phone and password):
        flash("يرجى ملء الاسم + رقم الهاتف + كلمة السر", "err")
        return redirect(url_for("admin_tech_new"))

    con = db.connect()
    try:
        con.execute("""
            INSERT INTO technicians(name, phone, password, specialty, points, created_at)
            VALUES (?,?,?,?,0,?)
        """, (name, phone, password, specialty, db.now()))
        con.commit()
    except Exception:
        con.close()
        flash("رقم الهاتف مستخدم مسبقاً", "err")
        return redirect(url_for("admin_tech_new"))
    con.close()

    flash("تمت إضافة الفني بنجاح", "ok")
    return redirect(url_for("admin_techs"))


@app.get("/admin/techs/<int:tech_id>/edit")
def admin_tech_edit(tech_id):
    if not admin_required():
        return redirect(url_for("admin_login"))
    con = db.connect()
    tech = con.execute("SELECT * FROM technicians WHERE id=?", (tech_id,)).fetchone()
    con.close()
    if not tech:
        return redirect(url_for("admin_techs"))
    return render_template("admin_tech_form.html", site_name=SITE_NAME, mode="edit", tech=tech)


@app.post("/admin/techs/<int:tech_id>/edit")
def admin_tech_edit_post(tech_id):
    if not admin_required():
        return redirect(url_for("admin_login"))

    name = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    specialty = request.form.get("specialty", "").strip()
    new_password = request.form.get("password", "").strip()

    con = db.connect()
    tech = con.execute("SELECT * FROM technicians WHERE id=?", (tech_id,)).fetchone()
    if not tech:
        con.close()
        return redirect(url_for("admin_techs"))

    try:
        if new_password:
            con.execute("""
                UPDATE technicians
                SET name=?, phone=?, specialty=?, password=?
                WHERE id=?
            """, (name, phone, specialty, new_password, tech_id))
        else:
            con.execute("""
                UPDATE technicians
                SET name=?, phone=?, specialty=?
                WHERE id=?
            """, (name, phone, specialty, tech_id))
        con.commit()
    except Exception:
        con.close()
        flash("تعذر التعديل: ربما رقم الهاتف مستخدم", "err")
        return redirect(url_for("admin_tech_edit", tech_id=tech_id))

    con.close()
    flash("تم التعديل بنجاح", "ok")
    return redirect(url_for("admin_techs"))


@app.post("/admin/techs/<int:tech_id>/delete")
def admin_tech_delete(tech_id):
    if not admin_required():
        return redirect(url_for("admin_login"))
    con = db.connect()
    con.execute("DELETE FROM technicians WHERE id=?", (tech_id,))
    con.commit()
    con.close()
    flash("تم حذف الفني", "ok")
    return redirect(url_for("admin_techs"))


# ---------- Admin: Add Points ----------
@app.get("/admin/points")
def admin_points():
    if not admin_required():
        return redirect(url_for("admin_login"))

    iqd_per_point = int(db.get_setting("iqd_per_point", "10000"))

    con = db.connect()
    techs = con.execute("SELECT id,name,phone,points FROM technicians ORDER BY name").fetchall()
    con.close()
    return render_template("admin_points.html", site_name=SITE_NAME, techs=techs, iqd_per_point=iqd_per_point)


@app.post("/admin/points/add")
def admin_points_add():
    if not admin_required():
        return redirect(url_for("admin_login"))

    tech_id = int(request.form.get("tech_id", "0"))
    amount = int(request.form.get("amount", "0") or 0)
    iqd_per_point = int(db.get_setting("iqd_per_point", "10000"))

    if tech_id <= 0 or amount <= 0:
        flash("أدخل مبلغ صحيح", "err")
        return redirect(url_for("admin_points"))

    points = max(1, amount // iqd_per_point)

    con = db.connect()
    con.execute("UPDATE technicians SET points = points + ? WHERE id=?", (points, tech_id))
    con.execute("""
        INSERT INTO points_tx(tech_id, purchase_amount, points_added, created_at, admin_id)
        VALUES (?,?,?,?,?)
    """, (tech_id, amount, points, db.now(), current_admin_id()))
    con.commit()
    con.close()

    flash(f"تمت إضافة {points} نقطة", "ok")
    return redirect(url_for("admin_points"))


# ---------- Admin: Gifts ----------
@app.get("/admin/gifts")
def admin_gifts():
    if not admin_required():
        return redirect(url_for("admin_login"))
    con = db.connect()
    gifts = con.execute("SELECT * FROM gifts ORDER BY id DESC").fetchall()
    con.close()
    return render_template("admin_gifts.html", site_name=SITE_NAME, gifts=gifts)


@app.get("/admin/gifts/new")
def admin_gift_new():
    if not admin_required():
        return redirect(url_for("admin_login"))
    return render_template("admin_gift_form.html", site_name=SITE_NAME)


@app.post("/admin/gifts/new")
def admin_gift_new_post():
    if not admin_required():
        return redirect(url_for("admin_login"))

    name = request.form.get("name", "").strip()
    points_required = int(request.form.get("points_required", "0") or 0)
    file = request.files.get("image")

    if not (name and points_required > 0):
        flash("أدخل اسم الهدية + عدد النقاط", "err")
        return redirect(url_for("admin_gift_new"))

    filename = None
    if file and file.filename:
        safe = secure_filename(file.filename)
        filename = f"{int(__import__('time').time())}_{safe}"
        file.save(os.path.join(UPLOAD_DIR, filename))

    con = db.connect()
    con.execute("""
        INSERT INTO gifts(name, points_required, image_filename, is_active, created_at)
        VALUES (?,?,?,?,?)
    """, (name, points_required, filename, 1, db.now()))
    con.commit()
    con.close()

    flash("تمت إضافة الهدية", "ok")
    return redirect(url_for("admin_gifts"))


@app.post("/admin/gifts/<int:gift_id>/toggle")
def admin_gift_toggle(gift_id):
    if not admin_required():
        return redirect(url_for("admin_login"))
    con = db.connect()
    gift = con.execute("SELECT is_active FROM gifts WHERE id=?", (gift_id,)).fetchone()
    if gift:
        new_val = 0 if gift["is_active"] == 1 else 1
        con.execute("UPDATE gifts SET is_active=? WHERE id=?", (new_val, gift_id))
        con.commit()
    con.close()
    return redirect(url_for("admin_gifts"))


@app.post("/admin/gifts/<int:gift_id>/delete")
def admin_delete_gift(gift_id):
    if not admin_required():
        return redirect(url_for("admin_login"))

    # جلب الهدية حتى نحذف الصورة من uploads
    gift = db.get_gift_by_id(gift_id)
    if gift and gift["image_filename"]:
        img_path = os.path.join(UPLOAD_DIR, gift["image_filename"])
        try:
            if os.path.exists(img_path):
                os.remove(img_path)
        except Exception:
            pass

    db.delete_gift(gift_id)
    flash("تم حذف الهدية", "ok")
    return redirect(url_for("admin_gifts"))


# ---------- Public/Home ----------
@app.get("/")
def home():
    return render_template("index.html", site_name=SITE_NAME)


# ---------- User Auth (Technician) ----------
@app.get("/login")
def user_login():
    return render_template("user_login.html", site_name=SITE_NAME)


@app.post("/login")
def user_login_post():
    phone = request.form.get("phone", "").strip()
    password = request.form.get("password", "").strip()

    con = db.connect()
    user = con.execute("SELECT * FROM technicians WHERE phone=?", (phone,)).fetchone()
    con.close()

    if user and user["password"] == password:
        session["user_logged_in"] = True
        session["user_id"] = user["id"]
        return redirect(url_for("user_dashboard"))

    return render_template("user_login.html", site_name=SITE_NAME, error="بيانات الدخول غير صحيحة")


@app.get("/logout")
def user_logout():
    session.clear()
    return redirect(url_for("user_login"))


# ---------- User Pages ----------
@app.get("/me")
def user_dashboard():
    if not user_required():
        return redirect(url_for("user_login"))
    con = db.connect()
    user = con.execute("SELECT id,name,points FROM technicians WHERE id=?", (current_user_id(),)).fetchone()
    con.close()
    return render_template("user_dashboard.html", site_name=SITE_NAME, user=user)


@app.get("/gifts")
def user_gifts():
    if not user_required():
        return redirect(url_for("user_login"))

    con = db.connect()
    user = con.execute("SELECT id,points FROM technicians WHERE id=?", (current_user_id(),)).fetchone()
    gifts = con.execute("SELECT * FROM gifts WHERE is_active=1 ORDER BY points_required ASC").fetchall()
    con.close()
    return render_template("user_gifts.html", site_name=SITE_NAME, user=user, gifts=gifts)


@app.post("/gifts/<int:gift_id>/redeem")
def user_redeem(gift_id):
    if not user_required():
        return redirect(url_for("user_login"))

    con = db.connect()
    user = con.execute("SELECT id,points FROM technicians WHERE id=?", (current_user_id(),)).fetchone()
    gift = con.execute("SELECT * FROM gifts WHERE id=? AND is_active=1", (gift_id,)).fetchone()

    if not gift or not user:
        con.close()
        return redirect(url_for("user_gifts"))

    if user["points"] < gift["points_required"]:
        con.close()
        flash("لا يمكن بسبب عدم كفاية الرصيد", "err")
        return redirect(url_for("user_gifts"))

    con.execute("UPDATE technicians SET points = points - ? WHERE id=?", (gift["points_required"], user["id"]))
    con.execute("""
        INSERT INTO redemptions(tech_id, gift_id, points_spent, created_at, status)
        VALUES (?,?,?,?,?)
    """, (user["id"], gift["id"], gift["points_required"], db.now(), "pending"))
    con.commit()

    new_points = con.execute("SELECT points FROM technicians WHERE id=?", (user["id"],)).fetchone()["points"]
    con.close()

    return render_template("user_congrats.html", site_name=SITE_NAME, new_points=new_points)


@app.get("/my-gifts")
def user_my_gifts():
    if not user_required():
        return redirect(url_for("user_login"))

    con = db.connect()
    rows = con.execute("""
        SELECT r.created_at, g.name, g.image_filename, r.points_spent
        FROM redemptions r
        JOIN gifts g ON g.id = r.gift_id
        WHERE r.tech_id=?
        ORDER BY r.id DESC
    """, (current_user_id(),)).fetchall()
    con.close()
    return render_template("user_my_gifts.html", site_name=SITE_NAME, rows=rows)


# ---------- Winners (Public) ----------
@app.get("/winners")
def winners():
    winners_list = db.get_winners()
    return render_template("winners.html", site_name=SITE_NAME, winners=winners_list)


# ===============================
# ADMIN SETTINGS (تغيير بيانات الأدمن)
# ===============================
@app.get("/admin/settings")
def admin_settings():
    if not admin_required():
        return redirect(url_for("admin_login"))

    if session.get("admin_role") != "super":
        return "غير مسموح"

    return render_template("admin_settings.html", site_name=SITE_NAME)


@app.post("/admin/settings")
def admin_settings_post():
    if not admin_required():
        return redirect(url_for("admin_login"))

    if session.get("admin_role") != "super":
        return "غير مسموح"

    new_email = request.form.get("email", "").strip()
    new_pass = request.form.get("password", "").strip()

    if not new_email or not new_pass:
        flash("اكتب ايميل وكلمة سر", "err")
        return redirect(url_for("admin_settings"))

    con = db.connect()
    con.execute("UPDATE admins SET email=?, password=? WHERE role='super'", (new_email, new_pass))
    con.commit()
    con.close()

    flash("تم التغيير بنجاح", "ok")
    return redirect(url_for("admin_settings"))


if __name__ == "__main__":
    app.run(debug=True)
