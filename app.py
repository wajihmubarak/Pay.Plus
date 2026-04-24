# تحديث مسار السحب لخصم الرصيد فوراً
@app.route('/api/withdraw', methods=['POST'])
def withdraw():
    if 'user_id' not in session: 
        return jsonify({"success": False, "message": "يجب تسجيل الدخول أولاً"})
    
    data = request.json
    amount = float(data['amount'])
    method = data['method']
    
    # جلب تفاصيل الحساب المرسلة (رقم المحفظة أو الحساب)
    details = data.get('details', 'غير محدد')

    with get_db() as conn:
        user = conn.execute("SELECT balance FROM users WHERE id = ?", (session['user_id'],)).fetchone()
        
        if user['balance'] < amount:
            return jsonify({"success": False, "message": "رصيدك غير كافٍ!"})

        # 1. خصم الرصيد من المستخدم
        conn.execute("UPDATE users SET balance = balance - ? WHERE id = ?", (amount, session['user_id']))
        
        # 2. تسجيل العملية في جدول السحب مع البيانات (رقم الحساب)
        conn.execute("INSERT INTO withdrawals (user_id, method, amount, status, details) VALUES (?, ?, ?, ?, ?)", 
                     (session['user_id'], method, amount, "قيد المراجعة", details))
        
        conn.commit()
        
        # جلب الرصيد الجديد لإرساله للواجهة
        new_balance = conn.execute("SELECT balance FROM users WHERE id = ?", (session['user_id'],)).fetchone()['balance']
        
    return jsonify({"success": True, "new_balance": new_balance})

# تحديث صفحة الإدمن لإظهار البيانات وزر الموافقة
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

# مسار للموافقة على السحب
@app.route('/api/admin/approve/<int:w_id>', methods=['POST'])
def approve_withdrawal(w_id):
    with get_db() as conn:
        conn.execute("UPDATE withdrawals SET status = 'تم الدفع ✅' WHERE id = ?", (w_id,))
        conn.commit()
    return jsonify({"success": True})
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
