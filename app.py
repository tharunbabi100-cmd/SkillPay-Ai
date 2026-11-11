
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session
)

from database import get_db_connection

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)

app = Flask(__name__)

app.secret_key = "skillpay-ai-dev-secret-change-before-deployment"


# ==========================================
# 1. HOME / DASHBOARD
# ==========================================

@app.route("/", methods=["GET"])
def home():

    if "student_id" not in session:
        return redirect(url_for("login"))

    return render_template("index.html")


# ==========================================
# 2. DATABASE CONNECTION TEST
# ==========================================

@app.route("/db-test")
def db_test():

    connection = None

    try:
        connection = get_db_connection()

        return {
            "message": "SkillPay AI database connected successfully!"
        }

    except Exception:
        app.logger.exception("Database connection failed")
        return {"error": "Database connection failed."}, 500

    finally:
        if connection:
            connection.close()


# ==========================================
# 3. STUDENT REGISTRATION
# ==========================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        full_name = request.form.get(
            "full_name", ""
        ).strip()

        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get("password", "")

        college_name = request.form.get(
            "college_name", ""
        ).strip()

        if not full_name or not email or not password:

            flash("Please fill in all required fields.")
            return redirect(url_for("register"))

        if len(password) < 8:

            flash("Password must contain at least 8 characters.")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        connection = None
        cursor = None

        try:

            connection = get_db_connection()
            cursor = connection.cursor()

            query = """
                INSERT INTO students
                (full_name, email, password, college_name)
                VALUES (%s, %s, %s, %s)
            """

            cursor.execute(
                query,
                (
                    full_name,
                    email,
                    hashed_password,
                    college_name
                )
            )

            connection.commit()

            flash("Registration successful! You can now log in.")

            return redirect(url_for("login"))

        except Exception as e:

            if connection:
                connection.rollback()

            if getattr(e, "errno", None) == 1062:

                flash("This email is already registered.")

            else:

                app.logger.exception("Registration failed")
                flash("Registration failed. Please try again.")

        finally:

            if cursor:
                cursor.close()

            if connection:
                connection.close()

    return render_template("register.html")


# ==========================================
# 4. STUDENT LOGIN
# ==========================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get(
            "email", ""
        ).strip().lower()

        password = request.form.get("password", "")

        connection = None
        cursor = None

        try:

            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            query = """
                SELECT student_id, full_name, email, password
                FROM students
                WHERE email = %s
            """

            cursor.execute(query, (email,))

            student = cursor.fetchone()

            if student and check_password_hash(
                student["password"], password
            ):

                session.clear()

                session["student_id"] = student["student_id"]
                session["student_name"] = student["full_name"]

                flash("Login successful!")

                return redirect(url_for("home"))

            flash("Invalid email or password.")

        except Exception:

            app.logger.exception("Login failed")
            flash("Something went wrong. Please try again.")

        finally:

            if cursor:
                cursor.close()

            if connection:
                connection.close()

    return render_template("login.html")


# ==========================================
# 5. STUDENT PROFILE
# ==========================================

@app.route("/profile")
def profile():

    if "student_id" not in session:
        return redirect(url_for("login"))

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                student_id,
                full_name,
                email,
                college_name,
                created_at
            FROM students
            WHERE student_id = %s
        """

        cursor.execute(
            query,
            (session["student_id"],)
        )

        student = cursor.fetchone()

        if not student:

            session.clear()
            return redirect(url_for("login"))

        return render_template(
            "profile.html",
            student=student
        )

    except Exception:

        app.logger.exception("Profile loading failed")
        return "Unable to load student profile.", 500

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================
# 6. ADD INCOME OR EXPENSE
# ==========================================

@app.route("/add-transaction", methods=["POST"])
def add_transaction():

    if "student_id" not in session:
        return {"error": "Please log in first."}, 401

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return {"error": "Invalid transaction data."}, 400

    transaction_type = data.get("type")
    description = data.get("description", "")

    if not isinstance(description, str):
        return {"error": "Invalid description."}, 400

    description = description.strip()

    try:
        amount = float(data.get("amount"))
    except (TypeError, ValueError):
        return {"error": "Enter a valid amount."}, 400

    if transaction_type not in ["income", "expense"]:
        return {"error": "Invalid transaction type."}, 400

    if not description or len(description) > 255:
        return {"error": "Enter a valid description."}, 400

    if not 0 < amount <= 99999999.99:
        return {"error": "Enter a valid amount."}, 400

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor()

        query = """
            INSERT INTO transactions
            (student_id, transaction_type, description, amount)
            VALUES (%s, %s, %s, %s)
        """

        cursor.execute(
            query,
            (
                session["student_id"],
                transaction_type,
                description,
                amount
            )
        )

        connection.commit()

        return {
            "message": "Transaction saved successfully!"
        }, 201

    except Exception:

        if connection:
            connection.rollback()

        app.logger.exception("Transaction saving failed")

        return {"error": "Could not save transaction."}, 500

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================
# 7. GET STUDENT TRANSACTIONS
# ==========================================

@app.route("/get-transactions", methods=["GET"])
def get_transactions():

    if "student_id" not in session:
        return {"error": "Please log in first."}, 401

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                transaction_id,
                transaction_type,
                description,
                amount,
                transaction_date
            FROM transactions
            WHERE student_id = %s
            ORDER BY transaction_date DESC
        """

        cursor.execute(
            query,
            (session["student_id"],)
        )

        transactions = cursor.fetchall()

        for transaction in transactions:

            transaction["amount"] = float(
                transaction["amount"]
            )

            transaction["transaction_date"] = (
                transaction["transaction_date"].isoformat()
            )

        return {"transactions": transactions}

    except Exception:

        app.logger.exception("Transaction retrieval failed")

        return {"error": "Could not retrieve transactions."}, 500

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================
# 8. COLLEGE FEES MANAGEMENT
# ==========================================

@app.route("/college-fees", methods=["GET", "POST"])
def college_fees():

    if "student_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        fee_title = request.form.get(
            "fee_title", ""
        ).strip()

        amount = request.form.get("amount", "")

        due_date = request.form.get(
            "due_date", ""
        ).strip()

        if not fee_title or len(fee_title) > 150:

            flash("Enter a valid fee description.")
            return redirect(url_for("college_fees"))

        try:

            fee_amount = float(amount)

            if not 0 < fee_amount <= 99999999.99:
                raise ValueError()

        except (ValueError, TypeError):

            flash("Please enter a valid fee amount.")
            return redirect(url_for("college_fees"))

        connection = None
        cursor = None

        try:

            connection = get_db_connection()
            cursor = connection.cursor()

            query = """
                INSERT INTO college_fees
                (student_id, fee_title, amount, due_date)
                VALUES (%s, %s, %s, %s)
            """

            cursor.execute(
                query,
                (
                    session["student_id"],
                    fee_title,
                    fee_amount,
                    due_date if due_date else None
                )
            )

            connection.commit()

            flash("College fee added successfully!")

        except Exception:

            if connection:
                connection.rollback()

            app.logger.exception("College fee saving failed")

            flash("Unable to save college fee.")

        finally:

            if cursor:
                cursor.close()

            if connection:
                connection.close()

        return redirect(url_for("college_fees"))

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                fee_id,
                fee_title,
                amount,
                due_date,
                payment_status
            FROM college_fees
            WHERE student_id = %s
            ORDER BY due_date ASC, fee_id DESC
        """

        cursor.execute(
            query,
            (session["student_id"],)
        )

        fees = cursor.fetchall()

        total_pending = sum(
            float(fee["amount"])
            for fee in fees
            if fee["payment_status"] == "Pending"
        )

        total_paid = sum(
            float(fee["amount"])
            for fee in fees
            if fee["payment_status"] == "Paid"
        )

        return render_template(
            "college_fees.html",
            fees=fees,
            total_pending=total_pending,
            total_paid=total_paid
        )

    except Exception:

        app.logger.exception("College fees loading failed")

        return "Unable to load college fees.", 500

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()


# ==========================================
# 9. MARK COLLEGE FEE AS PAID
# ==========================================

@app.route(
    "/update-fee-status/<int:fee_id>",
    methods=["POST"]
)
def update_fee_status(fee_id):

    if "student_id" not in session:
        return redirect(url_for("login"))

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor()

        query = """
            UPDATE college_fees
            SET payment_status = 'Paid'
            WHERE fee_id = %s
            AND student_id = %s
            AND payment_status = 'Pending'
        """

        cursor.execute(
            query,
            (
                fee_id,
                session["student_id"]
            )
        )

        connection.commit()

        if cursor.rowcount > 0:

            flash("College fee marked as Paid successfully!")

        else:

            flash("Fee record not found or already paid.")

    except Exception:

        if connection:
            connection.rollback()

        app.logger.exception("Fee status update failed")

        flash("Unable to update fee payment status.")

    finally:

        if cursor:
            cursor.close()

        if connection:
            connection.close()

    return redirect(url_for("college_fees"))


# ==========================================
# 10. STUDENT LOGOUT
# ==========================================

@app.route("/logout")
def logout():

    session.clear()

    flash("You have been logged out successfully.")

    return redirect(url_for("login"))


# ---------------- SCHOLARSHIP MANAGEMENT ----------------

@app.route("/scholarships", methods=["GET", "POST"])
def scholarships():
    if "student_id" not in session:
        return redirect(url_for("login"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        if request.method == "POST":
            scholarship_name = request.form.get(
                "scholarship_name", ""
            ).strip()

            provider = request.form.get("provider", "").strip()

            amount = request.form.get("amount", "").strip()

            deadline = request.form.get("deadline", "").strip()

            if not scholarship_name or not amount:
                flash("Scholarship name and amount are required.")

            else:
                try:
                    amount = float(amount)

                    if amount <= 0:
                        raise ValueError()

                    query = """
                        INSERT INTO scholarships
                        (student_id, scholarship_name, provider,
                         amount, deadline)
                        VALUES (%s, %s, %s, %s, %s)
                    """

                    cursor.execute(
                        query,
                        (
                            session["student_id"],
                            scholarship_name,
                            provider or None,
                            amount,
                            deadline or None
                        )
                    )

                    connection.commit()
                    flash("Scholarship added successfully!")

                except ValueError:
                    flash("Please enter a valid scholarship amount.")

        cursor.execute(
            """
            SELECT *
            FROM scholarships
            WHERE student_id = %s
            ORDER BY created_at DESC
            """,
            (session["student_id"],)
        )

        scholarship_list = cursor.fetchall()

        return render_template(
            "scholarships.html",
            scholarships=scholarship_list
        )

    except Exception:
        if connection:
            connection.rollback()

        app.logger.exception("Scholarship loading failed")
        flash("Unable to load scholarships.")
        return redirect(url_for("home"))

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


# Update scholarship application status
@app.route(
    "/update-scholarship/<int:scholarship_id>",
    methods=["POST"]
)
def update_scholarship(scholarship_id):
    if "student_id" not in session:
        return redirect(url_for("login"))

    new_status = request.form.get("application_status")

    allowed_statuses = [
        "Not Applied",
        "Applied",
        "Approved",
        "Rejected"
    ]

    if new_status not in allowed_statuses:
        flash("Invalid scholarship status.")
        return redirect(url_for("scholarships"))

    connection = None
    cursor = None

    try:
        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            """
            UPDATE scholarships
            SET application_status = %s
            WHERE scholarship_id = %s
            AND student_id = %s
            """,
            (
                new_status,
                scholarship_id,
                session["student_id"]
            )
        )

        connection.commit()

        if cursor.rowcount > 0:
            flash("Scholarship status updated!")
        else:
            flash("Scholarship record not found.")

    except Exception:
        if connection:
            connection.rollback()

        app.logger.exception("Scholarship status update failed")
        flash("Unable to update scholarship status.")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return redirect(url_for("scholarships"))



# ==========================================
# 11. RUN APPLICATION
# ==========================================

if __name__ == "__main__":

    app.run(debug=True)
