# Ishario - Monika Branch Technical Documentation

Ishario is a Flask-based sign-language learning and interaction platform built around two core ideas:

- a learner-facing web application for authentication, profile management, text/sign conversion, live webcam-based gesture recognition, and AI-assisted guidance
- an admin dashboard for monitoring users, feedback, and platform activity

This `monika` branch includes the stabilized local-development setup, MySQL bootstrap tooling, `.env`-driven configuration, OpenAI-backed chat support, MediaPipe-assisted live recognition, and a dataset-constrained live gesture matching pipeline.

## Table of Contents

- [What This Branch Implements](#what-this-branch-implements)
- [Architecture Overview](#architecture-overview)
- [Project Structure](#project-structure)
- [Technology Stack](#technology-stack)
- [Application Features](#application-features)
- [Live Gesture Recognition Pipeline](#live-gesture-recognition-pipeline)
- [AI Tutor / Chatbot](#ai-tutor--chatbot)
- [Database Design](#database-design)
- [Environment Configuration](#environment-configuration)
- [Local Setup](#local-setup)
- [Running the Project](#running-the-project)
- [HTTP Routes and APIs](#http-routes-and-apis)
- [Model Training](#model-training)
- [Admin Panel](#admin-panel)
- [Implementation Notes for This Branch](#implementation-notes-for-this-branch)
- [Troubleshooting](#troubleshooting)
- [Current Limitations](#current-limitations)

## What This Branch Implements

The `monika` branch adds and stabilizes the following:

- `.env`-based configuration loading from the repository root
- MySQL initialization via `scripts/init_mysql.py`
- dual-database setup:
  - `ishario_db` for admin, profiles, feedback, gesture/chat history
  - `signease` for learner authentication and sign-image storage
- safer database connection helpers in `Ishario-main/ishario/db.py`
- AI Tutor backend endpoint using the OpenAI Chat Completions API
- MediaPipe Hands integration for live webcam preprocessing
- dataset-only live sign recognition using similarity matching against local sign images
- compatibility loading for `model.h5` generated across nearby Keras versions
- live recognition guardrails:
  - no random guessing outside the dataset
  - threshold-based rejection
  - `"No Sign Detected"` fallback for uncertain input

## Architecture Overview

The project is organized around two Flask applications:

### 1. Learner Application

File: `Ishario-main/app.py`

Responsibilities:

- learner authentication and signup
- OTP-based password reset
- profile storage
- text-to-sign conversion
- sign-to-text image matching
- live webcam sign recognition
- AI Tutor chat experience
- learner-facing static pages and templates

### 2. Admin Application

File: `Ishario-main/admin.py`

Responsibilities:

- admin login
- dashboard statistics
- user management
- feedback management
- admin password update

## Project Structure

```text
Ishario-main/
├── .env.example
├── environment.yml
├── model.h5
├── model.h5.bak
├── db/
│   ├── ishario_db.sql
│   └── signease.sql
├── scripts/
│   └── init_mysql.py
└── Ishario-main/
    ├── app.py
    ├── admin.py
    ├── train_model.py
    ├── requirements.txt
    ├── ishario/
    │   ├── __init__.py
    │   └── db.py
    ├── static/
    │   ├── js/
    │   ├── profile_photos/
    │   └── signs/
    └── templates/
        ├── dashboard.html
        ├── live.html
        ├── profile.html
        ├── conversion.html
        ├── sign_match.html
        ├── singinpage.html
        └── admin/
```

## Technology Stack

### Backend

- Python 3.10
- Flask
- Flask-Mail
- MySQL Connector/Python
- python-dotenv
- requests

### Computer Vision / ML

- TensorFlow `2.17.0`
- Keras `3.12.1`
- OpenCV `4.9.0.80`
- MediaPipe `0.10.14`
- NumPy `1.26.4`
- h5py `3.11.0`

### Admin Utilities

- Flask-Bcrypt
- Flask-CORS
- Flask-JWT-Extended

## Application Features

### Learner Features

- user signup and login
- password reset with OTP
- dashboard landing page after authentication
- profile create/update with photo upload
- text-to-sign conversion using local/static or database-backed sign images
- sign-to-text conversion for uploaded sign images using ORB matching
- live webcam-based gesture recognition
- AI Tutor chat powered by OpenAI

### Static Pages / Learning Views

Templates include:

- `scrollingpage.html`
- `videos.html`
- `conversion.html`
- `advanced.html`
- `basics.html`
- `daily_life.html`
- `favorites.html`
- `feedback.html`
- `games.html`
- `progress.html`
- `sign_match.html`
- `speed_sign.html`
- `terms.html`
- `themed_quiz.html`
- `live.html`
- `profile.html`

## Live Gesture Recognition Pipeline

This branch implements a stricter live recognition flow in `Ishario-main/app.py`.

### Goal

The live system must recognize gestures only from the predefined dataset stored in `Ishario-main/static/signs`.

### Pipeline

1. The browser captures a webcam frame and sends it to `POST /predict` as a base64 image.
2. The backend decodes the frame using OpenCV.
3. MediaPipe Hands attempts to isolate a single hand region.
4. The detected hand ROI is normalized:
   - grayscale conversion
   - Gaussian blur
   - resize to `256x256`
   - histogram equalization
5. ORB keypoints and descriptors are extracted.
6. The ROI is compared against cached dataset descriptors from `static/signs`.
7. Similarity is scored using feature matching with:
   - ratio test
   - minimum good matches
   - minimum keypoints
   - global similarity threshold
8. The API returns:
   - the matched dataset label, or
   - `"No Sign Detected"` when confidence is insufficient

### Important Guardrails

- the live route does not guess labels outside the dataset
- no label is accepted unless the similarity threshold is met
- frames with no detected hand return `"No Sign Detected"`
- uncertain frames are not appended to the rolling live text buffer

### Dataset Match Controls

These environment variables tune live matching:

- `LIVE_MATCH_THRESHOLD` - minimum similarity score accepted
- `LIVE_MIN_MATCHES` - minimum number of good ORB matches
- `LIVE_RATIO_TEST` - ratio-test threshold for descriptor filtering
- `LIVE_MIN_KEYPOINTS` - minimum keypoints required before matching
- `LIVE_DEBOUNCE_S` - delay before appending stable output text
- `LIVE_HOLD_S` - hold time for stable label confirmation

### Dataset Size

The local sign dataset currently contains approximately `200` files in `Ishario-main/static/signs`.

## AI Tutor / Chatbot

The learner app includes an OpenAI-backed tutor endpoint:

- route: `POST /api/chat`

Behavior:

- maintains short per-session message history in memory
- optionally persists chat messages to `ishario_db.chat_messages`
- uses `OPENAI_API_KEY`
- uses `OPENAI_MODEL` with default `gpt-4o-mini`

System prompt intent:

- teach sign language
- guide users through the Ishario experience
- provide concise, practical answers

## Database Design

This project uses two MySQL databases.

### 1. `ishario_db`

Schema file: `db/ishario_db.sql`

Tables:

- `profiles`
  - user profile information
  - profile photo blob metadata
- `users`
  - general platform/admin-side user records
- `feedback`
  - learner feedback records
- `admin`
  - admin login records
- `gesture_history`
  - gesture recognition event storage
- `chat_messages`
  - persisted AI chat messages

### 2. `signease`

Schema file: `db/signease.sql`

Tables:

- `users`
  - learner authentication records
  - includes hashed password and OTP field
- `sign_images`
  - sign labels and corresponding image blobs

## Environment Configuration

Example configuration is provided in `.env.example`.

### Required Database Variables

```env
ISHARIO_DB_HOST=localhost
ISHARIO_DB_PORT=3306
ISHARIO_DB_NAME=ishario_db
ISHARIO_DB_USER=root
ISHARIO_DB_PASS=your_mysql_password

SIGNEASE_DB_HOST=localhost
SIGNEASE_DB_PORT=3306
SIGNEASE_DB_NAME=signease
SIGNEASE_DB_USER=root
SIGNEASE_DB_PASS=your_mysql_password
```

### Optional Variables

```env
MAIL_USERNAME=
MAIL_PASSWORD=
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
ISHARIO_MODEL_PATH=
ISHARIO_SEED_ADMIN_EMAIL=
ISHARIO_SEED_ADMIN_PASSWORD=
LIVE_MATCH_THRESHOLD=0.18
LIVE_MIN_MATCHES=14
LIVE_RATIO_TEST=0.75
LIVE_MIN_KEYPOINTS=12
LIVE_DEBOUNCE_S=0.9
LIVE_HOLD_S=0.6
```

## Local Setup

### 1. Create the Conda Environment

```powershell
conda env create -f environment.yml
conda activate ishario
```

### 2. Copy Environment File

```powershell
Copy-Item .env.example .env
```

Then update `.env` with your local MySQL password and optional API keys.

### 3. Initialize MySQL

```powershell
python scripts/init_mysql.py
```

What the script does:

- connects with MySQL admin credentials
- creates `ishario_db` and `signease` if missing
- applies `db/ishario_db.sql`
- applies `db/signease.sql`
- optionally seeds an admin user
- optionally creates a non-root app user and grants access

### 4. Optional: Seed Admin

```powershell
$env:ISHARIO_SEED_ADMIN_EMAIL="admin@example.com"
$env:ISHARIO_SEED_ADMIN_PASSWORD="admin123"
python scripts/init_mysql.py
```

## Running the Project

### Learner App

```powershell
cd Ishario-main
python app.py
```

Default URL:

- `http://127.0.0.1:5000`

### Admin App

```powershell
cd Ishario-main
python admin.py
```

Default URL:

- `http://127.0.0.1:5001`

## HTTP Routes and APIs

### Learner UI Routes

- `GET /`
- `GET /singinpage.html`
- `GET /dashboard`
- `GET /profile`
- `GET /videos`
- `GET /conversion`
- `GET /advanced`
- `GET /basics`
- `GET /daily_life`
- `GET /favorites`
- `GET /feedback`
- `GET /games`
- `GET /progress`
- `GET /sign_match`
- `GET /speed_sign`
- `GET /terms`
- `GET /themed_quiz`
- `GET /live`

### Learner API Routes

- `POST /api/login`
- `POST /api/signup`
- `GET /logout`
- `POST /send-otp`
- `POST /verifyotp`
- `POST /reset-password`
- `POST /api/profile`
- `POST /predict`
- `POST /api/live/reset`
- `POST /api/chat`
- `POST /text-to-sign`
- `POST /signtotext`
- `GET /profile/photo/<filename>`
- `GET /static/signs/<path:filename>`

### Admin Routes

- `GET /`
- `GET /admin/authentication`
- `GET /admin/keyfeatures`
- `GET /admin/dashboard`
- `GET /admin/user-management`
- `GET /admin/feedback`
- `GET /admin/security`

### Admin APIs

- `POST /api/login`
- `GET /api/total_users`
- `GET /api/active_learners`
- `GET /api/total_feedback`
- `GET /api/users`
- `GET /api/user/<id>`
- `POST /admin/add-user`
- `POST /admin/edit-user/<id>`
- `DELETE /admin/delete-user/<id>`
- `GET /api/feedbacks`
- `GET /api/feedback/<id>`
- `POST /admin/add-feedback`
- `POST /admin/edit-feedback/<id>`
- `DELETE /admin/delete-feedback/<id>`
- `POST /api/update-password`
- `POST /api/add-admin`

## Model Training

Training script:

- `Ishario-main/train_model.py`

Current training assumptions:

- dataset path is `archive/asl_alphabet_train/asl_alphabet_train`
- image size is `64x64`
- uses `ImageDataGenerator` with `validation_split=0.2`
- architecture:
  - `Conv2D(32)` + max pooling
  - `Conv2D(64)` + max pooling
  - `Conv2D(128)` + max pooling
  - flatten
  - dense `256`
  - dropout `0.5`
  - softmax output

Run training:

```powershell
cd Ishario-main
python train_model.py
```

Notes:

- the live webcam route in this branch is now dataset-similarity-based
- `model.h5` is still used for compatibility and for non-live ML flows
- model loading includes a compatibility path for Keras config fields such as `optional` and `quantization_config`

## Admin Panel

The admin app provides:

- user counts
- feedback counts
- user CRUD operations
- feedback CRUD operations
- admin login with JWT generation
- password update workflow

Files involved:

- `Ishario-main/admin.py`
- `Ishario-main/templates/admin/dashboard.html`
- `Ishario-main/templates/admin/keyfeatures.html`
- `Ishario-main/templates/admin/user-management.html`
- `Ishario-main/templates/admin/feedback.html`
- `Ishario-main/templates/admin/authentication.html`

## Implementation Notes for This Branch

### Configuration Improvements

- `.env` loading is handled in `Ishario-main/app.py`
- database defaults are centralized in `Ishario-main/ishario/db.py`

### Database Resilience

- unavailable database connections raise structured `DbUnavailable`
- auth/schema failures are converted into consistent JSON error responses
- startup creates `profiles` table if missing

### Model Compatibility Fixes

- `model.h5` loading now includes a fallback compatibility loader
- unsupported Keras config fields are stripped before reconstructing the model

### MediaPipe Stabilization

- the app expects the classic `mp.solutions.hands` API
- the environment is pinned to `mediapipe==0.10.14`

### Live Recognition Redesign

- moved from accepting classifier guesses to dataset-only similarity matching
- `"No Sign Detected"` is treated as a neutral result, not a prediction
- live text only accumulates stable accepted signs

## Troubleshooting

### MySQL Access Denied

Symptoms:

- `Access denied for user 'root'@'localhost'`
- `using password: NO`

Fix:

- verify `.env` contains the correct `ISHARIO_DB_PASS` and `SIGNEASE_DB_PASS`
- rerun:

```powershell
python scripts/init_mysql.py
```

### Unknown Database

Symptoms:

- `Unknown database 'ishario_db'`
- `Unknown database 'signease'`

Fix:

- initialize the schemas:

```powershell
python scripts/init_mysql.py
```

### MediaPipe Not Initialized

Symptoms:

- `MediaPipe hands not available`

Fix:

- use the provided conda environment
- ensure `mediapipe==0.10.14`
- run the real file `Ishario-main/app.py`, not a temporary editor runner file

### Model Not Loaded

Symptoms:

- `Failed to load model at model.h5`

Fixes:

- confirm `ISHARIO_MODEL_PATH` if the model is stored elsewhere
- retrain with:

```powershell
python Ishario-main/train_model.py
```

- or use the branch's compatibility loader path already built into `Ishario-main/app.py`

### Frequent "No Sign Detected"

Possible reasons:

- threshold too high
- lighting mismatch
- hand too far from the camera
- background clutter
- hand pose differs significantly from the dataset images

Try adjusting:

- `LIVE_MATCH_THRESHOLD`
- `LIVE_MIN_MATCHES`
- `LIVE_RATIO_TEST`

## Current Limitations

- the live recognizer is limited to labels represented in `static/signs`
- sign quality depends heavily on similarity to the stored dataset images
- AI Tutor requires a valid OpenAI API key
- OTP email requires valid SMTP credentials
- some training paths still assume a local dataset folder not committed in this repository
- admin authentication currently compares stored passwords directly for the admin table and should be hardened before production use

## Recommended Next Improvements

- hash admin passwords instead of storing/comparing plaintext values
- add automated tests for `/predict`, `/api/chat`, and DB helpers
- add migration tooling instead of raw SQL-only bootstrap
- persist live gesture history from the webcam flow
- expose a live debug panel for similarity score tuning
- document dataset preparation and augmentation workflow

---

If you are working on the `monika` branch, this README is intended to be the branch-level technical reference. For quick setup only, you can also check `Ishario-main/README.md`.
