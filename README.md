# Қойма — тауар қоймасын басқару жүйесі

Курстық жұмыс: тауар қоймасын басқаруға арналған веб-жүйе. Тауарларды есепке алады, қоймаға кіріс пен шығысты тіркейді, қалдығы аз тауарларды көрсетеді және қолданушыларға рөл бойынша рұқсат береді.

## Мүмкіндіктер

- **Авторизация:** тіркелу (Registration), кіру (Login), шығу (Logout). Токен HttpOnly cookie-де сақталады, шыққанда токен жарамсыз етіледі.
- **Рөлдер:**

| Рөл | Не істей алады |
|---|---|
| `user` (Қолданушы) | Тауарлар мен тарихты қарау. Тіркелген кез келген адамға автоматты беріледі |
| `manager` (Меңгеруші) | `user` мүмкіндіктері, тауар қосу/өзгерту, кіріс және шығыс |
| `admin` (Әкімші) | Бәрі, тауарды жою, қолданушылардың рөлін өзгерту және аккаунтты жою |

- **Негізгі бизнес-логика:** тауар CRUD, кіріс/шығыс, қалдықтан артық шығысты бұғаттау, қалдығы аз тауарларды белгілеу, қойма құнын есептеу, қозғалыс тарихы.
- **Валидация:** барлық кіріс деректері `pydantic` арқылы тексеріледі (түрі, ұзындығы, формат, өрістің қосымша болмауы).
- **Error handling:** барлық қате бірыңғай JSON форматымен қайтады, дұрыс HTTP кодтарымен.
- **Testing:** 38 автоматты тест (`pytest`).

## Технологиялар

| Қабат | Технология |
|---|---|
| Frontend | HTML, CSS, JavaScript (`app/static/`) |
| Backend | Python 3, Flask, REST API (JSON) |
| Database | SQLite (әдепкі) немесе PostgreSQL (Neon, Supabase, Railway) |
| Авторизация | JWT (PyJWT), құпиясөз хэші `scrypt` (Werkzeug) |
| Валидация | pydantic |
| Тест | pytest |

## Жоба құрылымы

```
app/
  __init__.py      Flask қолданбасын құру, логтау, бастапқы деректер
  config.py        .env оқу
  db.py            SQLite / PostgreSQL қабаты, кестелер схемасы
  auth.py          JWT жасау/тексеру, рөлдерді қорғау (@require)
  validation.py    pydantic модельдері, қазақша қате хабарлары
  errors.py        қателерді өңдеу
  seed.py          бастапқы admin/manager және демо-тауарлар
  routes/          auth.py, products.py, users.py (API маршруттары)
  static/          index.html, style.css, app.js (интерфейс)
tests/             conftest.py, test_auth.py, test_products.py, test_users.py
run.py             жергілікті іске қосу
Procfile           хостингте іске қосу (gunicorn)
.env.example       баптаулар үлгісі
```

## Жергілікті іске қосу

```bash
# 1. Виртуалды орта және тәуелділіктер
python -m venv .venv
.venv\Scripts\activate            # Windows
# source .venv/bin/activate       # macOS / Linux
pip install -r requirements.txt

# 2. Баптаулар
copy .env.example .env            # Windows  (macOS/Linux: cp .env.example .env)
# .env ашып, SECRET_KEY және аккаунт құпиясөздерін өзгертіңіз

# 3. Іске қосу
python run.py
```

Сайт: http://127.0.0.1:5000

Бірінші іске қосуда база мен кестелер өздігінен жасалады, `.env`-тегі `ADMIN_*` және `MANAGER_*` мәндерімен бастапқы аккаунттар қосылады. `SEED_DEMO_DATA=1` болса, 5 демо-тауар да қосылады.

## .env айнымалылары

| Айнымалы | Мағынасы |
|---|---|
| `SECRET_KEY` | JWT қол қою кілті, кемінде 32 таңба. Жасырын сақталады |
| `DATABASE_URL` | Бос қалдырса, SQLite (`warehouse.db`). PostgreSQL үшін `postgresql://user:pass@host/db` |
| `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` | Бастапқы әкімші |
| `MANAGER_USERNAME`, `MANAGER_EMAIL`, `MANAGER_PASSWORD` | Бастапқы меңгеруші |
| `SEED_DEMO_DATA` | `1` болса, бос базаға демо-тауарлар қосылады |
| `TOKEN_HOURS` | Токеннің жарамдылық мерзімі, сағатпен (әдепкі 8) |
| `COOKIE_SECURE` | HTTPS хостингте `1` қойыңыз |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING` |

`.env` файлы `.gitignore`-да тұр, GitHub-қа жүктелмейді. Үлгісі `.env.example` ішінде.

## REST API

Жауаптар JSON форматында. Жүйеге кіргеннен кейін токен cookie-де автоматты жіберіледі (не `Authorization: Bearer <token>` тақырыбымен).

| Method | URL | Рөл | Сипаттамасы |
|---|---|---|---|
| POST | `/api/auth/register` | — | Тіркелу (рөлі `user`) |
| POST | `/api/auth/login` | — | Кіру |
| POST | `/api/auth/logout` | кез келген | Шығу, токен жарамсыз болады |
| GET | `/api/auth/me` | кез келген | Ағымдағы қолданушы |
| GET | `/api/products` | кез келген | Тізім. `search`, `low=1`, `limit`, `offset` |
| GET | `/api/products/<id>` | кез келген | Бір тауар |
| POST | `/api/products` | manager, admin | Тауар қосу |
| PUT | `/api/products/<id>` | manager, admin | Толық өзгерту |
| PATCH | `/api/products/<id>` | manager, admin | Жартылай өзгерту |
| DELETE | `/api/products/<id>` | admin | Жою |
| POST | `/api/products/<id>/movements` | manager, admin | Кіріс/шығыс: `{"type":"in\|out","quantity":5}` |
| GET | `/api/movements` | кез келген | Қозғалыс тарихы |
| GET | `/api/stats` | кез келген | Қойма статистикасы |
| GET | `/api/users` | admin | Қолданушылар тізімі |
| PATCH | `/api/users/<id>` | admin | Рөлді өзгерту: `{"role":"manager"}` |
| DELETE | `/api/users/<id>` | admin | Аккаунтты жою |
| GET | `/api/health` | — | Сервер жұмысын тексеру |

**HTTP кодтары:** `200` сәтті, `201` жасалды, `204` жойылды, `400` JSON қате, `401` кірмеген немесе токен жарамсыз, `403` рұқсат жоқ, `404` табылмады, `409` қайшылық (логин/артикул бос емес, қалдық жеткіліксіз), `422` валидация қатесі, `429` тым көп сәтсіз кіру әрекеті, `500` сервер қатесі.

**Қате форматы:**

```json
{"error": {"code": "validation_error", "message": "Енгізілген деректерде қате бар.",
           "details": [{"field": "price", "message": "Мәні 0-ден кем болмауы керек."}]}}
```

**Мысал (curl):**

```bash
curl -c cookies.txt -H "Content-Type: application/json" \
     -d '{"username":"admin","password":"<ADMIN_PASSWORD>"}' http://127.0.0.1:5000/api/auth/login
curl -b cookies.txt http://127.0.0.1:5000/api/products
```

## Қауіпсіздік

- Құпиясөздер ашық күйінде сақталмайды, `scrypt` хэші ғана сақталады.
- Токен `HttpOnly` + `SameSite=Lax` cookie-де. JavaScript оны оқи алмайды.
- Логинді таңдап бұзудан қорғау: 5 минутта 5 сәтсіз әрекеттен кейін 429.
- Қате логин мен қате құпиясөзге бірдей жауап беріледі (аккаунттың бар-жоғы білінбейді).
- Тіркелу арқылы тек `user` рөлін алуға болады, рөлді өзгертуге тек `admin` құқылы.
- Рөл әр сұраныста базадан тексеріледі, сондықтан рөл өзгергенде бірден күшіне енеді.
- SQL сұраныстары параметрлермен жазылған (SQL injection-нан қорғау), интерфейсте мәтін экрандалады (XSS-тен қорғау).
- Шығысты тексеру `UPDATE ... WHERE quantity >= ?` ішінде жасалады, сондықтан қалдық минусқа кетпейді.

## Тестілеу

```bash
python -m pytest -v
```

38 тест тексереді: тіркелу және кіру валидациясы, қайталанған логин/email, шығудан кейін токеннің жарамсыздығы, жалған және мерзімі өткен токен, рөлдер бойынша рұқсат (`user`/`manager`/`admin`), тауар CRUD, кіріс/шығыс, қалдықтан артық шығыс, іздеу мен сүзгі, статистика, қолданушыларды басқару, қателердің JSON форматы.

## Debugging (қателерді анықтау)

- Барлық маңызды оқиғалар (кіру, сәтсіз кіру, тауар қосу/өзгерту/жою, рөл ауысуы) консольге және `logs/app.log` файлына жазылады.
- Күтпеген қате болса, қолданушыға жалпы хабар көрсетіледі, ал толық себебі (stack trace) `logs/app.log` ішінде қалады.
- Қателерді қадамдап қарау үшін: `FLASK_DEBUG=1 python run.py`. Қате бетін браузер көрсетеді, код өзгергенде сервер қайта іске қосылады. Тек жергілікті компьютерде қолданыңыз.
- Деталды лог үшін `.env` ішінде `LOG_LEVEL=DEBUG`.
- Браузерде: F12 → Network қойындысында әр API сұранысының коды мен JSON жауабы көрінеді.

## PostgreSQL-ға (Neon / Supabase / Railway) өту

1. Neon немесе Supabase-те жаңа база жасап, байланыс жолын (connection string) көшіріңіз.
2. `.env` ішінде жазыңыз: `DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require`
3. `pip install -r requirements.txt` (`psycopg2-binary` қосылған), `python run.py`. Кестелер бірінші іске қосуда өздігінен жасалады.

## Хостингке шығару (Render мысалы)

1. Кодты GitHub-қа жүктеңіз.
2. Render.com → New → Web Service → GitHub репозиторийін таңдаңыз.
3. Build command: `pip install -r requirements.txt`. Start command: `gunicorn "app:create_app()"`.
4. Environment бөліміне `.env` мәндерін қосыңыз (`SECRET_KEY`, `DATABASE_URL`, `ADMIN_*`, `MANAGER_*`, `COOKIE_SECURE=1`). Хостингте SQLite файлы сақталмауы мүмкін, сондықтан PostgreSQL қолданыңыз.
5. Жеке домен болса, Render → Settings → Custom Domains бөлімінде қосыңыз.

## Git жұмыс процесі

- `main` — тұрақты нұсқа.
- Әр бөлім бөлек branch-та жасалып, Merge арқылы `main`-ге қосылған: `feature/backend`, `feature/frontend`, `feature/tests`, `docs/readme`.
- Тарихты қарау: `git log --oneline --graph --all`.

## Белгілі шектеулер

- Рөлді өзгерткенде қолданушының ескі токені жарамды қалады, бірақ рөл әр сұраныста базадан оқылады, сондықтан жаңа құқық бірден қолданылады.
- Логинді бұғаттау есебі сервердің жадында сақталады. Сервер қайта қосылса, нөлге түседі.
- Email растау және құпиясөзді қалпына келтіру жоқ (қосымша функция ретінде Resend/Brevo арқылы қосуға болады).
