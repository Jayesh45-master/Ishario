from dotenv import load_dotenv
load_dotenv()
# log.py
import os
import io
import random
import string
import sys
import time
import threading
import json
from collections import Counter, deque
from pathlib import Path
import numpy as np
import mysql.connector
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, send_from_directory

try:
    import cv2
except ImportError:
    cv2 = None

try:
    from flask_mail import Mail, Message
except ImportError:
    Mail = None
    Message = None

from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

try:
    import mediapipe as mp
except ImportError:
    mp = None

try:
    import tensorflow as tf
except ImportError:
    tf = None

import base64

import requests

# ---------- App Directory + .env ----------
# Ensure local packages (e.g. `ishario/`) are importable even when this file is executed via runpy or other loaders.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Load .env from repo root (preferred) and app folder (fallback). Do not override real env vars.
load_dotenv(dotenv_path=Path(BASE_DIR).parent / ".env", override=False)
load_dotenv(dotenv_path=Path(BASE_DIR) / ".env", override=False)
load_dotenv(override=False)
from ishario.db import (
    DbUnavailable,
    connect_mysql,
    db_unavailable_json,
    env_db_config,
    is_schema_or_auth_error,
)

# ---------- Initialize Flask App ----------
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(24)

# ---------- Mail Configuration ----------
# Recommended: set these as environment variables instead of hardcoding
MAIL_USERNAME = os.environ.get("MAIL_USERNAME") or ""
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD") or ""

app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USERNAME=MAIL_USERNAME,
    MAIL_PASSWORD=MAIL_PASSWORD,
    MAIL_USE_TLS=True,
    MAIL_USE_SSL=False,
    MAIL_DEFAULT_SENDER=MAIL_USERNAME
)
mail = Mail(app) if Mail else None
if mail is None:
    print("[WARN] flask_mail is not installed; email features are disabled.")
elif not MAIL_USERNAME or not MAIL_PASSWORD:
    print("[WARN] MAIL_USERNAME/MAIL_PASSWORD not set; OTP email sending will fail until configured.")

# ---------- Database Configuration ----------
ISHARIO_DB_CONFIG = env_db_config("ISHARIO_DB")
SIGNEASE_DB_CONFIG = env_db_config("SIGNEASE_DB")
DB_SETUP_HINT = "Set ISHARIO_DB_* and SIGNEASE_DB_* env vars and run: python scripts/init_mysql.py"

# ---------- Sign Images Folder ----------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SIGNS_FOLDER = os.path.join(BASE_DIR, "static", "signs")
PROFILE_PHOTOS_DIR = os.path.join(BASE_DIR, "static", "profile_photos")
os.makedirs(SIGNS_FOLDER, exist_ok=True)
os.makedirs(PROFILE_PHOTOS_DIR, exist_ok=True)

ALLOWED_SIGN_EXTS = {"png", "jpg", "jpeg", "bmp", "gif"}

# ---------- Database Helper ----------
def get_db_connection(db_config=ISHARIO_DB_CONFIG, db_label: str = "ISHARIO_DB"):
    return connect_mysql(db_config, db_label=db_label)


def _db_unavailable_response(e: DbUnavailable):
    return jsonify(db_unavailable_json(e)), 503


def _db_problem_response(db_label: str, err: BaseException):
    if isinstance(err, DbUnavailable):
        return _db_unavailable_response(err)
    if is_schema_or_auth_error(err):
        return jsonify({"error": "db_unavailable", "db": db_label, "hint": DB_SETUP_HINT}), 503
    return jsonify({"error": "db_error", "db": db_label}), 500

# ---------- Profile Table Ensure ----------
def ensure_profiles_table_exists():
    try:
        conn = get_db_connection(ISHARIO_DB_CONFIG, "ISHARIO_DB")
        cursor = conn.cursor()
        create_sql = """
        CREATE TABLE IF NOT EXISTS profiles (
          id INT AUTO_INCREMENT PRIMARY KEY,
          user_id INT NULL,
          email VARCHAR(255) NOT NULL UNIQUE,
          first_name VARCHAR(100),
          last_name VARCHAR(100),
          alt_email VARCHAR(255),
          contact VARCHAR(30),
          username VARCHAR(100),
          dob DATE,
          about TEXT,
          photo LONGBLOB,
          photo_mime VARCHAR(100),
          photo_filename VARCHAR(255),
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        );
        """
        cursor.execute(create_sql)
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[WARN] Could not ensure profiles table exists (DB not reachable?): {e}")

# ---------- Helpers ----------
def get_logged_in_email():
    return session.get("email")

def fetch_sign_images():
    try:
        db = get_db_connection(SIGNEASE_DB_CONFIG, "SIGNEASE_DB")
        cursor = db.cursor()
        cursor.execute("SELECT image_data, sign_name FROM sign_images")
        images = cursor.fetchall()
        cursor.close()
        db.close()
        return images
    except Exception as e:
        print(f"[WARN] Could not fetch sign images: {e}")
        return []

def convert_blob_to_image(blob_data):
    if cv2 is None:
        return None
    try:
        image_array = np.frombuffer(blob_data, dtype=np.uint8)
        # Try color decode first, fallback to grayscale
        img = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if img is None:
            img = cv2.imdecode(image_array, cv2.IMREAD_GRAYSCALE)
        return img
    except Exception as e:
        print("Error converting blob to image:", e)
        return None

# ---------- Load Model with Error Handling ----------
def _strip_keras3_compat_fields(value):
    if isinstance(value, dict):
        cleaned = {}
        for key, child in value.items():
            if key in {"quantization_config", "optional"} and child is None:
                continue
            if key == "optional":
                continue
            cleaned[key] = _strip_keras3_compat_fields(child)
        return cleaned
    if isinstance(value, list):
        return [_strip_keras3_compat_fields(item) for item in value]
    return value


def _load_model_with_compat(model_path: str):
    try:
        return tf.keras.models.load_model(model_path, compile=False)
    except Exception as load_error:
        compat_markers = ("quantization_config", "optional", "batch_shape")
        if not any(marker in str(load_error) for marker in compat_markers):
            raise

        try:
            import h5py
        except ImportError:
            raise load_error

        with h5py.File(model_path, "r") as handle:
            model_config_raw = handle.attrs.get("model_config")
            if not model_config_raw:
                raise load_error
            if isinstance(model_config_raw, bytes):
                model_config_raw = model_config_raw.decode("utf-8")
            model_config = json.loads(model_config_raw)
            model_config = _strip_keras3_compat_fields(model_config)

        model = tf.keras.models.model_from_json(
            json.dumps(model_config),
            custom_objects={
                "Sequential": tf.keras.Sequential,
                "DTypePolicy": tf.keras.mixed_precision.Policy,
            },
        )
        model.load_weights(model_path)
        return model


model = None
if tf is None:
    print("[WARN] TensorFlow is not installed; ML prediction endpoints will be disabled.")
else:
    configured_path = os.environ.get("ISHARIO_MODEL_PATH") or ""
    candidates = [
        configured_path,
        os.path.join(os.getcwd(), "model.h5"),
        os.path.join(BASE_DIR, "model.h5"),
        os.path.abspath(os.path.join(BASE_DIR, "..", "model.h5")),
    ]
    candidates = [p for p in candidates if p]
    model_path = next((p for p in candidates if os.path.exists(p)), "")

    if not model_path:
        print("[WARN] Model not found. Set ISHARIO_MODEL_PATH or place model.h5 in the app folder (or repo root).")
        model = None
    else:
        try:
            model = _load_model_with_compat(model_path)
            print(f"[OK] Model loaded successfully from {model_path}")
        except Exception as e:
            print(f"[ERROR] Failed to load model at {model_path}: {e}")
            print("Suggestion: retrain using train_model.py, or set ISHARIO_MODEL_PATH to a valid model path.")
            model = None

labels = ["Hello","Thank You","Yes","No","Help","Good","Goodbye","Please"]

# ---------- Initialize MediaPipe Hands ----------
mp_hands = None
hands = None

if mp is None:
    print("[WARN] MediaPipe is not installed; hand tracking will be skipped.")
else:
    try:
        import importlib.util
        # Prefer stable import paths across different MediaPipe distributions.
        try:
            if hasattr(mp, "solutions"):
                mp_hands = mp.solutions.hands  # type: ignore[attr-defined]
        except Exception:
            mp_hands = None

        if mp_hands is None and importlib.util.find_spec("mediapipe.python.solutions.hands"):
            from mediapipe.python.solutions import hands as mp_hands_solution
            mp_hands = mp_hands_solution

        if mp_hands is None:
            raise ImportError("MediaPipe Hands module not found")

        hands = mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.7
        )
        print("[OK] MediaPipe hands tracking initialized")
    except Exception as e:
        print(f"[WARN] MediaPipe hands not available: {e}")
        print("[WARN] Hand tracking will be skipped, but prediction endpoint may still work")
        hands = None

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or ""
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL") or "https://api.openai.com/v1"
OPENAI_MODEL = os.environ.get("OPENAI_MODEL") or "gpt-4o-mini"

LIVE_STATE = {}
CHAT_STATE = {}
STATE_LOCK = threading.Lock()


def _get_client_id() -> str:
    client_id = session.get("client_id")
    if not client_id:
        client_id = os.urandom(16).hex()
        session["client_id"] = client_id
    return client_id


def _get_state(bucket: dict, client_id: str, factory):
    now = time.time()
    with STATE_LOCK:
        state = bucket.get(client_id)
        if state is None:
            state = factory()
            bucket[client_id] = state
        state["last_seen"] = now
        # Best-effort cleanup
        if len(bucket) > 500:
            stale = [k for k, v in bucket.items() if now - v.get("last_seen", now) > 1800]
            for k in stale[:200]:
                bucket.pop(k, None)
    return state


def _decode_image_payload(image_b64: str):
    if not image_b64:
        raise ValueError("Missing image")
    if "," in image_b64 and image_b64.strip().lower().startswith("data:image"):
        image_b64 = image_b64.split(",", 1)[1]
    img_bytes = base64.b64decode(image_b64)
    nparr = np.frombuffer(img_bytes, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Invalid image payload")
    return frame


def _hand_bbox_from_landmarks(landmarks, w: int, h: int, margin: float = 0.18):
    xs = [lm.x for lm in landmarks]
    ys = [lm.y for lm in landmarks]
    x1 = max(min(xs) - margin, 0.0)
    y1 = max(min(ys) - margin, 0.0)
    x2 = min(max(xs) + margin, 1.0)
    y2 = min(max(ys) + margin, 1.0)
    return int(x1 * w), int(y1 * h), int(x2 * w), int(y2 * h)


def _predict_frame(frame):
    # Returns (label, confidence, note)
    if model is None:
        raise RuntimeError("Model not loaded")

    roi = frame
    note = "full_frame"

    if hands is not None:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)
        if results.multi_hand_landmarks:
            h, w = frame.shape[:2]
            x1, y1, x2, y2 = _hand_bbox_from_landmarks(results.multi_hand_landmarks[0], w, h)
            if x2 > x1 and y2 > y1:
                roi = frame[y1:y2, x1:x2]
                note = "hand_roi"

    img = cv2.resize(roi, (64, 64))
    img = img / 255.0
    img = np.expand_dims(img, axis=0)

    prediction = model.predict(img, verbose=0)[0]
    idx = int(np.argmax(prediction))
    conf = float(prediction[idx])
    label = labels[idx] if 0 <= idx < len(labels) else str(idx)
    return label, conf, note


def _live_factory():
    return {
        "preds": deque(maxlen=10),  # list[(label, conf)]
        "stable": None,
        "stable_since": 0.0,
        "text": "",
        "last_append": 0.0,
        "last_seen": 0.0,
    }


def _update_live_state(state, label: str, conf: float):
    now = time.time()
    min_conf = float(os.environ.get("LIVE_MIN_CONF", "0.60"))
    state["preds"].append((label, conf))

    recent = [(l, c) for (l, c) in state["preds"] if c >= min_conf]
    if not recent:
        return {"stable": None, "stable_conf": 0.0, "text": state["text"]}

    counts = Counter(l for (l, _) in recent)
    stable_label, stable_count = counts.most_common(1)[0]
    stable_conf = sum(c for (l, c) in recent if l == stable_label) / max(1, sum(1 for (l, c) in recent if l == stable_label))

    if state["stable"] != stable_label:
        state["stable"] = stable_label
        state["stable_since"] = now

    # Debounced text building
    debounce_s = float(os.environ.get("LIVE_DEBOUNCE_S", "0.9"))
    hold_s = float(os.environ.get("LIVE_HOLD_S", "0.6"))
    if now - state["stable_since"] >= hold_s and now - state["last_append"] >= debounce_s:
        state["text"] = (state["text"] + " " + stable_label).strip()
        state["last_append"] = now

    return {"stable": stable_label, "stable_conf": float(stable_conf), "text": state["text"]}

@app.route("/predict", methods=["POST"])
def predict():
    if model is None:
        return jsonify({"error": "model_not_loaded", "hint": "Set ISHARIO_MODEL_PATH or place model.h5 next to the app."}), 503
    if cv2 is None:
        return jsonify({"error": "opencv_missing", "hint": "Install opencv-python."}), 503

    payload = request.get_json(silent=True) or {}
    image_b64 = payload.get("image") or ""

    try:
        frame = _decode_image_payload(image_b64)
    except Exception as e:
        return jsonify({"error": "bad_image", "detail": str(e)}), 400

    try:
        label, conf, note = _predict_frame(frame)
    except Exception as e:
        return jsonify({"error": "predict_failed", "detail": str(e)}), 500

    client_id = _get_client_id()
    live_state = _get_state(LIVE_STATE, client_id, _live_factory)
    stable = _update_live_state(live_state, label, conf)

    return jsonify(
        {
            "gesture": label,
            "confidence": conf,
            "note": note,
            "stable_gesture": stable.get("stable"),
            "stable_confidence": stable.get("stable_conf"),
            "text": stable.get("text", ""),
        }
    )


@app.route("/api/live/reset", methods=["POST"])
def live_reset():
    client_id = _get_client_id()
    with STATE_LOCK:
        LIVE_STATE.pop(client_id, None)
    return jsonify({"ok": True})


def _chat_factory():
    return {"messages": deque(maxlen=20), "last_seen": 0.0}


def _openai_chat(messages):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY not set")

    url = f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "temperature": 0.2,
    }
    resp = requests.post(url, headers=headers, json=body, timeout=25)
    if resp.status_code != 200:
        raise RuntimeError(f"OpenAI error {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    return (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()


@app.route("/api/chat", methods=["POST"])
def api_chat():
    payload = request.get_json(silent=True) or {}
    message = (payload.get("message") or "").strip()
    if not message:
        return jsonify({"error": "missing_message"}), 400

    if not OPENAI_API_KEY:
        return jsonify({"error": "openai_not_configured", "hint": "Set OPENAI_API_KEY (and optionally OPENAI_MODEL)."}), 503

    client_id = _get_client_id()
    chat_state = _get_state(CHAT_STATE, client_id, _chat_factory)

    system_prompt = (
        "You are Ishario AI Tutor, a helpful assistant that teaches sign language and helps users navigate Ishario. "
        "Be concise, practical, and friendly. If the user asks for a sign, describe the gesture step-by-step in text."
    )

    history = list(chat_state["messages"])
    messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": message}]

    try:
        reply = _openai_chat(messages)
        if not reply:
            reply = "I couldn't generate a response right now. Please try again."
    except Exception as e:
        return jsonify({"error": "chat_failed", "detail": str(e)}), 500

    chat_state["messages"].append({"role": "user", "content": message})
    chat_state["messages"].append({"role": "assistant", "content": reply})

    # Best-effort persistence (optional DB)
    user_email = get_logged_in_email()
    if user_email:
        try:
            conn = get_db_connection(ISHARIO_DB_CONFIG, "ISHARIO_DB")
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO chat_messages (user_email, role, content) VALUES (%s, %s, %s)",
                (user_email, "user", message),
            )
            cursor.execute(
                "INSERT INTO chat_messages (user_email, role, content) VALUES (%s, %s, %s)",
                (user_email, "assistant", reply),
            )
            conn.commit()
            cursor.close()
            conn.close()
        except Exception:
            pass

    return jsonify({"reply": reply})

def get_sign_image(word):
    # 1) Check local static folder for common extensions
    for ext in ["png", "jpg", "jpeg", "bmp", "gif"]:
        image_filename = f"{word}.{ext}"
        image_path = os.path.join(SIGNS_FOLDER, image_filename)
        if os.path.exists(image_path):
            return image_filename

    # 2) Fallback to DB
    try:
        db = get_db_connection(SIGNEASE_DB_CONFIG, "SIGNEASE_DB")
        cursor = db.cursor()
        cursor.execute("SELECT image_data FROM sign_images WHERE sign_name = %s", (word,))
        result = cursor.fetchone()
        cursor.close()
        db.close()
    except Exception as e:
        print(f"[WARN] Could not fetch sign image '{word}' from DB: {e}")
        return None
    if result:
        image_filename = f"{word}.png"
        image_path = os.path.join(SIGNS_FOLDER, image_filename)
        image = convert_blob_to_image(result[0])
        if image is not None:
            # If grayscale or color, write appropriate
            success = cv2.imwrite(image_path, image)
            if success:
                return image_filename
    return None

def match_sign(uploaded_image):
    # ORB-based matching with DB images
    orb = cv2.ORB_create()
    uploaded_gray = cv2.cvtColor(uploaded_image, cv2.COLOR_BGR2GRAY)
    kp1, des1 = orb.detectAndCompute(uploaded_gray, None)
    if des1 is None or len(kp1) < 10:
        return None

    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    best_match = None
    best_score = 0
    MATCH_THRESHOLD = 50

    for blob, text in fetch_sign_images():
        db_image = convert_blob_to_image(blob)
        if db_image is None:
            continue
        # Ensure descriptors computed on same channel type (grayscale)
        if len(db_image.shape) == 3:
            db_gray = cv2.cvtColor(db_image, cv2.COLOR_BGR2GRAY)
        else:
            db_gray = db_image
        kp2, des2 = orb.detectAndCompute(db_gray, None)
        if des2 is None or len(kp2) < 10:
            continue
        try:
            matches = bf.match(des1, des2)
            score = len(matches)
            if score > best_score and score > MATCH_THRESHOLD:
                best_score = score
                best_match = text
        except Exception:
            continue

    return best_match if best_match else None

# ---------- Authentication Routes ----------
@app.route('/singinpage.html')
def singinpage():
    return render_template('singinpage.html')

@app.route('/dashboard')
def dashboard():
    if 'email' not in session:
        return redirect(url_for('home'))

    email = session['email']
    try:
        conn = get_db_connection(SIGNEASE_DB_CONFIG, "SIGNEASE_DB")
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT first_name FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
    except Exception:
        return redirect(url_for('home'))

    if not user:
        return redirect(url_for('home'))

    return render_template('dashboard.html', name=user['first_name'])

SIGN_FOLDER = os.path.join('static', 'signs')

@app.route('/api/login', methods=['POST'])
def login():
    email = request.json.get('email')
    password = request.json.get('password')
    try:
        conn = get_db_connection(SIGNEASE_DB_CONFIG, "SIGNEASE_DB")
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
    except Exception as e:
        return _db_problem_response("SIGNEASE_DB", e)
    if user and check_password_hash(user['password_hash'], password):
        session['email'] = user['email']
        session['first_name'] = user.get('first_name')
        session['user_id'] = user.get('id')
        return jsonify({
            "message": "Login successful!", 
            "redirect": "/dashboard",
            "clearCompletionFlags": True
        })
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/signup', methods=['POST'])
def signup():
    first_name = request.form.get('first_name') or request.form.get('firstName')
    last_name = request.form.get('last_name') or request.form.get('lastName')
    username = request.form.get('username')
    email = request.form.get('email')
    contact = request.form.get('contact')
    password = request.form.get('password')

    if not email or not password or not username:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        conn = get_db_connection(SIGNEASE_DB_CONFIG, "SIGNEASE_DB")
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "Email already registered"}), 400
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "Username already taken"}), 400

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        cursor.execute("""
            INSERT INTO users (first_name, last_name, username, email, contact, password_hash)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (first_name, last_name, username, email, contact, hashed_password))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "Account created successfully!"}), 201
    except Exception as e:
        return _db_problem_response("SIGNEASE_DB", e)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

# ---------- Password Reset & OTP Routes ----------
@app.route("/send-otp", methods=["POST"])
def send_otp():
    email = request.form.get("email")
    if not email:
        return jsonify({"error": "Please provide email"}), 400

    if mail is None or Message is None:
        return jsonify({"error": "mail_unavailable", "hint": "Configure MAIL_USERNAME/MAIL_PASSWORD or install Flask-Mail."}), 503

    try:
        conn = get_db_connection(SIGNEASE_DB_CONFIG, "SIGNEASE_DB")
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        if not user:
            cursor.close()
            conn.close()
            return jsonify({"error": "Email not registered"}), 404
    except Exception as e:
        return _db_problem_response("SIGNEASE_DB", e)

    otp = ''.join(random.choices(string.digits, k=6))
    try:
        cursor.execute("UPDATE users SET otp = %s WHERE email = %s", (otp, email))
        conn.commit()
    except Exception as e:
        cursor.close()
        conn.close()
        if is_schema_or_auth_error(e):
            return _db_problem_response("SIGNEASE_DB", e)
        print("DB error while saving OTP:", e)
        return jsonify({"error": "Internal DB error"}), 500

    # Prepare and send email
    msg = Message("Password Reset OTP", recipients=[email])
    msg.body = f"Your OTP is: {otp}"

    try:
        mail.send(msg)
    except Exception as e:
        # If mail failed, don't leak sensitive internal info, but log it
        print(f"Error sending OTP to {email}: {e}")
        cursor.close()
        conn.close()
        return jsonify({"error": "Failed to send OTP email. Check mail configuration."}), 500

    # Close DB after successful mail send
    cursor.close()
    conn.close()

    session["reset_email"] = email
    return jsonify({"message": "OTP sent successfully"}), 200

@app.route("/verifyotp", methods=["POST"])
def verifyotp():
    entered_otp = request.form.get("otp")
    email = session.get("reset_email")
    if not entered_otp or not email:
        return jsonify({"error": "OTP or session missing"}), 400

    try:
        conn = get_db_connection(SIGNEASE_DB_CONFIG, "SIGNEASE_DB")
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT otp FROM users WHERE email = %s", (email,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()
    except Exception as e:
        return _db_problem_response("SIGNEASE_DB", e)

    if row and row.get("otp") == entered_otp:
        return jsonify({"message": "OTP verified"}), 200
    return jsonify({"error": "Invalid OTP"}), 400

# ---------- Set New Password After OTP Verification ----------
@app.route('/reset-password', methods=['POST'])
def resetpassword():
    """
    Expects JSON:
    {
        "email": "user@example.com",
        "otp": "123456",
        "new_password": "NewPass@123"
    }
    """
    data = request.get_json()
    email = data.get('email')
    otp = data.get('otp')
    new_password = data.get('new_password')

    if not email or not otp or not new_password:
        return jsonify({"error": "Missing required fields"}), 400

    try:
        conn = get_db_connection(SIGNEASE_DB_CONFIG, "SIGNEASE_DB")
        cursor = conn.cursor(dictionary=True)

        # Check if user exists and OTP matches
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()
        if not user:
            cursor.close()
            conn.close()
            return jsonify({"error": "Email not found"}), 404

        if user.get("otp") != otp:
            cursor.close()
            conn.close()
            return jsonify({"error": "Invalid OTP"}), 400

        # Hash the new password and update
        hashed_password = generate_password_hash(new_password, method='pbkdf2:sha256')
        cursor.execute(
            "UPDATE users SET password_hash = %s, otp = NULL WHERE email = %s",
            (hashed_password, email)
        )
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Password updated successfully!"}), 200
    except Exception as e:
        return _db_problem_response("SIGNEASE_DB", e)

# ---------- Profile API ----------
@app.route("/api/profile", methods=["POST"])
def api_save_profile():
    email = get_logged_in_email()
    if not email:
        return jsonify({"error": "Not authenticated"}), 401

    first_name = request.form.get("firstName") or request.form.get("first_name")
    last_name = request.form.get("lastName") or request.form.get("last_name")
    alt_email = request.form.get("altEmail") or request.form.get("alt_email")
    contact = request.form.get("contact")
    username = request.form.get("username")
    dob = request.form.get("dob")
    about = request.form.get("about")
    file = request.files.get("photo")

    photo_blob = photo_mime = photo_filename = None
    if file and file.filename:
        secure_name = secure_filename(file.filename)
        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        photo_filename = f"{timestamp}_{secure_name}"
        save_path = os.path.join(PROFILE_PHOTOS_DIR, photo_filename)
        file.save(save_path)
        # read binary for DB
        file.stream.seek(0)
        photo_blob = file.read()
        photo_mime = file.mimetype

    try:
        conn = get_db_connection(ISHARIO_DB_CONFIG, "ISHARIO_DB")
        cursor = conn.cursor()
        sql = """
        INSERT INTO profiles (email, first_name, last_name, alt_email, contact, username, dob, about, photo, photo_mime, photo_filename)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            first_name = VALUES(first_name),
            last_name = VALUES(last_name),
            alt_email = VALUES(alt_email),
            contact = VALUES(contact),
            username = VALUES(username),
            dob = VALUES(dob),
            about = VALUES(about),
            photo = VALUES(photo),
            photo_mime = VALUES(photo_mime),
            photo_filename = VALUES(photo_filename),
            updated_at = CURRENT_TIMESTAMP
        """
        cursor.execute(sql, (
            email, first_name, last_name, alt_email, contact, username, dob if dob else None,
            about, photo_blob, photo_mime, photo_filename
        ))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({"message": "Profile saved successfully"}), 200
    except Exception as e:
        return _db_problem_response("ISHARIO_DB", e)

# ---------- Other Routes ----------
@app.route('/profile')
def profile():
    return render_template("profile.html")

@app.route("/profile/photo/<filename>")
def serve_profile_photo(filename):
    file_path = os.path.join(PROFILE_PHOTOS_DIR, filename)
    if os.path.exists(file_path):
        return redirect(f"/static/profile_photos/{filename}")
    return "", 404



# Serve static files
@app.route('/static/signs/<path:filename>')
def serve_sign(filename):
    return send_from_directory(SIGNS_FOLDER, filename)

@app.route('/')
def home():
    return render_template('scrollingpage.html')

@app.route('/videos')
def videos():
    return render_template('videos.html')

@app.route('/conversion')
def conversion():
    return render_template('conversion.html')

@app.route('/advanced')
def advanced():
    return render_template('advanced.html')

@app.route('/basics')
def basics():
    return render_template('basics.html')

@app.route('/daily_life')
def daily_life():
    return render_template('daily_life.html')

@app.route('/favorites')
def favorites():
    return render_template('favorites.html')

@app.route('/feedback')
def feedback():
    return render_template('feedback.html')

@app.route('/games')
def games():
    return render_template('games.html')



@app.route('/progress')
def progress():
    return render_template('progress.html')

@app.route('/sign_match')
def sign_match():
    return render_template('sign_match.html')

@app.route('/speed_sign')
def speed_sign():
    return render_template('speed_sign.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/themed_quiz')
def themed_quiz():
    return render_template('themed_quiz.html')

@app.route('/live')
def live():
    return render_template('live.html')

# ---------- Text-to-Sign API ----------
@app.route('/text-to-sign', methods=['POST'])
def text_to_sign():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON provided"}), 400
    text = data.get("text", "").strip().lower()
    words = text.split()
    images = []
    for word in words:
        img = get_sign_image(word)
        if img:
            images.append(img)
        else:
            for letter in word:
                letter_img = get_sign_image(letter)
                if letter_img:
                    images.append(letter_img)
    if images:
        return jsonify({"images": images})
    return jsonify({"error": "Sign not found"}), 404

# ---------- Sign-to-Text API ----------
@app.route('/signtotext', methods=['POST'])
def sign_to_text():
    if 'files' not in request.files:
        return jsonify({"error": "No files provided"}), 400
    files = request.files.getlist('files')
    recognized_texts = []
    for file in files:
        if file.filename == '':
            continue
        file_bytes = np.frombuffer(file.read(), np.uint8)
        uploaded_image = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
        if uploaded_image is None:
            continue
        recognized_text = match_sign(uploaded_image)
        if recognized_text:
            recognized_texts.append(recognized_text)
    if not recognized_texts:
        return jsonify({"error": "No valid images processed"}), 400
    return jsonify({"text": " ".join(recognized_texts)}), 200

# ---------- Chatbot API ----------
@app.route('/chatbot', methods=['POST'])
def chatbot():
    """
    Expects JSON:
    {
        "message": "User's message"
    }
    Returns:
    {
        "reply": "Chatbot's reply"
    }
    """
    data = request.get_json()
    user_message = data.get('message', '').strip()
    if not user_message:
        return jsonify({"error": "No message provided"}), 400

    # Placeholder logic: echo or simple response
    # Replace with real AI model or API call
    if 'hello' in user_message.lower():
        reply = "Hello! How can I assist you with sign language today?"
    elif 'help' in user_message.lower():
        reply = "Sure, I can help. Ask me about signs, tutorials, or your progress."
    else:
        reply = f"You said: {user_message} (Chatbot logic to be improved)"

    return jsonify({"reply": reply})
# ---------- Run App ----------
if __name__ == "__main__":
    # DEBUG only: ensure mail creds provided
    if app.config['MAIL_USERNAME'] == "your_email@gmail.com" or app.config['MAIL_PASSWORD'] == "your_app_specific_password":
        print("WARNING: Mail username/password look like defaults. Set environment vars MAIL_USERNAME and MAIL_PASSWORD with real credentials.")

    # Best-effort DB bootstrap (never fatal)
    ensure_profiles_table_exists()
    
    # Show startup status
    print("\n" + "=" * 60)
    print("Ishario Flask Application Startup Status")
    print("=" * 60)
    print("[OK] Flask app initialized")
    print(f"[{'OK' if model else 'WARN'}] TensorFlow Model: {'Loaded' if model else 'NOT LOADED - Run: python train_model.py'}")
    print(f"[{'OK' if hands else 'WARN'}] MediaPipe Hands: {'Ready' if hands else 'NOT INITIALIZED'}")
    print("=" * 60 + "\n")
    
    app.run(debug=True)







