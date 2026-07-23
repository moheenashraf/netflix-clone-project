from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
from dotenv import load_dotenv

from auth import create_user, verify_login, get_user_by_id, get_all_users, delete_user_account, set_user_role
from profiles import create_profile, get_profile, update_profile
from movies import (
    get_movies_grouped_by_genre, get_all_movies, get_movie_by_id,
    add_movie, update_movie, delete_movie, get_all_genres
)
load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def profile_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("profile_completed"):
            flash("Please complete your profile first.")
            return redirect(url_for("complete_profile"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") != "admin":
            flash("Admin access only.")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return wrapper


@app.route("/")
def home():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    if not (name and email and password):
        flash("Please fill in all fields.")
        return redirect(url_for("signup"))

    if len(password) < 6:
        flash("Password must be at least 6 characters.")
        return redirect(url_for("signup"))

    try:
        user_id = create_user(name, email, password)
    except ValueError as e:
        flash(str(e))
        return redirect(url_for("signup"))

    session["user_id"] = user_id
    session["name"] = name
    session["role"] = "user"
    session["profile_completed"] = False

    flash("Account created! Let's finish setting up your profile.")
    return redirect(url_for("complete_profile"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = verify_login(email, password)
    if not user:
        flash("Invalid email or password.")
        return redirect(url_for("login"))

    session["user_id"] = user["id"]
    session["name"] = user["name"]
    session["role"] = user["role"]
    session["profile_completed"] = bool(user["profile_completed"])

    flash(f"Welcome back, {user['name']}!")

    if not session["profile_completed"]:
        return redirect(url_for("complete_profile"))
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You've been logged out.")
    return redirect(url_for("login"))


@app.route("/complete-profile", methods=["GET", "POST"])
@login_required
def complete_profile():
    if request.method == "GET":
        return render_template("complete_profile.html")

    full_name = request.form.get("full_name", "").strip()
    phone_number = request.form.get("phone_number", "").strip()
    age = request.form.get("age", "").strip()
    gender = request.form.get("gender", "")
    email = request.form.get("email", "").strip()

    if not (full_name and phone_number and age and gender and email):
        flash("Please fill in all fields.")
        return redirect(url_for("complete_profile"))

    if not age.isdigit():
        flash("Age must be a number.")
        return redirect(url_for("complete_profile"))

    create_profile(session["user_id"], full_name, phone_number, int(age), gender, email)
    session["profile_completed"] = True

    flash("Profile completed!")
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
@login_required
@profile_required
def dashboard():
    profile = get_profile(session["user_id"])
    return render_template("dashboard.html", profile=profile)


# ---------------- EDIT PROFILE ----------------
# ---------------- BROWSE MOVIES ----------------

@app.route("/browse")
@login_required
@profile_required
def browse():
    genres_with_movies = get_movies_grouped_by_genre()
    return render_template("browse.html", genres_with_movies=genres_with_movies)


@app.route("/edit-profile", methods=["GET", "POST"])
@login_required
@profile_required
def edit_profile():
    if request.method == "GET":
        profile = get_profile(session["user_id"])
        return render_template("edit_profile.html", profile=profile)

    full_name = request.form.get("full_name", "").strip()
    phone_number = request.form.get("phone_number", "").strip()
    age = request.form.get("age", "").strip()
    gender = request.form.get("gender", "")
    email = request.form.get("email", "").strip()

    if not (full_name and phone_number and age and gender and email):
        flash("Please fill in all fields.")
        return redirect(url_for("edit_profile"))

    if not age.isdigit():
        flash("Age must be a number.")
        return redirect(url_for("edit_profile"))

    update_profile(session["user_id"], full_name, phone_number, int(age), gender, email)

    flash("Profile updated successfully.")
    return redirect(url_for("dashboard"))

# ---------------- ADMIN: MANAGE USERS ----------------

@app.route("/admin/users")
@login_required
@admin_required
def admin_users():
    users = get_all_users()
    return render_template("admin_users.html", users=users)


@app.route("/admin/users/toggle-role/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def admin_toggle_role(user_id):
    if user_id == session.get("user_id"):
        flash("You can't change your own role.")
        return redirect(url_for("admin_users"))

    target_user = get_user_by_id(user_id)
    if not target_user:
        flash("User not found.")
        return redirect(url_for("admin_users"))

    new_role = "user" if target_user["role"] == "admin" else "admin"
    set_user_role(user_id, new_role)
    flash(f"{target_user['name']} is now {'an admin' if new_role == 'admin' else 'a regular user'}.")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
@login_required
@admin_required

def admin_delete_user(user_id):
    if user_id == session.get("user_id"):
        flash("You can't delete your own account.")
        return redirect(url_for("admin_users"))

    delete_user_account(user_id)
    flash("User deleted.")
    return redirect(url_for("admin_users"))

# ---------------- ADMIN: MANAGE MOVIES ----------------

@app.route("/admin/movies")
@login_required
@admin_required
def admin_movies():
    movies = get_all_movies()
    return render_template("admin_movies.html", movies=movies)


@app.route("/admin/movies/add", methods=["GET", "POST"])
@login_required
@admin_required
def admin_add_movie():
    genres = get_all_genres()

    if request.method == "GET":
        return render_template("admin_movie_form.html", movie=None, genres=genres)

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    poster_url = request.form.get("poster_url", "").strip()
    release_year = request.form.get("release_year", "").strip()
    genre_id = request.form.get("genre_id", "")

    if not (title and description and release_year and genre_id):
        flash("Please fill in all required fields.")
        return redirect(url_for("admin_add_movie"))

    if not release_year.isdigit():
        flash("Release year must be a number.")
        return redirect(url_for("admin_add_movie"))

    if not poster_url:
        poster_url = f"https://placehold.co/300x450/1a1a1a/ffffff?text={title.replace(' ', '+')}"

    add_movie(title, description, poster_url, int(release_year), int(genre_id))
    flash(f"'{title}' added.")
    return redirect(url_for("admin_movies"))


@app.route("/admin/movies/edit/<int:movie_id>", methods=["GET", "POST"])
@login_required
@admin_required
def admin_edit_movie(movie_id):
    genres = get_all_genres()

    if request.method == "GET":
        movie = get_movie_by_id(movie_id)
        if not movie:
            flash("Movie not found.")
            return redirect(url_for("admin_movies"))
        return render_template("admin_movie_form.html", movie=movie, genres=genres)

    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    poster_url = request.form.get("poster_url", "").strip()
    release_year = request.form.get("release_year", "").strip()
    genre_id = request.form.get("genre_id", "")

    if not (title and description and release_year and genre_id):
        flash("Please fill in all required fields.")
        return redirect(url_for("admin_edit_movie", movie_id=movie_id))

    if not release_year.isdigit():
        flash("Release year must be a number.")
        return redirect(url_for("admin_edit_movie", movie_id=movie_id))

    if not poster_url:
        poster_url = f"https://placehold.co/300x450/1a1a1a/ffffff?text={title.replace(' ', '+')}"

    update_movie(movie_id, title, description, poster_url, int(release_year), int(genre_id))
    flash(f"'{title}' updated.")
    return redirect(url_for("admin_movies"))


@app.route("/admin/movies/delete/<int:movie_id>", methods=["POST"])
@login_required
@admin_required
def admin_delete_movie(movie_id):
    delete_movie(movie_id)
    flash("Movie deleted.")
    return redirect(url_for("admin_movies"))


if __name__ == "__main__":
    app.run(debug=True)

if __name__ == "__main__":
    app.run(debug=True)