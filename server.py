from flask import Flask, render_template, request, jsonify, session
import sqlite3
import hashlib
import secrets
from datetime import datetime
import os
from functools import wraps

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

def get_db():
    conn = sqlite3.connect('dreamai.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT UNIQUE,
            points INTEGER DEFAULT 5,
            last_daily TEXT,
            dark_mode INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            prompt TEXT,
            image_url TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return {'error': 'Login required'}, 401
        return f(*args, **kwargs)
    return decorated

def get_user(user_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    conn.close()
    return dict(user) if user else None

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/api/login/google', methods=['POST'])
def google_login():
    data = request.json
    email = data.get('email')
    name = data.get('name')
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = c.fetchone()
    if not user:
        c.execute("INSERT INTO users (name, email, points) VALUES (?, ?, 5)", (name, email))
        conn.commit()
        user_id = c.lastrowid
    else:
        user_id = user['id']
    session['user_id'] = user_id
    conn.close()
    return jsonify({'success': True, 'user': get_user(user_id)})

@app.route('/api/login/github', methods=['POST'])
def github_login():
    data = request.json
    email = data.get('email')
    name = data.get('name')
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = c.fetchone()
    if not user:
        c.execute("INSERT INTO users (name, email, points) VALUES (?, ?, 5)", (name, email))
        conn.commit()
        user_id = c.lastrowid
    else:
        user_id = user['id']
    session['user_id'] = user_id
    conn.close()
    return jsonify({'success': True, 'user': get_user(user_id)})

@app.route('/api/me')
def get_me():
    if 'user_id' in session:
        return jsonify({'user': get_user(session['user_id'])})
    return jsonify({'user': None})

@app.route('/api/logout', methods=['POST'])
def do_logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/points')
@login_required
def my_points():
    user = get_user(session['user_id'])
    return jsonify({'points': user['points']})

@app.route('/api/claim', methods=['POST'])
@login_required
def claim():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT last_daily, points FROM users WHERE id = ?", (session['user_id'],))
    result = c.fetchone()
    today = datetime.now().date().isoformat()
    if result['last_daily'] != today:
        new_points = result['points'] + 5
        c.execute("UPDATE users SET points = ?, last_daily = ? WHERE id = ?", (new_points, today, session['user_id']))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'points': new_points})
    conn.close()
    return jsonify({'success': False, 'points': result['points']})

@app.route('/api/create', methods=['POST'])
@login_required
def create():
    data = request.json
    prompt = data.get('prompt')
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT points FROM users WHERE id = ?", (session['user_id'],))
    points = c.fetchone()['points']
    if points < 1:
        conn.close()
        return jsonify({'success': False, 'error': 'Not enough points'})
    c.execute("UPDATE users SET points = points - 1 WHERE id = ?", (session['user_id'],))
    conn.commit()
    seed = hashlib.md5(f"{prompt}{session['user_id']}{datetime.now()}".encode()).hexdigest()
    image_url = f"https://picsum.photos/seed/{seed}/512/512"
    c.execute("INSERT INTO images (user_id, prompt, image_url) VALUES (?, ?, ?)", (session['user_id'], prompt, image_url))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'image_url': image_url})

@app.route('/api/gallery')
@login_required
def my_gallery():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT prompt, image_url, created_at FROM images WHERE user_id = ? ORDER BY created_at DESC", (session['user_id'],))
    rows = c.fetchall()
    images = [{'prompt': row['prompt'], 'image_url': row['image_url'], 'date': row['created_at']} for row in rows]
    conn.close()
    return jsonify({'images': images})

@app.route('/api/stats')
@login_required
def my_stats():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) as total FROM images WHERE user_id = ?", (session['user_id'],))
    total = c.fetchone()['total']
    conn.close()
    return jsonify({'total': total})

@app.route('/api/darkmode', methods=['POST'])
@login_required
def set_dark():
    data = request.json
    dark = 1 if data.get('dark') else 0
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE users SET dark_mode = ? WHERE id = ?", (dark, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/create')
def create_page():
    return render_template('create.html')

@app.route('/gallery')
def gallery_page():
    return render_template('gallery.html')

@app.route('/badges')
def badges_page():
    return render_template('badges.html')

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)
