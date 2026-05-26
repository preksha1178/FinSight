import sqlite3
import mysql.connector
from datetime import date
import pandas as pd

# ════════════════════════════════
#         CONFIGURATION
# ════════════════════════════════

MYSQL_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "finsight_db"
}

# ════════════════════════════════
#         CONNECTION HELPERS
# ════════════════════════════════

def get_mysql_connection():
    try:
        conn = mysql.connector.connect(**MYSQL_CONFIG)
        return conn
    except:
        return None

def mysql_check_connection():
    conn = get_mysql_connection()
    if conn:
        conn.close()
        return True
    return False

# ════════════════════════════════
#         SQLITE FUNCTIONS
# ════════════════════════════════

def sqlite_setup():
    """Create SQLite tables if not exist"""
    conn = sqlite3.connect("finsight.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            snapshot_date TEXT,
            total_revenue REAL,
            total_expenses REAL,
            net_profit REAL,
            profit_margin REAL,
            cash_runway_days INTEGER,
            company_score INTEGER,
            company_position TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question TEXT,
            answer TEXT,
            asked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def sqlite_save_snapshot(kpis, company_position):
    sqlite_setup()
    conn = sqlite3.connect("finsight.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO snapshots
        (snapshot_date, total_revenue, total_expenses, net_profit,
         profit_margin, cash_runway_days, company_score, company_position)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(date.today()),
        float(kpis["total_revenue"]),
        float(kpis["total_expenses"]),
        float(kpis["net_profit"]),
        float(kpis["avg_profit_margin"]),
        int(kpis["cash_runway_days"]),
        int(company_position["total_score"]),
        str(company_position["position"])
    ))
    conn.commit()
    conn.close()

def sqlite_save_chat(question, answer):
    sqlite_setup()
    conn = sqlite3.connect("finsight.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_history (question, answer) VALUES (?, ?)",
        (str(question), str(answer))
    )
    conn.commit()
    conn.close()

def sqlite_get_snapshots():
    sqlite_setup()
    conn = sqlite3.connect("finsight.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT snapshot_date, total_revenue, total_expenses,
               net_profit, profit_margin, cash_runway_days,
               company_score, company_position
        FROM snapshots ORDER BY snapshot_date DESC LIMIT 20
    """)
    rows = cursor.fetchall()
    conn.close()
    if rows:
        return pd.DataFrame(rows, columns=[
            "Date", "Revenue", "Expenses", "Net Profit",
            "Margin %", "Cash Runway", "Score", "Position"
        ])
    return None

def sqlite_get_chat_history():
    sqlite_setup()
    conn = sqlite3.connect("finsight.db")
    cursor = conn.cursor()
    cursor.execute("""
        SELECT question, answer, asked_at
        FROM chat_history
        ORDER BY asked_at DESC LIMIT 50
    """)
    rows = cursor.fetchall()
    conn.close()
    return rows

# ════════════════════════════════
#         MYSQL FUNCTIONS
# ════════════════════════════════

def mysql_save_financial_data(income_df, expense_df, cash_df):
    conn = get_mysql_connection()
    if not conn:
        return False, "❌ MySQL not connected. Is XAMPP running?"
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM income")
        cursor.execute("DELETE FROM expenses")
        cursor.execute("DELETE FROM cash_flow")

        for _, row in income_df.iterrows():
            cursor.execute("""
                INSERT INTO income
                (month, revenue, other_income, total_income)
                VALUES (%s, %s, %s, %s)
            """, (
                str(row["Month"]),
                float(row["Revenue"]),
                float(row["Other_Income"]),
                float(row["Revenue"] + row["Other_Income"])
            ))

        for _, row in expense_df.iterrows():
            total = float(row["Rent"] + row["Salaries"] +
                         row["Utilities"] + row["Marketing"] + row["Misc"])
            cursor.execute("""
                INSERT INTO expenses
                (month, rent, salaries, utilities, marketing, misc, total_expenses)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                str(row["Month"]),
                float(row["Rent"]),
                float(row["Salaries"]),
                float(row["Utilities"]),
                float(row["Marketing"]),
                float(row["Misc"]),
                total
            ))

        for _, row in cash_df.iterrows():
            closing = float(row["Opening_Balance"] +
                           row["Cash_In"] - row["Cash_Out"])
            cursor.execute("""
                INSERT INTO cash_flow
                (month, opening_balance, cash_in, cash_out, closing_balance)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                str(row["Month"]),
                float(row["Opening_Balance"]),
                float(row["Cash_In"]),
                float(row["Cash_Out"]),
                closing
            ))

        conn.commit()
        return True, "✅ Data saved to MySQL!"
    except Exception as e:
        conn.rollback()
        return False, f"❌ MySQL Error: {str(e)}"
    finally:
        cursor.close()
        conn.close()

def mysql_save_snapshot(kpis, company_position):
    conn = get_mysql_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO company_snapshots
            (snapshot_date, total_revenue, total_expenses, net_profit,
             profit_margin, cash_runway_days, company_score, company_position)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            date.today(),
            float(kpis["total_revenue"]),
            float(kpis["total_expenses"]),
            float(kpis["net_profit"]),
            float(kpis["avg_profit_margin"]),
            int(kpis["cash_runway_days"]),
            int(company_position["total_score"]),
            str(company_position["position"])
        ))
        conn.commit()
        return True
    except:
        return False
    finally:
        cursor.close()
        conn.close()

def mysql_save_chat(question, answer):
    conn = get_mysql_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO ai_chat_history (question, answer) VALUES (%s, %s)",
            (str(question), str(answer))
        )
        conn.commit()
        return True
    except:
        return False
    finally:
        cursor.close()
        conn.close()

def mysql_get_snapshots():
    conn = get_mysql_connection()
    if not conn:
        return None
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT snapshot_date, total_revenue, total_expenses,
                   net_profit, profit_margin, cash_runway_days,
                   company_score, company_position
            FROM company_snapshots
            ORDER BY snapshot_date DESC LIMIT 20
        """)
        return cursor.fetchall()
    except:
        return None
    finally:
        cursor.close()
        conn.close()

def mysql_get_chat_history():
    conn = get_mysql_connection()
    if not conn:
        return None
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("""
            SELECT question, answer, asked_at
            FROM ai_chat_history
            ORDER BY asked_at DESC LIMIT 50
        """)
        return cursor.fetchall()
    except:
        return None
    finally:
        cursor.close()
        conn.close()

def mysql_run_query(query):
    conn = get_mysql_connection()
    if not conn:
        return None, "MySQL not connected"
    try:
        result = pd.read_sql(query, conn)
        conn.close()
        return result, None
    except Exception as e:
        return None, str(e)
    finally:
        conn.close()