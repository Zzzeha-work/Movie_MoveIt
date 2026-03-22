import sqlite3

def get_db():
    """
    Open a SQLite connection to the application's database.
    
    Returns:
        conn (sqlite3.Connection): Connection to "movie_moveit.db" with rows represented as sqlite3.Row objects (allowing column access by name).
    """
    conn = sqlite3.connect("movie_moveit.db")
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Create the application's SQLite schema if it does not already exist.
    
    Creates the following tables and their key columns/constraints:
    - users: id (PK), email (unique, not null), created_at, last_login
    - otp_codes: id (PK), email (not null), code (not null), expires_at (not null)
    - likes: id (PK), user_id (not null), movie_id (not null), movie_title, poster_path, saved_at; UNIQUE(user_id, movie_id)
    - watchlist: id (PK), user_id (not null), movie_id (not null), movie_title, poster_path, saved_at; UNIQUE(user_id, movie_id)
    - folders: id (PK), user_id (not null), name (not null), created_at
    - folder_items: id (PK), folder_id (not null), movie_id (not null), movie_title, poster_path, added_at; UNIQUE(folder_id, movie_id)
    
    Commits the schema changes and closes the database connection.
    """
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