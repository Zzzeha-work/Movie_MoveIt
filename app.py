from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
from flask_mail import Mail, Message
from database import get_db, init_db
import random
import string
import requests
import os
from datetime import datetime, timedelta

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "moviemoveit2025")
TMDB_KEY  = os.getenv("TMDB_API_KEY")
TMDB_BASE = "https://api.themoviedb.org/3"
LANG_MAP  = {"ko": "ko-KR", "en": "en-US", "ja": "ja-JP"}

# 이메일 설정
app.config['MAIL_SERVER']   = 'smtp.gmail.com'
app.config['MAIL_PORT']     = 587
app.config['MAIL_USE_TLS']  = True
app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
mail = Mail(app)

# DB 초기화
init_db()

# ─── 메인 ─────────────────────────────────────────────────
@app.route("/")
def index():
    """
    Render the application's main (home) page.
    
    Returns:
        Rendered HTML content for the index (home) page.
    """
    return render_template("index.html")

# ─── 영화 검색 ────────────────────────────────────────────
@app.route("/search")
def search():
    """
    Searches TMDB for movies matching the request's "q" query and returns up to 10 matching results.
    
    Reads the query string parameter "q" (default empty) and "lang" (defaults to "ko"), maps "lang" through LANG_MAP to choose the TMDB language, performs a TMDB /search/movie request, and returns the first 10 entries from the TMDB "results" array.
    
    Returns:
    	A JSON array of up to 10 movie result objects as returned by TMDB.
    """
    query     = request.args.get("q", "")
    lang      = request.args.get("lang", "ko")
    tmdb_lang = LANG_MAP.get(lang, "ko-KR")

    res = requests.get(f"{TMDB_BASE}/search/movie", params={
        "api_key":  TMDB_KEY,
        "query":    query,
        "language": tmdb_lang
    })
    movies = res.json().get("results", [])
    return jsonify(movies[:10])

# ─── 영화 상세 공통 함수 ──────────────────────────────────
def fetch_detail(movie_id, tmdb_lang):
    """
    Fetches a movie's full details, Korea-specific watch providers, and up to five cast members from TMDB.
    
    Parameters:
        movie_id (int | str): The TMDB movie identifier.
        tmdb_lang (str): TMDB language code used for detail and credits requests (e.g., "ko-KR", "en-US").
    
    Returns:
        tuple:
            detail (dict): Full TMDB movie detail JSON.
            providers (dict): Korea-specific provider info (contents of `results["KR"]`) or an empty dict if absent.
            cast (list): Up to five cast member objects (each a dict with cast fields) in billing order.
    """
    params_lang = {"api_key": TMDB_KEY, "language": tmdb_lang}
    params_base = {"api_key": TMDB_KEY}

    with ThreadPoolExecutor() as executor:
        f1 = executor.submit(requests.get,
             f"{TMDB_BASE}/movie/{movie_id}", params=params_lang)
        f2 = executor.submit(requests.get,
             f"{TMDB_BASE}/movie/{movie_id}/watch/providers", params=params_base)
        f3 = executor.submit(requests.get,
             f"{TMDB_BASE}/movie/{movie_id}/credits", params=params_lang)

    detail    = f1.result().json()
    providers = f2.result().json().get("results", {}).get("KR", {})
    cast      = f3.result().json().get("cast", [])[:5]
    return detail, providers, cast

# ─── 영화 상세 페이지 ─────────────────────────────────────
@app.route("/movie/<int:movie_id>")
def movie_detail(movie_id):
    """
    Render the movie detail page populated with TMDB data and user-specific status.
    
    Fetch movie details, watch providers, and cast from TMDB using the requested language, and render the "movie.html" template including whether the current user has liked or saved the movie and the user's folders when logged in.
    
    Parameters:
        movie_id: The TMDB movie identifier.
    
    Returns:
        A rendered template response for the movie detail page.
    """
    lang      = request.args.get("lang", "ko")
    tmdb_lang = LANG_MAP.get(lang, "ko-KR")
    detail, providers, cast = fetch_detail(movie_id, tmdb_lang)

    # 로그인 상태면 좋아요/나중에보기 여부 확인
    liked   = False
    watched = False
    user_folders = []
    if session.get("user_email"):
        db      = get_db()
        user    = db.execute("SELECT id FROM users WHERE email = ?",
                             (session["user_email"],)).fetchone()
        if user:
            user_id = user["id"]
            liked   = bool(db.execute(
                "SELECT id FROM likes WHERE user_id=? AND movie_id=?",
                (user_id, movie_id)).fetchone())
            watched = bool(db.execute(
                "SELECT id FROM watchlist WHERE user_id=? AND movie_id=?",
                (user_id, movie_id)).fetchone())
            user_folders = db.execute(
                "SELECT * FROM folders WHERE user_id=?", (user_id,)).fetchall()
        db.close()

    return render_template("movie.html",
                           movie=detail,
                           providers=providers,
                           cast=cast,
                           current_lang=lang,
                           liked=liked,
                           watched=watched,
                           user_folders=user_folders,
                           logged_in=bool(session.get("user_email")))

# ─── 영화 API (언어 변경용) ───────────────────────────────
@app.route("/api/movie/<int:movie_id>")
def movie_api(movie_id):
    """
    Provide a JSON response with selected movie details, streaming providers, and up to five cast members for the specified TMDB movie.
    
    Parameters:
        movie_id (int | str): TMDB movie identifier to fetch details for.
    
    Returns:
        response (flask.wrappers.Response): JSON object with keys:
            - title (str): Movie title.
            - overview (str): Movie overview/summary.
            - release_date (str): Release date string.
            - runtime (int): Runtime in minutes.
            - vote_average (float): Average user rating.
            - poster_path (str): Poster image path (TMDB).
            - providers (list): List of "flatrate" provider entries (empty list if none).
            - cast (list): Up to five cast member objects, each with:
                - name (str)
                - character (str)
                - profile_path (str)
    """
    lang      = request.args.get("lang", "ko")
    tmdb_lang = LANG_MAP.get(lang, "ko-KR")
    detail, providers, cast = fetch_detail(movie_id, tmdb_lang)

    return jsonify({
        "title":        detail.get("title", ""),
        "overview":     detail.get("overview", ""),
        "release_date": detail.get("release_date", ""),
        "runtime":      detail.get("runtime", 0),
        "vote_average": detail.get("vote_average", 0),
        "poster_path":  detail.get("poster_path", ""),
        "providers":    providers.get("flatrate", []),
        "cast": [
            {
                "name":         c.get("name", ""),
                "character":    c.get("character", ""),
                "profile_path": c.get("profile_path", "")
            }
            for c in cast
        ]
    })

# ─── AI 분석 ──────────────────────────────────────────────
@app.route("/ai-summary", methods=["POST"])
def ai_summary():
    """
    Generate an AI-written movie summary, three genre keywords, and two similar-movie recommendations in the requested language.
    
    Reads JSON from the request body with keys:
    - `title` (str): movie title used in the prompt.
    - `overview` (str): movie overview included in the prompt.
    - `lang` (str, optional): one of "ko", "en", "ja"; falls back to "ko" if missing or unsupported.
    
    If the environment variable `GROQ_API_KEY` is set, queries the GROQ chat completion model and returns the model's textual response. If `GROQ_API_KEY` is not set, returns a human-readable message indicating the AI feature is not configured.
    
    Returns:
        dict: JSON-serializable mapping with key `"summary"` containing the AI-generated text or a configuration notice.
    """
    data     = request.json
    title    = data.get("title", "")
    overview = data.get("overview", "")
    lang     = data.get("lang", "ko")

    prompts = {
        "ko": f"""영화 '{title}'에 대해 한국어로 작성해주세요:
1. 핵심 줄거리 요약 (2~3문장)
2. 장르 키워드 3개
3. 추천 유사 영화 2편
줄거리: {overview}""",
        "en": f"""About the movie '{title}', please provide in English:
1. Brief plot summary (2-3 sentences)
2. 3 genre keywords
3. 2 similar movie recommendations
Overview: {overview}""",
        "ja": f"""映画「{title}」について日本語で教えてください:
1. あらすじの要約（2〜3文）
2. ジャンルキーワード3つ
3. 似ている映画のおすすめ2本
あらすじ：{overview}"""
    }

    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        from groq import Groq
        client  = Groq(api_key=groq_key)
        message = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompts.get(lang, prompts["ko"])}]
        )
        return jsonify({"summary": message.choices[0].message.content})
    else:
        return jsonify({"summary": "AI 분석 기능을 사용하려면 GROQ_API_KEY를 설정해주세요."})

# ─── 로그인 페이지 ────────────────────────────────────────
@app.route("/login")
def login():
    """
    Render the login page or redirect already authenticated users to their account page.
    
    Returns:
        A Flask response that renders the "login.html" template, or a redirect response to the "mypage" route when a user is already logged in.
    """
    if session.get("user_email"):
        return redirect(url_for("mypage"))
    return render_template("login.html")

# ─── OTP 발송 ─────────────────────────────────────────────
@app.route("/send-otp", methods=["POST"])
def send_otp():
    """
    Generate and send a 6-digit one-time password (OTP) to the given email address and store it in the database with a 5-minute expiry.
    
    Validates the JSON request's "email" field (non-empty, contains "@"). If valid, deletes any existing OTP for the email, inserts a new OTP record with a 5-minute expiration, attempts to fetch a random popular movie to include as a recommendation in the email, and sends an HTML email containing the OTP (and optional movie recommendation). Returns a JSON response describing success or failure.
    
    Returns:
        dict: A JSON-serializable dict:
            - {"ok": True, "msg": "인증번호가 발송되었습니다!"} on successful send.
            - {"ok": False, "msg": "<error message>"} on validation failure or email/send error.
    
    Side effects:
        - Inserts a row into the `otp_codes` table and deletes any prior OTP for the email.
        - Sends an email via the configured Flask-Mail instance.
    """
    email = request.json.get("email", "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"ok": False, "msg": "이메일 형식이 올바르지 않습니다."})

    code       = ''.join(random.choices(string.digits, k=6))
    expires_at = datetime.now() + timedelta(minutes=5)

    db = get_db()
    db.execute("DELETE FROM otp_codes WHERE email = ?", (email,))
    db.execute("INSERT INTO otp_codes (email, code, expires_at) VALUES (?, ?, ?)",
               (email, code, expires_at))
    db.commit()
    db.close()

    # 랜덤 추천 영화 가져오기
    try:
        popular = requests.get(f"{TMDB_BASE}/movie/popular", params={
            "api_key": TMDB_KEY,
            "language": "ko-KR",
            "page": 1
        }).json().get("results", [])
        pick = random.choice(popular[:10]) if popular else None
    except:
        pick = None

    # 추천 영화 HTML 섹션
    movie_section = ""
    if pick:
        poster_url = f"https://image.tmdb.org/t/p/w300{pick['poster_path']}" \
                     if pick.get("poster_path") else ""
        movie_section = f"""
        <tr>
          <td style="padding:0 32px 32px;">
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="border-top:1px solid #2a2a2a; padding-top:24px;">
              <tr>
                <td>
                  <p style="color:#888; font-size:11px; text-transform:uppercase;
                             letter-spacing:1px; margin:0 0 14px;">
                    오늘의 추천 영화
                  </p>
                  <table cellpadding="0" cellspacing="0">
                    <tr>
                      {"<td style='padding-right:14px; vertical-align:top;'><img src='" + poster_url + "' width='70' style='border-radius:6px; display:block;'></td>" if poster_url else ""}
                      <td style="vertical-align:top;">
                        <p style="color:#fff; font-size:14px; font-weight:600;
                                   margin:0 0 5px;">{pick.get('title', '')}</p>
                        <p style="color:#888; font-size:12px; margin:0 0 8px;">
                          {str(pick.get('release_date',''))[:4]}
                          &nbsp;·&nbsp;
                          ⭐ {round(pick.get('vote_average', 0), 1)}
                        </p>
                        <p style="color:#aaa; font-size:12px; line-height:1.6; margin:0;">
                          {pick.get('overview', '')[:120]}...
                        </p>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>
          </td>
        </tr>
        """

    try:
        msg = Message(
            subject="[Movie, MoveIt] 인증번호",
            sender=os.getenv("MAIL_USERNAME"),
            recipients=[email]
        )
        msg.html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin:0; padding:0; background-color:#0d0d0d;
             font-family:-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="background:#0d0d0d; padding:40px 20px;">
    <tr>
      <td align="center">
        <table width="520" cellpadding="0" cellspacing="0"
               style="background:#141414; border-radius:16px;
                      border:1px solid #2a2a2a; overflow:hidden;">

          <!-- 헤더 -->
          <tr>
            <td style="background:#e50914; padding:20px 32px;">
              <p style="margin:0; color:#fff; font-size:20px;
                         font-weight:700; letter-spacing:1px;">
                🎬 Movie, MoveIt
              </p>
              <p style="margin:4px 0 0; color:rgba(255,255,255,0.7); font-size:12px;">
                영화를 발견하고, 움직이세요
              </p>
            </td>
          </tr>

          <!-- 본문 -->
          <tr>
            <td style="padding:32px 32px 24px;">
              <p style="color:#ccc; font-size:15px; line-height:1.6; margin:0 0 24px;">
                안녕하세요!<br>
                아래 인증번호를 입력해 로그인을 완료하세요.
              </p>

              <!-- 인증번호 박스 -->
              <table width="100%" cellpadding="0" cellspacing="0"
                     style="background:#1e1e1e; border:1px solid #333;
                            border-radius:12px; margin-bottom:20px;">
                <tr>
                  <td style="padding:24px; text-align:center;">
                    <p style="color:#888; font-size:12px; text-transform:uppercase;
                               letter-spacing:2px; margin:0 0 12px;">인증번호</p>
                    <p style="color:#e50914; font-size:42px; font-weight:800;
                               letter-spacing:10px; margin:0;">
                      {code}
                    </p>
                    <p style="color:#666; font-size:12px; margin:12px 0 0;">
                      ⏱ 5분 이내에 입력해주세요
                    </p>
                  </td>
                </tr>
              </table>

              <p style="color:#666; font-size:12px; line-height:1.7; margin:0;">
                본인이 요청하지 않은 경우 이 메일을 무시하세요.<br>
                계정은 자동으로 보호됩니다.
              </p>
            </td>
          </tr>

          <!-- 추천 영화 -->
          {movie_section}

          <!-- 푸터 -->
          <tr>
            <td style="padding:16px 32px; border-top:1px solid #2a2a2a;">
              <p style="color:#555; font-size:11px; margin:0; text-align:center;">
                © 2025 Movie, MoveIt &nbsp;·&nbsp; 이 메일은 자동 발송되었습니다.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""
        mail.send(msg)
        return jsonify({"ok": True, "msg": "인증번호가 발송되었습니다!"})
    except Exception as e:
        return jsonify({"ok": False, "msg": f"이메일 발송 실패: {str(e)}"})

# ─── OTP 인증 ─────────────────────────────────────────────
@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    """
    Verify a submitted one-time password (OTP) for an email address and sign the user in.
    
    On success, removes the used OTP, creates the user record if it does not exist, updates the user's last login time, stores the user's email in the session under "user_email", and commits database changes. On failure, no database changes are made and the request is rejected.
    
    Returns:
        A JSON response:
        - `{"ok": True, "msg": "로그인 성공!"}` when the OTP is valid and login succeeds.
        - `{"ok": False, "msg": "인증번호가 틀리거나 만료되었습니다."}` when the OTP is missing, incorrect, or expired.
    """
    email = request.json.get("email", "").strip().lower()
    code  = request.json.get("code", "").strip()

    db  = get_db()
    row = db.execute(
        "SELECT * FROM otp_codes WHERE email=? AND code=? AND expires_at>?",
        (email, code, datetime.now())
    ).fetchone()

    if not row:
        db.close()
        return jsonify({"ok": False, "msg": "인증번호가 틀리거나 만료되었습니다."})

    db.execute("DELETE FROM otp_codes WHERE email=?", (email,))
    user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not user:
        db.execute("INSERT INTO users (email) VALUES (?)", (email,))
    db.execute("UPDATE users SET last_login=? WHERE email=?",
               (datetime.now(), email))
    db.commit()
    db.close()

    session["user_email"] = email
    return jsonify({"ok": True, "msg": "로그인 성공!"})

# ─── 로그아웃 ─────────────────────────────────────────────
@app.route("/logout")
def logout():
    """
    Clear the current user session and redirect the client to the application's index page.
    
    Returns:
        A Flask redirect response to the index (root) route.
    """
    session.clear()
    return redirect(url_for("index"))

# ─── 좋아요 토글 ──────────────────────────────────────────
@app.route("/like", methods=["POST"])
def toggle_like():
    """
    Toggle the authenticated user's like status for a movie.
    
    If the user is not logged in, returns an error response. Otherwise this endpoint
    adds or removes a row in the `likes` table for the current user and the given
    movie, committing the change before returning.
    
    Returns:
    	A JSON object with:
    	- `ok` (bool): `True` on success, `False` when login is required.
    	- `liked` (bool, present when `ok` is `True`): `True` if the movie is now liked, `False` if the like was removed.
    	- `msg` (str, present when `ok` is `False`): error message explaining the failure (e.g., "로그인이 필요합니다.").
    """
    if not session.get("user_email"):
        return jsonify({"ok": False, "msg": "로그인이 필요합니다."})

    data        = request.json
    movie_id    = data.get("movie_id")
    movie_title = data.get("movie_title")
    poster_path = data.get("poster_path")

    db      = get_db()
    user    = db.execute("SELECT id FROM users WHERE email=?",
                         (session["user_email"],)).fetchone()
    user_id = user["id"]
    exists  = db.execute(
        "SELECT id FROM likes WHERE user_id=? AND movie_id=?",
        (user_id, movie_id)).fetchone()

    if exists:
        db.execute("DELETE FROM likes WHERE user_id=? AND movie_id=?",
                   (user_id, movie_id))
        liked = False
    else:
        db.execute(
            "INSERT INTO likes (user_id, movie_id, movie_title, poster_path) VALUES (?,?,?,?)",
            (user_id, movie_id, movie_title, poster_path))
        liked = True

    db.commit()
    db.close()
    return jsonify({"ok": True, "liked": liked})

# ─── 나중에 보기 토글 ─────────────────────────────────────
@app.route("/watchlist", methods=["POST"])
def toggle_watchlist():
    """
    Toggle whether the currently logged-in user has the given movie in their watchlist.
    
    Reads `movie_id`, `movie_title`, and `poster_path` from the request JSON and checks the user's watchlist in the database. If the movie is present it is removed; if absent it is inserted (using the provided title and poster). Requires an authenticated session.
    
    Returns:
        dict: On success, `{"ok": True, "saved": <bool>}` where `saved` is `True` if the movie was added and `False` if it was removed. If the user is not logged in, returns `{"ok": False, "msg": "로그인이 필요합니다."}`.
    """
    if not session.get("user_email"):
        return jsonify({"ok": False, "msg": "로그인이 필요합니다."})

    data        = request.json
    movie_id    = data.get("movie_id")
    movie_title = data.get("movie_title")
    poster_path = data.get("poster_path")

    db      = get_db()
    user    = db.execute("SELECT id FROM users WHERE email=?",
                         (session["user_email"],)).fetchone()
    user_id = user["id"]
    exists  = db.execute(
        "SELECT id FROM watchlist WHERE user_id=? AND movie_id=?",
        (user_id, movie_id)).fetchone()

    if exists:
        db.execute("DELETE FROM watchlist WHERE user_id=? AND movie_id=?",
                   (user_id, movie_id))
        saved = False
    else:
        db.execute(
            "INSERT INTO watchlist (user_id, movie_id, movie_title, poster_path) VALUES (?,?,?,?)",
            (user_id, movie_id, movie_title, poster_path))
        saved = True

    db.commit()
    db.close()
    return jsonify({"ok": True, "saved": saved})

# ─── 마이페이지 ───────────────────────────────────────────
@app.route("/mypage")
def mypage():
    """
    Render the authenticated user's profile page with their saved likes, watchlist, and folders.
    
    If there is no logged-in user, redirect to the login page.
    
    @returns A Flask response: a redirect to the login page when the user is not authenticated, otherwise the rendered "mypage.html" template with context variables `user`, `likes`, `watchlist`, and `folders`.
    """
    if not session.get("user_email"):
        return redirect(url_for("login"))

    db      = get_db()
    user    = db.execute("SELECT * FROM users WHERE email=?",
                         (session["user_email"],)).fetchone()
    user_id = user["id"]
    likes     = db.execute(
        "SELECT * FROM likes WHERE user_id=? ORDER BY saved_at DESC",
        (user_id,)).fetchall()
    watchlist = db.execute(
        "SELECT * FROM watchlist WHERE user_id=? ORDER BY saved_at DESC",
        (user_id,)).fetchall()
    folders   = db.execute(
        "SELECT * FROM folders WHERE user_id=? ORDER BY created_at DESC",
        (user_id,)).fetchall()
    db.close()

    return render_template("mypage.html",
                           user=user,
                           likes=likes,
                           watchlist=watchlist,
                           folders=folders)

# ─── 폴더 생성 ────────────────────────────────────────────
@app.route("/folder/create", methods=["POST"])
def create_folder():
    """
    Create a new folder for the currently logged-in user.
    
    Inserts a folder row linked to the authenticated user's account using the `name` field from the JSON request body.
    
    Returns:
        dict: `{'ok': True, 'folder_id': int, 'name': str}` on success.
        dict: `{'ok': False, 'msg': str}` on failure (e.g., user not logged in or `name` is empty).
    """
    if not session.get("user_email"):
        return jsonify({"ok": False, "msg": "로그인이 필요합니다."})

    name = request.json.get("name", "").strip()
    if not name:
        return jsonify({"ok": False, "msg": "폴더 이름을 입력해주세요."})

    db      = get_db()
    user    = db.execute("SELECT id FROM users WHERE email=?",
                         (session["user_email"],)).fetchone()
    db.execute("INSERT INTO folders (user_id, name) VALUES (?,?)",
               (user["id"], name))
    db.commit()
    folder_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.close()
    return jsonify({"ok": True, "folder_id": folder_id, "name": name})

# ─── 폴더에 영화 추가 ─────────────────────────────────────
@app.route("/folder/add", methods=["POST"])
def add_to_folder():
    """
    Add a movie to a folder for the currently logged-in user using fields from the request JSON.
    
    Expects request JSON to contain:
        folder_id, movie_id, movie_title, poster_path
    
    Returns:
        dict: JSON response with one of:
            - {"ok": True} on successful insertion.
            - {"ok": False, "msg": "로그인이 필요합니다."} if no user is logged in.
            - {"ok": False, "msg": "이미 추가된 영화입니다."} if the movie could not be added (e.g., duplicate).
    """
    if not session.get("user_email"):
        return jsonify({"ok": False, "msg": "로그인이 필요합니다."})

    data        = request.json
    folder_id   = data.get("folder_id")
    movie_id    = data.get("movie_id")
    movie_title = data.get("movie_title")
    poster_path = data.get("poster_path")

    db = get_db()
    try:
        db.execute(
            "INSERT INTO folder_items (folder_id, movie_id, movie_title, poster_path) VALUES (?,?,?,?)",
            (folder_id, movie_id, movie_title, poster_path))
        db.commit()
        return jsonify({"ok": True})
    except:
        return jsonify({"ok": False, "msg": "이미 추가된 영화입니다."})
    finally:
        db.close()

# ─── 폴더 상세 페이지 ─────────────────────────────────────
@app.route("/folder/<int:folder_id>")
def folder_detail(folder_id):
    """
    Render the folder page for the specified folder, requiring the user to be authenticated.
    
    Parameters:
        folder_id (int): Primary key of the folder to display.
    
    Returns:
        A Flask response: redirects to the login page if the user is not authenticated, otherwise renders the "folder.html" template with `folder` and `items`.
    """
    if not session.get("user_email"):
        return redirect(url_for("login"))

    db     = get_db()
    folder = db.execute("SELECT * FROM folders WHERE id=?",
                        (folder_id,)).fetchone()
    items  = db.execute(
        "SELECT * FROM folder_items WHERE folder_id=? ORDER BY added_at DESC",
        (folder_id,)).fetchall()
    db.close()

    return render_template("folder.html", folder=folder, items=items)

if __name__ == "__main__":
    app.run(debug=True)