import sqlite3
import os

def initialize_database():
    if os.path.exists("farm_game.db"):
        os.remove("farm_game.db")  # 可注释掉，保留旧数据
        print("🗑 旧数据库已删除")

    with open("init_db.sql", "r", encoding="gbk") as f:  
        sql_script = f.read()

    conn = sqlite3.connect("farm_game.db")
    conn.executescript(sql_script)
    conn.commit()
    conn.close()
    print("✅ 数据库初始化成功")

if __name__ == "__main__":
    initialize_database()
