# api_server.py — Flask API для Gym Mini App
# Запускать на PythonAnywhere как отдельное веб-приложение
# Порт: 5000 (или настрой через PythonAnywhere Web tab)

from flask import Flask, request, jsonify
import json, os, threading, hashlib, hmac, time

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

def _get_path(filename):
    cur_dir_p = os.path.abspath(os.path.join(os.path.dirname(__file__), filename))
    if os.path.exists(cur_dir_p):
        return cur_dir_p
    parent_p = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', filename))
    if os.path.exists(parent_p):
        return parent_p
    home_p = os.path.expanduser(f'~/{filename}')
    if os.path.exists(home_p):
        return home_p
    return cur_dir_p

DB_FILE      = _get_path('gym_database.json')
BODY_FILE    = _get_path('body_database.json')
PROFILE_FILE = _get_path('profiles_database.json')
PROGRAM_FILE = _get_path('programs_database.json')
BOT_TOKEN    = '8793508863:AAGt5pqrfPY3tmA4XhleEeOcJUstPQJp9aM'

_lock = threading.Lock()

# ── CORS — разрешаем GitHub Pages ──
@app.after_request
def cors(resp):
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    return resp

@app.route('/api/data', methods=['GET', 'OPTIONS'])
def get_data():
    if request.method == 'OPTIONS':
        return '', 204
    uid = request.args.get('uid')
    if not uid:
        return jsonify({'error': 'no uid'}), 400

    result = {'workouts': [], 'profile': {}, 'body': [], 'program': None}

    # Загружаем тренировки
    if os.path.exists(DB_FILE):
        with _lock:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                db = json.load(f)
        result['workouts'] = db.get(str(uid), [])

    # Загружаем профиль и историю AI
    if os.path.exists(PROFILE_FILE):
        try:
            with open(PROFILE_FILE, 'r', encoding='utf-8') as f:
                pdb = json.load(f)
            u_prof = pdb.get(str(uid), {})
            if isinstance(u_prof, dict):
                result['profile'] = u_prof.get('profile', u_prof)
                result['ai_chat_history'] = u_prof.get('ai_chat_history', [])
                result['gemini_key'] = u_prof.get('gemini_key', '')
        except Exception:
            pass

    # Загружаем программу тренировок
    if os.path.exists(PROGRAM_FILE):
        with open(PROGRAM_FILE, 'r', encoding='utf-8') as f:
            prg_db = json.load(f)
        result['program'] = prg_db.get(str(uid), None)

    # Загружаем данные тела
    if os.path.exists(BODY_FILE):
        with open(BODY_FILE, 'r', encoding='utf-8') as f:
            bdb = json.load(f)
        if isinstance(bdb, dict):
            user_body = bdb.get(str(uid), [])
            if isinstance(user_body, dict):
                result['body'] = user_body.get('entries', [])
            else:
                result['body'] = user_body if isinstance(user_body, list) else []
        else:
            result['body'] = []

    return jsonify(result)


@app.route('/api/save', methods=['POST', 'OPTIONS'])
def save_data():
    if request.method == 'OPTIONS':
        return '', 204
    body = request.get_json(silent=True)
    if not body:
        return jsonify({'error': 'no body'}), 400
    uid = str(body.get('uid'))
    data_payload = body.get('data', {})
    if not uid:
        return jsonify({'error': 'bad uid'}), 400

    new_workouts = data_payload.get('workouts', []) if isinstance(data_payload, dict) else []
    new_program = data_payload.get('program') if isinstance(data_payload, dict) else None
    new_body = data_payload.get('body') if isinstance(data_payload, dict) else None

    with _lock:
        # Сохранение тренировок
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                db = json.load(f)
        else:
            db = {}
        if uid not in db:
            db[uid] = []
            
        deleted_ids = {str(i) for i in body.get('deleted_ids', [])}
        if deleted_ids:
            db[uid] = [w for w in db[uid] if str(w.get('id')) not in deleted_ids]
            
        current_map = {str(w.get('id')): w for w in db[uid]}
        added = 0
        for w in new_workouts:
            wid = str(w.get('id'))
            if wid in deleted_ids:
                continue
            if wid in current_map:
                current_map[wid].update(w)
            else:
                current_map[wid] = w
                added += 1
        db[uid] = list(current_map.values())
                
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, ensure_ascii=False, indent=2)

        # Сохранение программы тренировок
        if new_program is not None:
            if os.path.exists(PROGRAM_FILE):
                try:
                    with open(PROGRAM_FILE, 'r', encoding='utf-8') as f:
                        prg_db = json.load(f)
                except Exception:
                    prg_db = {}
            else:
                prg_db = {}
            prg_db[uid] = new_program
            with open(PROGRAM_FILE, 'w', encoding='utf-8') as f:
                json.dump(prg_db, f, ensure_ascii=False, indent=2)

        # Сохранение данных тела
        if new_body is not None and isinstance(new_body, list):
            if os.path.exists(BODY_FILE):
                try:
                    with open(BODY_FILE, 'r', encoding='utf-8') as f:
                        bdb = json.load(f)
                except Exception:
                    bdb = {}
            else:
                bdb = {}
            bdb[uid] = new_body
            with open(BODY_FILE, 'w', encoding='utf-8') as f:
                json.dump(bdb, f, ensure_ascii=False, indent=2)

        # Сохранение профиля и истории AI чата
        new_profile = data_payload.get('profile', {}) if isinstance(data_payload, dict) else {}
        ai_chat_history = data_payload.get('ai_chat_history', []) if isinstance(data_payload, dict) else []
        gemini_key = data_payload.get('gemini_key', '') if isinstance(data_payload, dict) else ''
        
        if os.path.exists(PROFILE_FILE):
            try:
                with open(PROFILE_FILE, 'r', encoding='utf-8') as f:
                    pdb = json.load(f)
            except Exception:
                pdb = {}
        else:
            pdb = {}
            
        if uid not in pdb:
            pdb[uid] = {}
        if isinstance(pdb[uid], dict):
            if new_profile:
                pdb[uid]['profile'] = new_profile
            if ai_chat_history:
                pdb[uid]['ai_chat_history'] = ai_chat_history
            if gemini_key:
                pdb[uid]['gemini_key'] = gemini_key
        with open(PROFILE_FILE, 'w', encoding='utf-8') as f:
            json.dump(pdb, f, ensure_ascii=False, indent=2)

    return jsonify({'ok': True, 'added': added})


@app.route('/api/ping', methods=['GET'])
def ping():
    return jsonify({'status': 'ok', 'time': int(time.time())})


@app.route('/api/ai_chat', methods=['POST', 'OPTIONS'])
def ai_chat():
    if request.method == 'OPTIONS':
        return '', 204
    payload = request.get_json(silent=True) or {}
    key = payload.get('key', '').strip()
    contents = payload.get('contents', [])
    system_instruction = payload.get('systemInstruction')
    
    if not key:
        return jsonify({'error': {'message': 'No API key provided'}}), 400
        
    models_to_try = [
        'gemini-3.5-flash-lite',
        'gemini-3.6-flash',
        'gemini-2.5-flash',
        'gemini-3.1-pro-preview',
        'gemini-flash-latest'
    ]
    
    import urllib.request
    last_err = ''
    for m in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key}"
        body_data = {"contents": contents}
        if system_instruction:
            body_data["systemInstruction"] = system_instruction
            
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(body_data).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            res = urllib.request.urlopen(req, timeout=20)
            res_json = json.loads(res.read().decode('utf-8'))
            if 'candidates' in res_json and res_json['candidates']:
                return jsonify(res_json)
        except urllib.error.HTTPError as e:
            err_b = e.read().decode('utf-8', errors='replace')
            try:
                err_j = json.loads(err_b)
                if e.code == 400 and 'API_KEY_INVALID' in err_b:
                    return jsonify(err_j), 400
            except Exception:
                pass
            last_err = err_b
            continue
        except Exception as e:
            last_err = str(e)
            continue
            
    return jsonify({'error': {'message': last_err or 'Failed to query Gemini API'}}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
