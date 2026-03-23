from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
# from flask_mail import Mail, Message
from database import get_db, init_db
from datetime import datetime, timedelta
import random
import string
import requests
import os
import threading

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "moviemoveit2025")
TMDB_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE = "https://api.themoviedb.org/3"
LANG_MAP = {"ko": "ko-KR", "en": "en-US", "ja": "ja-JP"}

# 이메일 설정
import resend

# app.config['MAIL_SERVER'] = 'smtp.gmail.com'
# app.config['MAIL_PORT'] = 587
# app.config['MAIL_USE_TLS'] = True
# app.config['MAIL_USE_SSL'] = False
# app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
# app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")
# app.config['MAIL_DEFAULT_SENDER'] = os.getenv("MAIL_USERNAME")
# app.config['MAIL_TIMEOUT'] = 30
# mail = Mail(app)

# DB 초기화
init_db()


# ─── 메인 ─────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


# ─── 영화 검색 ────────────────────────────────────────────
@app.route("/search")
def search():
    query = request.args.get("q", "")
    lang = request.args.get("lang", "ko")
    tmdb_lang = LANG_MAP.get(lang, "ko-KR")

    movie_res = requests.get(f"{TMDB_BASE}/search/movie", params={
        "api_key": TMDB_KEY,
        "query": query,
        "language": tmdb_lang
    })
    movies = movie_res.json().get("results", [])

    person_res = requests.get(f"{TMDB_BASE}/search/person", params={
        "api_key": TMDB_KEY,
        "query": query,
        "language": tmdb_lang
    })
    persons = person_res.json().get("results", [])

    person_movies = []
    for person in persons[:3]:
        for credit in person.get("known_for", []):
            if credit.get("media_type") == "movie":
                credit["matched_person"] = person.get("name", "")
                credit["matched_role"] = person.get("known_for_department", "")
                person_movies.append(credit)

    movie_ids = {m["id"] for m in movies}
    person_movies = [m for m in person_movies if m["id"] not in movie_ids]

    return jsonify({
        "movies": movies[:10],
        "person_movies": person_movies[:6],
    })


# ─── 영화 상세 공통 함수 ──────────────────────────────────
def fetch_detail(movie_id, tmdb_lang):
    params_lang = {"api_key": TMDB_KEY, "language": tmdb_lang}
    params_base = {"api_key": TMDB_KEY}

    with ThreadPoolExecutor() as executor:
        f1 = executor.submit(requests.get,
                             f"{TMDB_BASE}/movie/{movie_id}", params=params_lang)
        f2 = executor.submit(requests.get,
                             f"{TMDB_BASE}/movie/{movie_id}/watch/providers", params=params_base)
        f3 = executor.submit(requests.get,
                             f"{TMDB_BASE}/movie/{movie_id}/credits", params=params_lang)

    detail = f1.result().json()
    providers = f2.result().json().get("results", {}).get("KR", {})
    cast = f3.result().json().get("cast", [])[:5]
    return detail, providers, cast


# ─── 영화 상세 페이지 ─────────────────────────────────────
@app.route("/movie/<int:movie_id>")
def movie_detail(movie_id):
    lang = request.args.get("lang", "ko")
    tmdb_lang = LANG_MAP.get(lang, "ko-KR")
    detail, providers, cast = fetch_detail(movie_id, tmdb_lang)

    liked = False
    watched = False
    user_folders = []
    if session.get("user_email"):
        db = get_db()
        user = db.execute("SELECT id FROM users WHERE email = ?",
                          (session["user_email"],)).fetchone()
        if user:
            user_id = user["id"]
            liked = bool(db.execute(
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
    lang = request.args.get("lang", "ko")
    tmdb_lang = LANG_MAP.get(lang, "ko-KR")
    detail, providers, cast = fetch_detail(movie_id, tmdb_lang)

    return jsonify({
        "title": detail.get("title", ""),
        "overview": detail.get("overview", ""),
        "release_date": detail.get("release_date", ""),
        "runtime": detail.get("runtime", 0),
        "vote_average": detail.get("vote_average", 0),
        "poster_path": detail.get("poster_path", ""),
        "providers": providers.get("flatrate", []),
        "cast": [
            {
                "name": c.get("name", ""),
                "character": c.get("character", ""),
                "profile_path": c.get("profile_path", "")
            }
            for c in cast
        ]
    })


# ─── AI 분석 ──────────────────────────────────────────────
@app.route("/ai-summary", methods=["POST"])
def ai_summary():
    data = request.json
    title = data.get("title", "")
    overview = data.get("overview", "")
    lang = data.get("lang", "ko")

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
        client = Groq(api_key=groq_key)
        message = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            max_tokens=500,
            messages=[{"role": "user", "content": prompts.get(lang, prompts["ko"])}]
        )
        return jsonify({"summary": message.choices[0].message.content})
    else:
        return jsonify({"summary": "AI 분석 기능을 사용하려면 GROQ_API_KEY를 설정해주세요."})


# ─── 로그인 페이지 ────────────────────────────────────────
@app.route("/login")
def login():
    if session.get("user_email"):
        return redirect(url_for("mypage"))
    return render_template("login.html")


# ─── OTP 발송 ─────────────────────────────────────────────
@app.route("/send-otp", methods=["POST"])
def send_otp():
    email = request.json.get("email", "").strip().lower()
    if not email or "@" not in email:
        return jsonify({"ok": False, "msg": "이메일 형식이 올바르지 않습니다."})

    code = ''.join(random.choices(string.digits, k=6))
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
                             letter-spacing:1px; margin:0 0 14px;">오늘의 추천 영화</p>
                  <table cellpadding="0" cellspacing="0">
                    <tr>
                      {"<td style='padding-right:14px; vertical-align:top;'><img src='" + poster_url + "' width='70' style='border-radius:6px; display:block;'></td>" if poster_url else ""}
                      <td style="vertical-align:top;">
                        <p style="color:#fff; font-size:14px; font-weight:600; margin:0 0 5px;">
                            {pick.get('title', '')}</p>
                        <p style="color:#888; font-size:12px; margin:0 0 8px;">
                          {str(pick.get('release_date', ''))[:4]} &nbsp;·&nbsp;
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
        </tr>"""

    # 이메일 HTML
    html_content = f"""<!DOCTYPE html>
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
          <tr>
            <td style="background:#e50914; padding:20px 32px;">
              <p style="margin:0; color:#fff; font-size:20px;
                         font-weight:700; letter-spacing:1px;">🎬 Movie, MoveIt</p>
              <p style="margin:4px 0 0; color:rgba(255,255,255,0.7); font-size:12px;">
                영화를 발견하고, 움직이세요</p>
            </td>
          </tr>
          <tr>
            <td style="padding:32px 32px 24px;">
              <p style="color:#ccc; font-size:15px; line-height:1.6; margin:0 0 24px;">
                안녕하세요!<br>아래 인증번호를 입력해 로그인을 완료하세요.</p>
              <table width="100%" cellpadding="0" cellspacing="0"
                     style="background:#1e1e1e; border:1px solid #333;
                            border-radius:12px; margin-bottom:20px;">
                <tr>
                  <td style="padding:24px; text-align:center;">
                    <p style="color:#888; font-size:12px; text-transform:uppercase;
                               letter-spacing:2px; margin:0 0 12px;">인증번호</p>
                    <p style="color:#e50914; font-size:42px; font-weight:800;
                               letter-spacing:10px; margin:0;">{code}</p>
                    <p style="color:#666; font-size:12px; margin:12px 0 0;">
                      ⏱ 5분 이내에 입력해주세요</p>
                  </td>
                </tr>
              </table>
              <p style="color:#666; font-size:12px; line-height:1.7; margin:0;">
                본인이 요청하지 않은 경우 이 메일을 무시하세요.<br>
                계정은 자동으로 보호됩니다.</p>
            </td>
          </tr>
          {movie_section}
          <tr>
            <td style="padding:16px 32px; border-top:1px solid #2a2a2a;">
              <p style="color:#555; font-size:11px; margin:0; text-align:center;">
                © 2025 Movie, MoveIt &nbsp;·&nbsp; 이 메일은 자동 발송되었습니다.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    # 비동기 이메일 발송
    def send_mail_async():
        try:
            import sib_api_v3_sdk
            configuration = sib_api_v3_sdk.Configuration()
            configuration.api_key['api-key'] = os.getenv("BREVO_API_KEY")
            api = sib_api_v3_sdk.TransactionalEmailsApi(
                sib_api_v3_sdk.ApiClient(configuration))
            api.send_transac_email(
                sib_api_v3_sdk.SendSmtpEmail(
                    to=[{"email": email}],
                    sender={"email": os.getenv("MAIL_USERNAME"),
                            "name": "Movie MoveIt"},
                    subject="[Movie, MoveIt] 인증번호",
                    html_content=html_content
                )
            )
            print(f"Mail sent to {email}")
        except Exception as e:
            print(f"Mail error: {e}")

    threading.Thread(target=send_mail_async).start()
    return jsonify({"ok": True, "msg": "인증번호가 발송되었습니다!"})


# ─── OTP 인증 ─────────────────────────────────────────────
@app.route("/verify-otp", methods=["POST"])
def verify_otp():
    email = request.json.get("email", "").strip().lower()
    code = request.json.get("code", "").strip()

    db = get_db()
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
    session.clear()
    return redirect(url_for("index"))


# ─── 좋아요 토글 ──────────────────────────────────────────
@app.route("/like", methods=["POST"])
def toggle_like():
    if not session.get("user_email"):
        return jsonify({"ok": False, "msg": "로그인이 필요합니다."})

    data = request.json
    movie_id = data.get("movie_id")
    movie_title = data.get("movie_title")
    poster_path = data.get("poster_path")

    db = get_db()
    user = db.execute("SELECT id FROM users WHERE email=?",
                      (session["user_email"],)).fetchone()
    user_id = user["id"]
    exists = db.execute(
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
    if not session.get("user_email"):
        return jsonify({"ok": False, "msg": "로그인이 필요합니다."})

    data = request.json
    movie_id = data.get("movie_id")
    movie_title = data.get("movie_title")
    poster_path = data.get("poster_path")

    db = get_db()
    user = db.execute("SELECT id FROM users WHERE email=?",
                      (session["user_email"],)).fetchone()
    user_id = user["id"]
    exists = db.execute(
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
    if not session.get("user_email"):
        return redirect(url_for("login"))

    lang = request.args.get("lang", "ko")

    db = get_db()
    user = db.execute("SELECT * FROM users WHERE email=?",
                      (session["user_email"],)).fetchone()
    user_id = user["id"]
    likes = db.execute(
        "SELECT * FROM likes WHERE user_id=? ORDER BY saved_at DESC",
        (user_id,)).fetchall()
    watchlist = db.execute(
        "SELECT * FROM watchlist WHERE user_id=? ORDER BY saved_at DESC",
        (user_id,)).fetchall()
    folders = db.execute(
        "SELECT * FROM folders WHERE user_id=? ORDER BY created_at DESC",
        (user_id,)).fetchall()
    db.close()

    return render_template("mypage.html",
                           user=user,
                           likes=likes,
                           watchlist=watchlist,
                           folders=folders,
                           current_lang=lang)


# ─── 폴더 생성 ────────────────────────────────────────────
@app.route("/folder/create", methods=["POST"])
def create_folder():
    if not session.get("user_email"):
        return jsonify({"ok": False, "msg": "로그인이 필요합니다."})

    name = request.json.get("name", "").strip()
    if not name:
        return jsonify({"ok": False, "msg": "폴더 이름을 입력해주세요."})

    db = get_db()
    user = db.execute("SELECT id FROM users WHERE email=?",
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
    if not session.get("user_email"):
        return jsonify({"ok": False, "msg": "로그인이 필요합니다."})

    data = request.json
    folder_id = data.get("folder_id")
    movie_id = data.get("movie_id")
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
    if not session.get("user_email"):
        return redirect(url_for("login"))

    db = get_db()
    folder = db.execute("SELECT * FROM folders WHERE id=?",
                        (folder_id,)).fetchone()
    items = db.execute(
        "SELECT * FROM folder_items WHERE folder_id=? ORDER BY added_at DESC",
        (folder_id,)).fetchall()
    db.close()

    return render_template("folder.html", folder=folder, items=items)


# ─── 취향 기반 AI 추천 ────────────────────────────────────
@app.route("/ai-recommend", methods=["POST"])
def ai_recommend():
    data = request.json
    liked_movies = data.get("liked_movies", [])
    lang = data.get("lang", "ko")
    movie_list = ", ".join(liked_movies[:10])

    prompts = {
        "ko": f"""사용자가 좋아하는 영화 목록: {movie_list}

이 취향을 분석해서 아래 형식으로 추천해주세요:

🎯 취향 분석
(2문장으로 이 사람의 영화 취향 설명)

🎬 추천 영화 3편
1. 영화제목 - 추천 이유 한 줄
2. 영화제목 - 추천 이유 한 줄
3. 영화제목 - 추천 이유 한 줄

📚 추천 책 1권
책제목 - 추천 이유 한 줄""",
        "en": f"""User's liked movies: {movie_list}

Based on this taste, recommend in this format:

🎯 Taste Analysis
(2 sentences about their movie preference)

🎬 3 Movie Recommendations
1. Title - One line reason
2. Title - One line reason
3. Title - One line reason

📚 1 Book Recommendation
Title - One line reason""",
        "ja": f"""ユーザーが好きな映画: {movie_list}

この好みを分析して以下の形式で推薦してください：

🎯 好み分析
（2文でこの人の映画の好みを説明）

🎬 おすすめ映画3本
1. タイトル - おすすめ理由1行
2. タイトル - おすすめ理由1行
3. タイトル - おすすめ理由1行

📚 おすすめ本1冊
タイトル - おすすめ理由1行"""
    }

    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        from groq import Groq
        client = Groq(api_key=groq_key)
        message = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            max_tokens=500,
            messages=[{"role": "user", "content": prompts.get(lang, prompts["ko"])}]
        )
        return jsonify({"result": message.choices[0].message.content})
    else:
        return jsonify({"result": "GROQ_API_KEY를 설정해주세요."})


# ─── 취향 테스트 AI 결과 ──────────────────────────────────
@app.route("/ai-quiz", methods=["POST"])
def ai_quiz():
    data = request.json
    answers = data.get("answers", {})
    lang = data.get("lang", "ko")

    a1 = answers.get(1, "")
    a2 = answers.get(2, "")
    a3 = answers.get(3, "")
    a4 = answers.get(4, "")

    prompts = {
        "ko": f"""사용자의 오늘 영화 취향 테스트 결과:
- 오늘 기분: {a1}
- 선호 배경: {a2}
- 같이 볼 사람: {a3}
- 보고 난 후 원하는 기분: {a4}

아래 형식으로 추천해주세요:

✨ 오늘의 추천 영화 타입
(이 사람에게 맞는 영화 스타일 2문장)

🎬 딱 맞는 영화 3편
1. 영화제목 - 이유 한 줄
2. 영화제목 - 이유 한 줄
3. 영화제목 - 이유 한 줄

📚 어울리는 책 1권
책제목 - 이유 한 줄""",
        "en": f"""Today's movie taste test:
- Mood: {a1}
- Preferred setting: {a2}
- Watching with: {a3}
- Desired feeling after: {a4}

Recommend in this format:

✨ Today's Recommended Movie Type
(2 sentences about what suits them)

🎬 3 Perfect Movies
1. Title - One line reason
2. Title - One line reason
3. Title - One line reason

📚 1 Matching Book
Title - One line reason""",
        "ja": f"""今日の映画の好みテスト結果：
- 今日の気分: {a1}
- 好みの舞台: {a2}
- 一緒に見る人: {a3}
- 見た後に感じたいこと: {a4}

以下の形式で推薦してください：

✨ 今日のおすすめ映画タイプ
（この人に合う映画スタイル2文）

🎬 ぴったりの映画3本
1. タイトル - 理由1行
2. タイトル - 理由1行
3. タイトル - 理由1行

📚 合う本1冊
タイトル - 理由1行"""
    }

    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        from groq import Groq
        client = Groq(api_key=groq_key)
        message = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            max_tokens=500,
            messages=[{"role": "user", "content": prompts.get(lang, prompts["ko"])}]
        )
        return jsonify({"result": message.choices[0].message.content})
    else:
        return jsonify({"result": "GROQ_API_KEY를 설정해주세요."})


# ─── 인기 영화 ────────────────────────────────────────────
@app.route("/popular")
def popular():
    lang = request.args.get("lang", "ko")
    tmdb_lang = LANG_MAP.get(lang, "ko-KR")
    res = requests.get(f"{TMDB_BASE}/movie/popular", params={
        "api_key": TMDB_KEY,
        "language": tmdb_lang,
        "page": 1
    })
    movies = res.json().get("results", [])
    return jsonify({"movies": movies[:5]})


if __name__ == "__main__":
    app.run(debug=True)
