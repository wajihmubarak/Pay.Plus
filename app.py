from flask import Flask, render_template, request, jsonify, session
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'payplus_key_123'

# الاتصال بقاعدة البيانات
def get_db():
    conn = sqlite3.connect('payplus.db')
    conn.row_factory = sqlite3.Row
    return conn

# إنشاء الجداول
def init_db():
    with get_db() as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS users 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, email TEXT UNIQUE, password TEXT, balance REAL DEFAULT 0, ads_count INTEGER DEFAULT 0)''')
        conn.execute('''CREATE TABLE IF NOT EXISTS withdrawals 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, method TEXT, amount REAL, status TEXT, date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    with get_db() as conn:
        withdrawals = conn.execute('SELECT withdrawals.*, users.name FROM withdrawals JOIN users ON withdrawals.user_id = users.id ORDER BY date DESC').fetchall()
    return render_template('admin.html', withdrawals=withdrawals)

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    hashed_pw = generate_password_hash(data['password'])
    try:
        with get_db() as conn:
            conn.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (data['name'], data['email'], hashed_pw))
            conn.commit()
        return jsonify({"success": True})
    except:
        return jsonify({"success": False, "message": "الايميل مسجل مسبقاً"})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (data['email'],)).fetchone()
        if user and check_password_hash(user['password'], data['password']):
            session['user_id'] = user['id']
            return jsonify({"success": True, "user": dict(user)})
    return jsonify({"success": False, "message": "بيانات خاطئة"})

@app.route('/api/watch-ad', methods=['POST'])
def watch_ad():
    if 'user_id' not in session: return jsonify({"success": False})
    with get_db() as conn:
        conn.execute("UPDATE users SET balance = balance + 3, ads_count = ads_count + 1 WHERE id = ?", (session['user_id'],))
        user = conn.execute("SELECT balance, ads_count FROM users WHERE id = ?", (session['user_id'],)).fetchone()
        conn.commit()
        return jsonify({"success": True, "new_balance": user['balance'], "new_ads_count": user['ads_count']})

@app.route('/api/withdraw', methods=['POST'])
def withdraw():
    if 'user_id' not in session: return jsonify({"success": False})
    data = request.json
    with get_db() as conn:
        conn.execute("INSERT INTO withdrawals (user_id, method, amount, status) VALUES (?, ?, ?, ?)", (session['user_id'], data['method'], data['amount'], "قيد المراجعة"))
        conn.commit()
    return jsonify({"success": True})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
