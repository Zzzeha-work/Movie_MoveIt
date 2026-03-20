from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor
import requests
import os

load_dotenv()

app = Flask(__name__)
TMDB_KEY  = os.getenv("TMDB_API_KEY")
TMDB_BASE = "https://api.themoviedb.org/3"

LANG_MAP = {
    "ko": "ko-KR",
    "en": "en-US",
    "ja": "ja-JP"
}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/search")
def search():
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

def fetch_detail(movie_id, tmdb_lang):
    """영화 기본정보 + OTT + 출연진 동시 호출"""
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

@app.route("/movie/<int:movie_id>")
def movie_detail(movie_id):
    lang      = request.args.get("lang", "ko")
    tmdb_lang = LANG_MAP.get(lang, "ko-KR")

    detail, providers, cast = fetch_detail(movie_id, tmdb_lang)

    return render_template("movie.html",
                           movie=detail,
                           providers=providers,
                           cast=cast,
                           current_lang=lang)

@app.route("/api/movie/<int:movie_id>")
def movie_api(movie_id):
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

@app.route("/ai-summary", methods=["POST"])
def ai_summary():
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

    # Groq 연동 (키 있을 때만 작동)
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

if __name__ == "__main__":
    app.run(debug=True)