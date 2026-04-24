from flask import Flask, render_template, request, jsonify, session
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'payplus_secure_key_2026' # مفتاح تشفير الجلسات لضمان الأمان

# وظيفة للاتصال بقاعدة بيانات SQLite
def get_db():
    conn = sqlite3.connect('payplus.db')
    conn.row_factory = sqlite3.Row  # للتمكن من الوصول للبيانات بأسماء الأعمدة
    return conn

# إنشاء الجداول وتجهيز قاعدة البيانات عند التشغيل
def init_db():
    with get_db() as conn:
        # جدول المستخدمين: يخزن الاسم، الايميل، الباسورد المشفر، الرصيد، وعدد الاعلانات
        conn.execute('''CREATE TABLE IF NOT EXISTS users 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
             name TEXT NOT NULL, 
             email TEXT UNIQUE NOT NULL, 
             password TEXT NOT NULL, 
             balance REAL DEFAULT 0, 
             ads_count INTEGER DEFAULT 0)''')
        
        # جدول السحوبات: يخزن تفاصيل الطلبات، المبلغ، وسيلة السحب، وبيانات التحويل (details)
        conn.execute('''CREATE TABLE IF NOT EXISTS withdrawals 
            (id INTEGER PRIMARY KEY AUTOINCREMENT, 
             user_id INTEGER, 
             method TEXT NOT NULL, 
             amount REAL NOT NULL, 
             status TEXT NOT NULL, 
             details TEXT NOT NULL, 
             date TIMESTAMP DEFAULT (DATETIME('now', 'localtime')),
             FOREIGN KEY (user_id) REFERENCES users (id))''')
        conn.commit()

# --- المسارات (Routes) ---

@app.route('/')
def index():
    return render_template('index.html')

# مسار لوحة الإدارة - يعرض كافة طلبات السحب لكل المستخدمين
@app.route('/admin')
def admin_panel():
    with get_db() as conn:
        withdrawals = conn.execute('''
            SELECT withdrawals.*, users.name, users.email 
            FROM withdrawals 
            JOIN users ON withdrawals.user_id = users.id 
            ORDER BY date DESC
        ''').fetchall()
    return render_template('admin.html', withdrawals=withdrawals)

# مسار تحديث حالة السحب (الموافقة) من قبل المدير
@app.route('/api/admin/approve/<int:w_id>', methods=['POST'])
def approve_withdrawal(w_id):
    with get_db() as conn:
        conn.execute("UPDATE withdrawals SET status = 'تم الدفع ✅' WHERE id = ?", (w_id,))
        conn.commit()
    return jsonify({"success": True})

# تسجيل مستخدم جديد
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = generate_password_hash(data.get('password')) # تشفير كلمة المرور
    
    try:
        with get_db() as conn:
            conn.execute("INSERT INTO users (name, email, password) VALUES (?, ?, ?)", (name, email, password))
            conn.commit()
        return jsonify({"success": True})
    except sqlite3.IntegrityError:
        return jsonify({"success": False, "message": "هذا البريد الإلكتروني مسجل مسبقاً!"})

# تسجيل الدخول والتحقق من البيانات
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')
    
    with get_db() as conn:
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            return jsonify({"success": True, "user": {
                "name": user['name'],
                "email": user['email'],
                "balance": user['balance'],
                "ads_count": user['ads_count']
            }})
    return jsonify({"success": False, "message": "خطأ في البريد الإلكتروني أو كلمة المرور"})

# مسار مشاهدة الإعلان - يضيف 3 دولار للرصيد في قاعدة البيانات
@app.route('/api/watch-ad', methods=['POST'])
def watch_ad():
    if 'user_id' not in session: 
        return jsonify({"success": False, "message": "غير مصرح لك"})
    
    user_id = session['user_id']
    with get_db() as conn:
        conn.execute("UPDATE users SET balance = balance + 3, ads_count = ads_count + 1 WHERE id = ?", (user_id,))
        conn.commit()
        user = conn.execute("SELECT balance, ads_count FROM users WHERE id = ?", (user_id,)).fetchone()
        return jsonify({
            "success": True, 
            "new_balance": user['balance'], 
            "new_ads_count": user['ads_count']
        })

# مسار طلب السحب - يخصم الرصيد فوراً ويسجل الطلب
@app.route('/api/withdraw', methods=['POST'])
def withdraw():
    if 'user_id' not in session: 
        return jsonify({"success": False, "message": "يجب تسجيل الدخول أولاً"})
    
    data = request.json
    user_id = session['user_id']
    amount = float(data.get('amount'))
    method = data.get('method')
    details = data.get('details')

    with get_db() as conn:
        user = conn.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
        
        if user['balance'] < amount:
            return jsonify({"success": False, "message": "عذراً، رصيدك غير كافٍ لإتمام هذه العملية"})
        
        # خصم المبلغ من رصيد المستخدم
        conn.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (amount, user_id))
        
        # إضافة العملية لجدول السحوبات مع الحالة "قيد المراجعة"
        conn.execute('''INSERT INTO withdrawals (user_id, method, amount, status, details) 
                        VALUES (?, ?, ?, ?, ?)''', 
                     (user_id, method, amount, "قيد المراجعة", details))
        conn.commit()
        
        new_balance = conn.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()['balance']
        return jsonify({"success": True, "new_balance": new_balance})

# مسار جلب سجل السحوبات الخاص بالمستخدم الحالي فقط
@app.route('/api/history')
def get_history():
    if 'user_id' not in session: 
        return jsonify([])
    
    user_id = session['user_id']
    with get_db() as conn:
        history = conn.execute('''SELECT method, amount, status, details, date 
                                 FROM withdrawals 
                                 WHERE user_id = ? 
                                 ORDER BY date DESC''', (user_id,)).fetchall()
        
        # تحويل النتائج إلى قائمة لسهولة التعامل معها في JavaScript
        history_list = []
        for row in history:
            history_list.append({
                "method": row['method'],
                "amount": row['amount'],
                "status": row['status'],
                "details": row['details'],
                "date": row['date']
            })
        return jsonify(history_list)

# تشغيل التطبيق وتجهيز قاعدة البيانات
if __name__ == '__main__':
    init_db() # إنشاء الجداول عند البدء
    # ملاحظة: host='0.0.0.0' ضرورية لعمل التطبيق داخل Docker أو على Render
    app.run(host='0.0.0.0', port=5000)
