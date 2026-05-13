from flask import Flask, render_template, request, redirect, url_for, session, flash
from database import get_db_connection, hash_password, init_db
from datetime import datetime
import os
import calendar
import csv
import io
from flask import Response, jsonify

app = Flask(__name__)
app.secret_key = 'secret-key'

if not os.path.exists('fintrackr.db'):
    init_db()

def check_budget_and_notify(user_id, budget_month):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT budget_amount FROM Budget WHERE user_id = ? AND budget_month = ?', 
                  (user_id, budget_month))
    budget = cursor.fetchone()
    
    if not budget:
        conn.close()
        return
    
    budget_amount = budget['budget_amount']
    
    cursor.execute('''
        SELECT SUM(t.amount) as total_spent
        FROM "Transaction" t
        JOIN Account a ON t.account_id = a.account_id
        WHERE a.user_id = ? 
        AND strftime('%Y-%m', t.tx_date) = ?
        AND t.tx_type = 'Expense'
    ''', (user_id, budget_month))
    
    result = cursor.fetchone()
    total_spent = result['total_spent'] if result['total_spent'] else 0
    
    percentage = (total_spent / budget_amount * 100) if budget_amount > 0 else 0
    
    if percentage >= 100:
        over_amount = total_spent - budget_amount
        message = f"ALERT: You have exceeded your budget by ${over_amount:.2f} ({percentage:.1f}% of budget)"
        
        cursor.execute('''
            SELECT notification_id FROM Notification 
            WHERE user_id = ? AND notification_type = 'Alert' 
            AND message = ? AND DATE(notification_date) = DATE('now')
        ''', (user_id, message))
        
        if not cursor.fetchone():
            cursor.execute('''
                INSERT INTO Notification (user_id, notification_type, message)
                VALUES (?, 'Alert', ?)
            ''', (user_id, message))
    
    elif percentage >= 50:
        threshold = int(percentage / 10) * 10
        if threshold >= 50:
            message = f"REMINDER: You have reached {threshold}% of your monthly budget (${total_spent:.2f} of ${budget_amount:.2f})"
            
            cursor.execute('''
                SELECT notification_id FROM Notification 
                WHERE user_id = ? AND notification_type = 'Reminder' 
                AND message LIKE ? AND DATE(notification_date) = DATE('now')
            ''', (user_id, f"%{threshold}% of your monthly budget%"))
            
            if not cursor.fetchone():
                cursor.execute('''
                    INSERT INTO Notification (user_id, notification_type, message)
                    VALUES (?, 'Reminder', ?)
                ''', (user_id, message))
    
    conn.commit()
    conn.close()

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM User WHERE username = ? OR email = ?', (username, email))
        if cursor.fetchone():
            flash('Username or email already exists!', 'error')
            conn.close()
            return redirect(url_for('register'))
        
        password_hash = hash_password(password)
        cursor.execute('''
            INSERT INTO User (username, email, password_hash)
            VALUES (?, ?, ?)
        ''', (username, email, password_hash))
        
        conn.commit()
        conn.close()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        password_hash = hash_password(password)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM User WHERE username = ? AND password_hash = ?', 
                      (username, password_hash))
        user = cursor.fetchone()
        conn.close()
        
        if user:
            session['user_id'] = user['user_id']
            session['username'] = user['username']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password!', 'error')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT SUM(balance) as total FROM Account WHERE user_id = ?', (user_id,))
    total_balance = cursor.fetchone()['total'] or 0
    
    cursor.execute('SELECT COUNT(*) as count FROM Account WHERE user_id = ?', (user_id,))
    account_count = cursor.fetchone()['count']
    
    current_month = datetime.now().strftime('%Y-%m')
    cursor.execute('SELECT budget_amount FROM Budget WHERE user_id = ? AND budget_month = ?', 
                  (user_id, current_month))
    budget_row = cursor.fetchone()
    current_budget = budget_row['budget_amount'] if budget_row else 0
    
    cursor.execute('''
        SELECT SUM(t.amount) as total_spent
        FROM "Transaction" t
        JOIN Account a ON t.account_id = a.account_id
        WHERE a.user_id = ? 
        AND strftime('%Y-%m', t.tx_date) = ?
        AND t.tx_type = 'Expense'
    ''', (user_id, current_month))
    spent_row = cursor.fetchone()
    current_spending = spent_row['total_spent'] if spent_row['total_spent'] else 0
    
    cursor.execute('''
        SELECT t.*, a.account_name, c.category_name
        FROM "Transaction" t
        JOIN Account a ON t.account_id = a.account_id
        LEFT JOIN Category c ON t.category_id = c.category_id
        WHERE a.user_id = ?
        ORDER BY t.tx_date DESC, t.transaction_id DESC
        LIMIT 5
    ''', (user_id,))
    recent_transactions = cursor.fetchall()
    
    cursor.execute('''
        SELECT * FROM Notification 
        WHERE user_id = ? AND is_read = 0
        ORDER BY notification_date DESC
        LIMIT 10
    ''', (user_id,))
    notifications = cursor.fetchall()
    
    conn.close()
    
    return render_template('dashboard.html', 
                         total_balance=total_balance,
                         account_count=account_count,
                         current_budget=current_budget,
                         current_spending=current_spending,
                         recent_transactions=recent_transactions,
                         notifications=notifications)

@app.route('/notifications')
def notifications():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM Notification 
        WHERE user_id = ?
        ORDER BY notification_date DESC
    ''', (user_id,))
    all_notifications = cursor.fetchall()
    
    conn.close()
    
    return render_template('notifications.html', notifications=all_notifications)

@app.route('/notifications/mark-read/<int:notification_id>')
def mark_notification_read(notification_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE Notification SET is_read = 1 WHERE notification_id = ? AND user_id = ?', 
                  (notification_id, session['user_id']))
    conn.commit()
    conn.close()
    
    return redirect(url_for('notifications'))

@app.route('/notifications/mark-all-read')
def mark_all_notifications_read():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE Notification SET is_read = 1 WHERE user_id = ?', (session['user_id'],))
    conn.commit()
    conn.close()
    
    flash('All notifications marked as read!', 'success')
    return redirect(url_for('notifications'))

@app.route('/accounts')
def accounts():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM Account WHERE user_id = ?', (user_id,))
    accounts = cursor.fetchall()
    conn.close()
    
    return render_template('accounts.html', accounts=accounts)

@app.route('/accounts/add', methods=['GET', 'POST'])
def add_account():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        user_id = session['user_id']
        account_name = request.form['account_name']
        account_type = request.form['account_type']
        balance = request.form['balance']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO Account (user_id, account_name, account_type, balance)
            VALUES (?, ?, ?, ?)
        ''', (user_id, account_name, account_type, balance))
        conn.commit()
        conn.close()
        
        flash('Account added successfully!', 'success')
        return redirect(url_for('accounts'))
    
    return render_template('add_account.html')

@app.route('/accounts/edit/<int:account_id>', methods=['GET', 'POST'])
def edit_account(account_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        account_name = request.form['account_name']
        account_type = request.form['account_type']
        balance = request.form['balance']
        
        cursor.execute('''
            UPDATE Account 
            SET account_name = ?, account_type = ?, balance = ?
            WHERE account_id = ? AND user_id = ?
        ''', (account_name, account_type, balance, account_id, session['user_id']))
        conn.commit()
        conn.close()
        
        flash('Account updated successfully!', 'success')
        return redirect(url_for('accounts'))
    
    cursor.execute('SELECT * FROM Account WHERE account_id = ? AND user_id = ?', 
                  (account_id, session['user_id']))
    account = cursor.fetchone()
    conn.close()
    
    return render_template('edit_account.html', account=account)

@app.route('/accounts/delete/<int:account_id>')
def delete_account(account_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM Account WHERE account_id = ? AND user_id = ?', 
                  (account_id, session['user_id']))
    conn.commit()
    conn.close()
    
    flash('Account deleted successfully!', 'success')
    return redirect(url_for('accounts'))

@app.route('/transactions')
def transactions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT t.*, a.account_name, c.category_name
        FROM "Transaction" t
        JOIN Account a ON t.account_id = a.account_id
        LEFT JOIN Category c ON t.category_id = c.category_id
        WHERE a.user_id = ?
        ORDER BY t.tx_date DESC, t.transaction_id DESC
    ''', (user_id,))
    transactions = cursor.fetchall()
    conn.close()
    
    return render_template('transactions.html', transactions=transactions)

@app.route('/transactions/add', methods=['GET', 'POST'])
def add_transaction():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        account_id = request.form['account_id']
        category_id = request.form.get('category_id') or None  
        tx_type = request.form['tx_type']
        amount = float(request.form['amount'])
        tx_date = request.form['tx_date']
        
        if tx_type == 'Income':
            category_id = None
        
        cursor.execute('''
            INSERT INTO "Transaction" (account_id, category_id, tx_type, amount, tx_date)
            VALUES (?, ?, ?, ?, ?)
        ''', (account_id, category_id, tx_type, amount, tx_date))
        
        if tx_type == 'Income':
            cursor.execute('UPDATE Account SET balance = balance + ? WHERE account_id = ?', (amount, account_id))
        else:  
            cursor.execute('UPDATE Account SET balance = balance - ? WHERE account_id = ?', (amount, account_id))
        
        conn.commit()
        
        tx_month = datetime.strptime(tx_date, '%Y-%m-%d').strftime('%Y-%m')
        check_budget_and_notify(user_id, tx_month)
        
        conn.close()
        
        flash('Transaction added successfully!', 'success')
        return redirect(url_for('transactions'))
    
    cursor.execute('SELECT * FROM Account WHERE user_id = ?', (user_id,))
    accounts = cursor.fetchall()
    cursor.execute('SELECT * FROM Category WHERE user_id = ? OR user_id IS NULL ORDER BY category_name', (user_id,))
    categories = cursor.fetchall()
    conn.close()
    
    return render_template('add_transaction.html', accounts=accounts, categories=categories)

@app.route('/transactions/delete/<int:transaction_id>')
def delete_transaction(transaction_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT t.*, a.user_id
        FROM "Transaction" t
        JOIN Account a ON t.account_id = a.account_id
        WHERE t.transaction_id = ?
    ''', (transaction_id,))
    transaction = cursor.fetchone()
    
    if transaction and transaction['user_id'] == session['user_id']:
        if transaction['tx_type'] == 'Income':
            cursor.execute('UPDATE Account SET balance = balance - ? WHERE account_id = ?', 
                         (transaction['amount'], transaction['account_id']))
        else:
            cursor.execute('UPDATE Account SET balance = balance + ? WHERE account_id = ?', 
                         (transaction['amount'], transaction['account_id']))
        
        cursor.execute('DELETE FROM "Transaction" WHERE transaction_id = ?', (transaction_id,))
        conn.commit()
        flash('Transaction deleted successfully!', 'success')
    
    conn.close()
    return redirect(url_for('transactions'))

@app.route('/transactions/export')
def export_transactions():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT t.tx_date, a.account_name, c.category_name, t.tx_type, t.amount
        FROM "Transaction" t
        JOIN Account a ON t.account_id = a.account_id
        LEFT JOIN Category c ON t.category_id = c.category_id
        WHERE a.user_id = ?
        ORDER BY t.tx_date DESC
    ''', (user_id,))
    transactions = cursor.fetchall()
    conn.close()
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date', 'Account', 'Category', 'Type', 'Amount'])
    
    for tx in transactions:
        category = tx['category_name'] if tx['category_name'] else 'Income'
        writer.writerow([tx['tx_date'], tx['account_name'], category, tx['tx_type'], tx['amount']])
    
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=transactions.csv"}
    )

@app.route('/categories')
def categories():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM Category WHERE user_id = ? OR user_id IS NULL ORDER BY category_name', (user_id,))
    categories = cursor.fetchall()
    conn.close()
    
    return render_template('categories.html', categories=categories)

@app.route('/categories/add', methods=['GET', 'POST'])
def add_category():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        category_name = request.form['category_name']
        
        user_id = session['user_id']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM Category WHERE category_name = ? AND (user_id = ? OR user_id IS NULL)', 
                      (category_name, user_id))
        if cursor.fetchone():
            flash('Category already exists!', 'error')
            conn.close()
            return redirect(url_for('add_category'))
        
        cursor.execute('INSERT INTO Category (category_name, user_id) VALUES (?, ?)', (category_name, user_id))
        conn.commit()
        conn.close()
        
        flash('Category added successfully!', 'success')
        return redirect(url_for('categories'))
    
    return render_template('add_category.html')

@app.route('/categories/delete/<int:category_id>')
def delete_category(category_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT category_name FROM Category WHERE category_id = ?', (category_id,))
    category = cursor.fetchone()
    
    if category and category['category_name'] in ['Entertainment', 'Food', 'Essentials']:
        flash('Cannot delete default categories!', 'error')
    else:
        cursor.execute('DELETE FROM Category WHERE category_id = ?', (category_id,))
        conn.commit()
        flash('Category deleted successfully!', 'success')
    
    conn.close()
    return redirect(url_for('categories'))

@app.route('/budgets')
def budgets():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT budget_month, budget_amount
        FROM Budget
        WHERE user_id = ?
        ORDER BY budget_month DESC
    ''', (user_id,))
    budgets = cursor.fetchall()
    
    budget_data = []
    for budget in budgets:
        cursor.execute('''
            SELECT SUM(t.amount) as total_spent
            FROM "Transaction" t
            JOIN Account a ON t.account_id = a.account_id
            WHERE a.user_id = ? 
            AND strftime('%Y-%m', t.tx_date) = ?
            AND t.tx_type = 'Expense'
        ''', (user_id, budget['budget_month']))
        
        spent_row = cursor.fetchone()
        total_spent = spent_row['total_spent'] if spent_row['total_spent'] else 0
        
        budget_data.append({
            'month': budget['budget_month'],
            'amount': budget['budget_amount'],
            'spent': total_spent,
            'percentage': (total_spent / budget['budget_amount'] * 100) if budget['budget_amount'] > 0 else 0
        })
    
    conn.close()
    
    return render_template('budgets.html', budgets=budget_data)

@app.route('/budgets/add', methods=['GET', 'POST'])
def add_budget():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        user_id = session['user_id']
        budget_month = request.form['budget_month']
        budget_amount = request.form['budget_amount']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM Budget WHERE user_id = ? AND budget_month = ?', 
                      (user_id, budget_month))
        if cursor.fetchone():
            flash('Budget for this month already exists! Please edit it instead.', 'error')
            conn.close()
            return redirect(url_for('add_budget'))
        
        cursor.execute('''
            INSERT INTO Budget (user_id, budget_month, budget_amount)
            VALUES (?, ?, ?)
        ''', (user_id, budget_month, budget_amount))
        conn.commit()
        conn.close()
        
        flash('Budget added successfully!', 'success')
        return redirect(url_for('budgets'))
    
    return render_template('add_budget.html')

@app.route('/budgets/edit/<budget_month>', methods=['GET', 'POST'])
def edit_budget(budget_month):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'POST':
        budget_amount = request.form['budget_amount']
        
        cursor.execute('''
            UPDATE Budget 
            SET budget_amount = ?
            WHERE user_id = ? AND budget_month = ?
        ''', (budget_amount, user_id, budget_month))
        conn.commit()
        conn.close()
        
        flash('Budget updated successfully!', 'success')
        return redirect(url_for('budgets'))
    
    cursor.execute('SELECT * FROM Budget WHERE user_id = ? AND budget_month = ?', 
                  (user_id, budget_month))
    budget = cursor.fetchone()
    conn.close()
    
    return render_template('edit_budget.html', budget=budget)

@app.route('/budgets/delete/<budget_month>')
def delete_budget(budget_month):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM Budget WHERE user_id = ? AND budget_month = ?', 
                  (session['user_id'], budget_month))
    conn.commit()
    conn.close()
    
    flash('Budget deleted successfully!', 'success')
    return redirect(url_for('budgets'))

@app.route('/summary')
def summary():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM Account WHERE user_id = ?', (user_id,))
    accounts = cursor.fetchall()
    
    selected_account_id = request.args.get('account_id')
    
    if not selected_account_id and accounts:
        selected_account_id = accounts[0]['account_id']
    
    chart_data = {
        'labels': [],
        'data': [],
        'colors': []
    }
    
    if selected_account_id:
        cursor.execute('''
            SELECT c.category_name, SUM(t.amount) as total
            FROM "Transaction" t
            LEFT JOIN Category c ON t.category_id = c.category_id
            WHERE t.account_id = ? AND t.tx_type = 'Expense'
            GROUP BY c.category_name
            HAVING total > 0
        ''', (selected_account_id,))
        
        results = cursor.fetchall()
        
        colors = [
            '#6366f1', '#8b5cf6', '#ec4899', '#10b981', '#f59e0b', 
            '#ef4444', '#3b82f6', '#14b8a6', '#84cc16', '#f97316'
        ]
        
        for i, row in enumerate(results):
            name = row['category_name'] if row['category_name'] else 'Uncategorized'
            chart_data['labels'].append(name)
            chart_data['data'].append(float(row['total']))
            chart_data['colors'].append(colors[i % len(colors)])
            
    conn.close()
    
    return render_template('summary.html', 
                         accounts=accounts, 
                         selected_account_id=int(selected_account_id) if selected_account_id else None,
                         chart_data=chart_data)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
