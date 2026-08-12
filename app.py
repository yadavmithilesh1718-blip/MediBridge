from flask import Flask, render_template, request
import sqlite3
import os

app = Flask(__name__)

# Upload Folder
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Database aur table create karna
connection = sqlite3.connect("medibridge.db")
cursor = connection.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS medicine (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    medicine_name TEXT,
    expiry_date TEXT,
    quantity INTEGER,
    condition TEXT
)
""")

connection.commit()
connection.close()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/donate", methods=["GET", "POST"])
def donate():

    if request.method == "POST":

        # Form Data
        medicine_name = request.form.get("medicine_name")
        expiry_date = request.form.get("expiry_date")
        quantity = request.form.get("quantity")
        condition = request.form.get("condition")

        # Image
        image = request.files.get("medicine_image")

        if image and image.filename != "":
            image.save(os.path.join(app.config["UPLOAD_FOLDER"], image.filename))
            print("Image Saved:", image.filename)

        # Print
        print("Medicine Name:", medicine_name)
        print("Expiry Date:", expiry_date)
        print("Quantity:", quantity)
        print("Condition:", condition)

        # Save in Database
        connection = sqlite3.connect("medibridge.db")
        cursor = connection.cursor()

        cursor.execute("""
        INSERT INTO medicine
        (medicine_name, expiry_date, quantity, condition)
        VALUES (?, ?, ?, ?)
        """, (medicine_name, expiry_date, quantity, condition))

        connection.commit()
        connection.close()

        print("Medicine Saved Successfully")

    return render_template("donate.html")


@app.route("/medicines")
def medicines():

    connection = sqlite3.connect("medibridge.db")
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM medicine")

    medicines = cursor.fetchall()

    connection.close()

    return render_template("medicines.html", medicines=medicines)


if __name__ == "__main__":
    app.run(debug=True)