import sqlite3
import hashlib
from datetime import datetime
import bcrypt

DATABASE = 'fintrackr.db'

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, password_hash):
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE User (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE Budget (
            user_id INTEGER NOT NULL,
            budget_month TEXT NOT NULL,
            budget_amount DECIMAL(15, 2) NOT NULL,
            PRIMARY KEY (user_id, budget_month),
            FOREIGN KEY (user_id) REFERENCES User(user_id) ON DELETE CASCADE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE Notification (
            notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            notification_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            notification_type TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES User(user_id) ON DELETE CASCADE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE Account (
            account_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            account_name TEXT NOT NULL,
            account_type TEXT NOT NULL,
            balance DECIMAL(15, 2) DEFAULT 0.00,
            FOREIGN KEY (user_id) REFERENCES User(user_id) ON DELETE CASCADE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE Category (
            category_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            category_name TEXT NOT NULL,
            UNIQUE(user_id, category_name),
            FOREIGN KEY (user_id) REFERENCES User(user_id) ON DELETE CASCADE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE "Transaction" (
            transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_id INTEGER NOT NULL,
            category_id INTEGER,
            tx_date DATE NOT NULL,
            tx_type TEXT NOT NULL,
            amount DECIMAL(15, 2) NOT NULL,
            FOREIGN KEY (account_id) REFERENCES Account(account_id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES Category(category_id)
        )
    ''')

    default_categories = ['Entertainment', 'Food', 'Essentials']
    for category in default_categories:
        cursor.execute('INSERT OR IGNORE INTO Category (user_id, category_name) VALUES (NULL, ?)', (category,))
    
    conn.commit()
    conn.close()
    print("Database initialized successfully!")

if __name__ == '__main__':
    init_db()
