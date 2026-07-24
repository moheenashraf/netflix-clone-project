from database import get_connection


def add_log(username, action, module, ip_address):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO logs (username, action, module, ip_address) VALUES (%s, %s, %s, %s)",
        (username, action, module, ip_address)
    )
    conn.commit()
    cursor.close()
    conn.close()


def get_all_logs():
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM logs ORDER BY id DESC")
    logs = cursor.fetchall()
    cursor.close()
    conn.close()
    return logs


def get_logs_for_user(username):
    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM logs WHERE username = %s ORDER BY id DESC", (username,))
    logs = cursor.fetchall()
    cursor.close()
    conn.close()
    return logs