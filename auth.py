import hashlib
import mysql.connector
from database import MYSQL_CONFIG

def hash_password(password):
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

def get_conn():
    try:
        return mysql.connector.connect(**MYSQL_CONFIG)
    except:
        return None

def register_user(username, password, full_name, email):
    """Register new user"""
    conn = get_conn()
    if not conn:
        return False, "❌ Database not connected. Start XAMPP!"

    cursor = conn.cursor()
    try:
        # Check if username exists
        cursor.execute(
            "SELECT id FROM users WHERE username = %s",
            (username,)
        )
        if cursor.fetchone():
            return False, "❌ Username already exists. Choose another."

        # Insert new user
        cursor.execute("""
            INSERT INTO users (username, password, full_name, email)
            VALUES (%s, %s, %s, %s)
        """, (
            username.strip(),
            hash_password(password),
            full_name.strip(),
            email.strip()
        ))
        conn.commit()
        return True, "✅ Account created successfully! Please login."

    except Exception as e:
        return False, f"❌ Error: {str(e)}"
    finally:
        cursor.close()
        conn.close()

def login_user(username, password):
    """Verify login credentials"""
    conn = get_conn()
    if not conn:
        return False, None, "❌ Database not connected. Start XAMPP!"

    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT id, username, full_name, email, role
            FROM users
            WHERE username = %s AND password = %s
        """, (username.strip(), hash_password(password)))

        user = cursor.fetchone()
        if user:
            return True, user, "✅ Login successful!"
        else:
            return False, None, "❌ Wrong username or password."

    except Exception as e:
        return False, None, f"❌ Error: {str(e)}"
    finally:
        cursor.close()
        conn.close()

def save_upload_history(user_id, filename, kpis, cp):
    """Save upload record to history"""
    conn = get_conn()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO upload_history
            (user_id, filename, total_revenue, total_expenses,
             net_profit, company_score, company_position)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            user_id,
            filename,
            float(kpis["total_revenue"]),
            float(kpis["total_expenses"]),
            float(kpis["net_profit"]),
            int(cp["total_score"]),
            str(cp["position"])
        ))
        conn.commit()
        return True
    except:
        return False
    finally:
        cursor.close()
        conn.close()

def save_user_chat(user_id, question, answer):
    """Save chat to user history"""
    conn = get_conn()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO user_chat_history (user_id, question, answer)
            VALUES (%s, %s, %s)
        """, (user_id, str(question), str(answer)))
        conn.commit()
        return True
    except:
        return False
    finally:
        cursor.close()
        conn.close()

def save_email_history(user_id, sent_to, alert_type):
    """Save email alert record"""
    conn = get_conn()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO email_history (user_id, sent_to, alert_type)
            VALUES (%s, %s, %s)
        """, (user_id, sent_to, alert_type))
        conn.commit()
        return True
    except:
        return False
    finally:
        cursor.close()
        conn.close()

def get_upload_history(user_id):
    """Get all uploads for this user"""
    conn = get_conn()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT filename, uploaded_at, total_revenue,
                   total_expenses, net_profit,
                   company_score, company_position
            FROM upload_history
            WHERE user_id = %s
            ORDER BY uploaded_at DESC
        """, (user_id,))
        return cursor.fetchall()
    except:
        return []
    finally:
        cursor.close()
        conn.close()

def get_user_chats(user_id):
    """Get chat history for this user"""
    conn = get_conn()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT question, answer, asked_at
            FROM user_chat_history
            WHERE user_id = %s
            ORDER BY asked_at DESC
            LIMIT 30
        """, (user_id,))
        return cursor.fetchall()
    except:
        return []
    finally:
        cursor.close()
        conn.close()

def get_email_history(user_id):
    """Get email alert history for this user"""
    conn = get_conn()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT sent_to, alert_type, sent_at
            FROM email_history
            WHERE user_id = %s
            ORDER BY sent_at DESC
        """, (user_id,))
        return cursor.fetchall()
    except:
        return []
    finally:
        cursor.close()
        conn.close()