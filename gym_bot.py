# -*- coding: utf-8 -*-
# ===================================================================================
#  GYM BOT v13.0 — НАУЧНЫЙ КОМБАЙН ДЛЯ ГИПЕРТРОФИИ
#  Полный монолит: Антропометрия, Navy Fat, TDEE, Recovery v3.0, PubMed x10
# ===================================================================================
# === ИМПОРТЫ ===
import os
# Фикс прокси для стабильной работы на PythonAnywhere (исключает ошибку 503 Tunnel Connection)
os.environ['http_proxy'] = 'http://proxy.server:3128'
os.environ['https_proxy'] = 'http://proxy.server:3128'

import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import json
import os
import csv
import time
import random
import io
import math
import urllib.request
import threading
from datetime import datetime, timedelta
from collections import defaultdict
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

# === БАЗА ЗНАНИЙ PUBMED И ДВИЖОК ТРЕНИРОВОК ===
try:
    from pubmed_knowledge import PUBMED_KNOWLEDGE, PUBMED_MYTHS, PUBMED_LANDMARKS, PUBMED_STANDARDS
except ImportError as e:
    print("Warning: Could not import pubmed_knowledge, using fallback empty dictionaries.", e)
    PUBMED_KNOWLEDGE = {}
    PUBMED_MYTHS = {}
    PUBMED_LANDMARKS = {}
    PUBMED_STANDARDS = {}

try:
    from training_engine import (
        generate_workout_program, get_warmup_ladder, calculate_rpe_adjustment,
        calculate_epley_1rm, EXERCISE_DATABASE, VOLUME_LANDMARKS,
        get_available_splits, analyze_athlete_profile
    )
except ImportError as e:
    print("Warning: Could not import training_engine:", e)
    generate_workout_program = None
    get_warmup_ladder = None
    calculate_rpe_adjustment = None
    calculate_epley_1rm = None
    def get_available_splits(d):
        if d == 3:
            return [
                {"id": "auto", "name": "🧬 ИИ Автовыбор"},
                {"id": "recovery_3d", "name": "🛡 Anti-Overtraining (3 дня)"},
                {"id": "ppl_3d", "name": "💪 Push / Pull / Legs (3 дня)"},
                {"id": "arnold_3d", "name": "👑 Arnold Split (3 дня)"},
                {"id": "sbd_3d", "name": "🏆 SBD Троеборье (3 дня)"},
                {"id": "full_body_3d", "name": "🔥 Full Body A/B/C (3 дня)"}
            ]
        elif d == 4:
            return [
                {"id": "auto", "name": "🧬 ИИ Автовыбор"},
                {"id": "upper_lower_4d", "name": "🏋️ Upper / Lower A & B (4 дня)"},
                {"id": "ppl_upper_4d", "name": "💪 PPL + Upper (4 дня)"},
                {"id": "sbd_power_4d", "name": "🏆 SBD Powerbuilding (4 дня)"}
            ]
        elif d == 5:
            return [
                {"id": "auto", "name": "🧬 ИИ Автовыбор"},
                {"id": "upper_lower_ppl_5d", "name": "🚀 Upper/Lower + PPL (5 дней)"},
                {"id": "bro_split_5d", "name": "🥩 Classic Bro Split (5 дней)"}
            ]
        elif d == 6:
            return [
                {"id": "auto", "name": "🧬 ИИ Автовыбор"},
                {"id": "ppl_6d", "name": "💪 Push / Pull / Legs × 2 (6 дней)"},
                {"id": "arnold_6d", "name": "👑 Arnold Split × 2 (6 дней)"}
            ]
        else:
            return [
                {"id": "auto", "name": "🧬 ИИ Автовыбор"},
                {"id": "full_body_2d", "name": "🔥 Full Body A & B (2 дня)"},
                {"id": "upper_lower_2d", "name": "🏋️ Верх / Низ Экспресс (2 дня)"}
            ]
    def analyze_athlete_profile(*a, **k):
        return {
            "recommendation": "Сбалансированное распределение объёма",
            "sbd_total": 0, "bench_ratio": 0, "squat_ratio": 0, "dead_ratio": 0
        }
    EXERCISE_DATABASE = {}
    VOLUME_LANDMARKS = {}

# ── ТОКЕН И ПРОКСИ (Автонастройка для PythonAnywhere) ──────────
TOKEN = os.environ.get('BOT_TOKEN', '8793508863:AAGt5pqrfPY3tmA4XhleEeOcJUstPQJp9aM')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

import telebot.apihelper as _apihelper
if os.path.exists('/home/kABACH0k') or 'PYTHONANYWHERE_DOMAIN' in os.environ or 'PYTHONANYWHERE_SITE' in os.environ:
    _apihelper.proxy = {
        'https': 'http://proxy.server:3128',
        'http': 'http://proxy.server:3128'
    }
else:
    PROXY_URL = ''   # ← вставь сюда свой рабочий прокси если локально
    if PROXY_URL:
        _apihelper.proxy = {'https': PROXY_URL, 'http': PROXY_URL}
    else:
        _apihelper.proxy = None
bot = telebot.TeleBot(TOKEN, threaded=True)

def query_gemini_coach(user_id, question_text):
    user_id_str = str(user_id)
    user_history = gym_db.get(user_id_str, [])
    
    # 1ПМ Рекорды
    records = {}
    for w in user_history:
        try:
            wt = float(w.get('weight', 0))
            rp = float(w.get('reps', 0))
            if wt > 0 and rp > 0:
                e = epley_1rm(wt, rp)
                ex = w.get('exercise', '')
                if ex and (ex not in records or e > records[ex]):
                    records[ex] = e
        except Exception:
            pass
            
    rec_str = ", ".join([f"{k}: {v} кг (1ПМ)" for k, v in records.items()]) if records else "Жим 69.3 кг, Присед 90.7 кг, Тяга 108.0 кг"
    
    # Последние тренировки с RPE
    by_date = {}
    for w in user_history:
        d = w.get('date')
        if d:
            by_date.setdefault(d, []).append(w)
            
    sorted_dates = sorted(by_date.keys(), key=lambda x: parse_date(x) or datetime.min, reverse=True)[:5]
    recent_summary = ""
    for d in sorted_dates:
        ex_dict = {}
        for s in by_date[d]:
            ex = s.get('exercise', 'Упр')
            rpe = s.get('rpe') or s.get('diff') or 'Легко'
            wt = s.get('weight', 0)
            rp = s.get('reps', 0)
            ex_dict.setdefault(ex, []).append(f"{wt}кг×{rp} ({rpe})")
        recent_summary += f"\n- {d}: " + "; ".join([f"{ex}: {', '.join(sets)}" for ex, sets in ex_dict.items()])
        
    user_profile = profiles_db.get(user_id_str, {})
    height_cm = user_profile.get('height_cm') or user_profile.get('height') or 180
    user_body = body_db.get(user_id_str, [])
    bw = (user_body[-1].get('bodyweight') if user_body else None) or user_profile.get('weight') or 75
    
    system_context = f"""
Ты — персональный научный тренер по силовым тренировкам (Evidence-Based Coach) на базе PubMed.
Данные атлета:
- Рост: {height_cm} см
- Вес тела: {bw} кг
- 1ПМ Рекорды: {rec_str}
- Всего подходов в дневнике: {len(user_history)}
- Последние тренировки с RPE: {recent_summary or 'Жим 50кг×6 (Тяжело)'}
- Особенность: Чувствительность к осевой нагрузке на позвоночник.

Вопрос атлета: "{question_text}".

Ответь структурированно, кратко, четко, с практическими советами в килограммах/подходах/повторениях, ссылаясь на доказательный тренинг (PubMed).
""".strip()

    models_to_try = [
        'gemini-2.5-flash',
        'gemini-2.5-pro',
        'gemini-3.6-flash',
        'gemini-flash-latest'
    ]
    
    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": system_context}]}
            ]
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            res = urllib.request.urlopen(req, timeout=10)
            res_data = json.loads(res.read().decode('utf-8'))
            if 'candidates' in res_data and res_data['candidates'] and res_data['candidates'][0].get('content'):
                return res_data['candidates'][0]['content']['parts'][0]['text']
        except Exception:
            continue
            
    return (
        f"🤖 *ИИ-Тренер (Научный анализ):*\n\n"
        f"Ваши рекорды: *{rec_str}* (в базе *{len(user_history)}* подходов).\n\n"
        f"Рекомендация по вопросу: _«{question_text}»_:\n"
        f"1. Тренируйтесь с запасом RIR 1-2 (RPE 7.5-8.0), избегая постоянных отказов (*Helms et al., 2018*).\n"
        f"2. Сохраняйте баланс жимовых и тяговых движений 1:1 для здоровья плечевого пояса.\n"
        f"3. Разносите тяжелые осевые нагрузки (присед и тягу) минимум на 48-72 часа."
    )
DB_FILE         = 'gym_database.json'
BODY_DB_FILE    = 'body_database.json'
PROFILE_DB_FILE = 'profiles_database.json'
PROGRAM_DB_FILE = 'programs_database.json'
user_states  = {}
temp_workout = {}
gym_db       = {}
body_db      = {}
profiles_db  = {}
programs_db  = {}
_db_lock          = threading.Lock()
_body_db_lock     = threading.Lock()
_profile_db_lock  = threading.Lock()
_program_db_lock  = threading.Lock()
DAYS_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
MOTIVATION_QUOTES = [
    "💀 «Боль временна. Слава вечна.» — Lance Armstrong",
    "🦾 «Мышцы не растут в зале — они растут во время восстановления.»",
    "🔥 «Разница между теми, кто выиграл и проиграл — это сделанный подход.»",
    "⚡️ «ЦНС — твой главный актив. Береги её.»",
    "🏆 «Слабый день сегодня — рекорд завтра.»",
    "💪 «Тяжёлая тренировка — это инвестиция в себя с 72-часовой доходностью.»",
    "🧬 «Суперкомпенсация — это не миф. Это биохимия.»",
    "📈 «Прогрессивная перегрузка. Каждую неделю.»",
    "🔩 «Настоящий атлет — тот, кто тренируется когда не хочется.»",
    "🌙 «Сон — это когда мышцы на самом деле растут. Спи 8 часов.»",
]
# === БАЗА ДАННЫХ — ЗАГРУЗКА/СОХРАНЕНИЕ ===
class AutoSyncDict(dict):
    def __init__(self, filepath, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.filepath = filepath
        self._last_mtime = 0
        self.reload()

    def reload(self):
        try:
            if not os.path.exists(self.filepath):
                return
            mtime = os.path.getmtime(self.filepath)
            if mtime > self._last_mtime:
                with open(self.filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self.clear()
                super().update(data)
                self._last_mtime = mtime
        except Exception:
            pass

    def get(self, key, default=None):
        self.reload()
        return super().get(key, default)

    def __getitem__(self, key):
        self.reload()
        return super().__getitem__(key)

    def __contains__(self, key):
        self.reload()
        return super().__contains__(key)

    def save(self):
        try:
            tmp = self.filepath + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(dict(self), f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.filepath)
            self._last_mtime = os.path.getmtime(self.filepath)
        except Exception as e:
            print(f"[ERROR] save_db: {e}")

gym_db = AutoSyncDict(DB_FILE)

def load_db():
    gym_db.reload()

def save_db():
    with _db_lock:
        gym_db.save()
def load_body_db():
    global body_db
    if os.path.exists(BODY_DB_FILE):
        try:
            with open(BODY_DB_FILE, 'r', encoding='utf-8') as f:
                body_db = json.load(f)
        except Exception:
            body_db = {}
    else:
        body_db = {}
def save_body_db():
    with _body_db_lock:
        try:
            tmp = BODY_DB_FILE + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(body_db, f, ensure_ascii=False, indent=2)
            os.replace(tmp, BODY_DB_FILE)
        except Exception as e:
            print(f"[ERROR] save_body_db: {e}")
def load_profile_db():
    global profiles_db
    if os.path.exists(PROFILE_DB_FILE):
        try:
            with open(PROFILE_DB_FILE, 'r', encoding='utf-8') as f:
                profiles_db = json.load(f)
        except Exception:
            profiles_db = {}
    else:
        profiles_db = {}
def save_profile_db():
    with _profile_db_lock:
        try:
            tmp = PROFILE_DB_FILE + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(profiles_db, f, ensure_ascii=False, indent=2)
            os.replace(tmp, PROFILE_DB_FILE)
        except Exception as e:
            print(f"[ERROR] save_profile_db: {e}")

def load_program_db():
    global programs_db
    if os.path.exists(PROGRAM_DB_FILE):
        try:
            with open(PROGRAM_DB_FILE, 'r', encoding='utf-8') as f:
                programs_db = json.load(f)
        except Exception:
            programs_db = {}
    else:
        programs_db = {}

def save_program_db():
    with _program_db_lock:
        try:
            tmp = PROGRAM_DB_FILE + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(programs_db, f, ensure_ascii=False, indent=2)
            os.replace(tmp, PROGRAM_DB_FILE)
        except Exception as e:
            print(f"[ERROR] save_program_db: {e}")

def clear_user_state(user_id):
    user_states.pop(user_id, None)
    temp_workout.pop(user_id, None)
load_db()
load_body_db()
load_profile_db()
load_program_db()
# === ВСПОМОГАТЕЛЬНЫЕ МАТЕМАТИЧЕСКИЕ ФУНКЦИИ ===
def get_date_and_day(dt_obj):
    return dt_obj.strftime("%d.%m.%Y"), DAYS_RU[dt_obj.weekday()]
def parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%d.%m.%Y")
    except Exception:
        return None
def format_reps_clean(s):
    if isinstance(s, dict):
        r = s.get('reps', 0)
        rir = s.get('rir')
    else:
        r = s
        rir = None
    try:
        r_float = float(r)
        if r_float == int(r_float):
            r_str = str(int(r_float))
        else:
            r_str = str(r_float)
    except Exception:
        r_str = str(r)
    if rir is not None:
        try:
            rir_float = float(rir)
            if rir_float == int(rir_float):
                rir_str = str(int(rir_float))
            else:
                rir_str = str(rir_float)
        except Exception:
            rir_str = str(rir)
        return f"{r_str} (+{rir_str} в зап.)"
    return r_str

def epley_1rm(weight, reps):
    try:
        reps_f = float(reps)
    except Exception:
        reps_f = 0.0
    if reps_f <= 1:
        return float(weight)
    return round(float(weight) * (1 + reps_f / 30.0), 1)

def brzycki_1rm(weight, reps):
    try:
        reps_f = float(reps)
    except Exception:
        reps_f = 0.0
    if reps_f >= 37:
        return float(weight)
    denom = 1.0278 - 0.0278 * reps_f
    if denom <= 0:
        return float(weight)
    return round(float(weight) / denom, 1)
def make_progress_bar(pct_str, length=10):
    try:
        pct = int(str(pct_str).replace('%', ''))
    except Exception:
        pct = 0
    filled = round((pct / 100) * length)
    bar = "█" * filled + "░" * (length - filled)
    return f"[{bar}] {pct}%"
def escape_md(text):
    """Экранирует символы Markdown в пользовательских данных."""
    if not text:
        return ''
    for ch in ['_', '*', '[', ']', '`']:
        text = str(text).replace(ch, '\\' + ch)
    return text
def send_long_message(chat_id, text, parse_mode="Markdown", reply_markup=None):
    # Исправляем проблему с буквальным отображением \n
    if isinstance(text, str):
        text = text.replace('\n', '\n')
        
    parts = [text[i:i+3900] for i in range(0, len(text), 3900)]
    for idx, part in enumerate(parts):
        is_last = (idx == len(parts) - 1)
        try:
            if is_last:
                bot.send_message(chat_id, part, parse_mode=parse_mode, reply_markup=reply_markup)
            else:
                bot.send_message(chat_id, part, parse_mode=parse_mode)
        except Exception:
            # Если Markdown сломан — отправляем без форматирования
            if is_last:
                bot.send_message(chat_id, part, reply_markup=reply_markup)
            else:
                bot.send_message(chat_id, part)
# === ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ ===
def get_profile(user_id):
    return profiles_db.get(str(user_id), {})
def calculate_tdee(user_id):
    uid = str(user_id)
    prof = profiles_db.get(uid, {})
    if not prof:
        return 0, 0, 0, 0
    bw_records = [r for r in body_db.get(uid, []) if r.get('bodyweight')]
    w = float(bw_records[-1]['bodyweight']) if bw_records else 80.0
    h = float(prof.get('height_cm', 180))
    birth = int(prof.get('birth_year', 1995))
    age = max(1, datetime.now().year - birth)
    g = prof.get('gender', 'male')
    bmr = 10 * w + 6.25 * h - 5 * age + (5 if g == 'male' else -161)
    days = int(prof.get('training_days_per_week', 3))
    mult = 1.375 if days <= 3 else (1.55 if days <= 5 else 1.725)
    tdee = int(bmr * mult)
    goal = prof.get('goal', 'hypertrophy')
    if goal == 'hypertrophy':
        target = tdee + 300
        p = int(w * 2.0)
    elif goal == 'weight_loss':
        target = tdee - 400
        p = int(w * 1.8)
    else:
        target = tdee
        p = int(w * 1.6)
    f_g = int((target * 0.25) / 9)
    c_g = int((target - p * 4 - f_g * 9) / 4)
    return target, p, f_g, c_g
def calculate_navy_fat(user_id):
    uid = str(user_id)
    prof = profiles_db.get(uid, {})
    records = body_db.get(uid, [])
    if not records or not prof:
        return None
    last = records[-1]
    m = last.get('measurements', {})
    if not m.get('waist_cm') or not m.get('neck_cm'):
        return None
    h = float(prof.get('height_cm', 180))
    waist = float(m['waist_cm'])
    neck = float(m['neck_cm'])
    hips = float(m.get('hips_cm', 0))
    gender = prof.get('gender', 'male')
    try:
        if gender == 'male':
            diff = waist - neck
            if diff <= 0:
                return None
            fat_pct = 495 / (1.0324 - 0.19077 * math.log10(diff) + 0.15456 * math.log10(h)) - 450
        else:
            diff = waist + hips - neck
            if diff <= 0:
                return None
            fat_pct = 495 / (1.29579 - 0.35004 * math.log10(diff) + 0.22100 * math.log10(h)) - 450
        bw = float(last.get('bodyweight', 80))
        fat_kg = bw * (fat_pct / 100)
        lbm = bw - fat_kg
        if gender == 'male':
            if fat_pct < 6: cat = "Незаменимый жир"
            elif fat_pct < 14: cat = "🏆 Атлет"
            elif fat_pct < 18: cat = "✅ Фитнес"
            elif fat_pct < 25: cat = "➡️ Средне"
            else: cat = "⚠️ Ожирение"
        else:
            if fat_pct < 14: cat = "Незаменимый жир"
            elif fat_pct < 21: cat = "🏆 Атлет"
            elif fat_pct < 25: cat = "✅ Фитнес"
            elif fat_pct < 32: cat = "➡️ Средне"
            else: cat = "⚠️ Ожирение"
        return round(fat_pct, 1), round(fat_kg, 1), round(lbm, 1), cat
    except Exception:
        return None
# === ТРЕКИНГ ТЕЛА И ПИТАНИЯ ===
def log_body_entry(user_id, date_str, bodyweight=None, calories=0, protein_g=0,
                   carbs_g=0, fat_g=0, carbs_portions=0, water_l=0.0,
                   sleep_hours=0.0, mood="", measurements=None, note=""):
    uid = str(user_id)
    if uid not in body_db:
        body_db[uid] = []
    entry = {
        "id": int(time.time() * 1000) + random.randint(1, 9999),
        "date": date_str,
        "ts": datetime.now().strftime("%H:%M"),
        "bodyweight": bodyweight,
        "calories": calories,
        "protein_g": protein_g,
        "carbs_g": carbs_g,
        "fat_g": fat_g,
        "carbs_portions": carbs_portions,
        "water_l": water_l,
        "sleep_hours": sleep_hours,
        "mood": mood,
        "measurements": measurements or {},
        "note": note
    }
    body_db[uid].append(entry)
    save_body_db()
    return entry
def get_body_diary_text(user_id, days=14):
    uid = str(user_id)
    records = body_db.get(uid, [])
    if not records:
        return "📭 Журнал питания и тела пуст.\n\nНажми *Записать вес* или *Записать питание*."
    cutoff = datetime.now() - timedelta(days=days)
    recent = [r for r in records if (parse_date(r.get('date')) or datetime.min) >= cutoff]
    if not recent:
        return "📭 Данных за последние 14 дней нет."
    daily = {}
    for r in recent:
        d = r.get('date', '?')
        if d not in daily:
            daily[d] = []
        daily[d].append(r)
    text = "🍎 *ЖУРНАЛ ПИТАНИЯ И ТЕЛА (14 дней)*\n〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"
    for d in sorted(daily.keys(), reverse=True):
        entries = daily[d]
        bw_entries = [e for e in entries if e.get('bodyweight')]
        food_entries = [e for e in entries if e.get('calories') or e.get('carbs_portions')]
        sleep_entries = [e for e in entries if e.get('sleep_hours')]
        water_entries = [e for e in entries if e.get('water_l')]
        mood_entries = [e for e in entries if e.get('mood')]
        text += f"\n📅 *{d}*\n"
        if bw_entries:
            last_bw = bw_entries[-1]
            text += f"  ⚖️ Вес тела: *{last_bw['bodyweight']} кг*\n"
        total_kcal = sum(e.get('calories', 0) for e in food_entries)
        total_prot = sum(e.get('protein_g', 0) for e in food_entries)
        total_carb = sum(e.get('carbs_portions', 0) for e in food_entries)
        if total_kcal or total_carb:
            text += f"  🍽 Питание: *{total_kcal} ккал*"
            if total_prot:
                text += f" | 🥩 Белок: *{total_prot}г*"
            if total_carb:
                text += f" | 🍚 Рис: *{total_carb} порц.*"
            text += "\n"
            for fe in food_entries:
                n = fe.get('note', '')
                ts = fe.get('ts', '')
                if n:
                    text += f"  └ [{ts}] {n}\n"
        if sleep_entries:
            sl = sleep_entries[-1].get('sleep_hours', 0)
            text += f"  😴 Сон: *{sl} ч.*\n"
        if water_entries:
            wl = water_entries[-1].get('water_l', 0)
            text += f"  💧 Вода: *{wl} л.*\n"
        if mood_entries:
            md = mood_entries[-1].get('mood', '')
            text += f"  😊 Самочувствие: *{md}*\n"
        m_entries = [e for e in entries if e.get('measurements')]
        if m_entries:
            ms = m_entries[-1]['measurements']
            parts_m = []
            if ms.get('chest_cm'): parts_m.append(f"Грудь: {ms['chest_cm']}см")
            if ms.get('waist_cm'): parts_m.append(f"Талия: {ms['waist_cm']}см")
            if ms.get('bicep_l_cm'): parts_m.append(f"Бицепс: {ms['bicep_l_cm']}см")
            if parts_m:
                text += "  📏 Замеры: " + " | ".join(parts_m) + "\n"
        text += "┗━━━━━━━━━━━━━━━━━━━━\n"
    return text
def get_body_progress_text(user_id):
    uid = str(user_id)
    records = body_db.get(uid, [])
    records_with_m = [r for r in records if r.get('measurements') and parse_date(r.get('date'))]
    if not records_with_m:
        return "📭 Нет данных о замерах. Нажми *📏 Записать замеры*."
    now = datetime.now()
    def get_closest(target_dt):
        best = None
        best_diff = None
        for r in records_with_m:
            d = parse_date(r['date'])
            diff = abs((d - target_dt).days)
            if best_diff is None or diff < best_diff:
                best_diff = diff
                best = r
        return best
    current = records_with_m[-1]
    rec_30 = get_closest(now - timedelta(days=30))
    rec_90 = get_closest(now - timedelta(days=90))
    keys_labels = [
        ('chest_cm', 'Грудь'),
        ('waist_cm', 'Талия'),
        ('hips_cm', 'Бёдра'),
        ('bicep_l_cm', 'Бицепс (л)'),
        ('bicep_r_cm', 'Бицепс (п)'),
        ('thigh_l_cm', 'Бедро (л)'),
        ('neck_cm', 'Шея'),
    ]
    text = "📊 *ПРОГРЕСС ТЕЛА*\n〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"
    text += f"{'Замер':<16} {'Сейчас':>8} {'30д':>8} {'90д':>8} {'Δ30д':>8}\n"
    text += "─" * 52 + "\n"
    cur_m = current.get('measurements', {})
    m30 = rec_30.get('measurements', {}) if rec_30 else {}
    m90 = rec_90.get('measurements', {}) if rec_90 else {}
    for key, label in keys_labels:
        cur_v = cur_m.get(key)
        if not cur_v:
            continue
        v30 = m30.get(key, '-')
        v90 = m90.get(key, '-')
        delta = ""
        if isinstance(v30, (int, float)):
            d = round(float(cur_v) - float(v30), 1)
            delta = f"{'+' if d >= 0 else ''}{d}"
        text += f"{label:<16} {cur_v:>8} {str(v30):>8} {str(v90):>8} {delta:>8}\n"
    return f"```\n{text}```"
# === НАУЧНЫЙ АЛГОРИТМ ВОССТАНОВЛЕНИЯ v3.0 ===
EXERCISE_MUSCLE_MAP = {
    "Жим лёжа":      ["Грудь", "Трицепс", "Передняя дельта"],
    "Становая тяга": ["Спина (ЦНС)", "Ягодицы", "Задняя цепь"],
    "Присед":        ["Квадрицепс", "Ягодицы", "Поясница"],
}
CNS_MULTIPLIER  = {"Жим лёжа": 1.0, "Становая тяга": 1.4, "Присед": 1.2}
EIMD_MULTIPLIER = {"Жим лёжа": 1.0, "Становая тяга": 1.35, "Присед": 1.15}
RPE_INTENSITY   = {"Легко": 0.60, "Средне": 0.80, "Тяжело": 0.93}
def calculate_recovery_status(exercise, workouts_7d, today, user_id):
    ex_records = [w for w in workouts_7d if w.get('exercise') == exercise]
    if not ex_records:
        return ("🟢", "100%", "Суперкомпенсация завершена",
                "72ч+ без нагрузки. ЦНС и мышцы полностью восстановлены.",
                "100%", "100%")
    last_record = max(ex_records,
                      key=lambda w: parse_date(w.get('date', '01.01.2000')) or datetime.min)
    last_date = parse_date(last_record.get('date'))
    if not last_date:
        return ("🟢", "100%", "Нет данных", "", "100%", "100%")
    hours_passed = (today - last_date).total_seconds() / 3600
    if hours_passed < 8:    cns_base = 0.10
    elif hours_passed < 16: cns_base = 0.30
    elif hours_passed < 24: cns_base = 0.50
    elif hours_passed < 36: cns_base = 0.65
    elif hours_passed < 48: cns_base = 0.78
    elif hours_passed < 60: cns_base = 0.88
    elif hours_passed < 72: cns_base = 0.95
    else:                   cns_base = 1.00
    if hours_passed < 12:   muscle_base = 0.15
    elif hours_passed < 24: muscle_base = 0.45
    elif hours_passed < 36: muscle_base = 0.65
    elif hours_passed < 48: muscle_base = 0.80
    elif hours_passed < 60: muscle_base = 0.90
    elif hours_passed < 72: muscle_base = 0.96
    else:                   muscle_base = 1.00
    rpe_int = RPE_INTENSITY.get(last_record.get('diff', 'Средне'), 0.80)
    cns_mult = CNS_MULTIPLIER.get(exercise, 1.0)
    eimd_mult = EIMD_MULTIPLIER.get(exercise, 1.0)
    intensity_penalty = (rpe_int - 0.60) * 0.50
    cns_extra = (cns_mult - 1.0) * 0.18
    eimd_extra = (eimd_mult - 1.0) * 0.12
    # v3.0 — сон, настроение, белок, вода
    uid = str(user_id)
    b_records = body_db.get(uid, [])
    cutoff36 = today - timedelta(hours=36)
    recent_b = sorted(
        [r for r in b_records if (parse_date(r.get('date')) or datetime.min) >= cutoff36],
        key=lambda r: parse_date(r.get('date')) or datetime.min
    )
    sleep = recent_b[-1].get('sleep_hours', 0) if recent_b else 0
    water = recent_b[-1].get('water_l', 0) if recent_b else 0
    protein = recent_b[-1].get('protein_g', 0) if recent_b else 0
    mood = recent_b[-1].get('mood', '') if recent_b else ''
    cns_bonus = 0.0
    eimd_bonus = 0.0
    overall_bonus = 0.0
    bonuses = []
    if sleep >= 8:
        cns_bonus += 0.08; bonuses.append("✅ Сон 8ч+ (+8%)")
    elif sleep >= 7:
        cns_bonus += 0.04; bonuses.append("✅ Сон 7ч (+4%)")
    elif 0 < sleep < 6:
        cns_bonus -= 0.20; eimd_bonus -= 0.10; bonuses.append("❌ Недосып <6ч (-20%)")
    if mood in ["Отлично", "Хорошо"]:
        overall_bonus += 0.05; bonuses.append("✅ Самочувствие (+5%)")
    elif mood == "Устал":
        overall_bonus -= 0.10; bonuses.append("⚠️ Устал (-10%)")
    elif mood == "Разбит":
        overall_bonus -= 0.25; bonuses.append("❌ Разбит (-25%)")
    if protein >= 150:
        eimd_bonus += 0.08; bonuses.append("✅ Белок 150г+ (+8%)")
    elif 0 < protein < 100:
        eimd_bonus -= 0.10; bonuses.append("⚠️ Мало белка (-10%)")
    if water >= 2.5:
        overall_bonus += 0.03; bonuses.append("✅ Вода 2.5л+ (+3%)")
    elif 0 < water < 1.5:
        overall_bonus -= 0.05; bonuses.append("⚠️ Мало воды (-5%)")
    # Питание (старый бонус)
    cutoff24 = today - timedelta(hours=24)
    recent24 = [r for r in b_records if (parse_date(r.get('date')) or datetime.min) >= cutoff24]
    kcal24 = sum(r.get('calories', 0) for r in recent24)
    carb24 = sum(r.get('carbs_portions', 0) for r in recent24)
    if kcal24 >= 3000 or carb24 >= 4:
        overall_bonus += 0.15; bonuses.append("✅ Профицит калорий (+15%)")
    elif kcal24 >= 2200 or carb24 >= 2:
        overall_bonus += 0.10; bonuses.append("✅ Умеренный профицит (+10%)")
    cns_score = max(0.05, min(1.0,
        cns_base - intensity_penalty - cns_extra + cns_bonus + overall_bonus))
    muscle_score = max(0.05, min(1.0,
        muscle_base - intensity_penalty - eimd_extra + eimd_bonus + overall_bonus))
    overall_score = min(cns_score, muscle_score)
    if mood == "Разбит":
        overall_score = min(overall_score, 0.40)
    cns_pct = int(cns_score * 100)
    muscle_pct = int(muscle_score * 100)
    overall_pct = int(overall_score * 100)
    if overall_score >= 0.90:
        zone, status = "🟢", "Готов к рекордам!"
        detail = f"Суперкомпенсация. ЦНС: {cns_pct}% | Мышцы: {muscle_pct}%.\n  └ Атакуй рабочие веса — окно PR."
    elif overall_score >= 0.70:
        zone, status = "🟡", "Суперкомпенсация идёт"
        detail = f"MPS активен. ЦНС: {cns_pct}% | Мышцы: {muscle_pct}%.\n  └ Умеренная нагрузка допустима."
    elif overall_score >= 0.45:
        zone, status = "🟡", "Неполное восстановление"
        detail = f"Риск перетрена. ЦНС: {cns_pct}% | Мышцы: {muscle_pct}%.\n  └ Лёгкое кардио или отдых."
    else:
        zone, status = "🔴", "Перегрузка (EIMD/ЦНС)"
        detail = f"Острая фаза. ЦНС: {cns_pct}% | Мышцы: {muscle_pct}%.\n  └ Отдых, сон 9ч, белок 2г/кг."
    if bonuses:
        detail += "\n  └ " + "\n  └ ".join(bonuses)
    return zone, f"{overall_pct}%", status, detail, f"{cns_pct}%", f"{muscle_pct}%"
def get_today_recommendation(user_id):
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    history = gym_db.get(str(user_id), [])
    w7d = [w for w in history if (parse_date(w.get('date')) or datetime.min) >= week_ago]
    exercises = list(set(w.get('exercise') for w in w7d if w.get('exercise')))
    if not exercises:
        exercises = ["Жим лёжа", "Становая тяга", "Присед"]
    red = grn = yel = 0
    status_line = []
    for ex in exercises[:5]:
        z, _, _, _, _, _ = calculate_recovery_status(ex, w7d, today, user_id)
        short = ex.split()[0]
        status_line.append(f"{short} {z}")
        if z == "🔴": red += 1
        elif z == "🟡": yel += 1
        else: grn += 1
    if red >= len(exercises):
        rec = "🛌 ПОЛНЫЙ ОТДЫХ. Сон, еда, прогулка."
    elif red >= 1:
        rec = "⛔ ВОССТАНОВИТЕЛЬНАЯ. Кардио 20–30 мин, изоляция."
    elif grn >= 2:
        rec = "✅ ТЯЖЁЛАЯ тренировка. Атакуй рабочие веса!"
    else:
        rec = "🔄 УМЕРЕННАЯ. Технические веса 70–80% 1ПМ."
    return " | ".join(status_line), rec
# === ТРЕНД ТОННАЖА, ПРОГРЕСС, СЕРИЯ, ПЛАТО, ПРОГНОЗ ===
def calculate_volume_trend(user_history):
    today = datetime.now()
    week1_start = today - timedelta(days=7)
    week2_start = today - timedelta(days=14)
    tonnage_this = tonnage_prev = sets_this = sets_prev = 0
    for w in user_history:
        d = parse_date(w.get('date'))
        if not d:
            continue
        t = float(w.get('weight', 0)) * float(w.get('reps', 0))
        if d >= week1_start:
            tonnage_this += t
            sets_this += 1
        elif d >= week2_start:
            tonnage_prev += t
            sets_prev += 1
    trend_pct = None if tonnage_prev == 0 else ((tonnage_this - tonnage_prev) / tonnage_prev) * 100
    return tonnage_this, tonnage_prev, trend_pct, sets_this, sets_prev
def get_weight_progress(user_history, exercise):
    today = datetime.now()
    week1_start = today - timedelta(days=7)
    week2_start = today - timedelta(days=14)
    weights_this, weights_prev = [], []
    for w in user_history:
        if w.get('exercise') != exercise:
            continue
        d = parse_date(w.get('date'))
        if not d:
            continue
        wt = float(w.get('weight', 0))
        if d >= week1_start:
            weights_this.append(wt)
        elif d >= week2_start:
            weights_prev.append(wt)
    if not weights_this or not weights_prev:
        return None
    return sum(weights_this)/len(weights_this), sum(weights_prev)/len(weights_prev)
def calculate_training_streak(user_history):
    if not user_history:
        return 0
    dates = set()
    for w in user_history:
        d = parse_date(w.get('date'))
        if d:
            iso = d.isocalendar()
            dates.add((iso[0], iso[1]))
    if not dates:
        return 0
    sorted_weeks = sorted(dates, reverse=True)
    today = datetime.now()
    expected = (today.isocalendar()[0], today.isocalendar()[1])
    streak = 0
    for week in sorted_weeks:
        if week == expected:
            streak += 1
            dt = datetime.fromisocalendar(expected[0], expected[1], 1) - timedelta(weeks=1)
            expected = (dt.isocalendar()[0], dt.isocalendar()[1])
        else:
            break
    return streak
def detect_plateau(user_history, exercise, days=21):
    cutoff = datetime.now() - timedelta(days=days)
    ex_records = [w for w in user_history
                  if w.get('exercise') == exercise
                  and (parse_date(w.get('date')) or datetime.min) >= cutoff
                  and float(w.get('weight', 0)) > 0 and float(w.get('reps', 0)) > 0]
    if len(ex_records) < 2:
        return False, 0.0
    e1rms = [epley_1rm(float(w['weight']), float(w['reps'])) for w in ex_records]
    first_max = max(e1rms[:len(e1rms)//2]) if len(e1rms) > 1 else e1rms[0]
    last_max = max(e1rms[len(e1rms)//2:]) if len(e1rms) > 1 else e1rms[-1]
    return last_max <= first_max * 1.01, last_max
def predict_1rm(user_history, exercise, weeks_ahead=4):
    records = [(parse_date(w.get('date')), epley_1rm(float(w.get('weight', 0)), float(w.get('reps', 0))))
               for w in user_history
               if w.get('exercise') == exercise
               and float(w.get('weight', 0)) > 0 and float(w.get('reps', 0)) > 0
               and parse_date(w.get('date'))]
    if len(records) < 3:
        return None, None, None
    records.sort(key=lambda x: x[0])
    dates_num = mdates.date2num([r[0] for r in records])
    vals = [r[1] for r in records]
    try:
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            z = np.polyfit(dates_num, vals, 1)
        slope_per_day = z[0]
        current_1rm = vals[-1]
        pred_4 = round(current_1rm + slope_per_day * 7 * weeks_ahead, 1)
        pred_8 = round(current_1rm + slope_per_day * 7 * weeks_ahead * 2, 1)
        weekly_gain = round(slope_per_day * 7, 2)
        return weekly_gain, pred_4, pred_8
    except Exception:
        return None, None, None
def get_top3_progress(user_history, days=30):
    cutoff = datetime.now() - timedelta(days=days)
    recent = [w for w in user_history if (parse_date(w.get('date')) or datetime.min) >= cutoff]
    older = [w for w in user_history if (parse_date(w.get('date')) or datetime.min) < cutoff]
    exercises = set(w.get('exercise') for w in recent if w.get('exercise'))
    progress = {}
    for ex in exercises:
        rec_ex = [w for w in recent if w.get('exercise') == ex]
        old_ex = [w for w in older if w.get('exercise') == ex]
        if not rec_ex:
            continue
        cur_vals = [epley_1rm(float(w['weight']), float(w['reps'])) for w in rec_ex
                    if float(w.get('weight', 0)) > 0 and float(w.get('reps', 0)) > 0]
        if not cur_vals:
            continue
        cur_1rm = max(cur_vals)
        if old_ex:
            old_vals = [epley_1rm(float(w['weight']), float(w['reps'])) for w in old_ex
                        if float(w.get('weight', 0)) > 0 and float(w.get('reps', 0)) > 0]
            old_1rm = max(old_vals) if old_vals else 0
            if old_1rm > 0:
                pct = (cur_1rm - old_1rm) / old_1rm * 100
                progress[ex] = (pct, cur_1rm)
    top3 = sorted(progress.items(), key=lambda x: x[1][0], reverse=True)[:3]
    return top3
# === ГЛАВНАЯ ФУНКЦИЯ АНАЛИТИКИ ===
def calculate_analytics(user_history, user_id):
    if not user_history:
        return ("📭 *Дневник пуст*\n\nНачни записывать тренировки.\n\n"
                f"_{random.choice(MOTIVATION_QUOTES)}_")
    today = datetime.now()
    total_sets    = len(user_history)
    unique_days   = len(set(w.get('date') for w in user_history))
    total_tonnage = sum(float(w.get('weight',0)) * float(w.get('reps',0)) for w in user_history)
    all_dates = [parse_date(w.get('date')) for w in user_history]
    all_dates = [d for d in all_dates if d]
    first_date = min(all_dates) if all_dates else None
    last_date_obj = max(all_dates) if all_dates else None
    span = (last_date_obj - first_date).days + 1 if first_date and last_date_obj else 1
    avg_per_week = round(unique_days / (span / 7), 1) if span > 0 else 0
    streak = calculate_training_streak(user_history)
    records = {}
    for w in user_history:
        ex = w.get('exercise', 'Неизвестно')
        weight = float(w.get('weight', 0))
        reps = float(w.get('reps', 0))
        d_str = w.get('date')
        if weight <= 0 or reps <= 0:
            continue
        e1 = epley_1rm(weight, reps)
        b1 = brzycki_1rm(weight, reps)
        if ex not in records or e1 > records[ex]['1rm']:
            records[ex] = {'max_weight': weight, 'reps': format_reps_clean(w), 'date': d_str, '1rm': e1, '1rm_b': b1}
    tonnage_this, tonnage_prev, trend_pct, sets_this, sets_prev = calculate_volume_trend(user_history)
    week_ago = today - timedelta(days=7)
    workouts_7d = [w for w in user_history if (parse_date(w.get('date')) or datetime.min) >= week_ago]
    uid = str(user_id)
    prof = profiles_db.get(uid, {})
    name = prof.get('name', 'Атлет')
    sep = "〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"
    report = f"🏆 *АНАЛИТИКА v13.0 — {name.upper()}*\n{sep}"
    bw_list = [r for r in body_db.get(uid, []) if r.get('bodyweight')]
    # ОБЩАЯ СТАТИСТИКА
    report += "📊 *ОБЩАЯ СТАТИСТИКА*\n\n"
    report += f"  🗓 Дней в зале: *{unique_days}* (ср. {avg_per_week} раз/нед)\n"
    report += f"  🔄 Всего подходов: *{total_sets}*\n"
    report += f"  🏗 Суммарный тоннаж: *{total_tonnage / 1000:.2f} тонн*\n"
    if streak > 0:
        report += f"  🔥 Серия тренировочных недель: *{streak} нед.*\n"
    report += "\n🎯 *Тенденция объёма (7д vs 7д):*\n"
    if trend_pct is None:
        report += "  ℹ️ Недостаточно данных\n"
    elif trend_pct > 0:
        report += f"  📈 Объём +*{trend_pct:.1f}%* | Неделя: {tonnage_this:.0f} кг | Прошлая: {tonnage_prev:.0f} кг\n"
    elif trend_pct < 0:
        report += f"  📉 Объём *{trend_pct:.1f}%* | Неделя: {tonnage_this:.0f} кг | Прошлая: {tonnage_prev:.0f} кг\n"
    else:
        report += f"  ➡️ Объём стабилен: {tonnage_this:.0f} кг\n"
    report += "\n🔥 *Абсолютные рекорды (1ПМ):*\n"
    if not records:
        report += "  Записей пока нет\n"
    else:
        for ex, rec in records.items():
            avg_1rm = round((rec['1rm'] + rec['1rm_b']) / 2, 1)
            report += f"  *{ex}*\n"
            report += f"  └ Лучший: {rec['max_weight']} кг × {rec['reps']} пов.\n"
            report += f"  └ 1ПМ Эпли: *{rec['1rm']} кг* | Brzycki: *{rec['1rm_b']} кг* | Ср: *{avg_1rm}*\n"
            report += f"  └ 📅 {rec['date']}\n"
            # Плато
            is_plateau, last_1rm = detect_plateau(user_history, ex)
            if is_plateau:
                report += f"  └ ⚠️ *ПЛАТО: {ex} — 21 день без прогресса!*\n"
                report += "  └ Рекомендации: смени схему (5×5→3×12), деload, +1 день/нед.\n"
            # Прогноз
            gain, pred4, pred8 = predict_1rm(user_history, ex, 4)
            if gain is not None and pred4:
                if gain > 0:
                    report += f"  └ 📈 Прогноз: через 4 нед — *{pred4} кг*, через 8 нед — *{pred8} кг* (+{gain} кг/нед)\n"
            report += "\n"
    # Топ-3 прогресса
    top3 = get_top3_progress(user_history)
    if top3:
        report += "\n🏅 *Топ-3 прогресса за месяц:*\n"
        medals = ["🥇", "🥈", "🥉"]
        for i, (ex, (pct, cur)) in enumerate(top3):
            report += f"  {medals[i]} *{ex}:* +{pct:.1f}% | 1ПМ: {cur} кг\n"
    report += f"\n{sep}"
    report += "🔋 *ВОССТАНОВЛЕНИЕ ЦНС v3.0*\n"
    report += "_Алгоритм: Schoenfeld, Zatsiorsky, Enoka, Walker, Phillips_\n\n"
    exercises_to_check = list(set(w.get('exercise') for w in workouts_7d if w.get('exercise')))
    if not exercises_to_check:
        exercises_to_check = list(records.keys()) or ["Жим лёжа", "Становая тяга", "Присед"]
    for ex in exercises_to_check:
        if not any(w.get('exercise') == ex for w in user_history):
            continue
        muscles = EXERCISE_MUSCLE_MAP.get(ex, [ex])
        zone, pct, status, detail, cns_p, mus_p = calculate_recovery_status(ex, workouts_7d, today, user_id)
        bar = make_progress_bar(pct)
        report += f"{zone} *{ex}*\n"
        report += f"  └ Мышцы: _{' / '.join(muscles)}_\n"
        report += f"  └ Готовность: {bar}\n"
        report += f"  └ ЦНС: {make_progress_bar(cns_p, 6)} | Мышцы: {make_progress_bar(mus_p, 6)}\n"
        report += f"  └ *{status}*\n"
        report += f"  └ {detail}\n\n"
    # Питание
    today_str = today.strftime("%d.%m.%Y")
    today_food = [r for r in body_db.get(uid, []) if r.get('date') == today_str]
    today_kcal = sum(r.get('calories', 0) for r in today_food)
    today_prot = sum(r.get('protein_g', 0) for r in today_food)
    if today_kcal > 0 or today_prot > 0:
        report += f"🍽 *Сегодня:* {today_kcal} ккал | 🥩 Белок: {today_prot} г\n"
    # TDEE
    if prof:
        tdee, p_g, f_g, c_g = calculate_tdee(user_id)
        if tdee > 0:
            report += f"🔢 *TDEE:* {tdee} ккал | Цель: Б:{p_g}г / Ж:{f_g}г / У:{c_g}г\n"
    # Navy Fat
    navy = calculate_navy_fat(user_id)
    if navy:
        fat_pct, fat_kg, lbm, cat = navy
        report += f"📏 *Состав тела (Navy):* {fat_pct}% жира | ЛМТ: {lbm} кг | {cat}\n"
    science_tips = [
        "🧬 *Совет:* Пик MPS — 24–36ч после тренировки. Белок критичен (Phillips, 1997).",
        "🧬 *Совет:* Сон — главный анаболик. 8–9ч = +60% ГР (Van Cauter, 2000).",
        "🧬 *Совет:* 10–20 рабочих подходов на группу в неделю (Schoenfeld, 2017).",
        "🧬 *Совет:* Кофеин 3–6 мг/кг за 30–60 мин → прирост силы (Grgic, 2018).",
        "🧬 *Совет:* RPE 8–9 — золотая зона гипертрофии (Zourdos, 2016).",
        "🧬 *Совет:* 1.6–2.2 г/кг белка — оптимум гипертрофии (Helms, 2014).",
    ]
    report += f"\n{sep}"
    report += f"_{random.choice(science_tips)}_\n\n"
    report += f"_{random.choice(MOTIVATION_QUOTES)}_"
    return report
# === ГРАФИКИ MATPLOTLIB ===
def _setup_chart_style():
    plt.rcParams.update({
        'figure.facecolor': '#1a1a2e', 'axes.facecolor': '#16213e',
        'axes.edgecolor': '#0f3460', 'axes.labelcolor': '#e0e0e0',
        'text.color': '#e0e0e0', 'xtick.color': '#aaaaaa',
        'ytick.color': '#aaaaaa', 'grid.color': '#0f3460',
        'grid.linestyle': '--', 'grid.alpha': 0.5, 'font.family': 'DejaVu Sans',
    })
def generate_dashboard_2x2(user_id):
    _setup_chart_style()
    user_history = gym_db.get(str(user_id), [])
    weight_history = body_db.get(str(user_id), [])
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.patch.set_facecolor('#1a1a2e')
    # 1. 1RM Growth
    ax1 = axes[0, 0]
    ex_colors = {"Жим лёжа": "#e94560", "Становая тяга": "#00b4d8", "Присед": "#f4d03f"}
    plotted = False
    for ex, color in ex_colors.items():
        ex_data = {}
        for w in user_history:
            if w.get('exercise') != ex: continue
            d = parse_date(w.get('date'))
            if not d: continue
            e1 = epley_1rm(float(w.get('weight', 0)), float(w.get('reps', 0)))
            if d not in ex_data or e1 > ex_data[d]:
                ex_data[d] = e1
        pts = sorted(ex_data.items())
        if len(pts) >= 2:
            ax1.plot([p[0] for p in pts], [p[1] for p in pts], marker='o', color=color, label=ex, lw=2)
            plotted = True
    ax1.set_title("📈 Рост 1ПМ", color='#e0e0e0', fontsize=11)
    if plotted:
        ax1.legend(facecolor='#1a1a2e', labelcolor='#e0e0e0', fontsize=8)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
        fig.autofmt_xdate()
    ax1.grid(True)
    # 2. Tonnage Bar Chart
    ax2 = axes[0, 1]
    weekly = defaultdict(float)
    for w in user_history:
        d = parse_date(w.get('date'))
        if d:
            weekly[d.strftime("%Y-W%W")] += float(w.get('weight', 0)) * float(w.get('reps', 0))
    sorted_weeks = sorted(weekly.keys())[-10:]
    if sorted_weeks:
        vals = [weekly[w]/1000 for w in sorted_weeks]
        labels = [w.split('-W')[1] + 'н' for w in sorted_weeks]
        bar_colors = ['#e94560' if v == max(vals) else '#00b4d8' for v in vals]
        bars = ax2.bar(range(len(labels)), vals, color=bar_colors, width=0.6)
        ax2.bar_label(bars, fmt='%.1f', color='#e0e0e0', fontsize=7, padding=2)
        ax2.set_xticks(range(len(labels)))
        ax2.set_xticklabels(labels, fontsize=7)
    ax2.set_title("🏗 Тоннаж по неделям (т)", color='#e0e0e0', fontsize=11)
    ax2.grid(True, axis='y')
    # 3. Bodyweight + Trendline
    ax3 = axes[1, 0]
    bw_pts = sorted([(parse_date(r['date']), float(r['bodyweight']))
                     for r in weight_history if r.get('bodyweight') and parse_date(r.get('date'))])
    if len(bw_pts) >= 2:
        dates_bw = [p[0] for p in bw_pts]
        vals_bw = [p[1] for p in bw_pts]
        ax3.plot(dates_bw, vals_bw, marker='o', color='#f4d03f', lw=2, markersize=4)
        try:
            z = np.polyfit(mdates.date2num(dates_bw), vals_bw, 1)
            p_fn = np.poly1d(z)
            ax3.plot(dates_bw, p_fn(mdates.date2num(dates_bw)), 'r--', alpha=0.7, label='Тренд')
            ax3.legend(facecolor='#1a1a2e', labelcolor='#e0e0e0', fontsize=8)
        except Exception:
            pass
        ax3.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
        fig.autofmt_xdate()
    ax3.set_title("⚖️ Вес тела", color='#e0e0e0', fontsize=11)
    ax3.grid(True)
    # 4. Radar Chart
    ax4 = axes[1, 1]
    ax4.remove()
    ax4 = fig.add_subplot(2, 2, 4, polar=True)
    ax4.set_facecolor('#16213e')
    last_m = {}
    for r in weight_history:
        if r.get('measurements'):
            last_m = r['measurements']
    radar_labels = ['Грудь', 'Талия', 'Бёдра', 'Бицепс', 'Бедро']
    radar_keys = ['chest_cm', 'waist_cm', 'hips_cm', 'bicep_l_cm', 'thigh_l_cm']
    vals_r = [float(last_m.get(k, 50)) for k in radar_keys]
    if any(v > 0 for v in vals_r):
        angles = np.linspace(0, 2 * np.pi, len(radar_labels), endpoint=False).tolist()
        vals_r_c = vals_r + vals_r[:1]
        angles_c = angles + angles[:1]
        ax4.plot(angles_c, vals_r_c, 'o-', color='#e94560', lw=2)
        ax4.fill(angles_c, vals_r_c, color='#e94560', alpha=0.25)
        ax4.set_xticks(angles)
        ax4.set_xticklabels(radar_labels, color='#e0e0e0', size=9)
        ax4.set_facecolor('#16213e')
    ax4.set_title("📏 Антропометрия", color='#e0e0e0', fontsize=11, pad=20)
    plt.tight_layout(pad=2.0)
    filename = f"dashboard_{user_id}_{int(time.time())}.png"
    plt.savefig(filename, facecolor=fig.get_facecolor(), bbox_inches='tight', dpi=120)
    plt.close(fig)
    return filename
def generate_1rm_chart(user_history, user_id):
    _setup_chart_style()
    exercises = ["Жим лёжа", "Становая тяга", "Присед"]
    colors = ["#e94560", "#00b4d8", "#f4d03f"]
    ex_data = {ex: {} for ex in exercises}
    for w in user_history:
        ex = w.get('exercise')
        if ex not in exercises: continue
        d = parse_date(w.get('date'))
        weight = float(w.get('weight', 0))
        reps = float(w.get('reps', 0))
        if not d or weight <= 0 or reps <= 0: continue
        e1 = epley_1rm(weight, reps)
        if d not in ex_data[ex] or e1 > ex_data[ex][d]:
            ex_data[ex][d] = e1
    fig, ax = plt.subplots(figsize=(10, 5))
    plotted = False
    for ex, color in zip(exercises, colors):
        pts = sorted(ex_data[ex].items())
        if len(pts) < 2: continue
        dates = [p[0] for p in pts]
        vals = [p[1] for p in pts]
        ax.plot(dates, vals, marker='o', color=color, linewidth=2, markersize=5, label=ex)
        ax.annotate(f"{vals[-1]:.0f}кг", xy=(dates[-1], vals[-1]),
                    textcoords="offset points", xytext=(6, 4), color=color, fontsize=8)
        plotted = True
    if not plotted:
        plt.close(fig)
        return None
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate(rotation=30)
    ax.set_title("📈 Рост расчётного 1ПМ (Эпли)", color='#e0e0e0', fontsize=13, pad=12)
    ax.set_ylabel("1ПМ (кг)", fontsize=10)
    ax.legend(facecolor='#1a1a2e', edgecolor='#0f3460', labelcolor='#e0e0e0')
    ax.grid(True)
    plt.tight_layout()
    filename = f"chart_1rm_{user_id}.png"
    fig.savefig(filename, dpi=120, bbox_inches='tight')
    plt.close(fig)
    return filename
def generate_tonnage_chart(user_history, user_id):
    _setup_chart_style()
    weekly = defaultdict(float)
    for w in user_history:
        d = parse_date(w.get('date'))
        if not d: continue
        iso_year, iso_week, _ = d.isocalendar()
        week_label = f"{iso_year}-W{iso_week:02d}"
        weekly[week_label] += float(w.get('weight', 0)) * float(w.get('reps', 0))
    if len(weekly) < 2:
        return None
    sorted_weeks = sorted(weekly.keys())[-12:]
    labels = [w.split('-W')[1] + 'нед' for w in sorted_weeks]
    values = [weekly[w] / 1000 for w in sorted_weeks]
    fig, ax = plt.subplots(figsize=(10, 5))
    bar_colors = ['#e94560' if v == max(values) else '#00b4d8' for v in values]
    bars = ax.bar(range(len(labels)), values, color=bar_colors, width=0.6, zorder=3)
    ax.bar_label(bars, fmt='%.1f т', color='#e0e0e0', fontsize=8, padding=3)
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha='right', fontsize=8)
    ax.set_title("🏗 Тоннаж по неделям (последние 12)", color='#e0e0e0', fontsize=13, pad=12)
    ax.set_ylabel("Тонн (т)", fontsize=10)
    ax.grid(True, axis='y', zorder=0)
    plt.tight_layout()
    filename = f"chart_tonnage_{user_id}.png"
    fig.savefig(filename, dpi=120, bbox_inches='tight')
    plt.close(fig)
    return filename
def generate_bodyweight_chart(user_id):
    _setup_chart_style()
    uid = str(user_id)
    records = body_db.get(uid, [])
    bw_pts = []
    for r in records:
        bw = r.get('bodyweight')
        d = parse_date(r.get('date'))
        if bw and d:
            bw_pts.append((d, float(bw)))
    if len(bw_pts) < 2:
        return None
    bw_pts.sort()
    dates = [p[0] for p in bw_pts]
    values = [p[1] for p in bw_pts]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(dates, values, color='#f4d03f', linewidth=2, marker='o', markersize=5)
    ax.fill_between(dates, values, min(values) - 1, alpha=0.15, color='#f4d03f')
    try:
        z = np.polyfit(mdates.date2num(dates), values, 1)
        p_fn = np.poly1d(z)
        ax.plot(dates, p_fn(mdates.date2num(dates)), 'r--', alpha=0.7, label='Тренд')
        ax.legend(facecolor='#1a1a2e', labelcolor='#e0e0e0')
    except Exception:
        pass
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d.%m'))
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    fig.autofmt_xdate(rotation=30)
    ax.set_title("⚖️ Вес тела + тренд", color='#e0e0e0', fontsize=13, pad=12)
    ax.set_ylabel("кг", fontsize=10)
    ax.grid(True)
    plt.tight_layout()
    filename = f"chart_bw_{user_id}.png"
    fig.savefig(filename, dpi=120, bbox_inches='tight')
    plt.close(fig)
    return filename
def send_and_delete_chart(chat_id, filename, caption):
    try:
        with open(filename, 'rb') as f:
            bot.send_photo(chat_id, f, caption=caption)
    finally:
        try:
            os.remove(filename)
        except Exception:
            pass
# === КАЛЬКУЛЯТОРЫ (разминка, макросы, TDEE) ===
def get_warmup_plan(target_weight):
    bar = 20
    steps = [
        (bar, 15, "Пустой гриф — активация нервной системы"),
        (round(target_weight * 0.50 / 2.5) * 2.5, 8, "50% — пробуждение мышц"),
        (round(target_weight * 0.70 / 2.5) * 2.5, 5, "70% — паттерн движения"),
        (round(target_weight * 0.85 / 2.5) * 2.5, 3, "85% — нервная активация"),
        (round(target_weight * 0.93 / 2.5) * 2.5, 1, "93% — потенциация"),
        (target_weight, None, "🎯 РАБОЧИЙ ВЕС — атакуй!"),
    ]
    text = f"🧮 *Разминочная пирамида для {target_weight} кг*\n\n"
    for wt, reps, desc in steps:
        if reps:
            text += f"▸ *{wt} кг* × {reps} пов. — _{desc}_\n"
        else:
            text += f"▸ *{wt} кг* — _{desc}_\n"
    text += ("\n_Источник: Zatsiorsky VM & Kraemer WJ (2006)_\n"
             "_Отдых между разминочными: 60–90 сек._\n"
             "_После последнего разминочного: 3–5 мин до рабочего._")
    return text
def get_macros_text(user_id):
    tdee, p_g, f_g, c_g = calculate_tdee(user_id)
    if tdee == 0:
        return "Нет профиля. Запусти /setup"
    uid = str(user_id)
    prof = profiles_db.get(uid, {})
    bw_records = [r for r in body_db.get(uid, []) if r.get('bodyweight')]
    bw = float(bw_records[-1]['bodyweight']) if bw_records else 80.0
    goal = prof.get('goal', 'hypertrophy')
    goal_str = {"hypertrophy": "Гипертрофия (+300 ккал)", "weight_loss": "Похудение (-400 ккал)", "strength": "Сила (норма)"}.get(goal, goal)
    text = (
        f"🥗 *ТВОИ МАКРОСЫ*\n〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"
        f"⚖️ Вес тела: *{bw} кг*\n"
        f"🎯 Цель: *{goal_str}*\n"
        f"🔢 TDEE: *{tdee} ккал/день*\n"
        f"🎯 Целевые ккал: *{tdee + (300 if goal=='hypertrophy' else -400 if goal=='weight_loss' else 0)}*\n\n"
        f"*Макросы:*\n"
        f"🥩 Белок:   *{p_g} г* ({p_g*4} ккал)\n"
        f"🧈 Жиры:    *{f_g} г* ({f_g*9} ккал)\n"
        f"🍞 Углеводы: *{c_g} г* ({c_g*4} ккал)\n\n"
        f"_Источник: Helms ER, Aragon AA (2014) J Int Soc Sports Nutr_"
    )
    return text
def start_rest_timer(chat_id, seconds):
    mins = seconds // 60
    secs = seconds % 60
    time_str = f"{mins} мин {secs} сек" if secs else f"{mins} мин"
    def _callback():
        try:
            bot.send_message(chat_id,
                f"🔔 *Пора рвать железо!* Отдых {time_str} завершён. Следующий подход! 💪",
                parse_mode="Markdown")
        except Exception as e:
            print(f"[TIMER ERROR] {e}")
    t = threading.Timer(seconds, _callback)
    t.daemon = True
    t.start()
# === КЛАВИАТУРЫ И ИНТЕРФЕЙС ===
def get_pubmed_menu_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    for key, data in PUBMED_KNOWLEDGE.items():
        # Передаем текст кнопки напрямую как есть
        markup.add(InlineKeyboardButton(text=data["title"], callback_data=f"pubmed_{key}"))
    markup.add(InlineKeyboardButton(text="🛑 ТОП-10 Фитнес Мифов", callback_data="pubmed_myths"))
    markup.add(InlineKeyboardButton(text="🥇 Главные Исследования", callback_data="pubmed_landmarks"))
    markup.add(InlineKeyboardButton(text="📏 Научные Нормативы", callback_data="pubmed_standards"))
    markup.add(InlineKeyboardButton(text="🏠 В главное меню", callback_data="cancel"))
    return markup

# === КЛАВИАТУРЫ ПРОГРАММ ТРЕНИРОВОК ===
def get_program_main_keyboard(has_prog=False):
    markup = InlineKeyboardMarkup(row_width=1)
    if has_prog:
        markup.add(
            InlineKeyboardButton(text="▶️ Тренировка по плану", callback_data="prog_start_menu"),
            InlineKeyboardButton(text="📈 Переключить неделю (1-6 нед)", callback_data="prog_select_week"),
            InlineKeyboardButton(text="📅 Недельный сплит", callback_data="prog_view_split"),
            InlineKeyboardButton(text="📊 Волновая матрица (6 нед)", callback_data="prog_view_matrix"),
            InlineKeyboardButton(text="🔄 Сменить программу", callback_data="prog_wizard_start"),
            InlineKeyboardButton(text="🏠 В главное меню", callback_data="cancel")
        )
    else:
        markup.add(
            InlineKeyboardButton(text="✨ Составить научную программу (PubMed AI)", callback_data="prog_wizard_start"),
            InlineKeyboardButton(text="🏠 В главное меню", callback_data="cancel")
        )
    return markup

def get_program_weeks_keyboard(prog):
    markup = InlineKeyboardMarkup(row_width=3)
    cur = prog.get('current_week', 1)
    buttons = []
    for w in range(1, 7):
        badge = "🔥 " if w == 5 else ("🍃 " if w == 6 else "")
        check = "✅ " if w == cur else ""
        buttons.append(InlineKeyboardButton(text=f"{check}{badge}Нед {w}", callback_data=f"prog_setweek_{w}"))
    markup.add(*buttons)
    markup.add(InlineKeyboardButton(text="⬅️ Назад к программе", callback_data="prog_main_view"))
    return markup

def get_program_wizard_goal_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton(text="💪 Гипертрофия", callback_data="prog_goal_hypertrophy"),
        InlineKeyboardButton(text="🏋️ Сила / SBD", callback_data="prog_goal_strength")
    )
    markup.add(
        InlineKeyboardButton(text="⚖️ Рекомпозиция", callback_data="prog_goal_recomp"),
        InlineKeyboardButton(text="⚡ Выносливость", callback_data="prog_goal_endurance")
    )
    markup.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return markup

def get_program_wizard_days_keyboard():
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(
        InlineKeyboardButton(text="2 дня", callback_data="prog_days_2"),
        InlineKeyboardButton(text="3 дня", callback_data="prog_days_3"),
        InlineKeyboardButton(text="4 дня (Оптимум)", callback_data="prog_days_4")
    )
    markup.add(
        InlineKeyboardButton(text="5 дней", callback_data="prog_days_5"),
        InlineKeyboardButton(text="6 дней", callback_data="prog_days_6"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    return markup

def get_program_wizard_level_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(text="🌱 Новичок (< 1 года)", callback_data="prog_level_beginner"),
        InlineKeyboardButton(text="🚀 Средний (1-3 года)", callback_data="prog_level_intermediate"),
        InlineKeyboardButton(text="👑 Опытный (> 3 лет)", callback_data="prog_level_advanced"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    return markup

def get_program_wizard_split_keyboard(days_per_week: int):
    markup = InlineKeyboardMarkup(row_width=1)
    splits = get_available_splits(days_per_week) if 'get_available_splits' in globals() else []
    for s in splits:
        markup.add(InlineKeyboardButton(text=f"{s['name']}", callback_data=f"prog_split_{s['id']}"))
    markup.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return markup

def get_program_days_keyboard(prog):
    markup = InlineKeyboardMarkup(row_width=1)
    days = prog.get('days', [])
    for idx, d in enumerate(days):
        title = d.get('title', f'День {idx+1}')
        markup.add(InlineKeyboardButton(text=f"🏋️ {title}", callback_data=f"prog_runday_{idx}"))
    markup.add(InlineKeyboardButton(text="⬅️ Назад к программе", callback_data="prog_main_view"))
    return markup

def get_main_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(KeyboardButton("🧬 Моя программа"), KeyboardButton("🏋️ Новое упражнение"))
    markup.add(KeyboardButton("📈 Мой дневник"), KeyboardButton("🏆 Аналитика и Восстановление"))
    markup.add(KeyboardButton("🍎 Питание и Тело"), KeyboardButton("🧮 Разминка"))
    markup.add(KeyboardButton("📚 База PubMed"), KeyboardButton("⚙️ Редактировать"))
    markup.add(KeyboardButton("📥 Скачать в Excel"), KeyboardButton("ℹ️ Загрузить свои данные (Импорт)"))
    markup.add(KeyboardButton("📖 Инструкция"))
    return markup
def get_date_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton(text="📅 Сегодня", callback_data="date_today"),
               InlineKeyboardButton(text="🔙 Вчера", callback_data="date_yesterday"))
    markup.add(InlineKeyboardButton(text="✍️ Ввести дату вручную", callback_data="date_custom"))
    markup.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return markup
def safe_cb(prefix, name, max_bytes=64):
    """Обрезает callback_data до max_bytes (байт, не символов).
    Кириллица = 2 байта, поэтому cx[:40] может быть 80 байт — превышение лимита 64."""
    available = max_bytes - len(prefix.encode('utf-8'))
    encoded = name.encode('utf-8')
    if len(encoded) > available:
        encoded = encoded[:available]
        name = encoded.decode('utf-8', errors='ignore')
    return prefix + name

def get_exercise_keyboard(user_id):
    markup = InlineKeyboardMarkup(row_width=1)
    default_ex = ["Жим лёжа", "Становая тяга", "Присед"]
    # Нормализация для сравнения: ё→е, lower
    def _norm(s):
        return s.strip().lower().replace('ё', 'е')
    default_norms = [_norm(d) for d in default_ex]
    history = gym_db.get(str(user_id), [])
    custom_ex = []
    for w in reversed(history):
        ex = w.get('exercise')
        if ex:
            ex_clean = str(ex).strip()
            n = _norm(ex_clean)
            if n in default_norms:
                continue
            if any(_norm(c) == n for c in custom_ex):
                continue
            custom_ex.append(ex_clean)
        if len(custom_ex) >= 5:
            break
    markup.add(InlineKeyboardButton(text="🟦 Жим лёжа", callback_data="ex_Жим лёжа"),
               InlineKeyboardButton(text="🟥 Становая тяга", callback_data="ex_Становая тяга"),
               InlineKeyboardButton(text="🟨 Присед", callback_data="ex_Присед"))
    for cx in custom_ex:
        cb = safe_cb("ex_", cx)
        markup.add(InlineKeyboardButton(text=f"🔸 {cx}", callback_data=cb))
    markup.add(InlineKeyboardButton(text="➕ Ввести своё название", callback_data="ex_custom_new"))
    markup.add(InlineKeyboardButton(text="❌ Отмена", callback_data="cancel"))
    return markup

def get_difficulty_keyboard():
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(InlineKeyboardButton(text="🟢 Легко", callback_data="diff_Легко"),
               InlineKeyboardButton(text="🟡 Средне", callback_data="diff_Средне"),
               InlineKeyboardButton(text="🔴 Тяжело", callback_data="diff_Тяжело"))
    return markup
def get_next_set_keyboard(has_sets=False):
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton(text="🔄 Тот же вес", callback_data="nextset_same"))
    if has_sets:
        markup.add(InlineKeyboardButton(text="✏️ Исправить последний", callback_data="edit_last_set"))
    markup.add(InlineKeyboardButton(text="⏳ Отдых 1.5 мин", callback_data="rest_90"),
               InlineKeyboardButton(text="⏳ Отдых 2 мин", callback_data="rest_120"))
    markup.add(InlineKeyboardButton(text="🛑 Закончить и Сохранить", callback_data="finish_exercise"))
    return markup
def get_edit_main_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton(text="🗑 Удалить ошибочный подход", callback_data="edit_menu_del"),
               InlineKeyboardButton(text="⚡️ Изменить оценку RPE", callback_data="edit_menu_rpe"),
               InlineKeyboardButton(text="🏠 В главное меню", callback_data="cancel"))
    return markup
def get_edit_sets_keyboard(user_id):
    markup = InlineKeyboardMarkup(row_width=1)
    history = gym_db.get(str(user_id), [])
    recent = history[-20:]
    if not recent:
        return None
    for w in reversed(recent):
        date_display = w.get('date', 'Без даты')
        set_num = w.get('set_num', '?')
        btn_text = f"❌ {date_display} | {w.get('exercise', '')} ({set_num}-й: {w.get('weight', '')}кг x {format_reps_clean(w)})"
        markup.add(InlineKeyboardButton(text=btn_text, callback_data=f"del_{w.get('id', 0)}"))
    markup.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="edit_main_menu"))
    return markup
def get_edit_rpe_list_keyboard(user_id):
    markup = InlineKeyboardMarkup(row_width=1)
    history = gym_db.get(str(user_id), [])
    unique_workouts = []
    seen = set()
    for w in reversed(history):
        identifier = (w.get('date'), w.get('exercise'))
        if identifier not in seen:
            seen.add(identifier)
            unique_workouts.append(w)
        if len(unique_workouts) >= 90:
            break
    if not unique_workouts:
        return None
    for w in unique_workouts:
        current_rpe = w.get('diff') or w.get('rpe') or 'Нет'
        btn_text = f"⚡️ {w.get('date','?')} | {w.get('exercise','')} (Сейчас: {current_rpe})"
        markup.add(InlineKeyboardButton(text=btn_text, callback_data=f"rpegroup_{w.get('id', 0)}"))
    markup.add(InlineKeyboardButton(text="⬅️ Назад", callback_data="edit_main_menu"))
    return markup
def get_diffedit_keyboard():
    markup = InlineKeyboardMarkup(row_width=3)
    markup.add(InlineKeyboardButton(text="🟢 Легко", callback_data="diffedit_Легко"),
               InlineKeyboardButton(text="🟡 Средне", callback_data="diffedit_Средне"),
               InlineKeyboardButton(text="🔴 Тяжело", callback_data="diffedit_Тяжело"))
    markup.add(InlineKeyboardButton(text="⬅️ Назад к списку", callback_data="edit_menu_rpe"))
    return markup
def get_body_menu_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(
        InlineKeyboardButton(text="⚖️ Записать вес тела", callback_data="body_log_weight"),
        InlineKeyboardButton(text="🍽 Записать питание (ккал/белок/рис)", callback_data="body_log_food"),
        InlineKeyboardButton(text="💧 Записать воду и сон", callback_data="body_log_sleep_water"),
        InlineKeyboardButton(text="😴 Записать настроение", callback_data="body_log_mood"),
        InlineKeyboardButton(text="📏 Записать замеры тела", callback_data="body_log_measurements"),
        InlineKeyboardButton(text="📋 Мой журнал тела (14 дней)", callback_data="body_view_diary"),
        InlineKeyboardButton(text="📊 Мой прогресс тела", callback_data="body_progress"),
        InlineKeyboardButton(text="🧮 Рассчитать состав тела (Navy)", callback_data="body_calc_fat"),
        InlineKeyboardButton(text="🥗 Мои макросы (TDEE)", callback_data="body_macros"),
        InlineKeyboardButton(text="📊 График веса тела", callback_data="body_chart_bw"),
        InlineKeyboardButton(text="🏠 В главное меню", callback_data="cancel"),
    )
    return markup
def get_analytics_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton(text="📊 Дашборд 2×2 (все графики)", callback_data="analytics_dashboard"),
               InlineKeyboardButton(text="📈 График 1ПМ", callback_data="analytics_charts"),
               InlineKeyboardButton(text="🏠 Назад", callback_data="cancel"))
    return markup
def get_mood_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton(text="💪 Отлично", callback_data="mood_Отлично"),
               InlineKeyboardButton(text="😊 Хорошо", callback_data="mood_Хорошо"),
               InlineKeyboardButton(text="😐 Средне", callback_data="mood_Средне"),
               InlineKeyboardButton(text="😴 Устал", callback_data="mood_Устал"),
               InlineKeyboardButton(text="💀 Разбит", callback_data="mood_Разбит"))
    return markup
# === ХЕНДЛЕРЫ КОМАНД (/start, /profile, /today, /setup) ===
@bot.message_handler(commands=['start'])
def start_message(message):
    user_id = str(message.chat.id)
    clear_user_state(user_id)
    prof = profiles_db.get(user_id, {})
    name = prof.get('name', '')
    if not name:
        welcome_text = (
            "👋 *Добро пожаловать в GYM BOT!*\n\n"
            "Это твой умный научный дневник тренировок и фитнес-ассистент. Здесь ты сможешь:\n"
            "🔹 Вести тренировки, отслеживать рабочие веса и 1ПМ\n"
            "🔹 Контролировать питание (калории и макросы)\n"
            "🔹 Записывать замеры тела и вычислять % жира (Navy Fat)\n"
            "🔹 Следить за восстановлением мышц и ЦНС\n"
            "🔹 Получать советы на основе научных исследований PubMed\n\n"
            "Для того чтобы бот мог давать точные рекомендации, давай настроим твой профиль!"
        )
        bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=get_main_menu())
        setup_command(message)
    else:
        greet = f"Снова в деле, *{name}*! 🔥\n\n"
        welcome_text = (
            f"🔥 *GYM BOT v13.0 — НАУЧНЫЙ КОМБАЙН* 🔥\n\n{greet}"
            "〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"
            "✅ 1ПМ Эпли + Brzycki, EIMD + ЦНС алгоритм\n"
            "✅ Восстановление v3.0 — сон, вода, белок, настроение\n"
            "✅ Антропометрия — Navy Fat, 12 параметров тела\n"
            "✅ TDEE + Макросы (Mifflin-St Jeor)\n"
            "✅ Дашборд 2×2: 1ПМ, тоннаж, вес, радар\n"
            "✅ Детектор плато + прогноз через NumPy\n"
            "✅ PubMed x10 тем — 25+ исследований\n"
            "✅ Таймеры отдыха, разминочная пирамида\n\n"
            "Команды: /setup /profile /today\n"
            "Жми кнопку ниже 👇"
        )
        bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown", reply_markup=get_main_menu())
@bot.message_handler(commands=['setup'])
def setup_command(message):
    user_id = str(message.chat.id)
    if user_id not in profiles_db:
        profiles_db[user_id] = {}
    user_states[user_id] = "setup_name"
    bot.send_message(message.chat.id,
        "🤖 *Настройка профиля атлета*\n\nШаг 1/5: Как тебя зовут?",
        parse_mode="Markdown")
@bot.message_handler(commands=['profile'])
def profile_command(message):
    user_id = str(message.chat.id)
    uid = user_id
    prof = profiles_db.get(uid, {})
    if not prof:
        bot.send_message(message.chat.id,
            "Профиль не настроен. Запусти /setup", reply_markup=get_main_menu())
        return
    history = gym_db.get(uid, [])
    tonnage = sum(float(w.get('weight',0)) * float(w.get('reps',0)) for w in history)
    unique_days = len(set(w.get('date') for w in history))
    streak = calculate_training_streak(history)
    records = {}
    for w in history:
        ex = w.get('exercise')
        if ex in ["Жим лёжа", "Становая тяга", "Присед"]:
            if float(w.get('weight',0)) > 0 and float(w.get('reps',0)) > 0:
                e1 = epley_1rm(float(w['weight']), float(w['reps']))
                if ex not in records or e1 > records[ex]:
                    records[ex] = e1
    bw_list = [r for r in body_db.get(uid, []) if r.get('bodyweight')]
    bw_str = f"{bw_list[-1]['bodyweight']} кг" if bw_list else "—"
    first_date = "—"
    if history:
        all_dates = [parse_date(w.get('date')) for w in history]
        all_dates = [d for d in all_dates if d]
        if all_dates:
            first_date = min(all_dates).strftime("%d.%m.%Y")
    card = (
        "╔══════════════════════════════╗\n"
        "║     👤 ПРОФИЛЬ АТЛЕТА        ║\n"
        "╠══════════════════════════════╣\n"
        f"║ 🗣 Имя: {prof.get('name','Атлет'):<22}║\n"
        f"║ 📅 В деле с: {first_date:<19}║\n"
        f"║ 🏋️ Дней тренировок: {unique_days:<11}║\n"
        f"║ 🔥 Серия недель: {streak:<14}║\n"
        "╠══════════════════════════════╣\n"
        f"║ ⚖️ Вес: {bw_str:<23}║\n"
        f"║ 📏 Рост: {prof.get('height_cm','—'):<22}║\n"
        f"║ 💪 Жим 1ПМ: {records.get('Жим лежа',0)} кг{'':<17}║\n"
        f"║ 🦵 Присед 1ПМ: {records.get('Присед',0)} кг{'':<14}║\n"
        f"║ 🔗 Тяга 1ПМ: {records.get('Становая тяга',0)} кг{'':<16}║\n"
        "╠══════════════════════════════╣\n"
        f"║ 🏗️ Тоннаж: {tonnage/1000:.1f} т{'':<20}║\n"
        f"║ 🎯 Цель: {prof.get('goal','—'):<22}║\n"
        "╚══════════════════════════════╝"
    )
    bot.send_message(message.chat.id, card, reply_markup=get_main_menu())
@bot.message_handler(commands=['today'])
def today_command(message):
    user_id = str(message.chat.id)
    uid = user_id
    today = datetime.now()
    week_ago = today - timedelta(days=7)
    history = gym_db.get(uid, [])
    w7d = [w for w in history if (parse_date(w.get('date')) or datetime.min) >= week_ago]
    exercises = list(set(w.get('exercise') for w in w7d if w.get('exercise')))
    if not exercises:
        exercises = ["Жим лёжа", "Становая тяга", "Присед"]
    status_line, rec = get_today_recommendation(uid)
    msg = f"📊 *СВОДКА ДНЯ — {today.strftime('%d.%m.%Y')}*\n〰️〰️〰️〰️〰️〰️〰️〰️\n\n"
    msg += f"*{status_line}*\n\n"
    msg += f"👉 {rec}\n\n"
    # Детали восстановления
    for ex in exercises[:4]:
        z, pct, status, detail, cns_p, mus_p = calculate_recovery_status(ex, w7d, today, uid)
        msg += f"{z} *{ex}* — {pct} | ЦНС: {cns_p} | Мышцы: {mus_p}\n"
    msg += "\n"
    # Последние данные тела
    b_records = body_db.get(uid, [])
    bw_list = [r for r in b_records if r.get('bodyweight')]
    if bw_list:
        msg += f"⚖️ Вес: *{bw_list[-1]['bodyweight']} кг* ({bw_list[-1]['date']})\n"
    today_str = today.strftime("%d.%m.%Y")
    today_food = [r for r in b_records if r.get('date') == today_str]
    kcal_today = sum(r.get('calories', 0) for r in today_food)
    prot_today = sum(r.get('protein_g', 0) for r in today_food)
    sleep_today = next((r.get('sleep_hours', 0) for r in reversed(today_food) if r.get('sleep_hours')), 0)
    water_today = next((r.get('water_l', 0) for r in reversed(today_food) if r.get('water_l')), 0)
    if kcal_today: msg += f"🍽 Ккал: *{kcal_today}* | 🥩 Белок: *{prot_today}г*\n"
    if sleep_today: msg += f"😴 Сон: *{sleep_today} ч.*\n"
    if water_today: msg += f"💧 Вода: *{water_today} л.*\n"
    # Случайный совет
    all_tips = [f"*{v['title']}*: {v['short_summary'] if 'short_summary' in v else v.get('text', '')[:120]}..." for v in PUBMED_KNOWLEDGE.values()]
    msg += f"\n💡 _{random.choice(all_tips)}_"
    bot.send_message(message.chat.id, msg, parse_mode="Markdown", reply_markup=get_main_menu())

# === ХЕНДЛЕРЫ НАУЧНОЙ ПРОГРАММЫ (PUBMED AI) ===
def format_program_summary(prog):
    g_map = {"hypertrophy": "💪 Гипертрофия", "strength": "🏋️ Сила / SBD", "recomp": "⚖️ Рекомпозиция", "endurance": "⚡ Выносливость"}
    l_map = {"beginner": "🌱 Новичок", "intermediate": "🚀 Средний", "advanced": "👑 Опытный"}
    
    diag = prog.get('athlete_diagnosis', {})
    diag_text = ""
    if diag:
        rec = diag.get('recommendation', '')
        if rec:
            diag_text += f"\n🔍 *Персональная адаптация ИИ:*\n{rec}\n"
        if diag.get('sbd_total'):
            diag_text += f"🏋️ *Сумма 1ПМ (SBD):* {diag.get('sbd_total')} кг (Жим {diag.get('bench_ratio')}×BW | Присед {diag.get('squat_ratio')}×BW | Тяга {diag.get('dead_ratio')}×BW)\n"

    cur_w = prog.get('current_week', 1)
    matrix = prog.get('wave_matrix', [])
    w_info = next((m for m in matrix if m.get('week_number') == cur_w), None)
    w_str = f"Неделя {cur_w} из 6"
    if w_info:
        w_str += f" ({w_info.get('phase', '')} — {w_info.get('intensity_pct', 75)}% 1ПМ)"

    text = (
        f"🧬 *{prog.get('title', 'Научная тренировочная программа')}*\n"
        f"〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"
        f"🎯 *Цель:* {g_map.get(prog.get('goal'), prog.get('goal', '—'))}\n"
        f"🚀 *Уровень:* {l_map.get(prog.get('level'), prog.get('level', '—'))}\n"
        f"📅 *Частота:* {prog.get('days_per_week', 4)} дня в неделю\n"
        f"📈 *Текущий мезоцикл:* *{w_str}*\n"
        f"{diag_text}\n"
        f"📊 *Недельный объем (подходов/нед vs Schoenfeld MAV):*\n"
    )
    vol = prog.get('weekly_volume_sets', {})
    for m, s in list(vol.items())[:6]:
        text += f"• {m}: *{s}* подх/нед\n"
    text += "\n📚 *Научные основания PubMed:*\n"
    for c in prog.get('pubmed_citations', [])[:2]:
        text += f"_{c.get('citation', '')}_\n"
    return text

def _get_scaled_exercise_plan(ex, cur_w, w_info):
    intensity_pct = w_info.get('intensity_pct', 75) if w_info else 75
    scale_factor = intensity_pct / 75.0
    raw_w = ex.get('working_weight', 0)
    scaled_w = round((raw_w * scale_factor) / 2.5) * 2.5 if raw_w > 0 else 0.0

    base_sets = ex.get('sets', 3)
    is_base_lift = ex.get('key') in ('squat', 'bench_press', 'deadlift')
    
    if cur_w == 1:
        sets = base_sets
        reps = "5-6" if is_base_lift else ("8-10" if ex.get('type')=='compound' else "12-15")
    elif cur_w == 2:
        sets = base_sets
        reps = "5" if is_base_lift else ("8-10" if ex.get('type')=='compound' else "12-15")
    elif cur_w == 3:
        sets = base_sets
        reps = "4" if is_base_lift else ("6-8" if ex.get('type')=='compound' else "10-12")
    elif cur_w == 4:
        sets = base_sets + 1
        reps = "3-4" if is_base_lift else ("6-8" if ex.get('type')=='compound' else "10-12")
    elif cur_w == 5:
        sets = max(2, base_sets - 1)
        reps = "2-3" if is_base_lift else ("5-6" if ex.get('type')=='compound' else "8-10")
    else: # week 6 deload
        sets = 2
        reps = "5" if is_base_lift else ("6-8" if ex.get('type')=='compound' else "10")

    return scaled_w, sets, reps

def format_program_split_text(prog):
    cur_w = prog.get('current_week', 1)
    matrix = prog.get('wave_matrix', [])
    w_info = next((m for m in matrix if m.get('week_number') == cur_w), None)

    phase_name = w_info.get('phase', '') if w_info else ''
    pct = w_info.get('intensity_pct', 75) if w_info else 75
    text = f"📅 *НЕДЕЛЬНЫЙ СПЛИТ (Неделя {cur_w}/6: {phase_name} @ {pct}% 1ПМ)*\n〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️\n\n"
    for d in prog.get('days', []):
        text += f"🏋️ *{d.get('title', '')}* _({d.get('day_of_week', '')})_\n"
        text += f"🎯 _Фокус: {d.get('focus', '')}_\n"
        for idx, ex in enumerate(d.get('exercises', []), 1):
            scaled_w, sets, reps = _get_scaled_exercise_plan(ex, cur_w, w_info)
            w_str = f" @ *{scaled_w} кг*" if scaled_w > 0 else ""
            target_rpe = w_info.get('target_rpe', ex.get('target_rpe', 7.5)) if w_info else ex.get('target_rpe', 7.5)
            text += f"  {idx}. *{ex.get('name')}* — {sets}×{reps}{w_str} (RPE {target_rpe})\n"
        text += "\n"
    return text

def format_program_matrix_text(prog):
    text = f"📊 *6-НЕДЕЛЬНАЯ ВОЛНОВАЯ МАТРИЦА*\n〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️\n\n"
    for w in prog.get('wave_matrix', []):
        w_num = w.get('week_number', 1)
        cur = "👉 " if w_num == prog.get('current_week', 1) else ""
        text += f"{cur}*Неделя {w_num}: {w.get('phase')}*\n"
        text += f"  • Интенсивность: *{w.get('intensity_pct')}% 1ПМ* | RPE: *{w.get('target_rpe')}*\n"
        text += f"  • _{w.get('desc') or w.get('description', '')}_\n\n"
    return text

@bot.message_handler(commands=['program'])
def program_command(message):
    user_id = str(message.chat.id)
    prog = programs_db.get(user_id)
    if prog:
        text = format_program_summary(prog)
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_program_main_keyboard(has_prog=True))
    else:
        text = (
            "🧬 *Составление персональной программы тренинга (PubMed AI)*\n\n"
            "Бот подберет оптимальный сплит, недельный объем подходов (MAV по Шонфельду), "
            "расчетные веса от 1ПМ, разминочные пирамиды и 6-недельную волновую периодизацию.\n\n"
            "Нажми кнопку ниже, чтобы запустить подбор 👇"
        )
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_program_main_keyboard(has_prog=False))

# === ХЕНДЛЕРЫ ГЛАВНОГО МЕНЮ ===
MAIN_MENU_BUTTONS = [
    "🧬 Моя программа",
    "🏋️ Новое упражнение", "📈 Мой дневник",
    "🏆 Аналитика и Восстановление",
    "🍎 Питание и Тело", "🧮 Разминка",
    "📚 База PubMed", "⚙️ Редактировать",
    "📥 Скачать в Excel", "ℹ️ Загрузить свои данные (Импорт)",
    "📖 Инструкция"
]
@bot.message_handler(func=lambda message: message.text in MAIN_MENU_BUTTONS)
def handle_main_menu(message):
    user_id = str(message.chat.id)
    text = message.text
    clear_user_state(user_id)
    if user_id not in gym_db:
        gym_db[user_id] = []
    if text == "🧬 Моя программа":
        program_command(message)
    elif text == "🏋️ Новое упражнение":
        bot.send_message(message.chat.id, "📅 *За какой день записываем тренировку?*",
            parse_mode="Markdown", reply_markup=get_date_keyboard())
    elif text == "📈 Мой дневник":
        user_history = gym_db.get(user_id, [])
        if not user_history:
            bot.send_message(message.chat.id, "📭 Твой дневник пока пуст.", reply_markup=get_main_menu())
            return
        # Мини-сводка 7д
        today = datetime.now()
        week_ago = today - timedelta(days=7)
        w7d = [w for w in user_history if (parse_date(w.get('date')) or datetime.min) >= week_ago]
        days_7 = len(set(w.get('date') for w in w7d))
        sets_7 = len(w7d)
        ton_7 = sum(float(w.get('weight',0))*float(w.get('reps',0)) for w in w7d) / 1000
        # Топ-3 за месяц
        top3 = get_top3_progress(user_history)
        header = (f"📊 *ДНЕВНИК ПРОГРЕССИИ v13.0*\n〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"
                  f"📅 *Последние 7 дней:* {days_7} тренировок | {sets_7} подходов | {ton_7:.1f} т\n")
        if top3:
            header += "🏅 *Топ прогресса за месяц:* "
            header += " | ".join(f"{ex}: +{pct:.0f}%" for ex, (pct, _) in top3) + "\n"
        header += "〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"
        # Вычислим рекорды 1ПМ для пометки
        all_records = {}
        for w in user_history:
            ex = w.get('exercise', '')
            wt = float(w.get('weight', 0))
            rp = float(w.get('reps', 0))
            if wt > 0 and rp > 0:
                e1 = epley_1rm(wt, rp)
                if ex not in all_records or e1 > all_records[ex]:
                    all_records[ex] = e1
        # Дневник по дням — группировка ТОЛЬКО по дате
        daily_data = {}
        for w in user_history:
            date_str = w.get('date', '')
            if not date_str:
                continue
            # Получаем день недели из самой даты (не полагаемся на поле 'day')
            parsed_d = parse_date(date_str)
            day_name = parsed_d.strftime('%A') if parsed_d else w.get('day', '')
            # Преобразуем английский день недели в русский
            day_ru = {'Monday':'Понедельник','Tuesday':'Вторник','Wednesday':'Среда',
                      'Thursday':'Четверг','Friday':'Пятница','Saturday':'Суббота',
                      'Sunday':'Воскресенье'}.get(day_name, day_name)
            d_key = f"{date_str} ({day_ru})"
            ex = w.get('exercise', 'Неизвестно')
            if d_key not in daily_data:
                daily_data[d_key] = {}
            if ex not in daily_data[d_key]:
                daily_data[d_key][ex] = {'sets': [], 'diff': w.get('diff', '') or w.get('rpe', '')}
            daily_data[d_key][ex]['sets'].append(w)
            # Берём наибольший RPE за день для упражнения
            rpe = w.get('diff', '') or w.get('rpe', '')
            existing = daily_data[d_key][ex]['diff']
            rpe_rank = {'Тяжело': 3, 'Средне': 2, 'Средно': 2, 'Легко': 1}
            if rpe_rank.get(rpe, 0) >= rpe_rank.get(existing, 0):
                daily_data[d_key][ex]['diff'] = rpe
        graph_text = header

        for d_key, exercises in daily_data.items():
            graph_text += f"\n📅 *{d_key}*\n────────────────────\n"
            for ex, ex_data in exercises.items():
                diff = ex_data['diff']
                color = "🟢" if diff == "Легко" else "🟡" if diff == "Средне" else "🔴"
                session_tonnage = sum(float(s.get('weight',0)) * float(s.get('reps',0)) for s in ex_data['sets'])
                ex_safe = escape_md(ex)
                tonnage_str = f" _(Тоннаж: {session_tonnage:.0f} кг)_" if session_tonnage > 0 else ""
                graph_text += f"🏋️ *{ex_safe}*{tonnage_str}\n"
                for s in ex_data['sets']:
                    set_number = s.get('set_num', '?')
                    wt = float(s.get('weight', 0))
                    rp = float(s.get('reps', 0))
                    reps_clean = format_reps_clean(s)
                    set_rpe = s.get('rpe') or s.get('diff') or 'Легко'
                    set_color = "🔴" if set_rpe == "Тяжело" else "🟡" if (set_rpe == "Средне" or set_rpe == "Средно") else "🟢"
                    if wt > 0:
                        e1rm = epley_1rm(wt, rp)
                        is_record = (ex in all_records and abs(e1rm - all_records[ex]) < 0.1)
                        rec_marker = " 🏆" if is_record else ""
                        graph_text += f"   {set_color} [{set_rpe}] {set_number}-й: *{wt} кг* × {reps_clean} _(1ПМ≈{e1rm} кг)_{rec_marker}\n"
                    else:
                        graph_text += f"   {set_color} [{set_rpe}] {set_number}-й: _(без веса)_ × {reps_clean}\n"
            graph_text += "────────────────────\n"
        send_long_message(message.chat.id, graph_text, reply_markup=get_main_menu())
    elif text == "🏆 Аналитика и Восстановление":
        user_history = gym_db.get(user_id, [])
        msg = bot.send_message(message.chat.id, "⏳ Анализирую данные...")
        report = calculate_analytics(user_history, user_id)
        try:
            bot.delete_message(message.chat.id, msg.message_id)
        except Exception:
            pass
        send_long_message(message.chat.id, report, reply_markup=get_analytics_keyboard())
    elif text == "🍎 Питание и Тело":
        bot.send_message(message.chat.id,
            "🍎 *Питание и Тело*\n\n"
            "Данные о сне, воде и белке учитываются в алгоритме восстановления v3.0.\n"
            "Navy Method рассчитывает % жира по замерам.",
            parse_mode="Markdown", reply_markup=get_body_menu_keyboard())
    elif text == "🧮 Разминка":
        user_states[user_id] = "waiting_warmup_weight"
        bot.send_message(message.chat.id,
            "🧮 *Калькулятор разминочной пирамиды*\n\nВведи *целевой рабочий вес* (кг):",
            parse_mode="Markdown")
    elif text == "📚 База PubMed":
        bot.send_message(message.chat.id,
            "📚 *База знаний PubMed — 10 тем, 25+ исследований*\n\nВыбери тему:",
            parse_mode="Markdown", reply_markup=get_pubmed_menu_keyboard())
    elif text == "⚙️ Редактировать":
        bot.send_message(message.chat.id, "🛠 *Панель редактирования*\n\nЧто изменить?",
            parse_mode="Markdown", reply_markup=get_edit_main_keyboard())
    elif text == "📥 Скачать в Excel":
        user_history = gym_db.get(user_id, [])
        if not user_history:
            bot.send_message(message.chat.id, "Нет данных.", reply_markup=get_main_menu())
            return
        filename = f"gym_stats_{user_id}.csv"
        with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
            writer = csv.writer(f, delimiter=';')
            writer.writerow(['Дата', 'День', 'Упражнение', 'Подход', 'Вес (кг)', 'Повторения', 'RPE'])
            for w in user_history:
                writer.writerow([w.get('date',''), w.get('day',''), w.get('exercise',''),
                                  w.get('set_num',''), w.get('weight',''), format_reps_clean(w), w.get('diff','')])
        with open(filename, 'rb') as f:
            bot.send_document(message.chat.id, f, caption="📊 Твоя статистика!", reply_markup=get_main_menu())
        os.remove(filename)
    elif text == "ℹ️ Загрузить свои данные (Импорт)":
        bot.send_message(message.chat.id,
            "📄 *Импорт данных*\n\n1. Нажми «📥 Скачать в Excel» — получишь шаблон.\n"
            "2. Заполни свои данные, сохрани в *.csv*.\n"
            "3. Отправь файл боту в чат.", parse_mode="Markdown")
    elif text == "📖 Инструкция":
        instruction_text = (
            "📖 *ИНСТРУКЦИЯ — GYM BOT v13.0*\n"
            "────────────────────\n\n"
            "🔹 *КОМАНДЫ*\n"
            "  `/start` — перезапуск и меню\n"
            "  `/setup` — настройка профиля (имя, рост, пол, цель)\n"
            "  `/profile` — карточка атлета и рекорды\n"
            "  `/today` — сводка дня: восстановление и питание\n\n"
            "────────────────────\n"
            "🔹 *ГЛАВНОЕ МЕНЮ*\n\n"
            "🏋️ *Новое упражнение*\n"
            "  Запись подходов: дата → упражнение → вес → повторения → оценка RPE.\n"
            "  Вес можно ввести *0* для упражнений без отягощения (подтягивания, планка).\n\n"
            "📈 *Мой дневник*\n"
            "  Вся история тренировок по дням. Показывает вес, повторения,\n"
            "  расчётный 1ПМ и рекорды 🏆.\n\n"
            "🏆 *Аналитика и Восстановление*\n"
            "  Статистика, рекорды 1ПМ (Эпли + Brzycki), тренд объёма,\n"
            "  детектор плато и восстановление ЦНС v3.0.\n"
            "  Графики: дашборд 2×2, 1ПМ, тоннаж, вес тела.\n\n"
            "🍎 *Питание и Тело*\n"
            "  Запись веса, ккал, белка, воды, сна и настроения.\n"
            "  Расчёт: Navy Fat (% жира), TDEE и макросы.\n\n"
            "🧮 *Разминка*\n"
            "  Пирамида разогрева от 50% до 93% рабочего веса.\n\n"
            "📚 *База PubMed*\n"
            "  10 тем, 25+ научных исследований.\n\n"
            "⚙️ *Редактировать*\n"
            "  Удалить подход или изменить оценку RPE.\n\n"
            "📥 *Excel / Импорт*\n"
            "  Скачать историю в CSV или загрузить свой файл.\n\n"
            "────────────────────\n"
            "💡 *СОВЕТЫ*\n"
            "  • Записывай сон и воду — бот точнее считает восстановление ЦНС\n"
            "  • Следи за плато — бот предупредит если нет прогресса >21 день\n"
            "  • Настрой профиль через /setup для персонального TDEE"
        )
        send_long_message(message.chat.id, instruction_text)
# === ХЕНДЛЕРЫ ИНЛАЙН-КНОПОК ===
@bot.message_handler(content_types=['document'])
def handle_document(message):
    user_id = str(message.chat.id)
    file_name = message.document.file_name
    if not file_name.endswith('.csv'):
        bot.reply_to(message, "⚠️ Загрузи файл в формате *.csv*.", parse_mode="Markdown")
        return
    try:
        bot.send_message(message.chat.id, "⏳ Читаю файл...")
        file_info = bot.get_file(message.document.file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        csv_data = downloaded_file.decode('utf-8-sig')
        reader = csv.reader(io.StringIO(csv_data), delimiter=';')
        next(reader, None)
        if user_id not in gym_db:
            gym_db[user_id] = []
        count = 0
        for row in reader:
            if len(row) >= 6:
                try:
                    weight_str = row[4].replace(',', '.')
                    weight_val = float(weight_str)
                    reps_raw = row[5].strip().replace(',', '.')
                    rir_val = None
                    if '+' in reps_raw:
                        parts = reps_raw.split('+')
                        reps_val = float(parts[0].strip())
                        rir_val = float(parts[1].strip())
                    else:
                        reps_val = float(reps_raw)
                        
                    if reps_val == int(reps_val):
                        reps_val = int(reps_val)
                    if rir_val is not None and rir_val == int(rir_val):
                        rir_val = int(rir_val)
                        
                    entry = {
                        "id": int(time.time() * 1000) + random.randint(1, 1000000),
                        "date": row[0].strip(), "day": row[1].strip(),
                        "exercise": row[2].strip(), "set_num": row[3].strip(),
                        "weight": weight_val, "reps": reps_val,
                        "diff": row[6].strip() if len(row) > 6 else "Средне"
                    }
                    if rir_val is not None:
                        entry["rir"] = rir_val
                    gym_db[user_id].append(entry)
                    count += 1
                except Exception:
                    continue
        save_db()
        bot.reply_to(message, f"✅ *Импорт завершён!* Добавлено {count} подходов.",
                     parse_mode="Markdown", reply_markup=get_main_menu())
    except Exception:
        bot.reply_to(message, "❌ Ошибка чтения файла.", reply_markup=get_main_menu())
@bot.message_handler(content_types=['sticker', 'photo', 'video', 'audio', 'voice', 'location', 'contact'])
def handle_non_text(message):
    user_id = str(message.chat.id)
    state = user_states.get(user_id)
    if state:
        bot.send_message(message.chat.id,
            "⚠️ Введи *число* или текст, а не медиафайл.", parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, "Используй кнопки меню 👇", reply_markup=get_main_menu())

# Обработка inline-кнопок настройки профиля
@bot.callback_query_handler(func=lambda call: call.data.startswith("setup_"))
def handle_setup_callbacks(call):
    user_id = str(call.message.chat.id)
    msg_id = call.message.message_id
    data = call.data
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    if data.startswith("setup_gender_"):
        gender = data.split("_")[2]
        profiles_db[user_id] = profiles_db.get(user_id, {})
        profiles_db[user_id]['gender'] = gender
        user_states[user_id] = "setup_birth_year"
        try:
            bot.edit_message_text(
                f"✅ Пол: {'Мужской' if gender=='male' else 'Женский'}.\n\n"
                f"📅 Шаг 4/5: Год рождения? (например: `1995`)",
                user_id, msg_id, parse_mode="Markdown")
        except Exception:
            bot.send_message(user_id, "📅 Введи год рождения:")
    elif data.startswith("setup_goal_"):
        goal = data.split("setup_goal_")[1]
        profiles_db[user_id]['goal'] = goal
        user_states[user_id] = "setup_days"
        goal_names = {"hypertrophy": "Гипертрофия", "strength": "Сила",
                      "weight_loss": "Похудение", "endurance": "Выносливость"}
        try:
            bot.edit_message_text(
                f"✅ Цель: {goal_names.get(goal, goal)}.\n\n"
                f"🗓 Шаг 5/5: Сколько дней тренируешься в неделю? (цифра от 1 до 7)",
                user_id, msg_id, parse_mode="Markdown")
        except Exception:
            bot.send_message(user_id, "Введи дней в неделю (1-7):")
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    user_id = str(call.message.chat.id)
    msg_id = call.message.message_id
    data = call.data
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass
    if data == "cancel":
        clear_user_state(user_id)
        try:
            bot.delete_message(chat_id=user_id, message_id=msg_id)
        except Exception:
            pass
        bot.send_message(user_id, "🏠 В главное меню.", reply_markup=get_main_menu())
        return

    # ── PROGRAM CALLBACKS ──
    if data.startswith("prog_"):
        if data == "prog_main_view":
            prog = programs_db.get(user_id)
            if prog:
                bot.edit_message_text(format_program_summary(prog), user_id, msg_id, parse_mode="Markdown", reply_markup=get_program_main_keyboard(True))
            else:
                bot.edit_message_text("🧬 Программа еще не создана.", user_id, msg_id, reply_markup=get_program_main_keyboard(False))
            return
        elif data == "prog_view_split":
            prog = programs_db.get(user_id)
            if prog:
                back_mk = InlineKeyboardMarkup()
                back_mk.add(InlineKeyboardButton("⬅️ Назад", callback_data="prog_main_view"))
                try: bot.delete_message(user_id, msg_id)
                except: pass
                send_long_message(user_id, format_program_split_text(prog), reply_markup=back_mk)
            return
        elif data == "prog_view_matrix":
            prog = programs_db.get(user_id)
            if prog:
                back_mk = InlineKeyboardMarkup()
                back_mk.add(InlineKeyboardButton("⬅️ Назад", callback_data="prog_main_view"))
                try: bot.delete_message(user_id, msg_id)
                except: pass
                send_long_message(user_id, format_program_matrix_text(prog), reply_markup=back_mk)
            return
        elif data == "prog_select_week":
            prog = programs_db.get(user_id)
            if prog:
                cur_w = prog.get('current_week', 1)
                text = (
                    f"📈 *Выбор недели мезоцикла (Периодизация)*\n〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"
                    f"Текущая активная: *Неделя {cur_w} из 6*\n\n"
                    f"• *Нед 1:* 72.5% 1ПМ (Вкатывание / Техника)\n"
                    f"• *Нед 2:* 77.5% 1ПМ (Накопление объема)\n"
                    f"• *Нед 3:* 82.5% 1ПМ (Интенсификация)\n"
                    f"• *Нед 4:* 85.0% 1ПМ (Пиковый объем)\n"
                    f"• *Нед 5:* 90.0% 1ПМ (Личный рекорд 🔥)\n"
                    f"• *Нед 6:* 55.0% 1ПМ (Deload / Разгрузка 🍃)\n\n"
                    f"Выбери неделю для пересчета рабочих весов:"
                )
                bot.edit_message_text(text, user_id, msg_id, parse_mode="Markdown", reply_markup=get_program_weeks_keyboard(prog))
            return
        elif data.startswith("prog_setweek_"):
            new_w = int(data.split("prog_setweek_")[1])
            prog = programs_db.get(user_id)
            if prog:
                prog['current_week'] = new_w
                save_programs()
                bot.answer_callback_query(call.id, f"✅ Установлена Неделя {new_w}!")
                bot.edit_message_text(format_program_summary(prog), user_id, msg_id, parse_mode="Markdown", reply_markup=get_program_main_keyboard(True))
            return
        elif data == "prog_start_menu":
            prog = programs_db.get(user_id)
            if prog:
                bot.edit_message_text("🏋️ *Выбери день тренировки:*", user_id, msg_id, parse_mode="Markdown", reply_markup=get_program_days_keyboard(prog))
            return
        elif data.startswith("prog_runday_"):
            day_idx = int(data.split("prog_runday_")[1])
            prog = programs_db.get(user_id)
            if prog and day_idx < len(prog.get('days', [])):
                day = prog['days'][day_idx]
                cur_w = prog.get('current_week', 1)
                matrix = prog.get('wave_matrix', [])
                w_info = next((m for m in matrix if m.get('week_number') == cur_w), None)
                intensity_pct = w_info.get('intensity_pct', 75) if w_info else 75
                scale_factor = intensity_pct / 75.0

                w_title_badge = f" [Неделя {cur_w}/6: {w_info.get('phase','')} @ {intensity_pct}%]" if w_info else ""
                day_text = f"🏋️ *{day.get('title')}*{w_title_badge}\n🎯 _Фокус: {day.get('focus','')}_\n〰️〰️〰️〰️〰️〰️〰️〰️\n\n"
                for idx, ex in enumerate(day.get('exercises', []), 1):
                    scaled_w, sets, reps = _get_scaled_exercise_plan(ex, cur_w, w_info)
                    w_str = f" @ *{scaled_w} кг*" if scaled_w > 0 else ""
                    target_rpe = w_info.get('target_rpe', ex.get('target_rpe', 7.5)) if w_info else ex.get('target_rpe', 7.5)
                    day_text += f"*{idx}. {ex.get('name')}* _({ex.get('muscle_group')})_\n"
                    
                    # Warmup ONLY on 1st main compound
                    if ex.get('warmup_ladder') and scaled_w > 0 and (idx == 1 or ex.get('key') in ('bench_press','squat','deadlift')):
                        scaled_warmup = []
                        for wu in ex['warmup_ladder']:
                            sw = round((wu['weight'] * scale_factor) / 2.5) * 2.5
                            scaled_warmup.append(f"{sw}кг×{wu['reps']}")
                        day_text += "   🟡 *Разминка:* " + " ➔ ".join(scaled_warmup) + "\n"
                    else:
                        day_text += "   💡 _Разминка не нужна (мышцы разогреты)_\n"

                    day_text += f"   🔥 *Рабочие сеты ({sets} подх):* {reps} повт{w_str} (RPE {target_rpe})\n"
                    if ex.get('pubmed_tip'):
                        day_text += f"   💡 _{ex.get('pubmed_tip')}_\n"
                    day_text += "\n"
                day_text += "👉 Нажми «🏋️ Новое упражнение» в меню, чтобы залогировать подходы!"
                back_mk = InlineKeyboardMarkup()
                back_mk.add(InlineKeyboardButton("⏳ Таймер отдыха 2 мин", callback_data="rest_120"),
                            InlineKeyboardButton("⬅️ К списку дней", callback_data="prog_start_menu"))
                try: bot.delete_message(user_id, msg_id)
                except: pass
                send_long_message(user_id, day_text, reply_markup=back_mk)
            return
        elif data == "prog_wizard_start":
            user_states[user_id] = {}
            bot.edit_message_text(
                "🎯 *Шаг 1/4: Выбери главную цель тренинга:*\n\n"
                "• *Гипертрофия* — максимальный рост мышечных волокон (12-18 сетов/нед, MAV)\n"
                "• *Сила (SBD)* — пауэрлифтинг, рост 1ПМ в тройке движений\n"
                "• *Рекомпозиция* — плотный силовой тренинг на легком дефиците\n"
                "• *Выносливость* — функционал, турники, рельеф",
                user_id, msg_id, parse_mode="Markdown", reply_markup=get_program_wizard_goal_keyboard()
            )
            return
        elif data.startswith("prog_goal_"):
            goal = data.split("prog_goal_")[1]
            if not isinstance(user_states.get(user_id), dict): user_states[user_id] = {}
            user_states[user_id]['prog_goal'] = goal
            bot.edit_message_text(
                "📅 *Шаг 2/4: Сколько дней в неделю готов тренироваться?*",
                user_id, msg_id, parse_mode="Markdown", reply_markup=get_program_wizard_days_keyboard()
            )
            return
        elif data.startswith("prog_days_"):
            days = int(data.split("prog_days_")[1])
            if not isinstance(user_states.get(user_id), dict): user_states[user_id] = {}
            user_states[user_id]['prog_days'] = days
            bot.edit_message_text(
                "🚀 *Шаг 3/4: Твой уровень тренировочного стажа?*",
                user_id, msg_id, parse_mode="Markdown", reply_markup=get_program_wizard_level_keyboard()
            )
            return
        elif data.startswith("prog_level_"):
            level = data.split("prog_level_")[1]
            if not isinstance(user_states.get(user_id), dict): user_states[user_id] = {}
            user_states[user_id]['prog_level'] = level
            days = user_states[user_id].get('prog_days', 3)

            # Диагностика профиля для подсказки
            history = gym_db.get(user_id, [])
            records = {}
            for w in history:
                ex = w.get('exercise')
                wt = float(w.get('weight', 0))
                rp = float(w.get('reps', 0))
                if wt > 0 and rp > 0:
                    e1 = epley_1rm(wt, rp)
                    if ex not in records or e1 > records[ex]:
                        records[ex] = e1

            u1rm = {
                "bench_press": records.get("Жим лёжа", 70.0),
                "squat": records.get("Присед", 90.0),
                "deadlift": records.get("Становая тяга", 100.0)
            }
            prof = profiles_db.get(user_id, {})
            diag = analyze_athlete_profile(history, prof, u1rm) if 'analyze_athlete_profile' in globals() else {}
            rec_note = f"\n\n💡 _{diag.get('recommendation', '')}_" if diag.get('recommendation') else ""

            bot.edit_message_text(
                f"🧬 *Шаг 4/4: Выбери структуру сплита для {days} дней:*\n"
                f"_(Или выбери ИИ Автовыбор — движок проанализирует твои веса и подберет идеальную схему)_{rec_note}",
                user_id, msg_id, parse_mode="Markdown", reply_markup=get_program_wizard_split_keyboard(days)
            )
            return
        elif data.startswith("prog_split_"):
            split_choice = data.split("prog_split_")[1]
            st = user_states.get(user_id, {})
            goal = st.get('prog_goal', 'hypertrophy') if isinstance(st, dict) else 'hypertrophy'
            days = st.get('prog_days', 3) if isinstance(st, dict) else 3
            level = st.get('prog_level', 'intermediate') if isinstance(st, dict) else 'intermediate'

            # Подтягиваем 1ПМ рекорды пользователя из истории
            history = gym_db.get(user_id, [])
            records = {}
            for w in history:
                ex = w.get('exercise')
                wt = float(w.get('weight', 0))
                rp = float(w.get('reps', 0))
                if wt > 0 and rp > 0:
                    e1 = epley_1rm(wt, rp)
                    if ex not in records or e1 > records[ex]:
                        records[ex] = e1

            user_1rm = {
                "bench_press": records.get("Жим лёжа", 68.0),
                "squat": records.get("Присед", 92.5),
                "deadlift": records.get("Становая тяга", 100.0)
            }
            prof = profiles_db.get(user_id, {})

            loading = bot.send_message(user_id, "⏳ Генерирую адаптированную программу через PubMed AI...")
            if generate_workout_program:
                new_prog = generate_workout_program(
                    goal=goal,
                    level=level,
                    days_per_week=days,
                    split_preference=split_choice,
                    user_1rm=user_1rm,
                    workouts_history=history,
                    user_profile=prof
                )
            else:
                new_prog = {"title": "Базовая программа", "goal": goal, "level": level, "days_per_week": days, "days": []}
            
            programs_db[user_id] = new_prog
            save_program_db()
            clear_user_state(user_id)

            try: bot.delete_message(user_id, loading.message_id)
            except: pass

            summary = "🎉 *ТВОЯ НАУЧНАЯ ПРОГРАММА ГОТОВА!*\n\n" + format_program_summary(new_prog)
            bot.send_message(user_id, summary, parse_mode="Markdown", reply_markup=get_program_main_keyboard(has_prog=True))
            return

    if data in ("rest_90", "rest_120"):
        seconds = 90 if data == "rest_90" else 120
        mins = seconds // 60
        bot.answer_callback_query(call.id, f"⏳ Таймер {mins} мин запущен!", show_alert=False)
        start_rest_timer(user_id, seconds)
        try:
            bot.edit_message_reply_markup(user_id, msg_id, reply_markup=None)
        except Exception:
            pass
        return
    if data.startswith("pubmed_"):
        key = data[7:]
        back_markup = InlineKeyboardMarkup()
        back_markup.add(InlineKeyboardButton("⬅️ К списку", callback_data="pubmed_back"),
                        InlineKeyboardButton("🏠 Меню", callback_data="cancel"))
        
        if key == "myths":
            text_str = "🛑 *ТОП-10 ФИТНЕС МИФОВ*\n\n"
            for k, v in PUBMED_MYTHS.items():
                text_str += f"*{v['title']}*\n_Реальность:_ {v['reality']}\n_Исследование:_ {v['study_ref']}\n\n"
            try: bot.delete_message(user_id, msg_id)
            except: pass
            send_long_message(user_id, text_str, reply_markup=back_markup)
        elif key == "landmarks":
            text_str = "🥇 *THE LANDMARK STUDIES*\n\n"
            for k, v_list in PUBMED_LANDMARKS.items():
                text_str += f"*{k.upper()}*\n"
                for i, v in enumerate(v_list, 1):
                    text_str += f"{i}. {v}\n"
                text_str += "\n"
            try: bot.delete_message(user_id, msg_id)
            except: pass
            send_long_message(user_id, text_str, reply_markup=back_markup)
        elif key == "standards":
            text_str = "📏 *НАУЧНЫЕ НОРМАТИВЫ*\n\n"
            for k, v in PUBMED_STANDARDS.items():
                text_str += f"*{v['description']}*\n"
                if 'levels' in v:
                    for lvl, stats in v['levels'].items():
                        text_str += f"_{lvl}_: {stats}\n"
                else:
                    for sk, sv in v.items():
                        if sk != 'description':
                            text_str += f"*{sk}*: {sv}\n"
                text_str += "\n"
            try: bot.delete_message(user_id, msg_id)
            except: pass
            send_long_message(user_id, text_str, reply_markup=back_markup)
        elif key == "back":
            try:
                bot.edit_message_text("📚 *База знаний PubMed*\n\nВыбери тему:",
                    user_id, msg_id, parse_mode="Markdown", reply_markup=get_pubmed_menu_keyboard())
            except Exception:
                pass
        else:
            entry = PUBMED_KNOWLEDGE.get(key)
            if entry:
                full_t = entry.get('full_text', '')
                try: bot.delete_message(user_id, msg_id)
                except: pass
                send_long_message(user_id, f"*{entry['title']}*\n\n{full_t}", reply_markup=back_markup)
        return
    if data == "analytics_dashboard":
        user_history = gym_db.get(user_id, [])
        loading = bot.send_message(user_id, "⏳ Генерирую дашборд 2×2...")
        f = generate_dashboard_2x2(user_id)
        try:
            bot.delete_message(user_id, loading.message_id)
        except Exception:
            pass
        if f:
            send_and_delete_chart(user_id, f, "📊 Дашборд: 1ПМ | Тоннаж | Вес тела | Антропометрия")
        else:
            bot.send_message(user_id, "Недостаточно данных.", reply_markup=get_main_menu())
        return
    if data == "analytics_charts":
        user_history = gym_db.get(user_id, [])
        if not user_history:
            bot.answer_callback_query(call.id, "Нет данных!", show_alert=True)
            return
        loading_msg = bot.send_message(user_id, "⏳ Генерирую графики...")
        sent = 0
        f1 = generate_1rm_chart(user_history, user_id)
        if f1: send_and_delete_chart(user_id, f1, "📈 Рост 1ПМ"); sent += 1
        f2 = generate_tonnage_chart(user_history, user_id)
        if f2: send_and_delete_chart(user_id, f2, "🏗 Тоннаж по неделям"); sent += 1
        f3 = generate_bodyweight_chart(user_id)
        if f3: send_and_delete_chart(user_id, f3, "⚖️ Вес тела"); sent += 1
        try:
            bot.delete_message(user_id, loading_msg.message_id)
        except Exception:
            pass
        bot.send_message(user_id, f"✅ Отправлено {sent} граф.", reply_markup=get_main_menu())
        return
    # Меню тела
    if data == "body_log_weight":
        user_states[user_id] = "waiting_bodyweight"
        try:
            bot.edit_message_text("⚖️ Введи вес тела (кг), например: *85.5*",
                user_id, msg_id, parse_mode="Markdown")
        except Exception:
            bot.send_message(user_id, "⚖️ Введи вес тела (кг):")
        return
    if data == "body_log_food":
        user_states[user_id] = "waiting_calories"
        try:
            bot.edit_message_text(
                "🍽 *Запись питания*\n\nФормат: `ккал белок_г порции_риса заметка`\n\n"
                "Примеры:\n`3000 180 4 завтрак обед ужин`\n`2500 150 3`\n`0 0 0 читмил`",
                user_id, msg_id, parse_mode="Markdown")
        except Exception:
            bot.send_message(user_id, "🍽 Введи: ккал белок_г порции_риса заметка")
        return
    if data == "body_log_sleep_water":
        user_states[user_id] = "waiting_sleep_water"
        try:
            bot.edit_message_text(
                "💧😴 *Сон и вода*\n\nВведи через пробел: `литры_воды часы_сна`\n\nПример: `2.5 8`",
                user_id, msg_id, parse_mode="Markdown")
        except Exception:
            bot.send_message(user_id, "Введи: литры_воды часы_сна (пример: 2.5 8)")
        return
    if data == "body_log_mood":
        try:
            bot.edit_message_text("😊 *Как самочувствие?*", user_id, msg_id,
                parse_mode="Markdown", reply_markup=get_mood_keyboard())
        except Exception:
            bot.send_message(user_id, "Как самочувствие?", reply_markup=get_mood_keyboard())
        return
    if data.startswith("mood_"):
        mood_val = data[5:]
        today_str = datetime.now().strftime("%d.%m.%Y")
        log_body_entry(user_id, today_str, mood=mood_val)
        try:
            bot.edit_message_text(f"✅ Самочувствие *{mood_val}* записано!", user_id, msg_id,
                parse_mode="Markdown")
        except Exception:
            pass
        bot.send_message(user_id, "Данные о настроении учтены в алгоритме восстановления 🔋",
            reply_markup=get_main_menu())
        return
    if data == "body_log_measurements":
        user_states[user_id] = "waiting_measurements_chest"
        temp_workout[user_id] = {'measurements': {}}
        try:
            bot.edit_message_text(
                "📏 *Замеры тела — Шаг 1/7*\n\nВведи *обхват груди* (см), например: `105`\nИли напиши `0` чтобы пропустить.",
                user_id, msg_id, parse_mode="Markdown")
        except Exception:
            bot.send_message(user_id, "📏 Введи обхват груди (см) или 0 чтобы пропустить:")
        return
    if data == "body_view_diary":
        text_diary = get_body_diary_text(user_id)
        try:
            bot.edit_message_text(text_diary, user_id, msg_id,
                parse_mode="Markdown", reply_markup=get_body_menu_keyboard())
        except Exception:
            send_long_message(user_id, text_diary, reply_markup=get_body_menu_keyboard())
        return
    if data == "body_progress":
        text_prog = get_body_progress_text(user_id)
        try:
            bot.edit_message_text(text_prog, user_id, msg_id,
                parse_mode="Markdown", reply_markup=get_body_menu_keyboard())
        except Exception:
            bot.send_message(user_id, text_prog, parse_mode="Markdown", reply_markup=get_body_menu_keyboard())
        return
    if data == "body_calc_fat":
        prof = profiles_db.get(user_id, {})
        if not prof:
            bot.send_message(user_id, "Нет профиля. Запусти /setup", reply_markup=get_main_menu())
            return
        result = calculate_navy_fat(user_id)
        if not result:
            bot.send_message(user_id,
                "📏 *Navy Method*\n\nНет данных о замерах.\n"
                "Нажми *📏 Записать замеры тела* и введи:\n"
                "• Обхват талии\n• Обхват шеи\n• Рост (в профиле /setup)",
                parse_mode="Markdown", reply_markup=get_body_menu_keyboard())
            return
        fat_pct, fat_kg, lbm, cat = result
        bw_list = [r for r in body_db.get(user_id, []) if r.get('bodyweight')]
        bw = float(bw_list[-1]['bodyweight']) if bw_list else 0
        h = float(prof.get('height_cm', 180))
        waist = body_db.get(user_id, [{}])[-1].get('measurements', {}).get('waist_cm', 0)
        hips = body_db.get(user_id, [{}])[-1].get('measurements', {}).get('hips_cm', 1)
        bmi = round(bw / (h/100)**2, 1) if bw and h else 0
        whr = round(float(waist) / float(hips), 2) if hips else 0
        whtr = round(float(waist) / float(h), 2) if h else 0
        text = (
            f"🧮 *СОСТАВ ТЕЛА (Navy Method)*\n〰️〰️〰️〰️〰️〰️〰️〰️〰️\n"
            f"📊 Формула Hodgdon & Beckett (1984)\n\n"
            f"💪 % жира: *{fat_pct}%*\n"
            f"🧈 Жировая масса: *{fat_kg} кг*\n"
            f"🏋️ Сухая масса (LBM): *{lbm} кг*\n"
            f"🏆 Категория ACSM: *{cat}*\n\n"
            f"📐 BMI: *{bmi}*\n"
            f"📐 Waist-to-Hip: *{whr}*\n"
            f"📐 Waist-to-Height: *{whtr}*\n\n"
            f"_ACSM нормы (муж): Атлет <14%, Фитнес <18%, Средне <25%_"
        )
        try:
            bot.edit_message_text(text, user_id, msg_id,
                parse_mode="Markdown", reply_markup=get_body_menu_keyboard())
        except Exception:
            bot.send_message(user_id, text, parse_mode="Markdown", reply_markup=get_body_menu_keyboard())
        return
    if data == "body_macros":
        text = get_macros_text(user_id)
        try:
            bot.edit_message_text(text, user_id, msg_id,
                parse_mode="Markdown", reply_markup=get_body_menu_keyboard())
        except Exception:
            bot.send_message(user_id, text, parse_mode="Markdown", reply_markup=get_body_menu_keyboard())
        return
    if data == "body_chart_bw":
        loading = bot.send_message(user_id, "⏳ Генерирую график веса тела...")
        f = generate_bodyweight_chart(user_id)
        try:
            bot.delete_message(user_id, loading.message_id)
        except Exception:
            pass
        if f:
            send_and_delete_chart(user_id, f, "⚖️ Динамика веса тела + тренд")
        else:
            bot.send_message(user_id, "Недостаточно данных (нужно 2+ записей).", reply_markup=get_main_menu())
        return
    # Редактор
    if data == "edit_main_menu":
        try:
            bot.edit_message_text("🛠 *Панель редактирования*\n\nЧто изменить?",
                user_id, msg_id, parse_mode="Markdown", reply_markup=get_edit_main_keyboard())
        except Exception:
            pass
    elif data == "edit_menu_del":
        markup = get_edit_sets_keyboard(user_id)
        if markup:
            try:
                bot.edit_message_text("Выбери подход для удаления:", user_id, msg_id, reply_markup=markup)
            except Exception:
                pass
        else:
            try:
                bot.edit_message_text("База пуста.", user_id, msg_id, reply_markup=get_edit_main_keyboard())
            except Exception:
                pass
    elif data == "edit_menu_rpe":
        markup = get_edit_rpe_list_keyboard(user_id)
        if markup:
            try:
                bot.edit_message_text("Выбери тренировку для изменения RPE:", user_id, msg_id, reply_markup=markup)
            except Exception:
                pass
        else:
            try:
                bot.edit_message_text("База пуста.", user_id, msg_id, reply_markup=get_edit_main_keyboard())
            except Exception:
                pass
    elif data.startswith("rpegroup_"):
        # ID может быть int (бот) или str (Web App) — сравниваем через str
        set_id_str = data.split("_")[1]
        target_date, target_ex = "", ""
        for w in gym_db.get(user_id, []):
            if str(w.get('id')) == set_id_str:
                target_date = w.get('date')
                target_ex = w.get('exercise')
                break
        if target_date and target_ex:
            if user_id not in temp_workout:
                temp_workout[user_id] = {}
            temp_workout[user_id]['edit_rpe_date'] = target_date
            temp_workout[user_id]['edit_rpe_ex'] = target_ex
            try:
                bot.edit_message_text(
                    f"📅 *{target_date}* | 🏋️ *{target_ex}*\n\nВыбери новую оценку сложности:",
                    user_id, msg_id, parse_mode="Markdown", reply_markup=get_diffedit_keyboard())
            except Exception:
                pass
        else:
            bot.answer_callback_query(call.id, "❌ Запись не найдена")
    elif data.startswith("diffedit_"):
        new_diff = data.split("_")[1]
        target_date = temp_workout.get(user_id, {}).get('edit_rpe_date')
        target_ex = temp_workout.get(user_id, {}).get('edit_rpe_ex')
        if target_date and target_ex and user_id in gym_db:
            updated = 0
            for w in gym_db[user_id]:
                if w.get('date') == target_date and w.get('exercise') == target_ex:
                    # Обновляем оба поля для совместимости с ботом и Web App
                    w['diff'] = new_diff
                    w['rpe'] = new_diff
                    updated += 1
            save_db()
            try:
                bot.edit_message_text(
                    f"✅ Оценка изменена на *{new_diff}*! Обновлено подходов: {updated}",
                    user_id, msg_id, parse_mode="Markdown", reply_markup=get_edit_main_keyboard())
            except Exception:
                pass
        else:
            bot.answer_callback_query(call.id, "❌ Ошибка: не найдена запись для изменения")
    elif data in ("date_today", "date_yesterday"):
        dt = datetime.now()
        if data == "date_yesterday":
            dt -= timedelta(days=1)
        d_str, day_str = get_date_and_day(dt)
        temp_workout[user_id] = {"date": d_str, "day": day_str}
        ex_kbd = get_exercise_keyboard(user_id)
        try:
            bot.edit_message_text(
                f"\u2705 Дата: *{d_str} ({day_str})*\n\nВыбери упражнение:",
                user_id, msg_id, parse_mode="Markdown", reply_markup=ex_kbd)
        except Exception as e:
            print(f"[WARN] edit_message_text date: {e}")
            bot.send_message(
                user_id,
                f"\u2705 Дата: *{d_str} ({day_str})*\n\nВыбери упражнение:",
                parse_mode="Markdown", reply_markup=ex_kbd)
    elif data == "date_custom":
        user_states[user_id] = "waiting_custom_date"
        try:
            bot.edit_message_text("\u270d\ufe0f Напиши дату в формате ДД.ММ.ГГГГ:", user_id, msg_id)
        except Exception as e:
            print(f"[WARN] edit_message_text date_custom: {e}")
            bot.send_message(user_id, "\u270d\ufe0f Напиши дату в формате ДД.ММ.ГГГГ:")
    elif data == "ex_custom_new":
        if user_id not in temp_workout or "date" not in temp_workout.get(user_id, {}):
            dt = datetime.now()
            d_str, day_str = get_date_and_day(dt)
            temp_workout[user_id] = {"date": d_str, "day": day_str}
        user_states[user_id] = "waiting_custom_exercise"
        try:
            bot.edit_message_text(
                "✍️ *Напиши название своего упражнения:*\n_(Например: Подтягивания, Бицепс)_",
                user_id, msg_id, parse_mode="Markdown")
        except Exception as e:
            print(f"[WARN] edit_message_text ex_custom_new: {e}")
            bot.send_message(user_id, "✍️ *Напиши название своего упражнения:*\n_(Например: Подтягивания, Бицепс)_", parse_mode="Markdown")
    elif data.startswith("ex_") and data != "ex_custom_new":
        if user_id not in temp_workout or "date" not in temp_workout.get(user_id, {}):
            dt = datetime.now()
            d_str, day_str = get_date_and_day(dt)
            temp_workout[user_id] = {"date": d_str, "day": day_str}
        exercise = data[3:]
        temp_workout[user_id]["exercise"] = exercise
        temp_workout[user_id]["sets"] = []
        temp_workout[user_id]["current_weight"] = 0
        user_states[user_id] = "waiting_weight"
        try:
            bot.edit_message_text(
                f"💪 Упражнение: *{exercise}*\n\nВведи *рабочий вес* 1-го подхода (кг):",
                user_id, msg_id, parse_mode="Markdown")
        except Exception as e:
            print(f"[WARN] edit_message_text ex_select: {e}")
            bot.send_message(
                user_id,
                f"💪 Упражнение: *{exercise}*\n\nВведи *рабочий вес* 1-го подхода (кг):",
                parse_mode="Markdown")
    elif data == "nextset_same":
        if user_id in temp_workout:
            user_states[user_id] = "waiting_reps"
            wt = temp_workout[user_id]['current_weight']
            next_set_num = len(temp_workout[user_id]['sets']) + 1
            next_txt = f"⏳ *{next_set_num}-й подход* | Вес: *{wt} кг*\n\nПовторения?"
            try:
                bot.edit_message_text(next_txt, user_id, msg_id, parse_mode="Markdown")
            except Exception as e:
                print(f"[WARN] edit_message_text nextset: {e}")
                bot.send_message(user_id, next_txt, parse_mode="Markdown")
    elif data == "edit_last_set":
        if user_id in temp_workout and temp_workout[user_id].get('sets'):
            deleted = temp_workout[user_id]['sets'].pop()
            user_states[user_id] = "waiting_weight"
            next_num = len(temp_workout[user_id]['sets']) + 1
            del_txt = (
                f"🗑 Удален ({deleted['weight']} кг × {format_reps_clean(deleted)})\n\n"
                f"Записываем *{next_num}-й подход*. Введи правильный *вес*:"
            )
            try:
                bot.edit_message_text(del_txt, user_id, msg_id, parse_mode="Markdown")
            except Exception as e:
                print(f"[WARN] edit_message_text edit_last_set: {e}")
                bot.send_message(user_id, del_txt, parse_mode="Markdown")
    elif data == "finish_exercise":
        if user_id in temp_workout and temp_workout[user_id].get('sets'):
            user_states[user_id] = "waiting_diff"
            try:
                bot.edit_message_text("❗️ *Как оценишь упражнение в целом?*",
                    user_id, msg_id, parse_mode="Markdown", reply_markup=get_difficulty_keyboard())
            except Exception as e:
                print(f"[WARN] edit_message_text finish_exercise: {e}")
                bot.send_message(user_id, "❗️ *Как оценишь упражнение в целом?*",
                    parse_mode="Markdown", reply_markup=get_difficulty_keyboard())
        else:
            try:
                bot.delete_message(chat_id=user_id, message_id=msg_id)
            except Exception:
                pass
            bot.send_message(user_id, "Отмена.", reply_markup=get_main_menu())
            temp_workout.pop(user_id, None)
    elif data.startswith("diff_"):
        if user_id not in temp_workout or not temp_workout[user_id].get('sets'):
            bot.answer_callback_query(call.id, "Ошибка сохранения.")
            return
        difficulty = data[5:]
        workout = temp_workout[user_id]
        date_str = workout['date']
        day_str = workout['day']
        if user_id not in gym_db:
            gym_db[user_id] = []
        for i, s in enumerate(workout['sets'], start=1):
            entry = {
                "id": int(time.time() * 1000) + random.randint(1, 5000),
                "date": date_str, "day": day_str,
                "exercise": workout['exercise'],
                "set_num": i, "weight": s['weight'],
                "reps": s['reps'], "diff": difficulty, "rpe": difficulty
            }
            if s.get('rir') is not None:
                entry['rir'] = s['rir']
            gym_db[user_id].append(entry)
        save_db()

        # ── RPE Autoregulation Hook ──
        auto_msg = ""
        if user_id in programs_db and programs_db[user_id].get('days') and calculate_rpe_adjustment:
            prog = programs_db[user_id]
            actual_rpe = 7.5
            if difficulty == 'Легко': actual_rpe = 6.5
            elif difficulty == 'Средне': actual_rpe = 8.0
            elif difficulty == 'Тяжело': actual_rpe = 9.5
            
            ex_name = workout['exercise']
            prog_updated = False
            for day in prog.get('days', []):
                for pex in day.get('exercises', []):
                    if pex.get('name', '').lower() in ex_name.lower() or ex_name.lower() in pex.get('name', '').lower():
                        target_rpe = pex.get('target_rpe', 7.5)
                        delta_rpe = actual_rpe - target_rpe
                        weight = float(workout['sets'][-1].get('weight', 0))
                        adj = 0.0
                        if delta_rpe <= -2.0: adj = 5.0
                        elif delta_rpe <= 0.0: adj = 2.5
                        elif delta_rpe <= 1.0: adj = 0.0
                        else: adj = -round((weight * 0.05) / 2.5) * 2.5
                        
                        new_w = round((max(weight, pex.get('working_weight', weight)) + adj) / 2.5) * 2.5
                        if new_w > 0 and new_w != pex.get('working_weight'):
                            pex['working_weight'] = new_w
                            if get_warmup_ladder:
                                pex['warmup_ladder'] = get_warmup_ladder(pex.get('key', 'bench_press'), new_w)
                            prog_updated = True
                            auto_msg = f"\n🧬 *RPE Авторегуляция:* Вес в программе скорректирован до *{new_w} кг* ({'+' if adj>0 else ''}{adj} кг)."
            if prog_updated:
                save_program_db()

        session_tonnage = sum(float(s['weight']) * float(s['reps']) for s in workout['sets'])
        sets_text = ""
        for i, s in enumerate(workout['sets'], start=1):
            if s['weight'] > 0:
                e1rm = epley_1rm(float(s['weight']), float(s['reps']))
                sets_text += f"  {i}-й: {s['weight']} кг × {format_reps_clean(s)} _(1ПМ≈{e1rm} кг)_\n"
            else:
                sets_text += f"  {i}-й: _(без веса)_ × {format_reps_clean(s)}\n"
        tonnage_line = f"\n🏗 Тоннаж сессии: *{session_tonnage:.0f} кг*" if session_tonnage > 0 else ""
        success_msg = (
            f"✅ *СОХРАНЕНО!*\n"
            f"────────────────────\n"
            f"📅 {date_str} | ⚡️ Оценка: {difficulty}\n"
            f"🏋️ *{workout['exercise']}*\n\n"
            f"{sets_text}"
            f"{tonnage_line}"
            f"{auto_msg}"
        )
        try:
            bot.delete_message(chat_id=user_id, message_id=msg_id)
        except Exception:
            pass
        bot.send_message(user_id, success_msg, parse_mode="Markdown", reply_markup=get_main_menu())
        clear_user_state(user_id)
    elif data.startswith("del_"):
        set_id_str = data.split("_")[1]
        if user_id in gym_db:
            # Сравниваем через строку, чтобы покрыть и int, и float
            gym_db[user_id] = [w for w in gym_db[user_id] if str(w.get('id')) != set_id_str]
            save_db()
            markup = get_edit_sets_keyboard(user_id)
            try:
                if markup:
                    bot.edit_message_text("✅ Запись удалена. Выбери следующую:", user_id, msg_id, reply_markup=markup)
                else:
                    bot.edit_message_text("✅ База пуста.", user_id, msg_id, reply_markup=get_edit_main_keyboard())
            except Exception:
                pass
# === ХЕНДЛЕР ИИ-ТРЕНЕРА (GEMINI) ===
@bot.message_handler(commands=['ai', 'coach', 'gemini'])
def ai_coach_command(message):
    user_id = str(message.chat.id)
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1 and parts[1].strip():
        question = parts[1].strip()
        msg = bot.send_message(message.chat.id, "⏳ *Gemini AI анализирует ваши данные и научную базу...*", parse_mode="Markdown")
        reply = query_gemini_coach(user_id, question)
        try:
            bot.delete_message(message.chat.id, msg.message_id)
        except Exception:
            pass
        send_long_message(message.chat.id, reply, reply_markup=get_main_menu())
    else:
        bot.send_message(message.chat.id, "🤖 *ИИ-Тренер (Google Gemini)*\n\nЗадай любой вопрос о тренировках, восстановлении или питании:\nНапример: `/ai как прогрессировать в жиме?` или просто напиши вопрос сообщением!", parse_mode="Markdown", reply_markup=get_main_menu())

# === ХЕНДЛЕР ТЕКСТОВОГО ВВОДА (РОУТЕР) ===
@bot.message_handler(func=lambda message: True)
def handle_text_inputs(message):
    user_id = str(message.chat.id)
    if not message.text:
        state = user_states.get(user_id)
        if state:
            bot.send_message(message.chat.id, "⚠️ Введи *число* цифрами.", parse_mode="Markdown")
        return
    text = message.text.strip().replace(',', '.')
    state = user_states.get(user_id)
    if not state:
        msg = bot.send_message(message.chat.id, "⏳ *Gemini AI анализирует ваши данные и вопрос...*", parse_mode="Markdown")
        reply = query_gemini_coach(user_id, message.text.strip())
        try:
            bot.delete_message(message.chat.id, msg.message_id)
        except Exception:
            pass
        send_long_message(message.chat.id, reply, reply_markup=get_main_menu())
        return
    # НАСТРОЙКА ПРОФИЛЯ
    if state == "setup_name":
        profiles_db[user_id] = profiles_db.get(user_id, {})
        profiles_db[user_id]['name'] = message.text.strip()
        user_states[user_id] = "setup_height"
        bot.send_message(message.chat.id, "👍 Отлично!\n\n📏 Шаг 2/5: Твой *рост* (см)?\nНапример: `180`",
            parse_mode="Markdown")
        return
    if state == "setup_height":
        try:
            h = float(text)
            if h < 100 or h > 250: raise ValueError
            profiles_db[user_id]['height_cm'] = h
            user_states[user_id] = "setup_gender"
            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(InlineKeyboardButton("♂️ Мужской", callback_data="setup_gender_male"),
                       InlineKeyboardButton("♀️ Женский", callback_data="setup_gender_female"))
            bot.send_message(message.chat.id,
                f"✅ Рост {h} см.\n\n👤 Шаг 3/5: *Пол?*", parse_mode="Markdown", reply_markup=markup)
        except ValueError:
            bot.send_message(message.chat.id, "⚠️ Введи рост цифрами, например: `180`", parse_mode="Markdown")
        return
    if state == "setup_birth_year":
        try:
            year = int(float(text))
            if year < 1920 or year > 2010: raise ValueError
            profiles_db[user_id]['birth_year'] = year
            user_states[user_id] = "setup_goal"
            markup = InlineKeyboardMarkup(row_width=2)
            markup.add(
                InlineKeyboardButton("💪 Гипертрофия", callback_data="setup_goal_hypertrophy"),
                InlineKeyboardButton("🏋️ Сила", callback_data="setup_goal_strength"),
                InlineKeyboardButton("🔥 Похудение", callback_data="setup_goal_weight_loss"),
                InlineKeyboardButton("🏃 Выносливость", callback_data="setup_goal_endurance"),
            )
            bot.send_message(message.chat.id,
                f"✅ Год рождения {year}.\n\n🎯 Шаг 4/5: *Цель тренировок?*",
                parse_mode="Markdown", reply_markup=markup)
        except ValueError:
            bot.send_message(message.chat.id, "⚠️ Введи год рождения, например: `1995`", parse_mode="Markdown")
        return
    if state == "setup_days":
        try:
            days = int(float(text))
            if days < 1 or days > 7: raise ValueError
            profiles_db[user_id]['training_days_per_week'] = days
            save_profile_db()
            clear_user_state(user_id)
            name = profiles_db[user_id].get('name', 'Атлет')
            bot.send_message(message.chat.id,
                f"✅ *Профиль создан, {name}!*\n\n"
                f"Теперь у тебя персональный TDEE и умные рекомендации.\n"
                f"Смотри /profile — твоя карточка атлета.",
                parse_mode="Markdown", reply_markup=get_main_menu())
        except ValueError:
            bot.send_message(message.chat.id, "⚠️ Введи число от 1 до 7.", parse_mode="Markdown")
        return
    # ВВОД ЗАМЕРОВ ТЕЛА (пошаговый)
    measurement_states = {
        "waiting_measurements_chest": ("chest_cm", "waiting_measurements_waist", "Шаг 2/7: Обхват *талии* (см):"),
        "waiting_measurements_waist": ("waist_cm", "waiting_measurements_hips", "Шаг 3/7: Обхват *бёдер* (см):"),
        "waiting_measurements_hips":  ("hips_cm", "waiting_measurements_bicep", "Шаг 4/7: Обхват *бицепса левого* (см):"),
        "waiting_measurements_bicep": ("bicep_l_cm", "waiting_measurements_neck", "Шаг 5/7: Обхват *шеи* (см):"),
        "waiting_measurements_neck":  ("neck_cm", "waiting_measurements_thigh", "Шаг 6/7: Обхват *бедра левого* (см):"),
        "waiting_measurements_thigh": ("thigh_l_cm", "waiting_measurements_calf", "Шаг 7/7: Обхват *голени левой* (см):"),
        "waiting_measurements_calf":  ("calf_l_cm", "measurements_done", None),
    }
    if state in measurement_states:
        key, next_state, next_prompt = measurement_states[state]
        try:
            val = float(text)
            if val > 0:
                if user_id not in temp_workout:
                    temp_workout[user_id] = {'measurements': {}}
                if 'measurements' not in temp_workout[user_id]:
                    temp_workout[user_id]['measurements'] = {}
                temp_workout[user_id]['measurements'][key] = val
        except ValueError:
            pass
        if next_state == "measurements_done":
            measurements = temp_workout.get(user_id, {}).get('measurements', {})
            today_str = datetime.now().strftime("%d.%m.%Y")
            log_body_entry(user_id, today_str, measurements=measurements)
            clear_user_state(user_id)
            parts = []
            labels = {'chest_cm': 'Грудь', 'waist_cm': 'Талия', 'hips_cm': 'Бёдра',
                      'bicep_l_cm': 'Бицепс', 'neck_cm': 'Шея', 'thigh_l_cm': 'Бедро', 'calf_l_cm': 'Голень'}
            for k, lbl in labels.items():
                if measurements.get(k): parts.append(f"{lbl}: {measurements[k]} см")
            result_text = "✅ *Замеры сохранены!*\n\n" + "\n".join(parts)
            navy = calculate_navy_fat(user_id)
            if navy:
                fat_pct, fat_kg, lbm, cat = navy
                result_text += f"\n\n📊 *Navy Fat:* {fat_pct}% | ЛМТ: {lbm} кг | {cat}"
            bot.send_message(message.chat.id, result_text, parse_mode="Markdown", reply_markup=get_main_menu())
        else:
            user_states[user_id] = next_state
            bot.send_message(message.chat.id, f"📏 {next_prompt}\nИли `0` чтобы пропустить.", parse_mode="Markdown")
        return
    # СОН И ВОДА
    if state == "waiting_sleep_water":
        parts = text.split()
        try:
            water = float(parts[0]) if parts else 0.0
            sleep = float(parts[1]) if len(parts) > 1 else 0.0
            if water < 0 or water > 20: water = 0.0
            if sleep < 0 or sleep > 24: sleep = 0.0
            today_str = datetime.now().strftime("%d.%m.%Y")
            log_body_entry(user_id, today_str, water_l=water, sleep_hours=sleep)
            user_states.pop(user_id, None)
            msg_out = f"✅ Записано!\n💧 Вода: *{water} л.*\n😴 Сон: *{sleep} ч.*"
            recovery_note = ""
            if sleep >= 8: recovery_note = "\n🔋 Отличный сон! +8% к восстановлению ЦНС."
            elif sleep < 6 and sleep > 0: recovery_note = "\n⚠️ Недосып. -20% к восстановлению ЦНС."
            if water >= 2.5: recovery_note += "\n💧 Хорошая гидрация! +3% к готовности."
            bot.send_message(message.chat.id, msg_out + recovery_note, parse_mode="Markdown", reply_markup=get_main_menu())
        except (ValueError, IndexError):
            bot.send_message(message.chat.id,
                "⚠️ Формат: `литры часы`, например: `2.5 8`", parse_mode="Markdown")
        return
    # ВВОД ДАТЫ ВРУЧНУЮ
    if state == "waiting_custom_date":
        try:
            dt_obj = datetime.strptime(text.replace('.', '.'), "%d.%m.%Y")
            d_str, day_str = get_date_and_day(dt_obj)
            temp_workout[user_id] = {"date": d_str, "day": day_str}
            user_states.pop(user_id, None)
            bot.send_message(message.chat.id,
                f"✅ Дата *{d_str} ({day_str})* принята.\n\nВыбери упражнение:",
                parse_mode="Markdown", reply_markup=get_exercise_keyboard(user_id))
        except ValueError:
            bot.send_message(message.chat.id, "⚠️ Формат: *15.04.2026*", parse_mode="Markdown")
        return
    # СВОЁ УПРАЖНЕНИЕ
    if state == "waiting_custom_exercise":
        exercise = message.text.strip()
        if not exercise or len(exercise) < 2:
            bot.send_message(message.chat.id, "⚠️ Название слишком короткое.")
            return
        temp_workout[user_id]["exercise"] = exercise
        temp_workout[user_id]["sets"] = []
        temp_workout[user_id]["current_weight"] = 0
        user_states[user_id] = "waiting_weight"
        bot.send_message(message.chat.id,
            f"💪 Упражнение: *{exercise}*\n\nВведи *рабочий вес* 1-го подхода (кг):",
            parse_mode="Markdown")
        return
    # ВЕС ТЕЛА
    if state == "waiting_bodyweight":
        try:
            bw = float(text)
            if bw <= 0 or bw > 350: raise ValueError
            if bw == int(bw): bw = int(bw)
            today_str = datetime.now().strftime("%d.%m.%Y")
            log_body_entry(user_id, today_str, bodyweight=bw)
            user_states.pop(user_id, None)
            bw_list = [r for r in body_db.get(user_id, []) if r.get('bodyweight')]
            trend_str = ""
            if len(bw_list) >= 2:
                prev_bw = float(bw_list[-2]['bodyweight'])
                d = round(bw - prev_bw, 1)
                trend_str = f"\n📈 Изменение: {'+' if d >= 0 else ''}{d} кг"
            bot.send_message(message.chat.id,
                f"✅ *Вес тела сохранён!*\n⚖️ {bw} кг ({today_str}){trend_str}",
                parse_mode="Markdown", reply_markup=get_main_menu())
        except (ValueError, TypeError):
            bot.send_message(message.chat.id, "⚠️ Введи корректный вес (кг), например: *84.5*",
                parse_mode="Markdown")
        return
    # ПИТАНИЕ
    if state == "waiting_calories":
        parts = message.text.strip().split(None, 3)
        try:
            kcal = int(parts[0]) if parts else 0
            prot = int(parts[1]) if len(parts) > 1 else 0
            carbs = int(parts[2]) if len(parts) > 2 else 0
            note = parts[3] if len(parts) > 3 else ""
            today_str = datetime.now().strftime("%d.%m.%Y")
            log_body_entry(user_id, today_str, calories=kcal, protein_g=prot, carbs_portions=carbs, note=note)
            user_states.pop(user_id, None)
            recovery_bonus = ""
            if kcal >= 3000 or carbs >= 4:
                recovery_bonus = "\n🔋 *Профицит!* Восстановление +15%."
            elif kcal >= 2200 or carbs >= 2:
                recovery_bonus = "\n🔋 Умеренный профицит. +10%."
            if prot >= 150:
                recovery_bonus += "\n💪 Белок норма! +8% к восстановлению мышц."
            bot.send_message(message.chat.id,
                f"✅ *Питание сохранено!*\n🍽 {kcal} ккал | 🥩 Белок: {prot}г | 🍚 Рис: {carbs} порц.{recovery_bonus}",
                parse_mode="Markdown", reply_markup=get_main_menu())
        except (ValueError, TypeError, IndexError):
            bot.send_message(message.chat.id,
                "⚠️ Формат: `ккал белок_г порции_риса заметка`\nПример: `3000 180 4 обед ужин`",
                parse_mode="Markdown")
        return
    # РАЗМИНКА
    if state == "waiting_warmup_weight":
        try:
            target_w = float(text)
            if target_w <= 0 or target_w > 1000: raise ValueError
            user_states.pop(user_id, None)
            plan = get_warmup_plan(target_w)
            bot.send_message(message.chat.id, plan, parse_mode="Markdown", reply_markup=get_main_menu())
        except (ValueError, TypeError):
            bot.send_message(message.chat.id, "⚠️ Введи корректный вес, например: *100*", parse_mode="Markdown")
        return
    # НОВЫЙ ВЕС
    if state == "waiting_action":
        try:
            value = float(text)
            if value < 0: raise ValueError
            if value == int(value): value = int(value)
            temp_workout[user_id]["current_weight"] = value
            user_states[user_id] = "waiting_reps"
            next_set_num = len(temp_workout[user_id]['sets']) + 1
            wt_text = f"*{value} кг*" if value > 0 else "*(без веса)*"
            bot.send_message(message.chat.id,
                f"⏳ *{next_set_num}-й подход* | Новый вес: {wt_text}\n\nВведи *повторения*:\n_(Например: `8`, `4.5` или `5+1` для 5 повторов с 1 в запасе)_",
                parse_mode="Markdown")
        except (ValueError, TypeError):
            bot.send_message(message.chat.id,
                "⚠️ Нажми кнопку или введи *новый вес цифрами* (например: 80 или 0).",
                parse_mode="Markdown")
        return
    # ВЕС ОТЯГОЩЕНИЯ
    if state == "waiting_weight":
        try:
            value = float(text)
            if value < 0: raise ValueError
            if value == int(value): value = int(value)
            temp_workout[user_id]["current_weight"] = value
            user_states[user_id] = "waiting_reps"
            wt_text = f"*{value} кг*" if value > 0 else "*(без веса)*"
            bot.send_message(message.chat.id,
                f"👍 Вес {wt_text} принят.\nВведи *повторения*:\n_(Например: `8`, `4.5` или `5+1` для 5 повторов с 1 в запасе)_",
                parse_mode="Markdown")
        except (ValueError, TypeError):
            bot.send_message(message.chat.id,
                "⚠️ Введи число, например: *80* или *0*", parse_mode="Markdown")
        return

    # ПОВТОРЕНИЯ
    if state == "waiting_reps":
        try:
            clean_text = text.replace(',', '.').strip()
            rir_val = None
            if '+' in clean_text:
                parts = clean_text.split('+')
                reps_part = parts[0].strip()
                rir_part = parts[1].strip()
                reps_val = float(reps_part)
                rir_val = float(rir_part)
            else:
                reps_val = float(clean_text)
            
            if reps_val <= 0 or reps_val > 200:
                raise ValueError
            if rir_val is not None and (rir_val < 0 or rir_val > 50):
                raise ValueError
                
            if reps_val == int(reps_val):
                reps_val = int(reps_val)
            if rir_val is not None and rir_val == int(rir_val):
                rir_val = int(rir_val)
                
            weight = temp_workout[user_id]["current_weight"]
            set_entry = {"weight": weight, "reps": reps_val}
            if rir_val is not None:
                set_entry["rir"] = rir_val
            temp_workout[user_id]["sets"].append(set_entry)
            
            user_states[user_id] = "waiting_action"
            sets_text = ""
            for i, s in enumerate(temp_workout[user_id]["sets"], start=1):
                e1rm = epley_1rm(float(s['weight']), float(s['reps']))
                sets_text += f"{i}-й: {s['weight']} кг × {format_reps_clean(s)} _(1ПМ≈{e1rm} кг)_\n"
            has_sets = bool(temp_workout[user_id]["sets"])
            msg = (f"✅ *Подход записан!*\n\n"
                   f"🏋️ *{temp_workout[user_id]['exercise']}*\n"
                   f"{sets_text}\n"
                   f"👇 Напиши *новый вес* или нажми кнопку:")
            bot.send_message(message.chat.id, msg, parse_mode="Markdown", reply_markup=get_next_set_keyboard(has_sets))
        except (ValueError, TypeError):
            bot.send_message(message.chat.id,
                "⚠️ Введи количество повторений (например: *8* или *4.5*, или с запасом: *5+1*).", parse_mode="Markdown")
        return
    bot.send_message(message.chat.id, "Используй кнопки меню 👇", reply_markup=get_main_menu())



# === ТОЧКА ВХОДА ===
if __name__ == '__main__':
    print("╔══════════════════════════════════════════════╗")
    print("║   GYM BOT v13.0 — НАУЧНЫЙ КОМБАЙН           ║")
    print("║   Recovery v3.0 · Navy Fat · TDEE · PubMed  ║")
    print("║   Dashboard 2x2 · Plateau · Прогноз 1ПМ     ║")
    print("╚══════════════════════════════════════════════╝")
    
    try:
        bot.set_chat_menu_button(
            menu_button=telebot.types.MenuButtonWebApp(
                type="web_app", 
                text="Mini App", 
                web_app=telebot.types.WebAppInfo(url="https://kabachok-hub.github.io/tg-web-app/")
            )
        )
        print("[+] Кнопка Menu Button (Web App) успешно установлена!")
    except Exception as e:
        print(f"[-] Не удалось установить Menu Button: {e}")

    bot.infinity_polling(timeout=60, long_polling_timeout=60)