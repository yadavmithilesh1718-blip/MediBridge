from flask import Flask, render_template, request, send_from_directory, redirect, session
import sqlite3
import os
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.secret_key = "medibridge-secret-key"

# Upload Folder
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Upload folder agar nahi hai to create karo
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# Database aur table create karna
connection = sqlite3.connect("medibridge.db")
cursor = connection.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS medicine (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    medicine_name TEXT,
    expiry_date TEXT,
    quantity INTEGER,
    condition TEXT,
    image_name TEXT
)
""")

# Existing medicine table me user_id add karna
try:
    cursor.execute("ALTER TABLE medicine ADD COLUMN user_id INTEGER")
    print("user_id column added successfully")
except sqlite3.OperationalError:
    print("user_id column already exists")

# Users table
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL
)
""")

# Medicine Requests Table

cursor.execute("""
CREATE TABLE IF NOT EXISTS medicine_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    medicine_id INTEGER NOT NULL,
    requester_id INTEGER NOT NULL,
    status TEXT DEFAULT 'Pending'
)
""")

print("Medicine Requests table ready")

connection.commit()
connection.close()


# Home Dashboard
@app.route("/")
def home():

    connection = sqlite3.connect("medibridge.db")
    cursor = connection.cursor()

    # Total medicines
    cursor.execute("SELECT COUNT(*) FROM medicine")
    total_medicines = cursor.fetchone()[0]

    # Total quantity
    cursor.execute("""
        SELECT COALESCE(SUM(quantity), 0)
        FROM medicine
    """)
    total_quantity = cursor.fetchone()[0]

    # Medicines for expiry calculation
    cursor.execute("""
        SELECT expiry_date
        FROM medicine
    """)
    medicines = cursor.fetchall()

    connection.close()

    # Expiry statistics
    today = datetime.today().date()

    valid_medicines = 0
    expiring_soon = 0
    expired_medicines = 0

    for medicine in medicines:

        try:
            expiry_date = datetime.strptime(
                medicine[0],
                "%Y-%m-%d"
            ).date()

            days_left = (expiry_date - today).days

            if days_left < 0:
                expired_medicines += 1

            elif days_left <= 30:
                expiring_soon += 1

            else:
                valid_medicines += 1

        except (ValueError, TypeError):
            pass

    return render_template(
        "index.html",
        total_medicines=total_medicines,
        valid_medicines=valid_medicines,
        expiring_soon=expiring_soon,
        expired_medicines=expired_medicines,
        total_quantity=total_quantity
    )


# Donate Medicine - Login Required
@app.route("/donate", methods=["GET", "POST"])
def donate():

    if "user_id" not in session:
        return redirect("/login")

    if request.method == "POST":

        medicine_name = request.form.get("medicine_name")
        expiry_date = request.form.get("expiry_date")
        quantity = request.form.get("quantity")
        condition = request.form.get("condition")

        # Image
        image = request.files.get("medicine_image")

        image_name = ""

        if image and image.filename != "":
            image_name = image.filename

            image.save(
                os.path.join(
                    app.config["UPLOAD_FOLDER"],
                    image_name
                )
            )

            print("Image Saved:", image_name)

        # Terminal me data print
        print("Medicine Name:", medicine_name)
        print("Expiry Date:", expiry_date)
        print("Quantity:", quantity)
        print("Condition:", condition)
        print("User ID:", session["user_id"])

        # Database me save
        connection = sqlite3.connect("medibridge.db")
        cursor = connection.cursor()

        cursor.execute("""
        INSERT INTO medicine
        (medicine_name, expiry_date, quantity, condition, image_name, user_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            medicine_name,
            expiry_date,
            quantity,
            condition,
            image_name,
            session["user_id"]
        ))

        connection.commit()
        connection.close()

        print("Medicine Saved Successfully")

    return render_template("donate.html")


# Register
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name")
        email = request.form.get("email")
        password = request.form.get("password")

        # Password ko secure hash me convert karna
        hashed_password = generate_password_hash(password)

        connection = sqlite3.connect("medibridge.db")
        cursor = connection.cursor()

        try:

            cursor.execute("""
            INSERT INTO users (name, email, password)
            VALUES (?, ?, ?)
            """, (name, email, hashed_password))

            connection.commit()

            print("User Registered Successfully")

        except sqlite3.IntegrityError:

            connection.close()

            return "Email already registered."

        connection.close()

        return redirect("/login")

    return render_template("register.html")


# Login
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        connection = sqlite3.connect("medibridge.db")
        cursor = connection.cursor()

        cursor.execute(
            "SELECT id, name, email, password FROM users WHERE email = ?",
            (email,)
        )

        user = cursor.fetchone()

        connection.close()

        if user is None:
            return "Invalid email or password."

        if check_password_hash(user[3], password):

            session["user_id"] = user[0]
            session["user_name"] = user[1]
            session["user_email"] = user[2]

            print("Login Successful:", user[2])

            return redirect("/")

        return "Invalid email or password."

    return render_template("login.html")


# Logout
@app.route("/logout")
def logout():

    session.clear()

    print("User Logged Out")

    return redirect("/")

# Medicines
@app.route("/medicines")
def medicines():

    search = request.args.get("search", "")

    connection = sqlite3.connect("medibridge.db")
    cursor = connection.cursor()

    if search:
        cursor.execute("""
        SELECT * FROM medicine
        WHERE medicine_name LIKE ?
        """, ("%" + search + "%",))
    else:
        cursor.execute("SELECT * FROM medicine")

    medicines = cursor.fetchall()

    connection.close()

    # Expiry Status Calculate
    today = datetime.today().date()

    medicine_data = []

    for medicine in medicines:

        try:
            expiry_date = datetime.strptime(
                medicine[2],
                "%Y-%m-%d"
            ).date()

            days_left = (expiry_date - today).days

            if days_left < 0:
                expiry_status = "Expired"

            elif days_left <= 30:
                expiry_status = "Expiring Soon"

            else:
                expiry_status = "Valid"

        except (ValueError, TypeError):
            expiry_status = "Unknown"

        # Original medicine data + expiry status
        medicine_data.append(
            medicine + (expiry_status,)
        )

    return render_template(
        "medicines.html",
        medicines=medicine_data,
        search=search
    )



# Uploaded images browser me dikhane ke liye
@app.route("/uploads/<filename>")
def uploaded_file(filename):

    return send_from_directory(
        app.config["UPLOAD_FOLDER"],
        filename
    )

# View Medicine Details
@app.route("/view/<int:medicine_id>")
def view_medicine(medicine_id):

    connection = sqlite3.connect("medibridge.db")
    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM medicine WHERE id = ?",
        (medicine_id,)
    )

    medicine = cursor.fetchone()

    connection.close()

    if medicine is None:
        return "Medicine not found"

    # Expiry Status
    try:
        expiry_date = datetime.strptime(
            medicine[2],
            "%Y-%m-%d"
        ).date()

        today = datetime.today().date()
        days_left = (expiry_date - today).days

        if days_left < 0:
            expiry_status = "Expired"

        elif days_left <= 30:
            expiry_status = "Expiring Soon"

        else:
            expiry_status = "Valid"

    except (ValueError, TypeError):
        expiry_status = "Unknown"

    return render_template(
        "view_medicine.html",
        medicine=medicine,
        expiry_status=expiry_status
    )

# Edit Medicine - Login Required + Owner Only
@app.route("/edit/<int:medicine_id>", methods=["GET", "POST"])
def edit_medicine(medicine_id):

    if "user_id" not in session:
        return redirect("/login")

    connection = sqlite3.connect("medibridge.db")
    cursor = connection.cursor()

    # Check medicine owner
    cursor.execute(
        "SELECT user_id FROM medicine WHERE id = ?",
        (medicine_id,)
    )

    owner = cursor.fetchone()

    # Medicine does not exist
    if owner is None:
        connection.close()
        return "Medicine not found"

    # Only owner can edit
    if owner[0] != session["user_id"]:
        connection.close()
        return "You are not allowed to edit this medicine."

    if request.method == "POST":

        medicine_name = request.form.get("medicine_name")
        expiry_date = request.form.get("expiry_date")
        quantity = request.form.get("quantity")
        condition = request.form.get("condition")

        cursor.execute("""
        UPDATE medicine
        SET medicine_name = ?,
            expiry_date = ?,
            quantity = ?,
            condition = ?
        WHERE id = ?
        """, (
            medicine_name,
            expiry_date,
            quantity,
            condition,
            medicine_id
        ))

        connection.commit()
        connection.close()

        print("Medicine Updated:", medicine_id)

        return redirect("/medicines")

    cursor.execute(
        "SELECT * FROM medicine WHERE id = ?",
        (medicine_id,)
    )

    medicine = cursor.fetchone()

    connection.close()

    return render_template(
        "edit.html",
        medicine=medicine
    )

# Delete Medicine - Login Required + Owner Only
@app.route("/delete/<int:medicine_id>")
def delete_medicine(medicine_id):

    if "user_id" not in session:
        return redirect("/login")

    connection = sqlite3.connect("medibridge.db")
    cursor = connection.cursor()

    # Medicine ki image aur owner ID nikalo
    cursor.execute(
        "SELECT image_name, user_id FROM medicine WHERE id = ?",
        (medicine_id,)
    )

    medicine = cursor.fetchone()

    # Medicine exist nahi karti
    if medicine is None:
        connection.close()
        return "Medicine not found"

    # Sirf owner hi delete kar sakta hai
    if medicine[1] != session["user_id"]:
        connection.close()
        return "You are not allowed to delete this medicine."

    # Database se medicine delete karo
    cursor.execute(
        "DELETE FROM medicine WHERE id = ?",
        (medicine_id,)
    )

    connection.commit()
    connection.close()

    # Agar image hai to uploads folder se bhi delete karo
    if medicine[0]:

        image_path = os.path.join(
            app.config["UPLOAD_FOLDER"],
            medicine[0]
        )

        if os.path.exists(image_path):
            os.remove(image_path)

    print("Medicine Deleted:", medicine_id)

    return redirect("/medicines")


# Request Medicine - Login Required
@app.route("/request-medicine/<int:medicine_id>")
def request_medicine(medicine_id):

    if "user_id" not in session:
        return redirect("/login")

    connection = sqlite3.connect("medibridge.db")
    cursor = connection.cursor()

    # Check medicine exists
    cursor.execute(
        "SELECT id, medicine_name, user_id FROM medicine WHERE id = ?",
        (medicine_id,)
    )

    medicine = cursor.fetchone()

    if medicine is None:
        connection.close()
        return "Medicine not found"

    # Owner apni medicine khud request nahi kar sakta
    if medicine[2] == session["user_id"]:
        connection.close()
        return "You cannot request your own medicine."

    # Check if request already exists
    cursor.execute("""
        SELECT id
        FROM medicine_requests
        WHERE medicine_id = ? AND requester_id = ?
    """, (
        medicine_id,
        session["user_id"]
    ))

    existing_request = cursor.fetchone()

    if existing_request:
        connection.close()
        return "You have already requested this medicine."

    # Create request
    cursor.execute("""
        INSERT INTO medicine_requests
        (medicine_id, requester_id, status)
        VALUES (?, ?, ?)
    """, (
        medicine_id,
        session["user_id"],
        "Pending"
    ))

    connection.commit()
    connection.close()

    print(
        "Medicine Request Created:",
        medicine_id,
        "Requester:",
        session["user_id"]
    )

    return "Medicine request sent successfully!"

# Run Application
if __name__ == "__main__":
    app.run(debug=True)

  