import sys
sys.path.insert(0, '.')
import sqlite3

# Check what tables exist
conn = sqlite3.connect("trends.db")
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print("Tables:", tables)
conn.close()

# Check which database.py is loaded
import database
print("Database file:", database.__file__)
