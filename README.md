# 🎬 Movie, MoveIt

> 영화를 검색하고, OTT 플랫폼을 확인하고, AI 추천을 받는 영화 정보 서비스

![Python](https://img.shields.io/badge/Python-3.13-blue)
![Flask](https://img.shields.io/badge/Flask-3.1.3-green)
![TMDB](https://img.shields.io/badge/TMDB-API-orange)
![Groq](https://img.shields.io/badge/Groq-LLaMA3-purple)

---

## 📌 프로젝트 소개

**Movie, MoveIt**은 영화 정보 검색, OTT 플랫폼 확인, AI 기반 영화 추천을 제공하는 웹 서비스입니다.
이메일 OTP 인증으로 간편하게 로그인하고, 좋아요/나중에 보기/폴더 기능으로 영화를 관리할 수 있습니다.

---

## ✨ 주요 기능

| 기능 | 설명 |
|---|---|
| 🔍 영화 검색 | 제목 / 감독 / 배우 이름으로 검색 |
| 📺 OTT 플랫폼 | 한국 기준 스트리밍 플랫폼 표시 |
| 🤖 AI 분석 | Groq LLaMA로 줄거리 요약 및 유사 영화 추천 |
| 🎮 취향 테스트 | 4지선다로 오늘의 맞춤 영화 추천 |
| 📧 이메일 로그인 | 비밀번호 없는 OTP 이메일 인증 |
| ❤️ 즐겨찾기 | 좋아요/ 싫어요 / 나중에 보기 / 폴더 관리 |
| 🌐 다국어 | 한국어 / English / 日本語 지원 |
| 🌙 다크모드 | 다크 / 라이트 테마 전환 |

---

## 🛠 기술 스택

**Backend**
- Python 3.13
- Flask 3.1.3
- SQLite3
- Flask-Mail (Gmail SMTP)

**Frontend**
- HTML5 / CSS3 / JavaScript
- Jinja2 템플릿 엔진
- 반응형 디자인 (CSS Grid)

**외부 API**
- TMDB API — 영화 정보, OTT 플랫폼, 출연진
- Groq API (LLaMA 3.1-8b-instant) — AI 분석 및 추천
- Gmail SMTP — OTP 인증 이메일

**개발 도구**
- PyCharm Community Edition
- GitHub + CodeRabbit (AI 코드 리뷰)
- Render (배포)

---

## 📁 프로젝트 구조
```
Movie_MoveIt/
├── app.py              # Flask 메인 서버
├── database.py         # SQLite DB 초기화
├── requirements.txt    # 패키지 목록
├── Procfile            # 배포 설정
└── templates/
    ├── base.html       # 공통 레이아웃
    ├── index.html      # 메인 검색 페이지
    ├── movie.html      # 영화 상세 페이지
    ├── login.html      # 로그인 페이지
    ├── mypage.html     # 마이페이지
    └── folder.html     # 폴더 페이지
```

---

## 🚀 로컬 실행 방법
```bash
# 1. 저장소 클론
git clone https://github.com/Zzzeha-work/Movie_MoveIt.git
cd Movie_MoveIt

# 2. 가상환경 생성 및 활성화
python -m venv venv
venv\Scripts\activate  # Windows

# 3. 패키지 설치
pip install -r requirements.txt

# 4. 환경변수 설정 (.env 파일 생성)
TMDB_API_KEY=발급받은키
GROQ_API_KEY=발급받은키
MAIL_USERNAME=Gmail주소
MAIL_PASSWORD=앱비밀번호
SECRET_KEY=임의의문자열

# 5. 서버 실행
python app.py
```

---

## 🗄 데이터베이스 구조
```
users          — 회원 정보 (이메일, 가입일)
otp_codes      — OTP 인증번호 (이메일, 코드, 만료시간)
likes          — 좋아요 목록
watchlist      — 나중에 보기 목록
folders        — 사용자 폴더
folder_items   — 폴더 내 영화
```

---

## 📱 페이지 구성

| 페이지 | URL | 설명 |
|---|---|---|
| 메인 | / | 영화 검색 + 취향 테스트 + 인기 영화 |
| 상세 | /movie/\<id\> | 영화 정보 + OTT + AI 분석 |
| 로그인 | /login | 이메일 OTP 인증 |
| 마이페이지 | /mypage | 즐겨찾기 + AI 추천 |
| 폴더 | /folder/\<id\> | 폴더별 영화 목록 |

---

## 🔐 환경변수

| 변수 | 설명 |
|---|---|
| TMDB_API_KEY | TMDB API 키 |
| GROQ_API_KEY | Groq API 키 |
| MAIL_USERNAME | Gmail 주소 |
| MAIL_PASSWORD | Gmail 앱 비밀번호 |
| SECRET_KEY | Flask 세션 키 |

---

## 👤 개발자

- **Zzzeha-work**
- 개발 기간: 2025년 3월 ~ 4월 (약 1개월)
- 개인 졸업작품 프로젝트

---

## 📄 License

This project is for educational purposes only.
