import sys
sys.path.insert(0, '.')
from database import init_db
import sqlite3

print("Calling init_db...")
init_db()
print("Done. Checking tables...")

conn = sqlite3.connect("trends.db")
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", tables)
conn.close()
