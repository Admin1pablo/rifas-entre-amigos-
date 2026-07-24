from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, session
import sqlite3
from pathlib import Path
from werkzeug.utils import secure_filename
from datetime import datetime

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "rifas.db"
UPLOAD_FOLDER = BASE_DIR / "uploads"
UPLOAD_FOLDER.mkdir(exist_ok=True)

app = Flask(__name__)
app.secret_key = "una-clave-secreta-muy-larga-rifas-rancho-2026"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()

    conn.executescript("""
    CREATE TABLE IF NOT EXISTS raffles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        vehicle TEXT NOT NULL,
        description TEXT,
        price REAL NOT NULL,
        total_numbers INTEGER NOT NULL,
        draw_date TEXT,
        image TEXT,
        status TEXT NOT NULL DEFAULT 'active',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS tickets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        raffle_id INTEGER NOT NULL,
        number INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'available',
        participant_name TEXT,
        phone TEXT,
        email TEXT,
        state TEXT,
        payment_status TEXT NOT NULL DEFAULT 'pending',
        payment_proof TEXT,
        reserved_until TEXT,
        created_at TEXT NOT NULL,
        UNIQUE(raffle_id, number),
        FOREIGN KEY(raffle_id) REFERENCES raffles(id)
    );
    """)

    try:
        conn.execute("ALTER TABLE tickets ADD COLUMN state TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE tickets ADD COLUMN payment_status TEXT NOT NULL DEFAULT 'pending'")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE tickets ADD COLUMN payment_proof TEXT")
    except sqlite3.OperationalError:
        pass
    try:
    conn.execute("ALTER TABLE raffles ADD COLUMN image TEXT")
    except sqlite3.OperationalError:
        pass
    existing = conn.execute("SELECT COUNT(*) AS c FROM raffles").fetchone()["c"]
    if existing == 0:
        cur = conn.execute("""
            INSERT INTO raffles(name, vehicle, description, price, total_numbers, draw_date, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'active', ?)
        """, (
            "Rifa de prueba #001",
            "Chevrolet Silverado 2020",
            "Primera rifa de prueba de Rifas Entre Amigos del Rancho.",
            100,
            10000,
            "Por anunciar",
            datetime.now().isoformat()
        ))

        raffle_id = cur.lastrowid

        conn.executemany(
            "INSERT INTO tickets(raffle_id, number, status, created_at) VALUES (?, ?, 'available', ?)",
            [(raffle_id, i, datetime.now().isoformat()) for i in range(10000)]
        )

        conn.executemany(
            "UPDATE tickets SET status='sold' WHERE raffle_id=? AND number=?",
            [(raffle_id, n) for n in [12, 45, 78, 101, 2458, 9999]]
        )

    conn.commit()
    conn.close()
    
@app.route("/")
def index():
    conn = get_db()
    raffles = conn.execute("SELECT * FROM raffles WHERE status='active' ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("index.html", raffles=raffles)

@app.route("/rifa/<int:raffle_id>")
def raffle(raffle_id):
    conn = get_db()

    conn.execute("""
        UPDATE tickets
        SET status='available',
            participant_name=NULL,
            phone=NULL,
            state=NULL,
            payment_proof=NULL,
            payment_status='pending',
            reserved_until=NULL
        WHERE status='reserved'
        AND reserved_until IS NOT NULL
        AND reserved_until < datetime('now')
    """)

    conn.commit()

    r = conn.execute(
        "SELECT * FROM raffles WHERE id=?",
        (raffle_id,)
    ).fetchone()

    sold = {
        row["number"]
        for row in conn.execute(
            "SELECT number FROM tickets WHERE raffle_id=? AND status='sold'",
            (raffle_id,)
        ).fetchall()
    }

    reserved = {
        row["number"]
        for row in conn.execute(
            "SELECT number FROM tickets WHERE raffle_id=? AND status='reserved'",
            (raffle_id,)
        ).fetchall()
    }

    conn.close()

    if not r:
        return "Rifa no encontrada", 404

    return render_template(
        "raffle.html",
        raffle=r,
        sold=sold,
        reserved=reserved
    )

@app.post("/api/reservar")
def reserve():
    raffle_id = int(request.form["raffle_id"])
    numbers = [int(x) for x in request.form.getlist("numbers")]
    name = request.form["name"].strip()
    phone = request.form["phone"].strip()
    state = request.form["state"].strip()
    payment_proof = request.files.get("payment_proof")

    if not numbers or not name or not phone or not state:
        flash("Completa tus datos y selecciona al menos un número.")
        return redirect(url_for("raffle", raffle_id=raffle_id))

    if not payment_proof or payment_proof.filename == "":
        flash("Debes subir tu comprobante de pago.")
        return redirect(url_for("raffle", raffle_id=raffle_id))

    filename = secure_filename(payment_proof.filename)
    payment_filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
    payment_path = UPLOAD_FOLDER / payment_filename
    payment_proof.save(payment_path)

    conn = get_db()
    placeholders = ",".join(["?"] * len(numbers))

    rows = conn.execute(
        f"SELECT number, status FROM tickets WHERE raffle_id=? AND number IN ({placeholders})",
        [raffle_id] + numbers
    ).fetchall()

    unavailable = [
        str(r["number"]).zfill(4)
        for r in rows
        if r["status"] != "available"
    ]

    if unavailable:
        conn.close()
        flash("Algunos números ya no están disponibles: " + ", ".join(unavailable))
        return redirect(url_for("raffle", raffle_id=raffle_id))

    conn.executemany("""
        UPDATE tickets
        SET status='reserved',
            participant_name=?,
            phone=?,
            state=?,
            payment_proof=?,
            reserved_until=datetime('now', '+6 hours')
        WHERE raffle_id=? AND number=?
    """, [
        (name, phone, state, payment_filename, raffle_id, n)
        for n in numbers
    ])

    conn.commit()
    conn.close()

    flash(f"¡Listo! Tus {len(numbers)} números quedaron apartados temporalmente.")
    return redirect(url_for("raffle", raffle_id=raffle_id))
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)
@app.route("/admin", methods=["GET", "POST"])
def admin():

    if not session.get("admin_logged_in"):

        if request.method == "POST":

            username = request.form.get("username", "").strip()
            password = request.form.get("password", "").strip()

            if username == "admin" and password == "RANCHO2026":

                session["admin_logged_in"] = True

                return redirect(url_for("admin"))

            flash("Usuario o contraseña incorrectos.")

        return render_template("admin_login.html")


    conn = get_db()

    raffles = conn.execute("""
        SELECT r.*,
        SUM(CASE WHEN t.status='sold' THEN 1 ELSE 0 END) sold_count,
        SUM(CASE WHEN t.status='reserved' THEN 1 ELSE 0 END) reserved_count
        FROM raffles r
        LEFT JOIN tickets t ON t.raffle_id=r.id
        GROUP BY r.id
        ORDER BY r.id DESC
    """).fetchall()


    tickets = conn.execute("""
        SELECT
            t.*,
            r.vehicle
        FROM tickets t
        JOIN raffles r ON r.id = t.raffle_id
        WHERE t.status = 'reserved'
        ORDER BY t.id DESC
    """).fetchall()


    conn.close()


    return render_template(
        "admin.html",
        raffles=raffles,
        tickets=tickets
    )
@app.route("/admin/logout")
def admin_logout():

    session.clear()

    return redirect(url_for("admin"))    
@app.post("/admin/aprobar/<int:ticket_id>")
def approve_ticket(ticket_id):
    conn = get_db()

    conn.execute("""
        UPDATE tickets
        SET status='sold',
            payment_status='approved'
        WHERE id=?
    """, (ticket_id,))

    conn.commit()
    conn.close()

    flash("Pago aprobado correctamente. El número ahora aparece como vendido.")
    return redirect(url_for("admin"))


@app.post("/admin/rechazar/<int:ticket_id>")
def reject_ticket(ticket_id):
    conn = get_db()

    conn.execute("""
        UPDATE tickets
        SET status='available',
            payment_status='rejected',
            participant_name=NULL,
            phone=NULL,
            state=NULL,
            payment_proof=NULL,
            reserved_until=NULL
        WHERE id=?
    """, (ticket_id,))

    conn.commit()
    conn.close()

    flash("Pago rechazado. El número volvió a estar disponible.")
    return redirect(url_for("admin"))    
@app.post("/admin/crear-rifa")
def create_raffle():
    name = request.form["name"]
    vehicle = request.form["vehicle"]
    description = request.form.get("description", "")
    price = float(request.form["price"])
    total_numbers = int(request.form["total_numbers"])
    draw_date = request.form.get("draw_date", "Por anunciar")

    conn = get_db()
    cur = conn.execute("""
        INSERT INTO raffles(name, vehicle, description, price, total_numbers, draw_date, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'active', ?)
    """, (name, vehicle, description, price, total_numbers, draw_date, datetime.now().isoformat()))
    raffle_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO tickets(raffle_id, number, status, created_at) VALUES (?, ?, 'available', ?)",
        [(raffle_id, i, datetime.now().isoformat()) for i in range(total_numbers)]
    )
    conn.commit()
    conn.close()
    flash("Rifa creada correctamente.")
    return redirect(url_for("admin"))
init_db()
if __name__ == "__main__":
    
    app.run(debug=True)
