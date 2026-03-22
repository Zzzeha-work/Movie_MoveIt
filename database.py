import sqlite3

def get_db():
    conn = sqlite3.connect("movie_moveit.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # 유저 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT UNIQUE NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_login DATETIME
        )
    """)

    # OTP 인증번호 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS otp_codes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            email      TEXT NOT NULL,
            code       TEXT NOT NULL,
            expires_at DATETIME NOT NULL
        )
    """)

    # 좋아요 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS likes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            movie_id    INTEGER NOT NULL,
            movie_title TEXT,
            poster_path TEXT,
            saved_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, movie_id)
        )
    """)

    # 나중에 보기 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            movie_id    INTEGER NOT NULL,
            movie_title TEXT,
            poster_path TEXT,
            saved_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, movie_id)
        )
    """)

    # 폴더 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS folders (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            name       TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 폴더 아이템 테이블
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS folder_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            folder_id   INTEGER NOT NULL,
            movie_id    INTEGER NOT NULL,
            movie_title TEXT,
            poster_path TEXT,
            added_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(folder_id, movie_id)
        )
    """)

    conn.commit()
    conn.close()
    print("DB 초기화 완료!")

if __name__ == "__main__":
    init_db()