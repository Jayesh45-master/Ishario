import os
import traceback
import random
import string
from datetime import datetime
from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_mysqldb import MySQL
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from flask_jwt_extended import JWTManager, create_access_token
app = Flask(__name__, template_folder="templates")
CORS(app)  # allow fetch from same origin / dev
bcrypt = Bcrypt(app)

# Config (use env vars in production)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'devsecret')
# JWT_SECRET_KEY is required by flask-jwt-extended; fallback to SECRET_KEY if not provided
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', app.config['SECRET_KEY'])
app.config['MYSQL_HOST'] = os.environ.get('ISHARIO_DB_HOST', 'localhost')
app.config['MYSQL_USER'] = os.environ.get('ISHARIO_DB_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.environ.get('ISHARIO_DB_PASS', 'Jayesh@45')
app.config['MYSQL_DB'] = os.environ.get('ISHARIO_DB_NAME', 'ishario_db')

# Initialize JWT manager
jwt = JWTManager(app)
app.config['MYSQL_DB'] = os.environ.get('ISHARIO_DB_NAME', 'ishario_db')

mysql = MySQL(app)

# Helper function for query count
def query_count(sql, params=None):
    cur = None
    try:
        cur = mysql.connection.cursor()
        cur.execute(sql, params or ())
        row = cur.fetchone()
        if row is None:
            return 0
        return int(row[0])  # returning the count from first column
    except Exception as e:
        app.logger.error("DB query failed: %s\n%s", e, traceback.format_exc())
        raise
    finally:
        if cur:
            cur.close()

# Helper function for querying database
def query_db(sql, params=None):
    cur = None
    try:
        cur = mysql.connection.cursor()
        cur.execute(sql, params or ())
        
        # For SELECT queries, fetch results
        if sql.strip().upper().startswith('SELECT'):
            result = cur.fetchall()
            # Convert to list of dictionaries for easier JSON serialization
            columns = [col[0] for col in cur.description]
            return [dict(zip(columns, row)) for row in result]
        else:
            # For INSERT, UPDATE, DELETE - commit changes
            mysql.connection.commit()
            return None
    except Exception as e:
        app.logger.error("DB query failed: %s\n%s", e, traceback.format_exc())
        mysql.connection.rollback()
        raise
    finally:
        if cur:
            cur.close()

# ---------------------------
# Home Page (Key Features) - ROOT URL
# ---------------------------
@app.route('/admin/keyfeatures')
def keyfeatures():
    try:
        # Get dashboard statistics
        total_users = query_count("SELECT COUNT(*) FROM users")
        active_learners = query_count("SELECT COUNT(*) FROM users")
        total_feedback = query_count("SELECT COUNT(*) FROM feedback")
        return render_template('admin/keyfeatures.html',
                               total_users=total_users,
                               active_learners=active_learners,
                               total_feedback=total_feedback)
    except Exception:
        return render_template('admin/keyfeatures.html', total_users=0, active_learners=0, total_feedback=0)

# ---------------------------
# Dashboard Routes - SEPARATE PATH
# ---------------------------
@app.route('/admin/dashboard')
def dashboard():
    try:
        # Get dashboard statistics
        total_users = query_count("SELECT COUNT(*) FROM users")
        active_learners = query_count("SELECT COUNT(*) FROM users")
        total_feedback = query_count("SELECT COUNT(*) FROM feedback")
        return render_template('admin/dashboard.html',
                               total_users=total_users,
                               active_learners=active_learners,
                               total_feedback=total_feedback)
    except Exception:
        return render_template('admin/dashboard.html', total_users=0, active_learners=0, total_feedback=0)


# ---------------------------
# API Routes
# ---------------------------
@app.route('/api/total_users')
def api_total_users():
    try:
        n = query_count("SELECT COUNT(*) FROM users")
        return jsonify({'total_users': n})
    except Exception as e:
        return jsonify({'error': 'db_error', 'detail': str(e)}), 500

@app.route('/api/active_learners')
def api_active_learners():
    try:
        n = query_count("SELECT COUNT(*) FROM users")
        return jsonify({'active_learners': n})
    except Exception as e:
        return jsonify({'error': 'db_error', 'detail': str(e)}), 500

@app.route('/api/total_feedback')
def api_total_feedback():
    try:
        n = query_count("SELECT COUNT(*) FROM feedback")
        return jsonify({'total_feedback': n})
    except Exception as e:
        return jsonify({'error': 'db_error', 'detail': str(e)}), 500

# ---------------------------
# User Management (template route)
# ---------------------------
def _random_name():
    first = ['Alex','Sam','Taylor','Jordan','Riley','Casey','Jamie','Morgan','Avery','Parker']
    last = ['Shah','Khan','Patel','Smith','Lee','Gupta','Singh','Mehta','Joshi','Desai']
    return f"{random.choice(first)} {random.choice(last)}"

def _random_username(name):
    base = ''.join(ch for ch in (name or '').lower() if ch.isalnum())
    if not base:
        base = 'user'
    suffix = ''.join(random.choices(string.digits, k=3))
    return f"{base}{suffix}"

def _random_progress():
    return random.choice(['none', 'beginner', 'intermediate', 'advanced', 'completed'])

def _normalize_user_record(raw):
    """Ensure returned user dict has id, name, email, username, created_at and some random defaults."""    
    email = raw.get('email') or raw.get('mail') or raw.get('user_email') or ''
    name = raw.get('name') or raw.get('full_name') or raw.get('first_name') or (email.split('@')[0] if email else None)
    if not name:
        name = _random_name()
    username = raw.get('username') or raw.get('user') or _random_username(name)
    created_at = raw.get('created_at') or raw.get('created') or raw.get('createdAt') or datetime.utcnow().isoformat()
    course_progress = raw.get('course_progress') or raw.get('progress') or _random_progress()
    role = raw.get('role') or random.choice(['user', 'admin', 'editor'])

    return {
        'id': raw.get('id'),
        'name': name,
        'email': email,
        'username': username,
        'created_at': created_at,
        'course_progress': course_progress,
        'role': role
    }

def _normalize_feedback_record(raw):
    """Ensure returned feedback dict has id, name, email, category, rating, message, status, reply and date."""
    return {
        'id': raw.get('id'),
        'name': raw.get('name') or '',
        'email': raw.get('email') or '',
        'category': raw.get('category') or 'general',
        'rating': raw.get('rating') or 0,
        'message': raw.get('message') or '',
        'status': raw.get('status') or 'pending',
        'reply': raw.get('reply') or '',
        'date': raw.get('date') or datetime.utcnow().isoformat()
    }

@app.route('/admin/user-management')
def user_management():
    try:
        raw_users = query_db("SELECT * FROM users")
        users = [_normalize_user_record(u) for u in raw_users]
        return render_template('admin/user-management.html', users=users)
    except Exception:
        return render_template('admin/user-management.html', users=[])

# API route to get users data
@app.route('/api/users')
def api_users():
    try:
        raw_users = query_db("SELECT * FROM users")
        users = [_normalize_user_record(u) for u in raw_users]
        return jsonify({'users': users})
    except Exception as e:
        return jsonify({'error': 'db_error', 'detail': str(e)}), 500

# API route to get a specific user by ID (for edit purposes)
@app.route('/api/user/<int:user_id>')
def api_user(user_id):
    try:
        raw = query_db("SELECT * FROM users WHERE id = %s", [user_id])
        if raw:
            user = _normalize_user_record(raw[0])
            return jsonify({'user': user})
        return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        return jsonify({'error': 'db_error', 'detail': str(e)}), 500

# Route to add a new user (use existing columns only)
@app.route('/admin/add-user', methods=['POST'])
def add_user():
    try:
        email = request.form.get('email')
        course_progress = request.form.get('course_progress', 'none')

        query_db("""
            INSERT INTO users (email, course_progress) 
            VALUES (%s, %s)
        """, [email, course_progress])

        return jsonify({'message': 'User added successfully'}), 200
    except Exception as e:
        return jsonify({'error': 'db_error', 'detail': str(e)}), 500

# Route to update user data (use existing columns only)
@app.route('/admin/edit-user/<int:user_id>', methods=['POST'])
def edit_user(user_id):
    try:
        email = request.form.get('email')
        course_progress = request.form.get('course_progress', 'none')

        query_db("""
            UPDATE users SET email = %s, course_progress = %s WHERE id = %s
        """, [email, course_progress, user_id])

        return jsonify({'message': 'User updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': 'db_error', 'detail': str(e)}), 500

# Route to delete a user
@app.route('/admin/delete-user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    try:
        query_db("DELETE FROM users WHERE id = %s", [user_id])
        return jsonify({'message': 'User deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': 'db_error', 'detail': str(e)}), 500


@app.route('/admin/feedback')
def feedback_management():
    try:
        # Fetch all feedbacks
        raw_feedbacks = query_db("SELECT * FROM feedback")
        feedbacks = [_normalize_feedback_record(f) for f in raw_feedbacks]
        return render_template('admin/feedback-management.html', feedbacks=feedbacks)
    except Exception:
        return render_template('admin/feedback.html', feedbacks=[])

# API route to get all feedback
@app.route('/api/feedbacks')
def api_feedbacks():
    try:
        raw_feedbacks = query_db("SELECT * FROM feedback")
        feedbacks = [_normalize_feedback_record(f) for f in raw_feedbacks]
        return jsonify({'feedbacks': feedbacks})
    except Exception as e:
        return jsonify({'error': 'db_error', 'detail': str(e)}), 500

# API route to get a specific feedback by ID (for view purposes)
@app.route('/api/feedback/<int:feedback_id>')
def api_feedback(feedback_id):
    try:
        raw = query_db("SELECT * FROM feedback WHERE id = %s", [feedback_id])
        if raw:
            feedback = _normalize_feedback_record(raw[0])
            return jsonify({'feedback': feedback})
        return jsonify({'error': 'Feedback not found'}), 404
    except Exception as e:
        return jsonify({'error': 'db_error', 'detail': str(e)}), 500

# Route to add a new feedback (for simplicity, this example just adds feedback with minimal data)
@app.route('/admin/add-feedback', methods=['POST'])
def add_feedback():
    try:
        name = request.form.get('name')
        email = request.form.get('email')
        category = request.form.get('category', 'general')
        rating = request.form.get('rating', 0)
        message = request.form.get('message')
        status = request.form.get('status', 'pending')
        date = datetime.utcnow().isoformat()

        # Add feedback to the database
        query_db("""
            INSERT INTO feedback (name, email, category, rating, message, status, date)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, [name, email, category, rating, message, status, date])

        return jsonify({'message': 'Feedback added successfully'}), 200
    except Exception as e:
        return jsonify({'error': 'db_error', 'detail': str(e)}), 500

# Route to update feedback status or reply
@app.route('/admin/edit-feedback/<int:feedback_id>', methods=['POST'])
def edit_feedback(feedback_id):
    try:
        status = request.form.get('status')
        reply = request.form.get('reply', '')

        # Update feedback in the database
        query_db("""
            UPDATE feedback SET status = %s, reply = %s WHERE id = %s
        """, [status, reply, feedback_id])

        return jsonify({'message': 'Feedback updated successfully'}), 200
    except Exception as e:
        return jsonify({'error': 'db_error', 'detail': str(e)}), 500

# Route to delete a feedback
@app.route('/admin/delete-feedback/<int:feedback_id>', methods=['DELETE'])
def delete_feedback(feedback_id):
    try:
        query_db("DELETE FROM feedback WHERE id = %s", [feedback_id])
        return jsonify({'message': 'Feedback deleted successfully'}), 200
    except Exception as e:
        return jsonify({'error': 'db_error', 'detail': str(e)}), 500

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()

    # Validate the received data
    if not data or not data.get('email') or not data.get('password'):
        return jsonify({'error': 'Email and password are required.'}), 400

    email = data.get('email').strip()
    password = data.get('password').strip()

    # Fetch admin data from the database
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM admin WHERE email = %s", [email])
    admin = cursor.fetchone()

    if not admin:
        return jsonify({'error': 'Invalid email or password'}), 400

    stored_password = admin[2]  # Assuming password column is at index 2

    # Verify the password (direct comparison)
    if stored_password != password:
        return jsonify({'error': 'Invalid email or password'}), 400

    # Generate a JWT token for the admin
    token = create_access_token(identity={'email': admin[1], 'id': admin[0]})

    return jsonify({'token': token}), 200


# Home page route (Login page route)
@app.route('/')
def home():
    return render_template('admin/authentication.html')

# ...existing code...

@app.route('/admin/authentication')
def authentication():
    try:
        return render_template('admin/authentication.html')
    except Exception:
        return render_template('admin/authentication.html')

# ...existing code...

@app.route('/api/update-password', methods=['POST'])
def update_password():
    data = request.get_json()
    
    # Check if all required fields are provided
    old_password = data.get('oldPassword', '').strip()
    new_password = data.get('newPassword', '').strip()
    confirm_password = data.get('confirmPassword', '').strip()

    # Validate inputs
    if not old_password or not new_password or not confirm_password:
        return jsonify({'error': 'All fields are required.'}), 400
    
    if new_password != confirm_password:
        return jsonify({'error': 'New passwords do not match.'}), 400

    if len(new_password) < 6:
        return jsonify({'error': 'New password should be at least 6 characters.'}), 400

    # Fetch admin data from DB (assuming admin ID = 1)
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM admin WHERE id = %s", [1])  # Adjust admin ID if needed
    admin = cursor.fetchone()

    if not admin:
        return jsonify({'error': 'Admin not found.'}), 404

    stored_password = admin[2]  # Assuming password column is at index 2

    # Verify old password (direct comparison as requested)
    if stored_password != old_password:
        return jsonify({'error': 'Old password is incorrect.'}), 400

    # Update new password in DB
    try:
        cursor.execute("UPDATE admin SET password = %s WHERE id = %s", [new_password, 1])
        mysql.connection.commit()
        return jsonify({'message': 'Password updated successfully.'}), 200
    except Exception as e:
        app.logger.error("Failed to update password: %s", str(e))
        return jsonify({'error': 'Database update failed.'}), 500


# Route to add admin account (with email)
@app.route('/api/add-admin', methods=['POST'])
def add_admin():
    data = request.get_json()
    email = data.get('email', '').strip()

    if not email:
        return jsonify({'error': 'Email is required.'}), 400

    # Insert new admin (name is optional)
    cursor = mysql.connection.cursor()
    cursor.execute("INSERT INTO admin (email) VALUES (%s)", [email])
    mysql.connection.commit()

    return jsonify({'message': 'Admin added successfully.'}), 200

@app.route('/admin/security')
def security():
    try:
        return render_template('admin/security.html')
    except Exception:
        return render_template('admin/security.html')

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
