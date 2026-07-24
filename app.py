from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
from dotenv import load_dotenv

from auth import (
    create_user, verify_login, get_user_by_id, get_user_by_email,
    create_password_reset_token, validate_reset_token, use_reset_token, update_password
)
from profiles import create_profile, get_profile, update_profile
from movies import (
    get_movies_grouped_by_genre, get_all_movies, get_movie_by_id,
    add_movie, update_movie, delete_movie, get_all_genres
)
from logs import add_log, get_all_logs, get_logs_for_user
from watch_history import record_watch, get_recently_watched, get_suggested_movies, get_all_watch_history

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


def log_action(action, module):
    add_log(session.get("name", "unknown"), action, module, request.remote_addr)


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

    log_action("Signed up", "Auth")

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

    log_action("Logged in", "Auth")

    flash(f"Welcome back, {user['name']}!")

    if not session["profile_completed"]:
        return redirect(url_for("complete_profile"))
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    flash("You've been logged out.")
    return redirect(url_for("login"))


# ---------------- FORGOT / RESET PASSWORD ----------------

@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("forgot_password.html", reset_link=None)

    email = request.form.get("email", "").strip().lower()
    user = get_user_by_email(email)

    if not user:
        flash("If that email exists, a reset link has been generated below.")
        return render_template("forgot_password.html", reset_link=None)

    token = create_password_reset_token(user["id"])
    reset_link = url_for("reset_password", token=token, _external=True)

    return render_template("forgot_password.html", reset_link=reset_link)


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    user_id = validate_reset_token(token)
    if not user_id:
        flash("This reset link is invalid or has expired. Please request a new one.")
        return redirect(url_for("forgot_password"))

    if request.method == "GET":
        return render_template("reset_password.html", token=token)

    new_password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if len(new_password) < 6:
        flash("Password must be at least 6 characters.")
        return redirect(url_for("reset_password", token=token))

    if new_password != confirm_password:
        flash("Passwords do not match.")
        return redirect(url_for("reset_password", token=token))

    update_password(user_id, new_password)
    use_reset_token(token)

    user = get_user_by_id(user_id)
    if user:
        add_log(user["name"], "Reset password", "Auth", request.remote_addr)

    flash("Password reset successfully. Please log in with your new password.")
    return redirect(url_for("login"))


@app.route("/complete-profile", methods=["GET", "POST"])
@login_required
def complete_profile():
    genres = get_all_genres()

    if request.method == "GET":
        return render_template("complete_profile.html", genres=genres)

    full_name = request.form.get("full_name", "").strip()
    phone_number = request.form.get("phone_number", "").strip()
    age = request.form.get("age", "").strip()
    gender = request.form.get("gender", "")
    favorite_genre_id = request.form.get("favorite_genre_id", "")

    if not (full_name and phone_number and age and gender and favorite_genre_id):
        flash("Please fill in all fields.")
        return redirect(url_for("complete_profile"))

    if not age.isdigit():
        flash("Age must be a number.")
        return redirect(url_for("complete_profile"))

    account = get_user_by_id(session["user_id"])
    account_email = account["email"] if account else ""

    create_profile(
        session["user_id"], full_name, phone_number, int(age), gender,
        account_email, int(favorite_genre_id)
    )
    session["profile_completed"] = True

    log_action("Completed profile", "Profile")

    flash("Profile completed!")
    return redirect(url_for("dashboard"))


@app.route("/dashboard")
@login_required
@profile_required
def dashboard():
    profile = get_profile(session["user_id"])
    recently_watched = get_recently_watched(session["user_id"], limit=5)
    suggested = get_suggested_movies(session["user_id"], limit=6)
    return render_template(
        "dashboard.html", profile=profile,
        recently_watched=recently_watched, suggested=suggested
    )


@app.route("/edit-profile", methods=["GET", "POST"])
@login_required
@profile_required
def edit_profile():
    genres = get_all_genres()

    if request.method == "GET":
        profile = get_profile(session["user_id"])
        return render_template("edit_profile.html", profile=profile, genres=genres)

    full_name = request.form.get("full_name", "").strip()
    phone_number = request.form.get("phone_number", "").strip()
    age = request.form.get("age", "").strip()
    gender = request.form.get("gender", "")
    favorite_genre_id = request.form.get("favorite_genre_id", "")

    if not (full_name and phone_number and age and gender and favorite_genre_id):
        flash("Please fill in all fields.")
        return redirect(url_for("edit_profile"))

    if not age.isdigit():
        flash("Age must be a number.")
        return redirect(url_for("edit_profile"))

    old_profile = get_profile(session["user_id"])

    update_profile(session["user_id"], full_name, phone_number, int(age), gender, int(favorite_genre_id))

    changes = []
    if old_profile:
        if old_profile["full_name"] != full_name:
            changes.append(f"name '{old_profile['full_name']}' -> '{full_name}'")
        if old_profile["phone_number"] != phone_number:
            changes.append(f"phone '{old_profile['phone_number']}' -> '{phone_number}'")
        if old_profile["age"] != int(age):
            changes.append(f"age '{old_profile['age']}' -> '{age}'")
        if old_profile["gender"] != gender:
            changes.append(f"gender '{old_profile['gender']}' -> '{gender}'")
        if old_profile["favorite_genre_id"] != int(favorite_genre_id):
            changes.append("favorite genre changed")

    action_text = "Updated profile: " + ("; ".join(changes) if changes else "no changes made")
    log_action(action_text, "Profile")

    flash("Profile updated successfully.")
    return redirect(url_for("dashboard"))


@app.route("/browse")
@login_required
@profile_required
def browse():
    genres_with_movies = get_movies_grouped_by_genre()
    return render_template("browse.html", genres_with_movies=genres_with_movies)


@app.route("/watch/<int:movie_id>")
@login_required
@profile_required
def watch_movie(movie_id):
    movie = get_movie_by_id(movie_id)
    if not movie:
        flash("Movie not found.")
        return redirect(url_for("browse"))

    record_watch(session["user_id"], movie_id)
    log_action(f"Watched movie: {movie['title']}", "Movies")
    flash(f"Now watching: {movie['title']}")
    return redirect(url_for("browse"))


@app.route("/logs")
@login_required
@profile_required
def logs_page():
    is_admin = session.get("role") == "admin"
    if is_admin:
        logs = get_all_logs()
    else:
        logs = get_logs_for_user(session.get("name"))
    return render_template("logs.html", logs=logs, is_admin=is_admin)


@app.route("/admin/watch-history")
@login_required
@admin_required
def admin_watch_history():
    history = get_all_watch_history()
    return render_template("admin_watch_history.html", history=history)


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
    log_action(f"Added movie: {title}", "Movies")
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

    old_movie = get_movie_by_id(movie_id)

    update_movie(movie_id, title, description, poster_url, int(release_year), int(genre_id))

    changes = []
    if old_movie:
        if old_movie["title"] != title:
            changes.append(f"title '{old_movie['title']}' -> '{title}'")
        if old_movie["release_year"] != int(release_year):
            changes.append(f"year '{old_movie['release_year']}' -> '{release_year}'")
        if old_movie["genre_id"] != int(genre_id):
            changes.append("genre changed")
        if old_movie["description"] != description:
            changes.append("description changed")
        if old_movie["poster_url"] != poster_url:
            changes.append("poster changed")

    action_text = f"Edited movie (ID {movie_id}): " + ("; ".join(changes) if changes else "no changes made")
    log_action(action_text, "Movies")
    flash(f"'{title}' updated.")
    return redirect(url_for("admin_movies"))


@app.route("/admin/movies/delete/<int:movie_id>", methods=["POST"])
@login_required
@admin_required
def admin_delete_movie(movie_id):
    movie = get_movie_by_id(movie_id)
    title = movie["title"] if movie else f"ID {movie_id}"
    delete_movie(movie_id)
    log_action(f"Deleted movie: {title}", "Movies")
    flash("Movie deleted.")
    return redirect(url_for("admin_movies"))


if __name__ == "__main__":
    app.run(debug=True)