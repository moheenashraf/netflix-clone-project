import os
import re
import uuid
import secrets
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from auth import (
    create_user,
    verify_login,
    get_user_by_id,
    get_user_by_email,
    create_password_reset_token,
    validate_reset_token,
    use_reset_token,
    update_password,
    mark_email_verified,
    get_all_users
)
try:
    from email_check import is_real_email
except ImportError:
    is_real_email = None

from emailer import send_email
from profiles import create_profile, get_profile, update_profile
from movies import (
    get_movies_grouped_by_genre, get_all_movies, get_movie_by_id,
    add_movie, update_movie, delete_movie, get_all_genres, get_trailer_for_movie
)
from logs import add_log, get_all_logs, get_logs_for_user
from watch_history import record_watch, get_recently_watched, get_suggested_movies, get_all_watch_history

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "fallback-secret-key-change-me")

@app.context_processor
def inject_profile():
    if "user_id" in session:
        return {"profile": get_profile(session["user_id"])}
    return {"profile": None}

# Absolute path for uploads inside Flask's root static directory
UPLOAD_FOLDER = os.path.join(app.root_path, "static", "uploads", "posters")
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "jfif", "avif", "gif", "bmp", "svg"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB limit


def is_valid_email_format(email):
    """Reliable email syntax validator."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def is_image_bytes(stream):
    """Detects whether binary stream is a valid image via magic bytes header."""
    try:
        pos = stream.tell()
        header = stream.read(512)
        stream.seek(pos)

        if not header:
            return False, "jpg"

        if header.startswith(b'\xff\xd8\xff') or b'JFIF' in header[:30] or b'Exif' in header[:30]:
            return True, "jpg"
        if header.startswith(b'\x89PNG\r\n\x1a\n'):
            return True, "png"
        if header.startswith(b'GIF87a') or header.startswith(b'GIF89a'):
            return True, "gif"
        if header.startswith(b'RIFF') and b'WEBP' in header[:30]:
            return True, "webp"
        if header.startswith(b'BM'):
            return True, "bmp"
        if b'<svg' in header.lower() or b'<?xml' in header.lower():
            return True, "svg"

        return False, "jpg"
    except Exception:
        return False, "jpg"


def allowed_file(file_storage):
    """Robust image validator checking MIME type, extension, and binary header."""
    if not file_storage:
        return False

    filename = getattr(file_storage, "filename", "") or ""
    mimetype = getattr(file_storage, "mimetype", "") or ""
    content_type = getattr(file_storage, "content_type", "") or ""

    if mimetype.startswith("image/") or content_type.startswith("image/"):
        return True

    if "." in filename:
        ext = filename.rsplit(".", 1)[1].strip().lower()
        if ext in ALLOWED_EXTENSIONS:
            return True

    if hasattr(file_storage, "stream"):
        is_valid_img, _ = is_image_bytes(file_storage.stream)
        if is_valid_img:
            return True

    return False


def save_uploaded_poster(file_storage):
    """Saves an uploaded poster image to absolute root static path."""
    if not file_storage or not file_storage.filename or file_storage.filename == "":
        return None, None

    is_valid_header, detected_ext = is_image_bytes(file_storage.stream)

    if not allowed_file(file_storage) and not is_valid_header:
        return None, f"Invalid image file ({file_storage.filename}). Please upload a valid image."

    try:
        ext = detected_ext
        if "." in file_storage.filename:
            ext = file_storage.filename.rsplit(".", 1)[1].strip().lower()

        original_name = secure_filename(file_storage.filename)
        if not original_name or len(original_name) < 2:
            original_name = f"poster.{ext}"
        elif not original_name.endswith(f".{ext}"):
            original_name = f"{original_name}.{ext}"

        unique_name = f"{uuid.uuid4().hex}_{original_name}"
        save_path = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
        
        file_storage.save(save_path)

        if not os.path.exists(save_path):
            return None, "Upload failed — file did not save to disk."

        poster_url = f"/static/uploads/posters/{unique_name}"
        print(f"[DEBUG SUCCESS] Saved image ({file_storage.filename}) -> {poster_url}")
        return poster_url, None
    except Exception as e:
        print(f"[DEBUG ERROR] Upload error: {e}")
        return None, f"Upload failed: {e}"


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


# ---------------- ERROR HANDLERS ----------------

@app.errorhandler(404)
def page_not_found(e):
    flash("The page you were looking for does not exist.")
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.errorhandler(500)
def internal_server_error(e):
    flash("An unexpected error occurred. Please try again.")
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


# ---------------- HOME ----------------

@app.route("/")
def home():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


# ---------------- SIGNUP ----------------

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "GET":
        return render_template("signup.html")

    email = request.form.get("email", "").strip().lower()

    if not email or not is_valid_email_format(email):
        flash("Please enter a valid email address.")
        return redirect(url_for("signup"))

    existing = get_user_by_email(email)
    
    if existing:
        if existing.get("email_verified"):
            flash("An account with this email already exists and is verified. Please log in.")
            return redirect(url_for("signup"))
        
        user_id = existing["id"]
        print(f"[DEBUG NOTICE] Account for {email} exists but unverified. Re-sending confirmation email.")
    else:
        placeholder_name = email.split("@")[0]
        placeholder_password = secrets.token_urlsafe(24)
        user_id = create_user(placeholder_name, email, placeholder_password)

    if not user_id:
        flash("Could not process account registration. Please try again.")
        return redirect(url_for("signup"))

    token = create_password_reset_token(user_id)
    confirm_link = url_for("set_password", token=token, _external=True)

    sent = send_email(
        email,
        "Confirm your MovieApp account",
        f"""
        <p>Welcome to MovieApp!</p>
        <p>Click the link below to confirm your email and set your password:</p>
        <p><a href="{confirm_link}">{confirm_link}</a></p>
        <p>This link expires in 30 minutes.</p>
        """
    )

    if sent:
        flash("Confirmation link sent! Check your email inbox (and Spam folder).")
        print(f"[DEBUG SUCCESS] Verification email sent to {email}")
    else:
        flash("Account registered, but email delivery failed. Please check your SMTP settings in .env.")
        print(f"[DEBUG ERROR] Failed to send verification email to {email}")

    return redirect(url_for("login"))


@app.route("/set-password/<token>", methods=["GET", "POST"])
def set_password(token):
    user_id = validate_reset_token(token)
    if not user_id:
        flash("This confirmation link is invalid or has expired. Please sign up again.")
        return redirect(url_for("signup"))

    if request.method == "GET":
        return render_template("set_password.html", token=token)

    new_password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if len(new_password) < 6:
        flash("Password must be at least 6 characters.")
        return redirect(url_for("set_password", token=token))

    if new_password != confirm_password:
        flash("Passwords do not match.")
        return redirect(url_for("set_password", token=token))

    update_password(user_id, new_password)
    mark_email_verified(user_id)
    use_reset_token(token)

    user = get_user_by_id(user_id)
    if user:
        add_log(user["name"], "Confirmed email and set password", "Auth", request.remote_addr)
        session["user_id"] = user["id"]
        session["name"] = user["name"]
        session["role"] = user["role"]
        session["profile_completed"] = bool(user["profile_completed"])

    flash("Account confirmed! Let's finish setting up your profile.")
    return redirect(url_for("complete_profile"))


# ---------------- LOGIN & LOGOUT (WITH AUTO-RESEND VERIFICATION) ----------------

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

    if not user.get("email_verified"):
        # Auto re-send verification link on unverified login attempt
        token = create_password_reset_token(user["id"])
        confirm_link = url_for("set_password", token=token, _external=True)
        
        sent = send_email(
            user["email"],
            "Confirm your MovieApp account",
            f"""
            <p>Welcome back to MovieApp!</p>
            <p>Click the link below to confirm your email and set your password:</p>
            <p><a href="{confirm_link}">{confirm_link}</a></p>
            <p>This link expires in 30 minutes.</p>
            """
        )
        
        if sent:
            flash("Your email is not confirmed yet. A NEW confirmation link has just been sent to your email inbox (and Spam folder).")
            print(f"[DEBUG SUCCESS] Re-sent verification link to {user['email']}")
        else:
            flash("Please confirm your email first. We attempted to resend the confirmation email, but sending failed. Check SMTP credentials.")
            print(f"[DEBUG ERROR] Failed to resend verification email to {user['email']}")
        
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
        return render_template("forgot_password.html")

    email = request.form.get("email", "").strip().lower()
    user = get_user_by_email(email)

    if user:
        token = create_password_reset_token(user["id"])
        reset_link = url_for("reset_password", token=token, _external=True)
        send_email(
            email,
            "Reset your MovieApp password",
            f"""
            <p>We received a request to reset your password.</p>
            <p><a href="{reset_link}">{reset_link}</a></p>
            <p>This link expires in 30 minutes. If you didn't request this, you can ignore this email.</p>
            """
        )

    flash("If that email exists, a password reset link has been sent to it.")
    return redirect(url_for("login"))


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


# ---------------- PROFILE MANAGEMENT ----------------

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

    existing_profile = get_profile(session["user_id"])
    if existing_profile:
        update_profile(
            session["user_id"], full_name, phone_number, int(age), gender, int(favorite_genre_id)
        )
    else:
        create_profile(
            session["user_id"], full_name, phone_number, int(age), gender,
            account_email, int(favorite_genre_id)
        )

    session["profile_completed"] = True
    log_action("Completed profile", "Profile")

    flash("Profile completed!")
    return redirect(url_for("dashboard"))


@app.route("/profile")
@app.route("/view-profile")
@login_required
@profile_required
def profile():
    """Route for viewing profile details."""
    profile_data = get_profile(session["user_id"])
    if not profile_data:
        flash("Profile data could not be found. Please complete your profile.")
        return redirect(url_for("complete_profile"))

    try:
        return render_template("profile.html", profile=profile_data)
    except Exception:
        return render_template(
            "dashboard.html", profile=profile_data,
            recently_watched=get_recently_watched(session["user_id"], limit=5),
            suggested=get_suggested_movies(session["user_id"], limit=6)
        )



@app.route("/edit-profile", methods=["GET", "POST"])
@login_required
@profile_required
def edit_profile():
    genres = get_all_genres()

    if request.method == "GET":
        profile_data = get_profile(session["user_id"])

        if not profile_data:
            flash("Profile not found. Please complete your profile.")
            return redirect(url_for("complete_profile"))

        return render_template(
            "edit_profile.html",
            profile=profile_data,
            genres=genres
        )

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

    # ---------------- PROFILE PHOTO ----------------

    profile_photo_url = old_profile.get("profile_photo_url") if old_profile else None

    photo = request.files.get("profile_photo")

    if photo and photo.filename:

        filename = secure_filename(photo.filename)

        extension = filename.rsplit(".", 1)[1].lower()

        new_filename = f"{uuid.uuid4()}.{extension}"

        upload_folder = os.path.join(app.static_folder, "uploads")

        os.makedirs(upload_folder, exist_ok=True)

        photo.save(os.path.join(upload_folder, new_filename))

        profile_photo_url = f"uploads/{new_filename}"

    # ---------------- UPDATE PROFILE ----------------

    update_profile(
        session["user_id"],
        full_name,
        phone_number,
        int(age),
        gender,
        int(favorite_genre_id),
        profile_photo_url
    )

    changes = []

    if old_profile:

        if old_profile.get("full_name") != full_name:
            changes.append(f"name '{old_profile.get('full_name')}' -> '{full_name}'")

        if old_profile.get("phone_number") != phone_number:
            changes.append(f"phone '{old_profile.get('phone_number')}' -> '{phone_number}'")

        if old_profile.get("age") != int(age):
            changes.append(f"age '{old_profile.get('age')}' -> '{age}'")

        if old_profile.get("gender") != gender:
            changes.append(f"gender '{old_profile.get('gender')}' -> '{gender}'")

        if old_profile.get("favorite_genre_id") != int(favorite_genre_id):
            changes.append("favorite genre changed")

    action_text = "Updated profile: " + (
        "; ".join(changes) if changes else "no changes made"
    )

    log_action(action_text, "Profile")

    flash("Profile updated successfully.")

    return redirect(url_for("dashboard"))


@app.route("/dashboard")
@login_required
@profile_required
def dashboard():
    profile_data = get_profile(session["user_id"])
    if not profile_data:
        flash("Profile data not found. Please complete your profile.")
        return redirect(url_for("complete_profile"))

    recently_watched = get_recently_watched(session["user_id"], limit=5)
    suggested = get_suggested_movies(session["user_id"], limit=6)
    return render_template(
        "dashboard.html", profile=profile_data,
        recently_watched=recently_watched, suggested=suggested
    )


@app.route("/browse")
@login_required
@profile_required
def browse():
    genres_with_movies = get_movies_grouped_by_genre()
    return render_template("browse.html", genres_with_movies=genres_with_movies)


@app.route("/movie/<int:movie_id>")
@login_required
@profile_required
def movie_detail(movie_id):
    movie = get_movie_by_id(movie_id)
    if not movie:
        flash("Movie not found.")
        return redirect(url_for("browse"))

    trailer_key = get_trailer_for_movie(movie.get("tmdb_id"))

    try:
        return render_template("movie_detail.html", movie=movie, trailer_key=trailer_key)
    except Exception:
        return render_template("movie_details.html", movie=movie, trailer_key=trailer_key)


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
    return redirect(url_for("movie_detail", movie_id=movie_id))


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


# ---------------- ADMIN ROUTES ----------------

@app.route("/admin/users")
@login_required
@admin_required
def admin_users():
    users = get_all_users()
    return render_template("admin_users.html", users=users)

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

    poster_file = request.files.get("poster_file")
    if poster_file and poster_file.filename != "":
        uploaded_poster_url, upload_error = save_uploaded_poster(poster_file)
        if upload_error:
            flash(f"Poster upload issue: {upload_error}")
            return redirect(url_for("admin_add_movie"))
        if uploaded_poster_url:
            poster_url = uploaded_poster_url

    if not poster_url:
        poster_url = f"https://placehold.co/300x450/1a1a1a/ffffff?text={title.replace(' ', '+')}"

    add_movie(title, description, poster_url, int(release_year), int(genre_id))
    log_action(f"Added movie: {title}", "Movies")
    flash(f"'{title}' added successfully.")
    return redirect(url_for("admin_movies"))


@app.route("/admin/movies/edit/<int:movie_id>", methods=["GET", "POST"])
@login_required
@admin_required
def admin_edit_movie(movie_id):
    genres = get_all_genres()
    old_movie = get_movie_by_id(movie_id)

    if not old_movie:
        flash("Movie not found.")
        return redirect(url_for("admin_movies"))

    if request.method == "GET":
        return render_template("admin_movie_form.html", movie=old_movie, genres=genres)

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

    poster_file = request.files.get("poster_file")
    if poster_file and poster_file.filename != "":
        uploaded_poster_url, upload_error = save_uploaded_poster(poster_file)
        if upload_error:
            flash(f"Poster upload issue: {upload_error}")
            return redirect(url_for("admin_edit_movie", movie_id=movie_id))
        if uploaded_poster_url:
            poster_url = uploaded_poster_url

    if not poster_url:
        poster_url = old_movie.get("poster_url", "")

    update_movie(movie_id, title, description, poster_url, int(release_year), int(genre_id))

    changes = []
    if old_movie.get("title") != title:
        changes.append(f"title '{old_movie.get('title')}' -> '{title}'")
    if old_movie.get("release_year") != int(release_year):
        changes.append(f"year '{old_movie.get('release_year')}' -> '{release_year}'")
    if old_movie.get("genre_id") != int(genre_id):
        changes.append("genre changed")
    if old_movie.get("description") != description:
        changes.append("description changed")
    if old_movie.get("poster_url") != poster_url:
        changes.append("poster changed")

    action_text = f"Edited movie (ID {movie_id}): " + ("; ".join(changes) if changes else "no changes made")
    log_action(action_text, "Movies")
    flash(f"'{title}' updated successfully.")
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