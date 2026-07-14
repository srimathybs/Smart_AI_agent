"""sql_tool.py — SQLite database with sample data"""
import sqlite3, os

DB_PATH = "smart_agent.db"

def _ensure_db():
    if os.path.exists(DB_PATH): return
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS sales (id INTEGER PRIMARY KEY, month TEXT, revenue REAL, units INTEGER, region TEXT)")
    c.executemany("INSERT INTO sales VALUES (?,?,?,?,?)", [
        (1,"Jan 2025",45000,320,"South"),(2,"Feb 2025",52000,380,"North"),
        (3,"Mar 2025",48000,340,"East"),(4,"Apr 2025",61000,450,"South"),
        (5,"May 2025",72000,520,"West"),(6,"Jun 2025",88000,640,"South"),
        (7,"Jul 2025",95000,700,"North"),(8,"Aug 2025",110000,810,"South"),
    ])
    c.execute("CREATE TABLE IF NOT EXISTS customers (id INTEGER PRIMARY KEY, name TEXT, segment TEXT, spend REAL, city TEXT)")
    c.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", [
        (1,"Ravi Kumar","Premium",12000,"Chennai"),(2,"Priya Sharma","Standard",3500,"Mumbai"),
        (3,"Arjun Nair","Premium",15000,"Bangalore"),(4,"Meera Pillai","Standard",2800,"Hyderabad"),
        (5,"Karthik Raja","Trial",500,"Chennai"),(6,"Divya Menon","Premium",18000,"Pune"),
    ])
    conn.commit(); conn.close()

class SQLQueryTool:
    name = "query_database"
    description = "Run SQL on SQLite DB. INPUT: SQL query. OUTPUT: results table. Tables: sales(month,revenue,units,region), customers(name,segment,spend,city)."
    def _run(self, query: str) -> str:
        _ensure_db()
        try:
            conn = sqlite3.connect(DB_PATH); c = conn.cursor()
            c.execute(query); rows = c.fetchall()
            cols = [d[0] for d in c.description] if c.description else []
            conn.close()
            if not rows: return "No results."
            col_w = [max(len(str(col)), max(len(str(r[i])) for r in rows)) for i,col in enumerate(cols)]
            header = " | ".join(str(col).ljust(w) for col,w in zip(cols,col_w))
            sep    = "-+-".join("-"*w for w in col_w)
            data   = [" | ".join(str(cell).ljust(w) for cell,w in zip(row,col_w)) for row in rows]
            return f"Results ({len(rows)} rows):\n\n" + "\n".join([header,sep]+data)
        except Exception as e: return f"SQL error: {str(e)}"
