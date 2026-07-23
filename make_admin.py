from database import get_connection

email = input("Enter the email of the account to make admin: ").strip().lower()

conn = get_connection()
cursor = conn.cursor()

cursor.execute("SELECT id FROM users WHERE email = %s", (email,))
row = cursor.fetchone()

if not row:
    print(f"No account found with email: {email}")
else:
    cursor.execute("UPDATE users SET role = 'admin' WHERE email = %s", (email,))
    conn.commit()
    print(f"'{email}' is now an admin.")

cursor.close()
conn.close()