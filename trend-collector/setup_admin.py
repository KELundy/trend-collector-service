import sys
sys.path.insert(0, '.')
from database import init_db
import sqlite3

init_db()
conn = sqlite3.connect("trends.db")
conn.execute("UPDATE users SET role='admin' WHERE id=1")
conn.commit()
rows = conn.execute("SELECT id, email, role FROM users").fetchall()
for r in rows:
    print(r)
conn.close()
