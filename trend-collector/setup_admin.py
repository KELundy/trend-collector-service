import sqlite3
conn = sqlite3.connect("trends.db")
conn.execute("UPDATE users SET role='admin' WHERE id=1")
conn.commit()
rows = conn.execute("SELECT id, email, role FROM users").fetchall()
for r in rows:
    print(r)
conn.close()
