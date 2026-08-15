// GYM MINI APP — app.js
const tg = window.Telegram && window.Telegram.WebApp;
if (tg) { tg.ready(); tg.expand(); }

const API = 'https://kABACh0k.pythonanywhere.com/api'; // замени на URL своего сервера
let DB = { workouts: [], profile: {}, body: [], program: null };
let currentTab = 'dashboard';
let diaryDays = 7; // Сохраняем текущий фильтр дневника
let workout = { exercise: '', date: '', sets: [], rpe: 'Легко', weight: 80, reps: 8 };

// ── Helpers ──
const $ = id => document.getElementById(id);
function parseReps(str) {
  str = String(str || '').replace(',', '.').trim();
  let reps = 0;
  let rir = null;
  if (str.includes('+')) {
    const parts = str.split('+');
    reps = parseFloat(parts[0]) || 0;
    rir = parseFloat(parts[1]) || null;
  } else {
    reps = parseFloat(str) || 0;
  }
  return { reps, rir };
}
function formatRepsClean(s) {
  let reps = 0;
  let rir = null;
  if (typeof s === 'object' && s !== null) {
    reps = parseFloat(s.reps) || 0;
    rir = s.rir !== undefined && s.rir !== null ? parseFloat(s.rir) : null;
  } else {
    const parsed = parseReps(s);
    reps = parsed.reps;
    rir = parsed.rir;
  }
  let repsStr = reps % 1 === 0 ? String(reps) : String(reps);
  if (rir !== null) {
    let rirStr = rir % 1 === 0 ? String(rir) : String(rir);
    return `${repsStr} (+${rirStr} в зап.)`;
  }
  return repsStr;
}
const epley = (w, r) => {
  const parsed = parseReps(r);
  const reps = parsed.reps;
  if (reps <= 0) return 0;
  return reps === 1 ? w : Math.round(w * (1 + reps / 30) * 10) / 10;
};
const parseDate = s => { if (!s) return null; const [d, m, y] = s.split('.'); return new Date(+y, +m - 1, +d); };
const fmtDate = d => `${String(d.getDate()).padStart(2, '0')}.${String(d.getMonth() + 1).padStart(2, '0')}.${d.getFullYear()}`;

function showToast(msg) {
  const t = $('toast'); t.textContent = msg; t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}

function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  $('tab-' + name).classList.add('active');
  document.querySelector(`[data-tab="${name}"]`).classList.add('active');
  currentTab = name;
  if (name === 'dashboard') renderDashboard();
  else if (name === 'program') renderProgramTab();
  else if (name === 'diary') renderDiary(diaryDays);
  else if (name === 'analytics') renderAnalytics();
  else if (name === 'profile') renderProfile();
}

// ── Load Data ──
async function loadData() {
  const uid = tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.id;
  if (!uid) {
    // Demo mode — load from localStorage
    const saved = localStorage.getItem('gym_db');
    if (saved) DB = JSON.parse(saved);
    initUI(); return;
  }
  
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 2500);

  try {
    const r = await fetch(`${API}/data?uid=${uid}`, { signal: controller.signal });
    clearTimeout(timeoutId);
    DB = await r.json();
  } catch (e) {
    clearTimeout(timeoutId);
    console.warn("API request failed or timed out. Falling back to localStorage.", e);
    const saved = localStorage.getItem('gym_db');
    if (saved) DB = JSON.parse(saved);
  }
  initUI();
}

let deletedIds = [];

async function saveData() {
  localStorage.setItem('gym_db', JSON.stringify(DB));
  const uid = tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.id;
  if (!uid) return;
  try {
    await fetch(`${API}/save`, { 
      method: 'POST', 
      headers: { 'Content-Type': 'application/json' }, 
      body: JSON.stringify({ uid, data: DB, deleted_ids: deletedIds }) 
    });
    deletedIds = []; // Очищаем после успешного сохранения
  } catch (e) { }
}

// ── Init ──
function initUI() {
  const user = tg && tg.initDataUnsafe && tg.initDataUnsafe.user;
  $('greeting').textContent = `💪 Привет, ${user && user.first_name ? user.first_name : 'Атлет'}!`;
  $('today-date').textContent = new Date().toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' });
  $('avatar-letter').textContent = (user && user.first_name ? user.first_name : 'A')[0].toUpperCase();
  renderDashboard();
  renderExerciseChips();
  renderQuickWeights();
  setupSVGGradient();
}

function setupSVGGradient() {
  const svg = document.querySelector('.ring');
  const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
  defs.innerHTML = `<linearGradient id="grad" x1="0%" y1="0%" x2="100%" y2="0%"><stop offset="0%" stop-color="#7c5cff"/><stop offset="100%" stop-color="#00e5c8"/></linearGradient>`;
  svg.prepend(defs);
}

// ── Dashboard ──
function renderDashboard() {
  const ws = DB.workouts || [];
  const days = [...new Set(ws.map(w => w.date))];
  const tonnage = ws.reduce((s, w) => s + (w.weight || 0) * (w.reps || 0), 0);
  const allE1rm = ws.filter(w => w.weight > 0).map(w => epley(w.weight, w.reps));
  const max1rm = allE1rm.length ? Math.max(...allE1rm) : 0;

  $('stat-sessions').textContent = days.length;
  $('stat-tonnage').textContent = tonnage > 1000 ? (tonnage / 1000).toFixed(1) + 'т' : Math.round(tonnage);
  $('stat-1rm').textContent = max1rm ? max1rm + 'кг' : '—';

  // Streak
  const weekSet = new Set(ws.map(w => { const d = parseDate(w.date); return d ? `${d.getFullYear()}-${d.getMonth()}-${Math.floor(d.getDate() / 7)}` : null; }).filter(Boolean));
  $('stat-streak').textContent = weekSet.size;
  $('streak-num').textContent = weekSet.size;

  // Program Banner on Dashboard
  const titleEl = $('dash-prog-title');
  const subEl = $('dash-prog-sub');
  if (hasValidProgram(DB.program)) {
    if (titleEl) titleEl.textContent = `${DB.program.split_name || 'Активный сплит'}`;
    if (subEl) {
      const gName = DB.program.goal === 'hypertrophy' ? 'Гипертрофия' : DB.program.goal === 'strength' ? 'Сила (SBD)' : DB.program.goal === 'recomp' ? 'Рекомпозиция' : 'Выносливость';
      subEl.textContent = `Неделя ${DB.program.current_week || 1} из 6 · ${gName} (${DB.program.days_per_week || 4} дн/нед)`;
    }
  } else {
    if (titleEl) titleEl.textContent = 'Составить тренировочный сплит';
    if (subEl) subEl.textContent = 'Авторегуляция RPE, разминки и 6-недельная матрица';
  }

  renderRecovery();
  renderLastWorkout();
  renderPRList();
  renderHealthTracker();
}

function renderRecovery() {
  const ws = DB.workouts || [];
  const now = new Date();
  const cutoff7 = new Date(now - 7 * 24 * 3600 * 1000);
  const w7d = ws.filter(w => { const d = parseDate(w.date); return d && d >= cutoff7; });

  // CNS/EIMD multipliers (from bot)
  const CNS_MULT  = { 'Жим лёжа': 1.0, 'Становая тяга': 1.4, 'Присед': 1.2 };
  const EIMD_MULT = { 'Жим лёжа': 1.0, 'Становая тяга': 1.35, 'Присед': 1.15 };
  const RPE_INT   = { 'Легко': 0.60, 'Средне': 0.80, 'Тяжело': 0.93 };

  const exercises = [...new Set(ws.map(w => w.exercise))].filter(Boolean);

  let totalCns = 0, totalMuscle = 0, count = 0;
  const pills = $('recovery-pills');
  pills.innerHTML = '';

  exercises.slice(0, 6).forEach(ex => {
    const exRecs = w7d.filter(w => w.exercise === ex);
    if (!exRecs.length) return;

    // find last session date
    const lastRec = exRecs.reduce((a, b) => (parseDate(a.date) > parseDate(b.date) ? a : b));
    const lastDate = parseDate(lastRec.date);
    if (!lastDate) return;

    const hoursPassed = (now - lastDate) / 3600000;

    // CNS base by hours
    let cnsBase = hoursPassed < 8 ? 0.10 : hoursPassed < 16 ? 0.30 :
                  hoursPassed < 24 ? 0.50 : hoursPassed < 36 ? 0.65 :
                  hoursPassed < 48 ? 0.78 : hoursPassed < 60 ? 0.88 :
                  hoursPassed < 72 ? 0.95 : 1.00;
    let muscleBase = hoursPassed < 12 ? 0.15 : hoursPassed < 24 ? 0.45 :
                     hoursPassed < 36 ? 0.65 : hoursPassed < 48 ? 0.80 :
                     hoursPassed < 60 ? 0.90 : hoursPassed < 72 ? 0.96 : 1.00;

    const rpeInt = RPE_INT[lastRec.rpe] || RPE_INT[lastRec.diff] || 0.80;
    const cnsM = CNS_MULT[ex] || 1.0;
    const eimdM = EIMD_MULT[ex] || 1.0;
    const penalty = (rpeInt - 0.60) * 0.50;
    const cnsExtra = (cnsM - 1.0) * 0.18;
    const eimdExtra = (eimdM - 1.0) * 0.12;

    const cnsScore = Math.max(0.05, Math.min(1.0, cnsBase - penalty - cnsExtra));
    const muscleScore = Math.max(0.05, Math.min(1.0, muscleBase - penalty - eimdExtra));
    const overallScore = Math.min(cnsScore, muscleScore);

    totalCns += cnsScore;
    totalMuscle += muscleScore;
    count++;

    const pct = Math.round(overallScore * 100);
    const cls = pct >= 70 ? 'green' : pct >= 40 ? 'yellow' : 'red';
    pills.innerHTML += `<span class="pill ${cls}" title="${ex}: ЦНС ${Math.round(cnsScore*100)}% Мыш ${Math.round(muscleScore*100)}%">${ex.split(' ')[0]} ${pct}%</span>`;
  });

  // Overall recovery
  const avgCns = count ? totalCns / count : 1.0;
  const avgMuscle = count ? totalMuscle / count : 1.0;
  const overall = Math.round(Math.min(avgCns, avgMuscle) * 100);

  $('recovery-pct').textContent = overall;
  const offset = 314 - (314 * overall / 100);
  $('recovery-circle').style.strokeDashoffset = offset;

  let cnsLabel = Math.round(avgCns * 100);
  let musLabel = Math.round(avgMuscle * 100);
  $('recovery-status').textContent = overall >= 90 ? `✅ Готов к рекордам! (ЦНС ${cnsLabel}% | Мышцы ${musLabel}%)` :
    overall >= 70 ? `🟡 Суперкомпенсация идёт (ЦНС ${cnsLabel}% | Мышцы ${musLabel}%)` :
    overall >= 45 ? `⚠️ Неполное восстановление (ЦНС ${cnsLabel}% | Мышцы ${musLabel}%)` :
    `🔴 Нужен отдых (ЦНС ${cnsLabel}% | Мышцы ${musLabel}%)`;
}

function renderLastWorkout() {
  const ws = DB.workouts || [];
  if (!ws.length) return;
  const sortedDates = [...new Set(ws.map(w => w.date))].sort((a, b) => parseDate(b) - parseDate(a));
  const lastDate = sortedDates[0];
  const last = ws.filter(w => w.date === lastDate);
  const exs = [...new Set(last.map(w => w.exercise))];
  const card = $('last-workout-card');
  card.innerHTML = `<div style="font-size:.75rem;color:var(--text2);margin-bottom:8px">📅 ${lastDate}</div>`;
  exs.forEach(ex => {
    const sets = last.filter(w => w.exercise === ex);
    const tonnage = sets.reduce((s, w) => s + (w.weight || 0) * (w.reps || 0), 0);
    card.innerHTML += `<div class="workout-row"><span class="workout-ex">${ex}</span><span class="workout-detail">${sets.length} подх · ${Math.round(tonnage)} кг</span></div>`;
  });
}

function renderPRList() {
  const ws = DB.workouts || [];
  const records = {};
  ws.filter(w => w.weight > 0).forEach(w => {
    const e = epley(w.weight, w.reps);
    if (!records[w.exercise] || e > records[w.exercise].e1rm) records[w.exercise] = { e1rm: e, weight: w.weight, reps: w.reps, rir: w.rir };
  });
  const medals = ['🥇', '🥈', '🥉'];
  const list = $('pr-list');
  list.innerHTML = '';
  Object.entries(records).slice(0, 5).forEach(([ex, r], i) => {
    list.innerHTML += `<div class="pr-item"><span class="pr-medal">${medals[i] || '🏅'}</span><div class="pr-info"><div class="pr-ex">${ex}</div><div class="pr-val">${r.weight}кг × ${formatRepsClean(r)}</div></div><span class="pr-num">${r.e1rm} кг</span></div>`;
  });
  if (!list.innerHTML) list.innerHTML = '<p class="empty-state">Нет рекордов</p>';
}

// ── Workout Tab ──
function renderExerciseChips() {
  const ws = DB.workouts || [];
  const defaults = ['Жим лёжа', 'Становая тяга', 'Присед'];
  const custom = [...new Set(ws.map(w => w.exercise))].filter(e => !defaults.includes(e)).slice(0, 5);
  const all = [...defaults, ...custom];
  const chips = $('exercise-chips');
  const achips = $('analytics-chips');
  chips.innerHTML = '';
  achips && (achips.innerHTML = '');
  all.forEach(ex => {
    chips.innerHTML += `<button class="ex-chip" onclick="selectExercise('${ex}', this)">${ex}</button>`;
    achips && (achips.innerHTML += `<button class="ex-chip" onclick="selectAnalyticsEx('${ex}', this)">${ex}</button>`);
  });
}

function selectExercise(name, el) {
  document.querySelectorAll('#exercise-chips .ex-chip').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
  workout.exercise = name;
  $('selected-ex-name').textContent = name;
  $('selected-exercise-display').style.display = 'flex';
  $('custom-exercise-input').value = '';
  updateE1RM();
}

function selectCustomExercise() {
  const v = $('custom-exercise-input').value.trim();
  if (!v) return;
  workout.exercise = v;
  $('selected-ex-name').textContent = v;
  $('selected-exercise-display').style.display = 'flex';
  document.querySelectorAll('#exercise-chips .ex-chip').forEach(c => c.classList.remove('active'));
}

function clearExercise() {
  workout.exercise = '';
  $('selected-exercise-display').style.display = 'none';
}

function selectDate(type, el) {
  document.querySelectorAll('.date-chips .chip').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
  if (type === 'today') { workout.date = fmtDate(new Date()); $('custom-date-input').style.display = 'none'; }
  else if (type === 'yesterday') { const d = new Date(); d.setDate(d.getDate() - 1); workout.date = fmtDate(d); $('custom-date-input').style.display = 'none'; }
  else { $('custom-date-input').style.display = 'block'; }
}

function setCustomDate() {
  const v = $('custom-date-input').value;
  if (!v) return;
  const [y, m, d] = v.split('-');
  workout.date = `${d}.${m}.${y}`;
}

function renderQuickWeights() {
  const ws = DB.workouts || [];
  const hist = [...new Set(ws.map(w => w.weight).filter(w => w > 0))].sort((a, b) => a - b).slice(-6);
  if (!hist.length) return;
  const qw = $('quick-weights');
  qw.innerHTML = '';
  hist.forEach(w => { qw.innerHTML += `<button class="chip" onclick="setWeight(${w})">${w}</button>`; });
}

function updateWeight(v) {
  workout.weight = +v;
  $('weight-input').value = +v === 0 ? '0' : v;
  updateE1RM();
}

function adjustWeight(delta) {
  const nw = Math.max(0, Math.round((workout.weight + delta) * 10) / 10);
  workout.weight = nw;
  $('weight-input').value = nw;
  $('weight-slider').value = nw;
  updateE1RM();
}

function setWeight(v) {
  workout.weight = v;
  $('weight-input').value = v;
  $('weight-slider').value = v;
  updateE1RM();
}

function updateWeightFromInput(v) {
  const num = parseFloat(v);
  workout.weight = isNaN(num) ? 0 : num;
  $('weight-slider').value = workout.weight;
  updateE1RM();
}

function toggleNoWeight() {
  const cb = $('no-weight-cb');
  if (cb.checked) { 
    workout.weight = 0; 
    $('weight-input').value = '0'; 
    $('weight-input').disabled = true; 
    $('weight-slider').disabled = true; 
  } else { 
    workout.weight = 80; 
    $('weight-input').value = '80'; 
    $('weight-input').disabled = false; 
    $('weight-slider').disabled = false; 
  }
  updateE1RM();
}

function adjustReps(delta) {
  const parsed = parseReps(workout.reps);
  let newReps = Math.max(0.5, Math.min(50, parsed.reps + delta));
  if (newReps % 1 === 0) newReps = parseInt(newReps);
  if (parsed.rir !== null) {
    workout.reps = `${newReps}+${parsed.rir}`;
  } else {
    workout.reps = String(newReps);
  }
  $('reps-input').value = workout.reps;
  updateE1RM();
}

function setReps(v) {
  workout.reps = String(v);
  $('reps-input').value = v;
  updateE1RM();
}

function updateRepsFromInput(v) {
  workout.reps = v;
  updateE1RM();
}

function selectRPE(v, el) {
  document.querySelectorAll('.rpe-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  workout.rpe = v;
}

let currentRIR = 0;
function selectRIR(val, el) {
  document.querySelectorAll('.rir-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  currentRIR = parseInt(val);
}
function resetRIR() {
  currentRIR = 0;
  document.querySelectorAll('.rir-btn').forEach(b => b.classList.remove('active'));
  const btn0 = $('rir-0');
  if (btn0) btn0.classList.add('active');
}

function updateE1RM() {
  const parsed = parseReps(workout.reps);
  const e = workout.weight > 0 && parsed.reps > 0 ? epley(workout.weight, workout.reps) : null;
  $('e1rm-val').textContent = e ? e + ' кг' : '—';
}

function getDateFromUI() {
  // Считываем дату напрямую из UI, чтобы избежать рассинхрона между DOM и JS-переменной
  const chips = document.querySelectorAll('.date-chips .chip');
  let activeIdx = 0;
  chips.forEach((c, i) => { if (c.classList.contains('active')) activeIdx = i; });
  if (activeIdx === 0) {
    // "Сегодня"
    return fmtDate(new Date());
  } else if (activeIdx === 1) {
    // "Вчера"
    const d = new Date(); d.setDate(d.getDate() - 1); return fmtDate(d);
  } else {
    // "Другая" — берём из input
    const v = $('custom-date-input').value;
    if (v) {
      const [y, m, d] = v.split('-');
      return `${d}.${m}.${y}`;
    }
    return fmtDate(new Date()); // фоллбэк
  }
}

function addSet() {
  if (!workout.exercise) { showToast('❌ Выбери упражнение!'); return; }
  // Считываем дату напрямую из UI-чипов (не из JS-переменной!)
  workout.date = getDateFromUI();
  // Считываем текущий RPE прямо из активной кнопки в DOM
  const activeRpeBtn = document.querySelector('.rpe-btn.active');
  let currentRpe = workout.rpe;
  if (activeRpeBtn) {
    if (activeRpeBtn.classList.contains('green')) currentRpe = 'Легко';
    else if (activeRpeBtn.classList.contains('yellow')) currentRpe = 'Средне';
    else if (activeRpeBtn.classList.contains('red')) currentRpe = 'Тяжело';
  }
  workout.rpe = currentRpe;
  
  // Считываем повторения прямо из поля ввода
  const repsVal = $('reps-input').value;
  const parsed = parseReps(repsVal);
  const set = { 
    exercise: workout.exercise, 
    date: workout.date, 
    weight: workout.weight, 
    reps: parsed.reps, 
    rpe: currentRpe, 
    diff: currentRpe, 
    set_num: workout.sets.length + 1 
  };
  
  // Если в текстовом вводе не указан '+', берем из RIR кнопок
  if (parsed.rir !== null) {
    set.rir = parsed.rir;
  } else if (currentRIR > 0) {
    set.rir = currentRIR;
  }
  
  workout.sets.push(set);
  renderSetsLog();
  $('save-btn').style.display = 'block';
  showToast(`✅ Подход ${workout.sets.length} добавлен`);
  
  // Сбрасываем RIR на дефолтный (Отказ)
  resetRIR();
}

function renderSetsLog() {
  const log = $('sets-log');
  if (!workout.sets.length) { log.innerHTML = '<p class="empty-state">Ещё нет подходов</p>'; return; }
  log.innerHTML = workout.sets.map((s, i) => {
    const repsClean = formatRepsClean(s);
    const e = s.weight > 0 ? `1ПМ≈${epley(s.weight, s.reps)}кг` : 'без веса';
    const wt = s.weight > 0 ? `${s.weight}кг × ${repsClean}` : `(без веса) × ${repsClean}`;
    return `<div class="set-item"><span class="set-num">${i + 1}-й подход</span><span class="set-data">${wt}</span><span class="set-1rm">${e}</span><button class="set-del" onclick="delSet(${i})">🗑</button></div>`;
  }).join('');
}

function delSet(i) {
  workout.sets.splice(i, 1);
  workout.sets.forEach((s, j) => s.set_num = j + 1);
  renderSetsLog();
  if (!workout.sets.length) $('save-btn').style.display = 'none';
}

async function saveWorkout() {
  if (!workout.sets.length) { showToast('Нет подходов!'); return; }
  if (!DB.workouts) DB.workouts = [];
  // Assign unique IDs BEFORE pushing to avoid duplicate float IDs
  const ts = Date.now();
  workout.sets.forEach((s, i) => { s.id = String(ts + i); DB.workouts.push(s); });
  
  // Autoregulation Hook: If active program exists, adjust weights
  if (DB.program && DB.program.days) {
    let progUpdated = false;
    workout.sets.forEach(s => {
      const exName = s.exercise;
      const weight = parseFloat(s.weight) || 0;
      let actualRpe = 7.5;
      if (s.rpe === 'Легко') actualRpe = 6.5;
      else if (s.rpe === 'Средне') actualRpe = 8.0;
      else if (s.rpe === 'Тяжело') actualRpe = 9.5;
      if (s.rir !== undefined && s.rir !== null) {
        actualRpe = Math.max(6.0, Math.min(10.0, 10.0 - parseFloat(s.rir)));
      }

      DB.program.days.forEach(day => {
        day.exercises.forEach(pex => {
          if (pex.name.toLowerCase().includes(exName.toLowerCase()) || exName.toLowerCase().includes(pex.name.toLowerCase())) {
            const targetRpe = pex.target_rpe || 7.5;
            const deltaRpe = actualRpe - targetRpe;
            let adj = 0;
            if (deltaRpe <= -2.0) adj = 5.0;
            else if (deltaRpe <= 0.0) adj = 2.5;
            else if (deltaRpe <= 1.0) adj = 0.0;
            else adj = -Math.round(weight * 0.05 / 2.5) * 2.5;

            const newW = Math.round((Math.max(weight, pex.working_weight || weight) + adj) / 2.5) * 2.5;
            if (newW > 0 && newW !== pex.working_weight) {
              pex.working_weight = newW;
              pex.warmup_ladder = getWarmupLadder(pex.key || 'bench_press', newW);
              progUpdated = true;
            }
          }
        });
      });
    });
    if (progUpdated) {
      showToast('🧬 RPE Авторегуляция обновила программу!');
    }
  }

  await saveData();
  showToast('✅ Тренировка сохранена!');
  // Сброс состояния: упражнение и подходы сбрасываются, дата ОСТАЁТСЯ как есть
  const keepDate = getDateFromUI();
  workout = { exercise: '', date: keepDate, sets: [], rpe: 'Легко', weight: 80, reps: 8 };
  // Сбрасываем кнопки сложности в UI на "Легко"
  document.querySelectorAll('.rpe-btn').forEach(b => b.classList.remove('active'));
  const greenBtn = document.querySelector('.rpe-btn.green');
  if (greenBtn) greenBtn.classList.add('active');
  // Дата НЕ сбрасывается — чипы и input остаются как есть
  renderSetsLog();
  resetRIR();
  $('save-btn').style.display = 'none';
  $('selected-exercise-display').style.display = 'none';
  document.querySelectorAll('#exercise-chips .ex-chip').forEach(c => c.classList.remove('active'));
  renderExerciseChips();
  renderQuickWeights();
  renderDashboard();
}

// ── Diary ──
function filterDiary(days, el) {
  diaryDays = days; // Запоминаем выбранный фильтр
  document.querySelectorAll('.diary-filter .chip').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
  renderDiary(days);
}

function renderDiary(days) {
  const ws = DB.workouts || [];
  const cutoff = days > 0 ? new Date(Date.now() - days * 24 * 3600 * 1000) : new Date(0);
  const filtered = ws.filter(w => { const d = parseDate(w.date); return d && d >= cutoff; });
  // Group by date → exercise
  const byDate = {};
  filtered.forEach(w => {
    const d = w.date;
    if (!byDate[d]) byDate[d] = {};
    const ex = w.exercise || 'Неизвестно';
    if (!byDate[d][ex]) byDate[d][ex] = { sets: [], rpe: null };
    byDate[d][ex].sets.push(w);
    // Track hardest RPE for exercise — strict > to avoid last-set overwrite bug
    const rpeRank = { 'Тяжело': 3, 'Средне': 2, 'Средно': 2, 'Легко': 1 };
    const r = w.rpe || w.diff || 'Легко';
    if (byDate[d][ex].rpe === null || (rpeRank[r] || 0) > (rpeRank[byDate[d][ex].rpe] || 0)) byDate[d][ex].rpe = r;
  });
  // Compute all-time 1RM records
  const allRecords = {};
  ws.filter(w => w.weight > 0).forEach(w => {
    const e = epley(w.weight, w.reps);
    if (!allRecords[w.exercise] || e > allRecords[w.exercise]) allRecords[w.exercise] = e;
  });
  const list = $('diary-list');
  const dates = Object.keys(byDate).sort((a, b) => parseDate(b) - parseDate(a));
  if (!dates.length) { list.innerHTML = '<p class="empty-state">Нет тренировок за период</p>'; return; }
  list.innerHTML = dates.map(date => {
    const exs = byDate[date];
    const dayTonnage = Object.values(exs).flatMap(e => e.sets).reduce((s, w) => s + (w.weight || 0) * (w.reps || 0), 0);
    const numSets = Object.values(exs).reduce((s, e) => s + e.sets.length, 0);
    const dayRpeMax = Object.values(exs).reduce((max, e) => {
      const rk = { 'Тяжело': 3, 'Средне': 2, 'Средно': 2, 'Легко': 1 };
      return (rk[e.rpe] || 0) > (rk[max] || 0) ? e.rpe : max;
    }, 'Легко');
    const dayColor = dayRpeMax === 'Тяжело' ? '#ff4d6d' : dayRpeMax === 'Средне' ? '#ffd700' : '#00e5c8';
    // Get day of week from date
    const pd = parseDate(date);
    const dayNames = ['Вс','Пн','Вт','Ср','Чт','Пт','Сб'];
    const dayName = pd ? dayNames[pd.getDay()] : '';
    const exHtml = Object.entries(exs).map(([ex, exData]) => {
      const { sets, rpe } = exData;
      const exTonnage = sets.reduce((s, w) => s + (w.weight || 0) * (w.reps || 0), 0);
      const maxE1rm = sets.filter(w => w.weight > 0).reduce((m, w) => Math.max(m, epley(w.weight, w.reps)), 0);
      const isRecord = maxE1rm > 0 && allRecords[ex] && Math.abs(maxE1rm - allRecords[ex]) < 0.1;
      
      const rpeClass = rpe === 'Тяжело' ? 'rpe-badge-hard' : rpe === 'Средне' ? 'rpe-badge-medium' : 'rpe-badge-easy';
      const rpeText = rpe === 'Тяжело' ? '🔴 Тяжело' : rpe === 'Средне' ? '🟡 Средне' : '🟢 Легко';

      const recordHtml = isRecord ? `<span class="diary-ex-record-badge">🏆 Рекорд</span>` : '';
      let metaStr = '';
      if (exTonnage > 0) metaStr += `🏋️‍♂️ ${Math.round(exTonnage)} кг`;
      if (maxE1rm > 0) metaStr += (metaStr ? ' · ' : '') + `⚡ 1ПМ≈${maxE1rm}кг`;

      const badges = sets.map((s, idx) => {
        const repsClean = formatRepsClean(s);
        const wt = s.weight > 0 ? `${s.weight}кг×${repsClean}` : `BW×${repsClean}`;
        return `<div class="diary-set-pill">
          <span class="diary-set-pill-num">${idx + 1}</span>
          <span>${wt}</span>
          <span class="diary-set-pill-del" onclick="deleteHistorySet('${s.id}', event)" title="Удалить подход">&times;</span>
        </div>`;
      }).join('');

      return `<div class="diary-exercise">
        <div class="diary-ex-header">
          <div class="diary-ex-title-wrap">
            <span class="diary-ex-title">${ex}</span>
            <div class="diary-ex-meta-info">
              <span>${metaStr}</span>
              ${recordHtml}
            </div>
          </div>
          <span class="diary-ex-rpe-badge ${rpeClass}">${rpeText}</span>
        </div>
        <div class="diary-sets-grid">${badges}</div>
      </div>`;
    }).join('');

    return `<div class="diary-day glass">
      <div class="diary-day-header">
        <div class="diary-day-date-box">
          <span class="diary-day-weekday" style="background-color: ${dayColor}">${dayName}</span>
          <span class="diary-day-date">${date}</span>
        </div>
        <div class="diary-day-stats">
          <span class="diary-day-sets-count">${numSets} подходов</span>
          <span class="diary-day-tonnage-sum">${Math.round(dayTonnage)} кг</span>
        </div>
      </div>
      <div class="diary-exercises-list">
        ${exHtml}
      </div>
    </div>`;
  }).join('');
}

async function deleteHistorySet(id, event) {
  if (event) event.stopPropagation();
  if (!confirm('🗑 Удалить этот подход?')) return;
  deletedIds.push(String(id));
  DB.workouts = DB.workouts.filter(w => String(w.id) !== String(id));
  renderDiary(diaryDays); // Используем сохранённый фильтр
  await saveData();
  showToast('✅ Подход удалён');
}

// ── Analytics ──
function renderAnalytics() {
  renderVolumeChart();
  renderVolumeBreakdown();
  renderPlateauList();
  renderVolumeTrend();
  renderTop3Progress();
}

function selectAnalyticsEx(ex, el) {
  document.querySelectorAll('#analytics-chips .ex-chip').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
  $('chart-ex-label').textContent = ex;
  render1RMChart(ex);
}

function render1RMChart(ex) {
  if (!window.Chart) {
    $('chart-empty').textContent = '⚠️ График 1ПМ недоступен (ошибка сети/блокировка CDN)';
    $('chart-empty').style.display = 'block';
    return;
  }
  const ws = (DB.workouts || []).filter(w => w.exercise === ex && w.weight > 0);
  const byDate = {};
  ws.forEach(w => { const e = epley(w.weight, w.reps); if (!byDate[w.date] || e > byDate[w.date]) byDate[w.date] = e; });
  const dates = Object.keys(byDate).sort((a, b) => parseDate(a) - parseDate(b));
  if (dates.length < 2) { $('chart-empty').style.display = 'block'; return; }
  $('chart-empty').style.display = 'none';
  const ctx = $('chart-1rm').getContext('2d');
  if (window._chart1rm) window._chart1rm.destroy();
  window._chart1rm = new Chart(ctx, {
    type: 'line',
    data: { labels: dates.map(d => d.slice(0, 5)), datasets: [{ data: dates.map(d => byDate[d]), borderColor: '#7c5cff', backgroundColor: 'rgba(124,92,255,0.1)', tension: 0.4, fill: true, pointBackgroundColor: '#7c5cff', pointRadius: 4 }] },
    options: { plugins: { legend: { display: false } }, scales: { x: { ticks: { color: '#9090b0', font: { size: 10 } }, grid: { color: 'rgba(255,255,255,0.05)' } }, y: { ticks: { color: '#9090b0', font: { size: 10 } }, grid: { color: 'rgba(255,255,255,0.05)' } } } }
  });
}

function renderVolumeChart() {
  if (!window.Chart) return;
  const ws = DB.workouts || [];
  const byWeek = {};
  ws.forEach(w => { const d = parseDate(w.date); if (!d) return; const wk = `${d.getFullYear()}-W${Math.ceil(d.getDate() / 7) + d.getMonth() * 4}`; byWeek[wk] = (byWeek[wk] || 0) + (w.weight || 0) * (w.reps || 0); });
  const weeks = Object.keys(byWeek).sort().slice(-8);
  if (!weeks.length) return;
  const ctx = $('chart-volume').getContext('2d');
  if (window._chartVol) window._chartVol.destroy();
  window._chartVol = new Chart(ctx, {
    type: 'bar',
    data: { labels: weeks.map((_, i) => `Нед ${i + 1}`), datasets: [{ data: weeks.map(w => byWeek[w]), backgroundColor: 'rgba(0,229,200,0.7)', borderRadius: 6 }] },
    options: { plugins: { legend: { display: false } }, scales: { x: { ticks: { color: '#9090b0', font: { size: 10 } }, grid: { display: false } }, y: { ticks: { color: '#9090b0', font: { size: 10 } }, grid: { color: 'rgba(255,255,255,0.05)' } } } }
  });
}

function renderVolumeBreakdown() {
  const ws = DB.workouts || [];
  const vol = {};
  ws.forEach(w => { vol[w.exercise] = (vol[w.exercise] || 0) + (w.weight || 0) * (w.reps || 0); });
  const sorted = Object.entries(vol).sort((a, b) => b[1] - a[1]);
  const max = (sorted[0] && sorted[0][1]) || 1;
  const div = $('volume-breakdown');
  div.innerHTML = sorted.slice(0, 6).map(([ex, v]) => `<div class="breakdown-item"><span class="breakdown-label">${ex}</span><div class="breakdown-bar-wrap"><div class="breakdown-bar" style="width:${v / max * 100}%"></div></div><span class="breakdown-val">${Math.round(v / 1000)}т</span></div>`).join('');
}

function renderPlateauList() {
  const ws = DB.workouts || [];
  const exs = [...new Set(ws.map(w => w.exercise))];
  const div = $('plateau-list');
  div.innerHTML = '';
  exs.forEach(ex => {
    const recs = ws.filter(w => w.exercise === ex && w.weight > 0).sort((a, b) => parseDate(a.date) - parseDate(b.date));
    if (recs.length < 4) return;
    const e1rms = recs.map(w => epley(w.weight, w.reps));
    const half = Math.floor(e1rms.length / 2);
    const old = Math.max(...e1rms.slice(0, half));
    const cur = Math.max(...e1rms.slice(half));
    const isPlat = cur <= old * 1.02;
    div.innerHTML += `<div class="plateau-item ${isPlat ? 'warning' : 'ok'}"><div class="plateau-ex">${isPlat ? '⚠️' : '✅'} ${ex}</div><div class="plateau-detail">${isPlat ? 'Плато! Нет прогресса более 21 дня' : 'Прогресс есть — продолжай!'} (1ПМ: ${cur}кг)</div></div>`;
  });
  if (!div.innerHTML) div.innerHTML = '<p class="empty-state">Недостаточно данных</p>';
}

function renderVolumeTrend() {
  const ws = DB.workouts || [];
  const now = new Date();
  const w1Start = new Date(now - 7 * 86400000);
  const w2Start = new Date(now - 14 * 86400000);
  let tThis = 0, tPrev = 0, sThis = 0, sPrev = 0;
  ws.forEach(w => {
    const d = parseDate(w.date);
    if (!d) return;
    const t = (w.weight || 0) * (w.reps || 0);
    if (d >= w1Start) { tThis += t; sThis++; }
    else if (d >= w2Start) { tPrev += t; sPrev++; }
  });
  const div = $('volume-trend');
  if (!div) return;
  if (!sThis && !sPrev) { div.innerHTML = '<p class="empty-state">Недостаточно данных</p>'; return; }
  const trendPct = tPrev > 0 ? ((tThis - tPrev) / tPrev * 100).toFixed(1) : null;
  const arrow = trendPct === null ? '—' : trendPct > 0 ? `📈 +${trendPct}%` : `📉 ${trendPct}%`;
  const cls = trendPct === null ? '' : trendPct > 0 ? 'color:#00e5c8' : 'color:#ff6b6b';
  div.innerHTML = `
    <div class="hist-row"><span>📊 Эта неделя</span><span class="hist-val">${Math.round(tThis / 1000 * 10) / 10} т (${sThis} подх)</span></div>
    <div class="hist-row"><span>📅 Прошлая неделя</span><span class="hist-val">${Math.round(tPrev / 1000 * 10) / 10} т (${sPrev} подх)</span></div>
    <div class="hist-row"><span>📈 Тренд</span><span class="hist-val" style="${cls}">${arrow}</span></div>`;
}

function renderTop3Progress() {
  const ws = DB.workouts || [];
  const now = new Date();
  const cutoff30 = new Date(now - 30 * 86400000);
  const recent = ws.filter(w => { const d = parseDate(w.date); return d && d >= cutoff30; });
  const older  = ws.filter(w => { const d = parseDate(w.date); return d && d < cutoff30; });
  const exs = [...new Set(recent.map(w => w.exercise))];
  const progress = [];
  exs.forEach(ex => {
    const curVals = recent.filter(w => w.exercise === ex && w.weight > 0).map(w => epley(w.weight, w.reps));
    if (!curVals.length) return;
    const cur1rm = Math.max(...curVals);
    const oldVals = older.filter(w => w.exercise === ex && w.weight > 0).map(w => epley(w.weight, w.reps));
    if (!oldVals.length) return;
    const old1rm = Math.max(...oldVals);
    if (old1rm > 0) progress.push({ ex, pct: (cur1rm - old1rm) / old1rm * 100, cur1rm });
  });
  progress.sort((a, b) => b.pct - a.pct);
  const div = $('top3-progress');
  if (!div) return;
  const medals = ['🥇','🥈','🥉'];
  if (!progress.length) { div.innerHTML = '<p class="empty-state">Недостаточно данных для сравнения</p>'; return; }
  div.innerHTML = progress.slice(0, 3).map((p, i) => {
    const sign = p.pct >= 0 ? '+' : '';
    const cls = p.pct >= 0 ? 'color:#00e5c8' : 'color:#ff6b6b';
    return `<div class="pr-item"><span class="pr-medal">${medals[i]}</span><div class="pr-info"><div class="pr-ex">${p.ex}</div><div class="pr-val">1ПМ: ${p.cur1rm} кг</div></div><span class="pr-num" style="${cls}">${sign}${p.pct.toFixed(1)}%</span></div>`;
  }).join('');
}

// ── Profile ──
function renderProfile() {
  const ws = DB.workouts || [];
  const profile = DB.profile || {};
  const body = (DB.body || []).slice(-1)[0] || {};
  const userName = tg && tg.initDataUnsafe && tg.initDataUnsafe.user && tg.initDataUnsafe.user.first_name;
  $('profile-name').textContent = userName || profile.name || '—';
  const goals = { hypertrophy: '💪 Гипертрофия', strength: '🏋️ Сила', weight_loss: '🔥 Похудение', endurance: '🏃 Выносливость' };
  $('profile-goal').textContent = goals[profile.goal] || '—';
  // Вес тела: API бота сохраняет как bodyweight, веб как weight — проверяем оба
  const bodyWeight = body.bodyweight || body.weight;
  $('p-weight').textContent = bodyWeight ? bodyWeight + 'кг' : '—';
  const heightCm = profile.height_cm || profile.height || 0;
  $('p-height').textContent = heightCm ? heightCm + 'см' : '—';
  let fatPct = '—';
  if (body.measurements && heightCm) {
    const m = body.measurements;
    const waist = parseFloat(m.waist_cm);
    const neck = parseFloat(m.neck_cm);
    const hips = parseFloat(m.hips_cm || 0);
    const h = parseFloat(heightCm);
    const gender = profile.gender || 'male';
    if (waist && neck) {
      if (gender === 'male') {
        const d = waist - neck;
        if (d > 0) fatPct = (495 / (1.0324 - 0.19077 * Math.log10(d) + 0.15456 * Math.log10(h)) - 450).toFixed(1);
      } else {
        const d = waist + hips - neck;
        if (d > 0) fatPct = (495 / (1.29579 - 0.35004 * Math.log10(d) + 0.22100 * Math.log10(h)) - 450).toFixed(1);
      }
    }
  }
  $('p-fat').textContent = fatPct !== '—' ? fatPct + '%' : (body.fat ? body.fat + '%' : '—');
  // Вес тела для нормативов и БЖУ
  const bw = parseFloat(bodyWeight) || 75;
  let tdee = '—';
  if (bodyWeight && heightCm && profile.birth_year) {
    const age = Math.max(1, new Date().getFullYear() - profile.birth_year);
    const g = profile.gender || 'male';
    const bmr = 10 * parseFloat(bodyWeight) + 6.25 * heightCm - 5 * age + (g === 'male' ? 5 : -161);
    const days = parseInt(profile.training_days_per_week || 3);
    const mult = days <= 3 ? 1.375 : (days <= 5 ? 1.55 : 1.725);
    tdee = Math.round(bmr * mult);
  }
  if (tdee !== '—') {
    const goal = profile.goal || 'hypertrophy';
    let target = tdee;
    let protein = Math.round(bw * 1.6);
    if (goal === 'hypertrophy') {
      target = tdee + 300;
      protein = Math.round(bw * 2.0);
    } else if (goal === 'weight_loss') {
      target = tdee - 400;
      protein = Math.round(bw * 1.8);
    }
    const fats = Math.round((target * 0.25) / 9);
    const carbs = Math.round((target - protein * 4 - fats * 9) / 4);
    $('p-tdee').innerHTML = `<span style="font-size:1.15rem;font-weight:800;">${target} ккал</span><small style="font-size:0.62rem;display:block;color:var(--text2);margin-top:2px;font-weight:600;letter-spacing:0.02em;">${protein}г Б · ${fats}г Ж · ${carbs}г У</small>`;
  } else {
    $('p-tdee').textContent = '—';
  }
  const days = [...new Set(ws.map(w => w.date))].length;
  const tonnage = ws.reduce((s, w) => s + (w.weight || 0) * (w.reps || 0), 0);
  const sets = ws.length;
  $('history-summary').innerHTML = `<div class="hist-row"><span>🗓 Тренировочных дней</span><span class="hist-val">${days}</span></div><div class="hist-row"><span>🔢 Всего подходов</span><span class="hist-val">${sets}</span></div><div class="hist-row"><span>🏗 Общий тоннаж</span><span class="hist-val">${(tonnage / 1000).toFixed(1)} т</span></div>`;
  const records = {};
  ws.filter(w => w.weight > 0).forEach(w => { const e = epley(w.weight, w.reps); if (!records[w.exercise] || e > records[w.exercise]) records[w.exercise] = e; });
  const stds = [['Жим лёжа', [0.75, 1.25, 1.5]], ['Присед', [1.0, 1.5, 2.0]], ['Становая тяга', [1.25, 1.75, 2.5]]];
  const stdDiv = $('strength-standards');
  stdDiv.innerHTML = stds.map(([ex, [n, m, a]]) => {
    const pr = records[ex] || 0;
    const rat = bw > 0 ? pr / bw : 0;
    const lvl = rat >= a ? ['Элита', 'elite'] : rat >= m ? ['Продвинутый', 'good'] : rat >= n ? ['Средний', 'ok'] : ['Новичок', 'base'];
    return `<div class="standard-item"><span class="std-label">${ex}</span><span class="std-val">${pr ? pr + 'кг' : '—'}</span><span class="std-badge ${lvl[1]}">${lvl[0]}</span></div>`;
  }).join('');
}

function toggleTheme() {
  const d = document.documentElement;
  const isLight = d.getAttribute('data-theme') === 'light';
  d.setAttribute('data-theme', isLight ? 'dark' : 'light');
  $('theme-btn').textContent = isLight ? '🌙 Тёмная' : '☀️ Светлая';
}

function clearSession() {
  if (!confirm('Очистить текущую сессию (несохранённые подходы)?')) return;
  workout.sets = [];
  workout.exercise = '';
  $('selected-exercise-display').style.display = 'none';
  document.querySelectorAll('#exercise-chips .ex-chip').forEach(c => c.classList.remove('active'));
  $('save-btn').style.display = 'none';
  $('no-weight-cb').checked = false;
  $('weight-input').disabled = false;
  $('weight-slider').disabled = false;
  setWeight(80);
  setReps(8);
  document.querySelectorAll('.rpe-btn').forEach(b => b.classList.remove('active'));
  const greenBtn = document.querySelector('.rpe-btn.green');
  if (greenBtn) greenBtn.classList.add('active');
  workout.rpe = 'Легко';
  renderSetsLog();
  showToast('🗑 Сессия очищена');
}

// ── Chart.js CDN check ──
function loadChartJS(cb) {
  if (window.Chart) { cb(); return; }
  const s = document.createElement('script');
  s.src = 'https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js';
  s.onload = cb;
  s.onerror = () => {
    console.warn("Failed to load Chart.js, loading app without charts.");
    cb();
  };
  document.head.appendChild(s);
}

// ── Health Tracker & PubMed Hub functions ──
let selectedMood = '';

function renderHealthTracker() {
  const todayStr = fmtDate(new Date());
  const entries = DB.body || [];
  const todayEntry = entries.find(e => e.date === todayStr);
  const lastEntry = entries.length ? entries[entries.length - 1] : {};

  const weight = (todayEntry && (todayEntry.bodyweight || todayEntry.weight)) || (lastEntry && (lastEntry.bodyweight || lastEntry.weight)) || '—';
  const sleep = (todayEntry && todayEntry.sleep_hours) !== undefined && todayEntry.sleep_hours !== null ? todayEntry.sleep_hours : '—';
  const water = (todayEntry && todayEntry.water_l) !== undefined && todayEntry.water_l !== null ? todayEntry.water_l : '—';
  const cal = (todayEntry && todayEntry.calories) || '—';

  $('track-weight').textContent = weight;
  $('track-sleep').textContent = sleep;
  $('track-water').textContent = water;
  $('track-cal').textContent = cal;
}

function openHealthModal() {
  const todayStr = fmtDate(new Date());
  const entries = DB.body || [];
  const todayEntry = entries.find(e => e.date === todayStr) || {};
  const lastEntry = entries.length ? entries[entries.length - 1] : {};

  $('h-weight').value = todayEntry.bodyweight || todayEntry.weight || lastEntry.bodyweight || lastEntry.weight || '';
  $('h-sleep').value = todayEntry.sleep_hours !== undefined ? todayEntry.sleep_hours : '';
  $('h-water').value = todayEntry.water_l !== undefined ? todayEntry.water_l : '';
  $('h-calories').value = todayEntry.calories || '';
  $('h-protein').value = todayEntry.protein_g || '';
  
  selectedMood = todayEntry.mood || '';
  document.querySelectorAll('.mood-btn').forEach(btn => {
    btn.classList.remove('active');
    if (selectedMood && btn.textContent.includes(selectedMood)) btn.classList.add('active');
  });
  
  $('health-modal').style.display = 'flex';
}

function closeHealthModal() {
  $('health-modal').style.display = 'none';
}

function selectMood(mood, el) {
  document.querySelectorAll('.mood-btn').forEach(b => b.classList.remove('active'));
  el.classList.add('active');
  selectedMood = mood;
}

async function saveHealthParams() {
  const weight = parseFloat($('h-weight').value) || null;
  const sleep = parseFloat($('h-sleep').value) || null;
  const water = parseFloat($('h-water').value) || null;
  const calories = parseInt($('h-calories').value) || 0;
  const protein = parseInt($('h-protein').value) || 0;

  if (!DB.body) DB.body = [];

  const todayStr = fmtDate(new Date());
  let entry = DB.body.find(e => e.date === todayStr);
  if (!entry) {
    entry = {
      id: String(Date.now()),
      date: todayStr,
      ts: new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }),
      bodyweight: weight,
      calories: calories,
      protein_g: protein,
      water_l: water,
      sleep_hours: sleep,
      mood: selectedMood,
      measurements: {}
    };
    DB.body.push(entry);
  } else {
    if (weight !== null) entry.bodyweight = weight;
    if (sleep !== null) entry.sleep_hours = sleep;
    if (water !== null) entry.water_l = water;
    entry.calories = calories;
    entry.protein_g = protein;
    entry.mood = selectedMood;
  }

  await saveData();
  showToast('✅ Показатели здоровья обновлены!');
  closeHealthModal();
  renderDashboard();
  renderProfile();
}

// ── PubMed Articles ──
let currentPubmedCategory = 'all';

const PUBMED_ARTICLES = [
  {
    category: "recovery",
    title: "🍺 Алкоголь и синтез белка",
    summary: "Алкоголь после тренировки подавляет активность mTOR и снижает синтез мышечного белка (MPS) на 24-37%.",
    study: "Parr EB et al. (2014) | PMID: 24533157",
    details: "Употребление алкоголя (1.5 г/кг) после силовой снизило синтез белка на 37% без протеина и на 24% даже при приеме 25 г сывороточного белка. Доказал прямое угнетающее действие этанола на мышечный анаболизм."
  },
  {
    category: "supplements",
    title: "🧪 Бета-аланин: Буфер закисления",
    summary: "Бета-аланин повышает концентрацию карнозина в мышцах, увеличивая выносливость в сетах длительностью от 60 до 240 секунд.",
    study: "Hobson RM et al. (2012) | PMID: 22267562",
    details: "Бета-аланин достоверно повышает выносливость в упражнениях длительностью от 60 до 240 секунд. Эффект на сетах <60 сек минимален. Определил точную временную нишу для эффективности бета-аланина."
  },
  {
    category: "supplements",
    title: "☕️ Кофеин: Сила в чашке",
    summary: "Кофеин в дозе 3-6 мг/кг повышает силу на 3-5%, мощность на 6-8% и снижает RPE. Оптимальное время — за 30-60 минут до тренировки.",
    study: "Grgic J et al. (2018) | PMID: 29946216",
    details: "Кофеин повышает 1ПМ в жиме лежа на 2.1 кг и общий тренировочный объём на 6.5% при дозе 3-6 мг/кг. Количественно оценил эффект кофеина на силовые показатели."
  },
  {
    category: "supplements",
    title: "☕️ Кофеин: Сила в чашке",
    summary: "Кофеин в дозе 3-6 мг/кг повышает силу на 3-5%, мощность на 6-8% и снижает RPE. Оптимальное время — за 30-60 минут до тренировки.",
    study: "Warren GL et al. (2010) | PMID: 20966192",
    details: "Кофеин снижает болевое восприятие на 5.2% и воспринимаемое усилие (RPE) на 5.6%. Объяснил механизм: кофеин работает через снижение RPE, а не через прямое усиление мышц."
  },
  {
    category: "supplements",
    title: "☕️ Кофеин: Сила в чашке",
    summary: "Кофеин в дозе 3-6 мг/кг повышает силу на 3-5%, мощность на 6-8% и снижает RPE. Оптимальное время — за 30-60 минут до тренировки.",
    study: "Guest NS et al. (2021) | PMID: 33388079",
    details: "Генетический полиморфизм CYP1A2 влияет на метаболизм кофеина. 'Медленные' метаболизаторы получают меньше пользы и больше побочных эффектов. Объяснил, почему кофеин работает не на всех одинаково."
  },
  {
    category: "nutrition",
    title: "🍚 Углеводы: Топливо для силы и роста",
    summary: "Гликоген — основное топливо для анаэробной работы. Низкоуглеводные диеты снижают тренировочную производительность на 5-15%.",
    study: "Escobar KA et al. (2016) | PMID: 27042165",
    details: "Низкоуглеводная диета снизила объём тренировки на 12% и субъективное усилие повысилось на 15%. Прямое доказательство влияния углеводов на силовой тренинг."
  },
  {
    category: "nutrition",
    title: "🍚 Углеводы: Топливо для силы и роста",
    summary: "Гликоген — основное топливо для анаэробной работы. Низкоуглеводные диеты снижают тренировочную производительность на 5-15%.",
    study: "Ivy JL et al. (2002) | PMID: 12235033",
    details: "Приём углеводов + белка после тренировки ускорил ресинтез гликогена на 38% по сравнению с только углеводами. Обосновал комбинацию углеводов и белка после тренировки."
  },
  {
    category: "nutrition",
    title: "🍚 Углеводы: Топливо для силы и роста",
    summary: "Гликоген — основное топливо для анаэробной работы. Низкоуглеводные диеты снижают тренировочную производительность на 5-15%.",
    study: "Vargas-Molina S et al. (2020) | PMID: 32958094",
    details: "Кето-группа потеряла больше жира, но набрала достоверно меньше мышц, чем группа с нормальными углеводами. Показал, что кето-диета субоптимальна для гипертрофии."
  },
  {
    category: "training",
    title: "🏃‍♂️ Кардио и силовые: Эффект интерференции",
    summary: "Кардио перед силовой снижает мышечную силу и истощает гликоген. Лучше разделять их или делать кардио после тренировки.",
    study: "Murlasits Z et al. (2018) | PMID: 27318712",
    details: "Выполнение кардио непосредственно перед силовой снизило 1ПМ в жиме и приседе на 12-18% и замедлило рост мышц. Научно доказал негативное влияние кардио на последующую силовую работу (эффект интерференции)."
  },
  {
    category: "supplements",
    title: "💊 Цитруллин малат: Выносливость и памп",
    summary: "8 г цитруллина перед тренировкой повышают количество повторений в отказных подходах на 53% и снижают боль в мышцах на 40%.",
    study: "Pérez-Guisado J, Jakeman PM (2010) | PMID: 20386124",
    details: "Прием 8 г цитруллина малата дал прирост повторений в жиме лежа на 52.92% в последних сетах и снизил мышечную боль (DOMS) на 40% через 24-48 часов. Определил цитруллин как мощную добавку для преодоления утомления в силовом тренинге."
  },
  {
    category: "recovery",
    title: "🧠 Усталость ЦНС и перетрен",
    summary: "Утомление ЦНС снижает рекрутирование мышечных волокон. Три стадии: функциональное перенапряжение → нефункциональное → синдром перетренированности.",
    study: "Meeusen R et al. (2013) | PMID: 23247672",
    details: "Перетрен имеет 3 стадии: FO (функциональное, 2-4 нед восстановления), NFO (нефункциональное, 2-3 мес), OTS (синдром, месяцы-годы). Официальный консенсус по диагностике перетренированности."
  },
  {
    category: "recovery",
    title: "🧠 Усталость ЦНС и перетрен",
    summary: "Утомление ЦНС снижает рекрутирование мышечных волокон. Три стадии: функциональное перенапряжение → нефункциональное → синдром перетренированности.",
    study: "Halson SL & Jeukendrup AE (2004) | PMID: 15027528",
    details: "Соотношение кортизол/тестостерон >30% выше нормы — маркер перетрена. HRV снижается на 15-20% при накоплении усталости. Определил биомаркеры для раннего выявления перетрена."
  },
  {
    category: "recovery",
    title: "🧠 Усталость ЦНС и перетрен",
    summary: "Утомление ЦНС снижает рекрутирование мышечных волокон. Три стадии: функциональное перенапряжение → нефункциональное → синдром перетренированности.",
    study: "Grandou C et al. (2020) | PMID: 31820371",
    details: "Субъективные маркеры самочувствия (wellness questionnaires) предсказывают перетрен на 78% точно — лучше, чем анализы крови. Доказал, что простые анкеты лучше дорогих анализов для мониторинга."
  },
  {
    category: "supplements",
    title: "💊 Креатин: Король добавок",
    summary: "Креатин моногидрат — самая изученная и эффективная спортивная добавка. Повышает силу на 5-10%, мышечную массу на 1-2 кг за 4-12 недель.",
    study: "Lanhers C et al. (2017) | PMID: 27328852",
    details: "Креатин повышает 1ПМ верхней части тела на 5.3% и нижней на 5.2% по сравнению с плацебо. Крупнейший мета-анализ, подтвердивший эргогенный эффект креатина."
  },
  {
    category: "supplements",
    title: "💊 Креатин: Король добавок",
    summary: "Креатин моногидрат — самая изученная и эффективная спортивная добавка. Повышает силу на 5-10%, мышечную массу на 1-2 кг за 4-12 недель.",
    study: "Chilibeck PD et al. (2017) | PMID: 28070459",
    details: "Креатин + тренировки дают дополнительно +1.37 кг сухой массы тела по сравнению с плацебо + тренировки. Количественно оценил эффект креатина на гипертрофию."
  },
  {
    category: "supplements",
    title: "💊 Креатин: Король добавок",
    summary: "Креатин моногидрат — самая изученная и эффективная спортивная добавка. Повышает силу на 5-10%, мышечную массу на 1-2 кг за 4-12 недель.",
    study: "Kreider RB et al. (2017) | PMID: 28615996",
    details: "Креатин моногидрат безопасен при длительном применении (до 5 лет). Нет доказательств вреда для почек у здоровых людей. Официальная позиция ISSN по безопасности креатина."
  },
  {
    category: "nutrition",
    title: "🍕 Диетические перерывы: Исследование MATADOR",
    summary: "Чередование 2 недель дефицита калорий с 2... (MATADOR) теряет на 50% больше жира.",
    study: "Byrne NM et al. (2018) | PMID: 29117865",
    details: "Группа MATADOR (2 недели диеты / 2 недели отдыха на поддержке) потеряла на 50% больше жира и сохранила на 40% больше сухой массы. Доказал преимущество интервальной диеты над непрерывным дефицитом калорий."
  },
  {
    category: "nutrition",
    title: "🔥 Жиросжигание: Наука рекомпозиции",
    summary: "Дефицит калорий — единственный способ потери жира. При высоком белке и силовых тренировках можно сохранить или даже нарастить мышцы на дефиците.",
    study: "Helms ER et al. (2014) | PMID: 24864135",
    details: "Оптимальный темп жиропотери: 0.5-1% массы тела в неделю. Быстрее — потеря мышц увеличивается. Установил безопасный темп сушки для натуральных атлетов."
  },
  {
    category: "nutrition",
    title: "🔥 Жиросжигание: Наука рекомпозиции",
    summary: "Дефицит калорий — единственный способ потери жира. При высоком белке и силовых тренировках можно сохранить или даже нарастить мышцы на дефиците.",
    study: "Barakat C et al. (2020) | PMID: 31247944",
    details: "Body recomposition (одновременный набор мышц + потеря жира) возможна у новичков, людей с лишним весом и при возвращении после перерыва. Обосновал, для кого рекомпозиция реальна."
  },
  {
    category: "nutrition",
    title: "🔥 Жиросжигание: Наука рекомпозиции",
    summary: "Дефицит калорий — единственный способ потери жира. При высоком белке и силовых тренировках можно сохранить или даже нарастить мышцы на дефиците.",
    study: "Longland TM et al. (2016) | PMID: 26817506",
    details: "Группа с высоким белком (2.4 г/кг) на дефиците 40% набрала +1.2 кг мышц и потеряла -4.8 кг жира. Группа с 1.2 г/кг потеряла жир, но не набрала мышц. Доказал возможность рекомпозиции при высоком белке у новичков."
  },
  {
    category: "training",
    title: "🧬 Типы мышечных волокон",
    summary: "Тип I (медленные) и Тип II (быстрые) волокна растут при разных нагрузках. Оптимальная программа включает работу во всех диапазонах повторений.",
    study: "Ogborn D & Schoenfeld BJ (2014) | PMID: N/A",
    details: "Тип II волокна имеют вдвое больший потенциал для гипертрофии, чем Тип I. Они лучше всего растут при 6-12 повт. Обосновал приоритет средних повторений для максимальной массы."
  },
  {
    category: "training",
    title: "🧬 Типы мышечных волокон",
    summary: "Тип I (медленные) и Тип II (быстрые) волокна растут при разных нагрузках. Оптимальная программа включает работу во всех диапазонах повторений.",
    study: "Trappe S et al. (2004) | PMID: 14555683",
    details: "Высокие повторения (15-25) гипертрофировали Тип I волокна на 23%, в то время как тяжёлые (3-5) — только на 6%. Доказал, что для полного развития мышцы нужны разные диапазоны повторений."
  },
  {
    category: "recovery",
    title: "💧 Гидратация и сила",
    summary: "Потеря 2% массы тела от обезвоживания снижает силу на 6-10%, мощность на 3% и выносливость на 10-20%.",
    study: "Cheuvront SN & Kenefick RW (2014) | PMID: 24435467",
    details: "Потеря >2% массы тела от обезвоживания достоверно снижает все аспекты спортивной производительности. Установил порог критического обезвоживания."
  },
  {
    category: "recovery",
    title: "💧 Гидратация и сила",
    summary: "Потеря 2% массы тела от обезвоживания снижает силу на 6-10%, мощность на 3% и выносливость на 10-20%.",
    study: "Kraft JA et al. (2012) | PMID: 22124357",
    details: "Обезвоживание на 2.5% массы тела снизило жим лежа на 6.3% и объём тренировки на 14%. Прямо измерил влияние обезвоживания на силовые показатели."
  },
  {
    category: "recovery",
    title: "💧 Гидратация и сила",
    summary: "Потеря 2% массы тела от обезвоживания снижает силу на 6-10%, мощность на 3% и выносливость на 10-20%.",
    study: "Judelson DA et al. (2007) | PMID: 17887812",
    details: "Обезвоживание снижает анаболические гормоны (тестостерон -15%) и повышает катаболические (кортизол +20%). Показал гормональный механизм вреда обезвоживания."
  },
  {
    category: "training",
    title: "📊 Объём тренировок: Сколько подходов нужно?",
    summary: "Научный консенсус: 10-20 рабочих подходов в неделю на мышечную группу обеспечивают максимальную гипертрофию. Выше 20 — рост замедляется.",
    study: "Schoenfeld BJ et al. (2017) | PMID: 27433992",
    details: "Доза-отклик: >10 подходов/нед дают +9.8% роста мышц, 5-9 подходов — +6.6%, <5 — +5.4%. Окончательно доказал преимущество высокого объёма над низким для гипертрофии."
  },
  {
    category: "training",
    title: "📊 Объём тренировок: Сколько подходов нужно?",
    summary: "Научный консенсус: 10-20 рабочих подходов в неделю на мышечную группу обеспечивают максимальную гипертрофию. Выше 20 — рост замедляется.",
    study: "Baz-Valle E et al. (2022) | PMID: 35237172",
    details: "12-20 подходов в неделю — оптимум; превышение 20 подходов не даёт дополнительных преимуществ и повышает риск перетрена. Определил верхнюю границу полезного объёма (MRV)."
  },
  {
    category: "training",
    title: "📊 Объём тренировок: Сколько подходов нужно?",
    summary: "Научный консенсус: 10-20 рабочих подходов в неделю на мышечную группу обеспечивают максимальную гипертрофию. Выше 20 — рост замедляется.",
    study: "Radaelli R et al. (2015) | PMID: 25546444",
    details: "Группы с высоким объемом (3 и 5 подходов) показали достоверно больший рост мышечной массы, чем группа 1 подхода у тренированных мужчин. Показал долгосрочные эффекты объема у опытных атлетов."
  },
  {
    category: "training",
    title: "📊 Объём тренировок: Сколько подходов нужно?",
    summary: "Научный консенсус: 10-20 рабочих подходов в неделю на мышечную группу обеспечивают максимальную гипертрофию. Выше 20 — рост замедляется.",
    study: "Krieger JW (2010) | PMID: 20300012",
    details: "Множественные подходы (2-3) дают на 46% больший эффект размера для гипертрофии по сравнению с одним подходом. Один из первых мета-анализов, доказавших преимущество многоподходной работы."
  },
  {
    category: "training",
    title: "🧠 Связь Мозг-Мышцы (MMC)",
    summary: "Фокус на целевой мышце повышает её ЭМГ-активацию на 20-30% при нагрузке <60% 1ПМ. При тяжёлых весах эффект исчезает.",
    study: "Schoenfeld BJ et al. (2018) | PMID: 29933730",
    details: "Группа с внутренним фокусом ('сжимай бицепс') показала вдвое больший рост бицепса vs группа с внешним фокусом ('подними вес'). Первое прямое доказательство влияния MMC на гипертрофию."
  },
  {
    category: "training",
    title: "🧠 Связь Мозг-Мышцы (MMC)",
    summary: "Фокус на целевой мышце повышает её ЭМГ-активацию на 20-30% при нагрузке <60% 1ПМ. При тяжёлых весах эффект исчезает.",
    study: "Calatayud J et al. (2016) | PMID: 26209563",
    details: "Внутренний фокус повысил ЭМГ грудных на 20% и трицепса на 25% при жиме лежа с 50% 1ПМ. При 80% — эффект исчез. Определил границу эффективности MMC — до 60% 1ПМ."
  },
  {
    category: "recovery",
    title: "🩹 DOMS и мышечные повреждения",
    summary: "Боль после тренировки (DOMS) — НЕ показатель эффективности. Гипертрофия происходит и без боли. Чрезмерные повреждения замедляют рост.",
    study: "Damas F et al. (2018) | PMID: 29422874",
    details: "Мышечные повреждения — побочный эффект тренировки, а не причина роста. Гипертрофия может происходить без DOMS и EIMD. Разделил механизмы повреждения и роста мышц."
  },
  {
    category: "recovery",
    title: "🩹 DOMS и мышечные повреждения",
    summary: "Боль после тренировки (DOMS) — НЕ показатель эффективности. Гипертрофия происходит и без боли. Чрезмерные повреждения замедляют рост.",
    study: "Schoenfeld BJ & Contreras B (2013) | PMID: N/A",
    details: "Основные триггеры гипертрофии: механическое напряжение > метаболический стресс > мышечные повреждения (в порядке важности). Установил иерархию механизмов гипертрофии."
  },
  {
    category: "recovery",
    title: "🩹 DOMS и мышечные повреждения",
    summary: "Боль после тренировки (DOMS) — НЕ показатель эффективности. Гипертрофия происходит и без боли. Чрезмерные повреждения замедляют рост.",
    study: "Roberts LA et al. (2015) | PMID: 26174323",
    details: "Холодная ванна (10°C, 10 мин) после каждой тренировки СНИЗИЛА гипертрофию на 30% по сравнению с контролем. Опроверг рутинное использование холодных ванн после силовых."
  },
  {
    category: "supplements",
    title: "🐟 Омега-3: Синтез белка и суставы",
    summary: "Полиненасыщенные жирные кислоты Омега-3 усиливают анаболический отклик на аминокислоты и инсулин.",
    study: "Smith GI et al. (2011) | PMID: 21159787",
    details: "Прием 4 г Омега-3 в день достоверно повысил чувствительность мышц к анаболическому сигналу (инсулину и аминокислотам), усилив MPS. Доказал анаболический эффект Омега-3 жирных кислот у здоровых молодых людей."
  },
  {
    category: "training",
    title: "📅 Периодизация и Деload",
    summary: "Периодизированные программы на 22% эффективнее непериодизированных. Деload каждые 4-8 недель предотвращает перетрен и травмы.",
    study: "Williams TD et al. (2017) | PMID: 28497285",
    details: "Периодизированные программы дают +22% больший прирост силы vs непериодизированные. Обосновал периодизацию как стандарт для всех уровней."
  },
  {
    category: "training",
    title: "📅 Периодизация и Деload",
    summary: "Периодизированные программы на 22% эффективнее непериодизированных. Деload каждые 4-8 недель предотвращает перетрен и травмы.",
    study: "Harries SK et al. (2015) | PMID: 26382135",
    details: "DUP (ежедневная волнообразная периодизация) даёт +28% больший прирост силы vs линейная периодизация. DUP стала стандартом для атлетов среднего и продвинутого уровня."
  },
  {
    category: "training",
    title: "📅 Периодизация и Деload",
    summary: "Периодизированные программы на 22% эффективнее непериодизированных. Деload каждые 4-8 недель предотвращает перетрен и травмы.",
    study: "Pritchard HJ et al. (2015) | PMID: 25968229",
    details: "Деload с 40% снижением объёма улучшил 1ПМ на 0.8-2.3% после возвращения к нормальным тренировкам. Подтвердил суперкомпенсацию после разгрузочной недели."
  },
  {
    category: "training",
    title: "📈 Прогрессия нагрузок: Как расти постоянно?",
    summary: "Без систематического увеличения механического напряжения рост мышц прекращается. Прогрессия возможна через вес, повторения, объём и технику.",
    study: "Plotkin D et al. (2022) | PMID: 35291020",
    details: "Прогрессивная перегрузка — необходимое условие долгосрочной гипертрофии. Без неё адаптация прекращается за 6-8 недель. Подтвердил центральную роль прогрессии для всех уровней атлетов."
  },
  {
    category: "training",
    title: "📈 Прогрессия нагрузок: Как расти постоянно?",
    summary: "Без систематического увеличения механического напряжения рост мышц прекращается. Прогрессия возможна через вес, повторения, объём и технику.",
    study: "Williams TD et al. (2017) | PMID: 28497285",
    details: "Периодизированные программы с прогрессией дают +22% больший прирост силы vs непериодизированные. Доказал, что структурированная прогрессия эффективнее хаотичного тренинга."
  },
  {
    category: "nutrition",
    title: "🥩 Белок: Сколько, когда и какой?",
    summary: "1.6-2.2 г белка на кг массы тела в день — научно обоснованный оптимум для максимальной гипертрофии. Тайминг вторичен.",
    study: "Morton RW et al. (2018) | PMID: 28698222",
    details: "Оптимальная доза белка для гипертрофии — 1.62 г/кг/день. Выше 2.2 г/кг дополнительной пользы нет. Крупнейший мета-анализ по белку и гипертрофии, установивший точный оптимум."
  },
  {
    category: "nutrition",
    title: "🥩 Белок: Сколько, когда и какой?",
    summary: "1.6-2.2 г белка на кг массы тела в день — научно обоснованный оптимум для максимальной гипертрофии. Тайминг вторичен.",
    study: "Schoenfeld BJ & Aragon AA (2018) | PMID: 29497353",
    details: "Анаболическое окно длится минимум 4-6 часов, а не 30 минут. Главное — общее потребление белка за день. Окончательно развенчал миф о 30-минутном анаболическом окне."
  },
  {
    category: "nutrition",
    title: "🥩 Белок: Сколько, когда и какой?",
    summary: "1.6-2.2 г белка на кг массы тела в день — научно обоснованный оптимум для максимальной гипертрофии. Тайминг вторичен.",
    study: "Res PT et al. (2012) | PMID: 22330017",
    details: "40 г казеина перед сном увеличили ночной MPS на 22% и улучшили белковый баланс. Обосновал приём белка перед сном как эффективную стратегию."
  },
  {
    category: "nutrition",
    title: "🥩 Белок: Сколько, когда и какой?",
    summary: "1.6-2.2 г белка на кг массы тела в день — научно обоснованный оптимум для максимальной гипертрофии. Тайминг вторичен.",
    study: "Kim IY et al. (2016) | PMID: 26530155",
    details: "Равномерное распределение белка (4 приёма по 40 г) дало на 25% больше MPS за день vs 2 больших приёма. Показал важность распределения белка в течение дня."
  },
  {
    category: "training",
    title: "⚖️ Повторения и интенсивность: 5, 10 или 30?",
    summary: "Мышцы растут в ЛЮБОМ диапазоне повторений (от 5 до 30+), если подходы выполняются близко к отказу. Но для силы нужны тяжёлые веса.",
    study: "Schoenfeld BJ et al. (2017) | PMID: 28085795",
    details: "Нагрузка 8-12 повт. и 25-35 повт. привели к идентичной гипертрофии бицепса и квадрицепса при работе до отказа. Разрушил миф о «единственном правильном диапазоне» для гипертрофии."
  },
  {
    category: "training",
    title: "⚖️ Повторения и интенсивность: 5, 10 или 30?",
    summary: "Мышцы растут в ЛЮБОМ диапазоне повторений (от 5 до 30+), если подходы выполняются близко к отказу. Но для силы нужны тяжёлые веса.",
    study: "Lasevicius T et al. (2018) | PMID: 30319436",
    details: "20% 1ПМ не дало гипертрофии даже до отказа. 40%, 60% и 80% 1ПМ дали одинаковый рост. Минимальный порог ~40% 1ПМ. Определил нижнюю границу эффективной нагрузки для гипертрофии."
  },
  {
    category: "training",
    title: "⚖️ Повторения и интенсивность: 5, 10 или 30?",
    summary: "Мышцы растут в ЛЮБОМ диапазоне повторений (от 5 до 30+), если подходы выполняются близко к отказу. Но для силы нужны тяжёлые веса.",
    study: "Morton RW et al. (2016) | PMID: 26838985",
    details: "Тренировка с 30-50% 1ПМ до отказа дала ту же гипертрофию, что и 75-90% 1ПМ у тренированных мужчин. Подтвердил, что лёгкие веса до отказа — эффективная стратегия."
  },
  {
    category: "training",
    title: "⏱ Интервалы отдыха между подходами",
    summary: "Длинный отдых (2-3 мин) даёт больше гипертрофии и силы, чем короткий (1 мин), за счёт сохранения объёма и качества подходов.",
    study: "Schoenfeld BJ et al. (2016) | PMID: 26605807",
    details: "Отдых 3 мин дал достоверно больший рост мышц (+30%) и силы (+15%) vs отдых 1 мин при равном числе подходов. Ключевое исследование, изменившее рекомендации по отдыху."
  },
  {
    category: "training",
    title: "⏱ Интервалы отдыха между подходами",
    summary: "Длинный отдых (2-3 мин) даёт больше гипертрофии и силы, чем короткий (1 мин), за счёт сохранения объёма и качества подходов.",
    study: "Grgic J et al. (2017) | PMID: 28748451",
    details: "Для максимальной силы: отдых >2 мин. Для гипертрофии: >2 мин оптимально, но 60-90 сек допустимо при снижении веса. Систематизировал все данные по интервалам отдыха."
  },
  {
    category: "training",
    title: "📏 Амплитуда движений: Full ROM vs Partial ROM",
    summary: "Полная амплитуда движений (Full ROM) превосходит частичную амплитуду для мышечной гипертрофии.",
    study: "Pedrosa GF et al. (2020) | PMID: 32030125",
    details: "Работа в нижней части амплитуды (растянутая позиция мышцы) дала значительно большую гипертрофию, чем работа в верхней части. Показал важность растяжения мышцы под нагрузкой для запуска гипертрофии."
  },
  {
    category: "training",
    title: "👴 Силовые и старение (саркопения)",
    summary: "После 30 лет человек теряет 3-8% мышечной массы за декаду. Силовые тренировки — единственный доказанный способ предотвратить саркопению.",
    study: "Peterson MD et al. (2011) | PMID: 20881881",
    details: "Силовые тренировки у пожилых (60+) увеличивают мышечную массу на 1.1 кг в среднем за 20 недель. Доказал, что мышцы растут даже после 60 лет."
  },
  {
    category: "training",
    title: "👴 Силовые и старение (саркопения)",
    summary: "После 30 лет человек теряет 3-8% мышечной массы за декаду. Силовые тренировки — единственный доказанный способ предотвратить саркопению.",
    study: "Cruz-Jentoft AJ et al. (2019) | PMID: 30312372",
    details: "Саркопения (потеря мышц) связана с повышением смертности на 40-50% и увеличением риска падений на 60%. Определил саркопению как клиническое заболевание с чёткими критериями."
  },
  {
    category: "recovery",
    title: "😴 Сон: Главный легальный анаболик",
    summary: "Дефицит сна снижает тестостерон на 10-15%, повышает кортизол и снижает синтез белка. Оптимум для атлетов — 8-9 часов.",
    study: "Leproult R & Van Cauter E (2011) | PMID: 21632481",
    details: "Сон по 5 часов в течение 1 недели снизил тестостерон у здоровых мужчин на 10-15%. Прямо доказал разрушительное влияние недосыпа на анаболические гормоны."
  },
  {
    category: "recovery",
    title: "😴 Сон: Главный легальный анаболик",
    summary: "Дефицит сна снижает тестостерон на 10-15%, повышает кортизол и снижает синтез белка. Оптимум для атлетов — 8-9 часов.",
    study: "Dattilo M et al. (2011) | PMID: 21550729",
    details: "70% суточного ГР (гормона роста) выделяется в фазу глубокого сна (N3). Без полноценного сна — нет полноценного ГР. Обосновал связь качества сна с восстановлением мышц."
  },
  {
    category: "recovery",
    title: "😴 Сон: Главный легальный анаболик",
    summary: "Дефицит сна снижает тестостерон на 10-15%, повышает кортизол и снижает синтез белка. Оптимум для атлетов — 8-9 часов.",
    study: "Knowles OE et al. (2018) | PMID: 29605100",
    details: "Дефицит сна снижает силовые показатели на 5-10%, скорость реакции на 9%, точность на 14%. Количественно оценил влияние недосыпа на спортивную производительность."
  },
  {
    category: "recovery",
    title: "😴 Сон: Главный легальный анаболик",
    summary: "Дефицит сна снижает тестостерон на 10-15%, повышает кортизол и снижает синтез белка. Оптимум для атлетов — 8-9 часов.",
    study: "Mah CD et al. (2011) | PMID: 21731144",
    details: "Увеличение сна до 10 часов у баскетболистов улучшило точность бросков на 9% и спринт на 4%. Показал, что больше сна = лучшие результаты даже у элитных атлетов."
  },
  {
    category: "training",
    title: "⏱ Темп повторений: Быстро или медленно?",
    summary: "Темп выполнения повторений от 0.5 до 8 секунд дает схожую гипертрофию. Сверхмедленный темп неэффективен.",
    study: "Schoenfeld BJ et al. (2015) | PMID: 25601394",
    details: "Гипертрофия одинакова при темпе повторения от 0.5 до 8 секунд. Темп >10 секунд (super-slow) дает худший рост. Показал, что время под нагрузкой (TUT) вторично по отношению к уровню механического напряжения."
  },
  {
    category: "recovery",
    title: "🧬 Тестостерон и тренировки",
    summary: "Острый подъём тестостерона после тренировки НЕ влияет на гипертрофию. Важнее базовый уровень, сон и процент жира.",
    study: "West DWD et al. (2010) | PMID: 19164770",
    details: "Острый подъём тестостерона и ГР после тренировки НЕ коррелировал с ростом мышц. Рост мышц определялся MPS, а не гормонами. Разрушил миф о гормональном отклике как драйвере гипертрофии."
  },
  {
    category: "recovery",
    title: "🧬 Тестостерон и тренировки",
    summary: "Острый подъём тестостерона после тренировки НЕ влияет на гипертрофию. Важнее базовый уровень, сон и процент жира.",
    study: "Morton RW et al. (2016) | PMID: 26895395",
    details: "Ни тестостерон, ни ГР, ни IGF-1 после тренировки не предсказывали рост мышц. Единственный предиктор — MPS. Подтвердил, что острые гормональные изменения не определяют гипертрофию."
  },
  {
    category: "recovery",
    title: "🧬 Тестостерон и тренировки",
    summary: "Острый подъём тестостерона после тренировки НЕ влияет на гипертрофию. Важнее базовый уровень, сон и процент жира.",
    study: "Vingren JL et al. (2010) | PMID: 20020789",
    details: "Базовый уровень тестостерона в нормальном физиологическом диапазоне не коррелирует с потенциалом для гипертрофии. Показал, что нормальный диапазон тестостерона достаточен для роста."
  },
  {
    category: "training",
    title: "🔄 Частота тренировок: Сколько раз в неделю?",
    summary: "При равном недельном объёме частота 2 раза/нед на группу превосходит 1 раз/нед для гипертрофии. 3 раза дают минимальное преимущество над 2.",
    study: "Schoenfeld BJ et al. (2016) | PMID: 27102172",
    details: "Тренировка мышечной группы 2+ раз/нед достоверно превосходит 1 раз/нед для гипертрофии (ES = 0.25 vs 0.13). Научно обосновал преимущество повышенной частоты над классическим бро-сплитом."
  },
  {
    category: "training",
    title: "🔄 Частота тренировок: Сколько раз в неделю?",
    summary: "При равном недельном объёме частота 2 раза/нед на группу превосходит 1 раз/нед для гипертрофии. 3 раза дают минимальное преимущество над 2.",
    study: "Grgic J et al. (2018) | PMID: 29325495",
    details: "Силовые показатели улучшаются одинаково при частоте 1-3 раза/нед при равном объёме. Для гипертрофии 2 раза/нед оптимальнее. Разделил влияние частоты на силу и гипертрофию."
  },
  {
    category: "training",
    title: "🔄 Частота тренировок: Сколько раз в неделю?",
    summary: "При равном недельном объёме частота 2 раза/нед на группу превосходит 1 раз/нед для гипертрофии. 3 раза дают минимальное преимущество над 2.",
    study: "Yue FL et al. (2018) | PMID: 29485930",
    details: "Тренировка каждой мышцы 2 раза в неделю повышает синтез мышечного белка (MPS) на 68% эффективнее, чем 1 раз. Объяснил механизм преимущества высокой частоты через MPS."
  },
  {
    category: "supplements",
    title: "☀️ Витамин D: Сила и тестостерон",
    summary: "Витамин D регулирует кальциевый обмен и силу мышц. Его дефицит напрямую снижает спортивные показатели.",
    study: "Carrillo AE et al. (2013) | PMID: 27379691",
    details: "Устранение дефицита витамина D3 повысило силовые показатели и взрывную мощность мышц у спортсменов. Подтвердил прямую связь между нормальным уровнем витамина D и физической силой."
  },
  {
    category: "training",
    title: "🛡 Разминка и профилактика травм",
    summary: "Динамическая разминка снижает риск травм на 30-50%. Статическая растяжка перед силовой снижает силу на 5-8% и НЕ предотвращает травмы.",
    study: "Lauersen JB et al. (2014) | PMID: 24100287",
    details: "Силовые тренировки снижают риск травм на 68%. Растяжка НЕ снижает риск травм. Доказал, что сила — лучшая профилактика травм."
  },
  {
    category: "training",
    title: "🛡 Разминка и профилактика травм",
    summary: "Динамическая разминка снижает риск травм на 30-50%. Статическая растяжка перед силовой снижает силу на 5-8% и НЕ предотвращает травмы.",
    study: "Simic L et al. (2013) | PMID: 23316808",
    details: "Статическая растяжка >60 сек перед силовой снижает максимальную силу на 5.4% и мощность на 2.0%. Обосновал отказ от статической растяжки перед силовой."
  },
  {
    category: "training",
    title: "🛡 Разминка и профилактика травм",
    summary: "Динамическая разминка снижает риск травм на 30-50%. Статическая растяжка перед силовой снижает силу на 5-8% и НЕ предотвращает травмы.",
    study: "Behm DG et al. (2016) | PMID: 26642915",
    details: "Динамическая разминка повышает температуру мышц на 1-2°C, увеличивает ROM на 5-10% и снижает риск травм на 30-50%. Обосновал протокол динамической разминки."
  },
  {
    category: "supplements",
    title: "🥛 Сывороточный протеин против сои и казеина",
    summary: "Сывороточный белок усваивается быстрее, содержит больше лейцина и сильнее стимулирует синтез белка (MPS) после тренировки.",
    study: "Tang JE et al. (2009) | PMID: 19589961",
    details: "Сывороточный протеин (Whey) стимулирует MPS после силовой тренировки на 18% сильнее соевого и на 93% сильнее казеина. Доказал анаболическое превосходство быстрых белков с высоким содержанием лейцина после тренировки."
  }
];

function openPubmedModal() {
  $('pubmed-modal').style.display = 'flex';
  selectPubmedCategory('all', document.querySelector('#pubmed-cats .chip'));
}

function closePubmedModal() {
  $('pubmed-modal').style.display = 'none';
}

function selectPubmedCategory(cat, el) {
  currentPubmedCategory = cat;
  document.querySelectorAll('#pubmed-cats .chip').forEach(c => c.classList.remove('active'));
  el.classList.add('active');
  filterPubmed();
}

function renderPubmedArticles(filter = '') {
  const query = filter.toLowerCase().trim();
  const list = $('pubmed-topics-list');
  
  const filtered = PUBMED_ARTICLES.filter(a => {
    // Category match
    const categoryMatch = currentPubmedCategory === 'all' || a.category === currentPubmedCategory;
    // Text search match
    const textMatch = !query || 
      a.title.toLowerCase().includes(query) || 
      a.summary.toLowerCase().includes(query) || 
      a.details.toLowerCase().includes(query);
    return categoryMatch && textMatch;
  });

  if (!filtered.length) {
    list.innerHTML = '<p class="empty-state">Исследований не найдено</p>';
    return;
  }

  list.innerHTML = filtered.map(a => `
    <div class="pubmed-topic-card">
      <div class="pubmed-topic-title">${a.title}</div>
      <div class="pubmed-topic-summary">${a.summary}</div>
      <div class="pubmed-topic-study">🔍 Исследование: ${a.study}</div>
      <div class="pubmed-topic-details">${a.details}</div>
    </div>
  `).join('');
}

function filterPubmed() {
  const q = $('pubmed-search').value;
  renderPubmedArticles(q);
}

// ═══════════════════════════════════════════════════════════════════
// 🧬 EVIDENCE-BASED TRAINING & PERIODIZATION ENGINE (JS CORE)
// ═══════════════════════════════════════════════════════════════════

const EXERCISE_CATALOG = {
  bench_press: { key: 'bench_press', name: 'Жим штанги лёжа', muscle: 'Грудь', category: 'chest', type: 'compound', equipment: 'barbell', sets: 4, reps: '5-8', rpe: 7.5, rest: 180, tip: 'Опускание до касания груди обеспечивает максимальное растяжение волокон (Schoenfeld 2020).' },
  incline_dumbbell_press: { key: 'incline_dumbbell_press', name: 'Жим гантелей на наклонной скамье (30°)', muscle: 'Грудь (верх)', category: 'chest', type: 'compound', equipment: 'dumbbell', sets: 3, reps: '8-12', rpe: 8.0, rest: 120, tip: 'Угол 30° активирует ключичную порцию грудных на 30% сильнее (Rodríguez-Ridao 2020).' },
  dips_chest: { key: 'dips_chest', name: 'Брусья (акцент на грудь)', muscle: 'Грудь (низ/середина)', category: 'chest', type: 'compound', equipment: 'bodyweight', sets: 3, reps: '8-12', rpe: 8.0, rest: 120, tip: 'Наклон корпуса вперед 30° максимально нагружает стернальную головку грудных мышц.' },
  cable_crossover: { key: 'cable_crossover', name: 'Сведение в кроссовере на блоке', muscle: 'Грудь', category: 'chest', type: 'isolation', equipment: 'cables', sets: 3, reps: '12-15', rpe: 8.5, rest: 90, tip: 'Постоянное механическое натяжение во всей траектории движения (Pinto 2012).' },
  
  deadlift: { key: 'deadlift', name: 'Становая тяга (Классика / Сумо)', muscle: 'Спина / Задняя цепь', category: 'back', type: 'compound', equipment: 'barbell', sets: 3, reps: '3-5', rpe: 8.0, rest: 240, tip: 'Максимальный рекрутинг двигательных единиц задней мышечной цепи (Cholewa 2019).' },
  barbell_row: { key: 'barbell_row', name: 'Тяга штанги в наклоне (к поясу)', muscle: 'Спина (широчайшие)', category: 'back', type: 'compound', equipment: 'barbell', sets: 4, reps: '6-8', rpe: 7.5, rest: 150, tip: 'Тяга к низу живота активирует нижние широчайшие и ромбовидные мышцы (Edelburg 2021).' },
  lat_pulldown: { key: 'lat_pulldown', name: 'Тяга верхнего блока к груди', muscle: 'Широчайшие спины', category: 'back', type: 'compound', equipment: 'cables', sets: 3, reps: '8-12', rpe: 8.0, rest: 120, tip: 'Тяга к груди безопаснее для плеч и дает больший ЭМГ-отклик (Sperandei 2009).' },
  pullups: { key: 'pullups', name: 'Подтягивания на турнике', muscle: 'Спина (широчайшие)', category: 'back', type: 'compound', equipment: 'bodyweight', sets: 3, reps: '6-10', rpe: 8.0, rest: 150, tip: 'Полный ROM с паузой в растянутой нижней точке увеличивает гипертрофию (Pedrosa 2022).' },
  seated_cable_row: { key: 'seated_cable_row', name: 'Горизонтальная тяга блока к поясу', muscle: 'Спина (середина)', category: 'back', type: 'compound', equipment: 'cables', sets: 3, reps: '10-12', rpe: 8.0, rest: 90, tip: 'Сведение лопаток в конце движения на 1 сек усиливает рекрутинг ромбовидных мышц.' },
  
  squat: { key: 'squat', name: 'Приседания со штангой на спине', muscle: 'Квадрицепс / Ягодицы', category: 'legs', type: 'compound', equipment: 'barbell', sets: 4, reps: '5-8', rpe: 7.5, rest: 210, tip: 'Глубокий присед (ниже параллели) удваивает гипертрофию ягодиц и аддукторов (Kubo 2019).' },
  romanian_deadlift: { key: 'romanian_deadlift', name: 'Румынская тяга со штангой / гантелями', muscle: 'Бицепс бедра / Ягодицы', category: 'legs', type: 'compound', equipment: 'barbell', sets: 3, reps: '8-10', rpe: 7.5, rest: 150, tip: 'Растяжение задней поверхности под нагрузкой стимулирует гипертрофию через титин (Pedrosa 2022).' },
  leg_press: { key: 'leg_press', name: 'Жим ногами в тренажере', muscle: 'Квадрицепсы / Бедра', category: 'legs', type: 'compound', equipment: 'machine', sets: 3, reps: '10-12', rpe: 8.0, rest: 120, tip: 'Высокая механическая нагрузка на квадрицепс при сниженной осевой нагрузке на позвоночник.' },
  bulgarian_split_squat: { key: 'bulgarian_split_squat', name: 'Болгарские сплит-приседания', muscle: 'Квадрицепс / Ягодицы', category: 'legs', type: 'compound', equipment: 'dumbbell', sets: 3, reps: '8-12', rpe: 8.0, rest: 90, tip: 'Унилатеральная нагрузка устраняет асимметрию и глубоко растягивает ягодицы.' },
  leg_curl: { key: 'leg_curl', name: 'Сгибания ног сидя / лежа', muscle: 'Бицепс бедра', category: 'legs', type: 'isolation', equipment: 'machine', sets: 3, reps: '10-15', rpe: 8.5, rest: 90, tip: 'Сгибания сидя превосходят сгибания лежа на 14% по гипертрофии бицепса бедра (Maeo 2021).' },
  leg_extension: { key: 'leg_extension', name: 'Разгибания ног в тренажере', muscle: 'Прямая мышца бедра', category: 'legs', type: 'isolation', equipment: 'machine', sets: 3, reps: '12-15', rpe: 8.5, rest: 90, tip: 'Изолирует прямую мышцу бедра, которая слабо работает в приседе (Earp 2015).' },
  calf_raises: { key: 'calf_raises', name: 'Подъемы на носки стоя', muscle: 'Икроножные', category: 'calves', type: 'isolation', equipment: 'machine', sets: 4, reps: '12-15', rpe: 8.5, rest: 75, tip: 'Пауза 2 сек в нижней точке растяжения исключает ахиллов рефлекс и растит икры (Kassiano 2023).' },
  
  overhead_press: { key: 'overhead_press', name: 'Армейский жим стоя / сидя', muscle: 'Передняя дельта / Плечи', category: 'shoulders', type: 'compound', equipment: 'barbell', sets: 3, reps: '6-8', rpe: 7.5, rest: 150, tip: 'Базовый строитель силы плечевого пояса и стабильности кора (Saeterbakken 2011).' },
  lateral_raises: { key: 'lateral_raises', name: 'Махи гантелями в стороны', muscle: 'Средняя дельта', category: 'shoulders', type: 'isolation', equipment: 'dumbbell', sets: 4, reps: '12-15', rpe: 8.5, rest: 75, tip: 'Ключевое движение для ширины плеч. На блоке нагрузка более непрерывная (Pedrosa 2022).' },
  face_pulls: { key: 'face_pulls', name: 'Face Pulls на канате к лицу', muscle: 'Задняя дельта / Ротаторы', category: 'shoulders', type: 'isolation', equipment: 'cables', sets: 3, reps: '12-15', rpe: 8.5, rest: 75, tip: 'Профилактика травм плеча и развитие задней дельты для осанки.' },
  
  barbell_biceps_curl: { key: 'barbell_biceps_curl', name: 'Подъем штанги на бицепс стоя', muscle: 'Бицепс', category: 'arms', type: 'isolation', equipment: 'barbell', sets: 3, reps: '8-12', rpe: 8.0, rest: 90, tip: 'Супинация кисти и полный разгиб локтя в нижней точке для длинной головки бицепса.' },
  incline_dumbbell_curl: { key: 'incline_dumbbell_curl', name: 'Сгибания на наклонной скамье', muscle: 'Бицепс (длинная головка)', category: 'arms', type: 'isolation', equipment: 'dumbbell', sets: 3, reps: '10-12', rpe: 8.5, rest: 90, tip: 'Глубокое растяжение длинной головки бицепса ускоряет рост (Oliveira 2009).' },
  hammer_curls: { key: 'hammer_curls', name: 'Молотковые сгибания (хват нейтральный)', muscle: 'Брахиалис / Предплечья', category: 'arms', type: 'isolation', equipment: 'dumbbell', sets: 3, reps: '10-12', rpe: 8.5, rest: 75, tip: 'Брахиалис выталкивает бицепс наружу, создавая визуальную толщину руки.' },
  skull_crushers: { key: 'skull_crushers', name: 'Французский жим лежа', muscle: 'Трицепс (длинная головка)', category: 'arms', type: 'isolation', equipment: 'barbell', sets: 3, reps: '8-12', rpe: 8.0, rest: 90, tip: 'Отвод плеча назад усиливает натяжение длинной головки трицепса (Maeo 2022).' },
  tricep_rope_pushdown: { key: 'tricep_rope_pushdown', name: 'Разгибания на трицепс на блоке', muscle: 'Трицепс (латеральная головка)', category: 'arms', type: 'isolation', equipment: 'cables', sets: 3, reps: '10-12', rpe: 8.5, rest: 75, tip: 'Разведение канатов внизу обеспечивает максимальное пиковое сокращение.' },
  
  hanging_leg_raises: { key: 'hanging_leg_raises', name: 'Подъемы ног в висе на турнике', muscle: 'Пресс / Кор', category: 'core', type: 'isolation', equipment: 'bodyweight', sets: 3, reps: '12-15', rpe: 8.0, rest: 75, tip: 'Подкручивание таза к ребрам обязательно для сокращения прямой мышцы живота (Escamilla 2006).' },
  cable_woodchopper: { key: 'cable_woodchopper', name: 'Скручивания на блоке (Молитва)', muscle: 'Пресс', category: 'core', type: 'isolation', equipment: 'cables', sets: 3, reps: '12-15', rpe: 8.0, rest: 60, tip: 'Прогрессивная перегрузка весом для гипертрофии кубиков пресса.' }
};

function getWarmupLadder(exKey, workingWeight) {
  const ex = EXERCISE_CATALOG[exKey] || {};
  const eq = ex.equipment || 'barbell';
  const ladder = [];
  const round25 = w => Math.round(w / 2.5) * 2.5;

  if (eq === 'barbell') {
    if (exKey === 'deadlift' || exKey === 'romanian_deadlift') {
      const startW = workingWeight >= 60 ? 50.0 : Math.max(20.0, workingWeight * 0.5);
      ladder.push({ step: 1, weight: startW, reps: 5, note: 'Старт, натяг и высота дисков' });
      if (workingWeight > 70) ladder.push({ step: 2, weight: round25(workingWeight * 0.70), reps: 3, note: 'Скорость съема (70%)' });
      if (workingWeight > 85) ladder.push({ step: 3, weight: round25(workingWeight * 0.88), reps: 1, note: 'Подводящий сингл (88% PAP)' });
    } else {
      ladder.push({ step: 1, weight: 20.0, reps: 10, note: 'Пустой гриф, траектория' });
      if (workingWeight >= 40) ladder.push({ step: 2, weight: round25(workingWeight * 0.50), reps: 5, note: 'Включение моторных единиц (50%)' });
      if (workingWeight >= 55) ladder.push({ step: 3, weight: round25(workingWeight * 0.72), reps: 3, note: 'Взрывной темп (72%)' });
      if (workingWeight >= 70) ladder.push({ step: 4, weight: round25(workingWeight * 0.88), reps: 1, note: 'Подводящий сингл (88%)' });
    }
  } else if (eq === 'dumbbell' || eq === 'machine') {
    if (workingWeight >= 20) {
      ladder.push({ step: 1, weight: round25(workingWeight * 0.50), reps: 8, note: 'Суставная разминка (50%)' });
      ladder.push({ step: 2, weight: round25(workingWeight * 0.75), reps: 4, note: 'Подводка (75%)' });
    } else if (workingWeight > 10) {
      ladder.push({ step: 1, weight: round25(workingWeight * 0.60), reps: 6, note: 'Разогрев (60%)' });
    }
  }
  return ladder;
}

function hasValidProgram(p) {
  return Boolean(p && typeof p === 'object' && Array.isArray(p.days) && p.days.length > 0);
}

// Wizard State
let wizardState = {
  goal: 'hypertrophy',
  level: 'intermediate',
  days: 4,
  equipment: 'gym',
  split: 'auto'
};
let selectedProgramDay = 0;

function openProgramWizard() {
  const container = $('program-container');
  if (container) container.innerHTML = renderProgramWizardHTML();
  const rebBtn = $('prog-rebuild-btn');
  if (rebBtn) rebBtn.style.display = 'none';
}

function selectWizardOption(field, value, el) {
  wizardState[field] = value;
  const parent = el.closest('.wizard-options-grid');
  if (parent) {
    parent.querySelectorAll('.wizard-option').forEach(opt => opt.classList.remove('active'));
  }
  el.classList.add('active');
}

function getAvailableSplitsForDays(daysCount) {
  const d = parseInt(daysCount) || 4;
  if (d === 2) {
    return [
      { id: 'auto', name: '🧬 ИИ Автовыбор', desc: 'Подбор под цели и слабые места' },
      { id: 'full_body_2d', name: '🔥 Full Body A & B', desc: 'Все тело 2 раза в неделю' },
      { id: 'upper_lower_2d', name: '🏋️ Верх / Низ Экспресс', desc: 'День 1 Верх, День 2 Низ' }
    ];
  } else if (d === 3) {
    return [
      { id: 'auto', name: '🧬 ИИ Автовыбор', desc: 'Подбор под цели и слабые места' },
      { id: 'ppl_3d', name: '💪 Push / Pull / Legs', desc: 'Толкай / Тяни / Ноги (Золотой стандарт)' },
      { id: 'arnold_3d', name: '👑 Arnold Split', desc: 'Грудь+Спина / Руки+Плечи / Ноги (Арнольд)' },
      { id: 'sbd_3d', name: '🏆 SBD Троеборье', desc: 'Присед / Жим / Тяга (Сила 1ПМ)' },
      { id: 'full_body_3d', name: '🔥 Full Body A/B/C', desc: 'Высокая частота 3 раза в неделю' }
    ];
  } else if (d === 4) {
    return [
      { id: 'auto', name: '🧬 ИИ Автовыбор', desc: 'Золотой стандарт PubMed' },
      { id: 'upper_lower_4d', name: '🏋️ Upper / Lower A & B', desc: '2 Верха и 2 Низа (Сбалансированно)' },
      { id: 'ppl_upper_4d', name: '💪 PPL + Upper', desc: 'PPL + день специализации на верх' },
      { id: 'sbd_power_4d', name: '🏆 SBD Powerbuilding', desc: "Тяжелая база + объемный рельеф" }
    ];
  } else if (d === 5) {
    return [
      { id: 'auto', name: '🧬 ИИ Автовыбор', desc: 'Идеально для объема' },
      { id: 'upper_lower_ppl_5d', name: '🚀 Upper/Lower + PPL', desc: 'Силовые дни + Памп дни' },
      { id: 'bro_split_5d', name: '🥩 Classic Bro Split', desc: '1 мышечная группа в день' }
    ];
  } else {
    return [
      { id: 'auto', name: '🧬 ИИ Автовыбор', desc: 'Максимальный объем' },
      { id: 'ppl_6d', name: '💪 Push / Pull / Legs × 2', desc: 'Каждая группа 2 раза в неделю' },
      { id: 'arnold_6d', name: '👑 Arnold Split × 2', desc: 'Суперсетовый памп' }
    ];
  }
}

function analyzeAthleteProfileJS(workouts, user1rm) {
  const bench = parseFloat(user1rm.bench_press) || 68.0;
  const squat = parseFloat(user1rm.squat) || 92.5;
  const dead = parseFloat(user1rm.deadlift) || 100.0;

  const benchRatio = (bench / (squat || 1));
  const deadRatio = (dead / (squat || 1));

  let specialization = 'balanced';
  let recommendation = '✅ Сбалансированное развитие силовых показателей.';

  if (benchRatio < 0.70) {
    specialization = 'chest_focus';
    recommendation = '📊 Жим лёжа отстает относительно ног. Добавлен увеличенный объем на грудные и плечи.';
  } else if (deadRatio < 1.10) {
    specialization = 'back_focus';
    recommendation = '📊 Становая тяга и спина отстают относительно приседа. Увеличен акцент на широчайшие и заднюю цепь.';
  }

  return {
    sbd_total: Math.round(bench + squat + dead),
    bench_to_squat: benchRatio.toFixed(2),
    specialization,
    recommendation
  };
}

function renderProgramWizardHTML() {
  const ws = DB.workouts || [];
  const records = {};
  ws.filter(w => w.weight > 0).forEach(w => {
    const e = epley(w.weight, w.reps);
    if (!records[w.exercise] || e > records[w.exercise]) records[w.exercise] = e;
  });

  const defBench = records['Жим лёжа'] || 68.0;
  const defSquat = records['Присед'] || 92.5;
  const defDead = records['Становая тяга'] || 100.0;

  const splits = getAvailableSplitsForDays(wizardState.days);

  return `
    <div class="wizard-card glass">
      <div style="margin-bottom:14px;">
        <span class="badge" style="background:rgba(124,92,255,0.25); color:#c4b5fd; border:1px solid rgba(124,92,255,0.4); padding:4px 10px; border-radius:20px; font-size:0.75rem; font-weight:700;">🧬 PubMed AI Generator</span>
        <h2 style="font-size:1.15rem; font-weight:900; margin-top:6px;">Мастер составления тренировок</h2>
        <p style="font-size:0.78rem; color:var(--text2); margin-top:2px;">Адаптивный подбор сплита, объема (MAV) и волновой периодизации под твою силу</p>
      </div>

      <div class="wizard-step-title">🎯 1. Главная цель тренировок</div>
      <div class="wizard-options-grid">
        <div class="wizard-option ${wizardState.goal==='hypertrophy'?'active':''}" onclick="selectWizardOption('goal', 'hypertrophy', this)">
          <span class="wizard-opt-icon">💪</span>
          <span class="wizard-opt-title">Гипертрофия</span>
          <span class="wizard-opt-desc">Максимальный набор массы (12-18 сетов/нед, MAV)</span>
        </div>
        <div class="wizard-option ${wizardState.goal==='strength'?'active':''}" onclick="selectWizardOption('goal', 'strength', this)">
          <span class="wizard-opt-icon">🏋️</span>
          <span class="wizard-opt-title">Сила / SBD</span>
          <span class="wizard-opt-desc">Пауэрлифтинг, рост 1ПМ в жиме, приседе, тяге</span>
        </div>
        <div class="wizard-option ${wizardState.goal==='recomp'?'active':''}" onclick="selectWizardOption('goal', 'recomp', this)">
          <span class="wizard-opt-icon">⚖️</span>
          <span class="wizard-opt-title">Рекомпозиция</span>
          <span class="wizard-opt-desc">Сжигание жира с сохранением мышечной массы</span>
        </div>
        <div class="wizard-option ${wizardState.goal==='endurance'?'active':''}" onclick="selectWizardOption('goal', 'endurance', this)">
          <span class="wizard-opt-icon">⚡</span>
          <span class="wizard-opt-title">Выносливость</span>
          <span class="wizard-opt-desc">Плотный тренинг, рельеф и турники/брусья</span>
        </div>
      </div>

      <div class="wizard-step-title">📅 2. Тренировочных дней в неделю</div>
      <div class="wizard-options-grid" style="grid-template-columns: repeat(5, 1fr);">
        ${[2, 3, 4, 5, 6].map(d => `
          <div class="wizard-option ${wizardState.days===d?'active':''}" style="align-items:center; padding:10px 4px;" onclick="wizardState.days=${d}; wizardState.split='auto'; renderProgramTab();">
            <span style="font-size:1.2rem; font-weight:800;">${d}</span>
            <span style="font-size:0.65rem; color:var(--text2);">${d===4?'Оптим.':'дня'}</span>
          </div>
        `).join('')}
      </div>

      <div class="wizard-step-title">🧬 3. Структура сплита (Методика)</div>
      <div class="wizard-options-grid" style="grid-template-columns: 1fr;">
        ${splits.map(s => `
          <div class="wizard-option ${wizardState.split===s.id?'active':''}" style="padding:10px 14px;" onclick="selectWizardOption('split', '${s.id}', this)">
            <span class="wizard-opt-title">${s.name}</span>
            <span class="wizard-opt-desc">${s.desc}</span>
          </div>
        `).join('')}
      </div>

      <div class="wizard-step-title">🚀 4. Уровень подготовки</div>
      <div class="wizard-options-grid">
        <div class="wizard-option ${wizardState.level==='beginner'?'active':''}" onclick="selectWizardOption('level', 'beginner', this)">
          <span class="wizard-opt-icon">🌱</span>
          <span class="wizard-opt-title">Новичок (&lt; 1 года)</span>
          <span class="wizard-opt-desc">Линейная прогрессия весов (+2.5 кг/нед)</span>
        </div>
        <div class="wizard-option ${wizardState.level==='intermediate'?'active':''}" onclick="selectWizardOption('level', 'intermediate', this)">
          <span class="wizard-opt-icon">🚀</span>
          <span class="wizard-opt-title">Средний (1-3 года)</span>
          <span class="wizard-opt-desc">Волновая периодизация + RPE авторегуляция</span>
        </div>
        <div class="wizard-option ${wizardState.level==='advanced'?'active':''}" onclick="selectWizardOption('level', 'advanced', this)">
          <span class="wizard-opt-icon">👑</span>
          <span class="wizard-opt-title">Опытный (&gt; 3 лет)</span>
          <span class="wizard-opt-desc">Блоковая периодизация и делоад-циклы</span>
        </div>
      </div>

      <div class="wizard-step-title">⚖️ 5. Твои силовые максимумы (1ПМ, кг)</div>
      <p style="font-size:0.72rem; color:var(--accent3); margin-top:-6px; margin-bottom:10px;">✨ Автоматически подтянуты твои лучшие рекорды из дневника:</p>
      
      <div style="display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:8px; margin-bottom:16px; width:100%; box-sizing:border-box;">
        <div style="background:rgba(255,255,255,0.04); border:1px solid var(--border); border-radius:12px; padding:10px 4px; text-align:center; min-width:0;">
          <div style="font-size:0.72rem; color:var(--text2); font-weight:700; margin-bottom:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">💪 Жим лёжа</div>
          <input type="number" id="wiz-bench" class="glass-input" value="${defBench}" step="2.5" style="width:100%; box-sizing:border-box; min-width:0; padding:8px 2px; text-align:center; font-weight:800; font-size:1.05rem; background:rgba(0,0,0,0.3); border:1px solid rgba(124,92,255,0.4); border-radius:8px; color:var(--text);"/>
          <span style="font-size:0.65rem; color:var(--text2); margin-top:2px; display:block;">1ПМ (кг)</span>
        </div>
        <div style="background:rgba(255,255,255,0.04); border:1px solid var(--border); border-radius:12px; padding:10px 4px; text-align:center; min-width:0;">
          <div style="font-size:0.72rem; color:var(--text2); font-weight:700; margin-bottom:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">🦵 Присед</div>
          <input type="number" id="wiz-squat" class="glass-input" value="${defSquat}" step="2.5" style="width:100%; box-sizing:border-box; min-width:0; padding:8px 2px; text-align:center; font-weight:800; font-size:1.05rem; background:rgba(0,0,0,0.3); border:1px solid rgba(124,92,255,0.4); border-radius:8px; color:var(--text);"/>
          <span style="font-size:0.65rem; color:var(--text2); margin-top:2px; display:block;">1ПМ (кг)</span>
        </div>
        <div style="background:rgba(255,255,255,0.04); border:1px solid var(--border); border-radius:12px; padding:10px 4px; text-align:center; min-width:0;">
          <div style="font-size:0.72rem; color:var(--text2); font-weight:700; margin-bottom:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">🔗 Тяга</div>
          <input type="number" id="wiz-dead" class="glass-input" value="${defDead}" step="2.5" style="width:100%; box-sizing:border-box; min-width:0; padding:8px 2px; text-align:center; font-weight:800; font-size:1.05rem; background:rgba(0,0,0,0.3); border:1px solid rgba(124,92,255,0.4); border-radius:8px; color:var(--text);"/>
          <span style="font-size:0.65rem; color:var(--text2); margin-top:2px; display:block;">1ПМ (кг)</span>
        </div>
      </div>

      <button class="btn-primary" onclick="generateProgramFromWizard()" style="margin-top: 6px; padding: 14px; font-size: 0.95rem; font-weight:800; width:100%;">
        ✨ Сгенерировать адаптированную программу
      </button>
    </div>
  `;
}

function generateProgramFromWizard() {
  const benchInput = $('wiz-bench');
  const squatInput = $('wiz-squat');
  const deadInput = $('wiz-dead');

  const user1rm = {
    bench_press: parseFloat(benchInput ? benchInput.value : 68.0) || 68.0,
    squat: parseFloat(squatInput ? squatInput.value : 92.5) || 92.5,
    deadlift: parseFloat(deadInput ? deadInput.value : 100.0) || 100.0
  };

  const program = generateScientificProgram({
    goal: wizardState.goal,
    level: wizardState.level,
    days: wizardState.days,
    equipment: wizardState.equipment,
    split: wizardState.split || 'auto',
    user1rm
  });

  DB.program = program;
  saveData();
  showToast('🎉 Научная программа успешно создана!');
  renderProgramTab();
  renderDashboard();
}

function generateScientificProgram({ goal, level, days, equipment, split, user1rm }) {
  const daysCount = parseInt(days) || 4;
  let splitName = '';
  let splitType = split || 'auto';
  let daysLayout = [];

  const analysis = analyzeAthleteProfileJS(DB.workouts || [], user1rm);

  // Auto split selector based on goal and analysis
  if (splitType === 'auto') {
    if (daysCount === 2) {
      splitType = 'full_body_2d';
    } else if (daysCount === 3) {
      if (goal === 'strength') splitType = 'sbd_3d';
      else if (goal === 'hypertrophy') splitType = analysis.specialization === 'chest_focus' ? 'arnold_3d' : 'ppl_3d';
      else splitType = 'ppl_3d';
    } else if (daysCount === 4) {
      splitType = goal === 'strength' ? 'sbd_power_4d' : 'upper_lower_4d';
    } else if (daysCount === 5) {
      splitType = 'upper_lower_ppl_5d';
    } else {
      splitType = 'ppl_6d';
    }
  }

  const round25 = w => Math.max(10.0, Math.round(w / 2.5) * 2.5);
  const createEx = (key, sets, reps, rpe) => {
    const ex = EXERCISE_CATALOG[key] || { name: key, muscle: 'Основная', category: 'other', rest: 120, tip: '' };
    let workW = 0.0;
    const factor = goal === 'strength' ? 0.82 : 0.75;
    const bench = parseFloat(user1rm.bench_press) || 68.0;
    const squat = parseFloat(user1rm.squat) || 92.5;
    const dead = parseFloat(user1rm.deadlift) || 100.0;

    if (key === 'bench_press') workW = round25(bench * factor);
    else if (key === 'squat') workW = round25(squat * factor);
    else if (key === 'deadlift') workW = round25(dead * (goal === 'strength' ? 0.82 : 0.775));
    else if (key === 'overhead_press') workW = round25(bench * 0.58);
    else if (key === 'barbell_row') workW = round25(bench * 0.70);
    else if (key === 'incline_dumbbell_press') workW = Math.max(10.0, Math.round(((bench * 0.50) / 2) / 2.0) * 2.0);
    else if (key === 'romanian_deadlift') workW = round25(dead * 0.65);
    else if (key === 'leg_press') workW = Math.round(squat * 1.25 / 5.0) * 5.0;
    else if (key === 'lat_pulldown') workW = 42.5;
    else if (key === 'seated_cable_row') workW = 45.0;
    else if (key === 'lateral_raises') workW = 8.0;
    else if (key === 'barbell_biceps_curl') workW = Math.max(15.0, round25(bench * 0.38));
    else if (key === 'tricep_rope_pushdown' || key === 'skull_crushers') workW = Math.max(15.0, round25(bench * 0.35));

    if (goal === 'strength' && (reps === '6-8' || reps === '5-6')) reps = '3-5';

    const isMainBase = (key === 'bench_press' || key === 'squat' || key === 'deadlift');

    return {
      key,
      name: ex.name,
      muscle_group: ex.muscle,
      category: ex.category,
      sets,
      reps,
      target_rpe: rpe,
      target_rir: Math.max(0, Math.round(10 - rpe)),
      rest_sec: goal === 'strength' ? (ex.rest || 120) + 30 : (ex.rest || 120),
      base_weight: workW,
      working_weight: workW,
      warmup_ladder: (workW > 0 && isMainBase) ? getWarmupLadder(key, workW) : [],
      pubmed_tip: ex.tip || ''
    };
  };

  if (splitType === 'recovery_3d') {
    splitName = 'Anti-Overtraining Split: Верх / Низ / Тяга+Плечи (3 дня)';
    daysLayout = [
      { day_number: 1, title: 'День 1: Верх (Грудь + Спина + Плечи + Трицепс)', day_of_week: 'Понедельник', focus: 'Upper Body / 0% осевой нагрузки на позвоночник', exercises: [createEx('bench_press', 3, '6-8', 7.5), createEx('barbell_row', 3, '8-10', 7.5), createEx('incline_dumbbell_press', 3, '8-10', 8.0), createEx('lat_pulldown', 3, '8-12', 8.0), createEx('lateral_raises', 3, '12-15', 8.5), createEx('tricep_rope_pushdown', 2, '10-12', 8.5)] },
      { day_number: 2, title: 'День 2: Низ (Присед + Квадрицепс + Бицепс бедра + Пресс)', day_of_week: 'Среда', focus: 'Lower Squat & Quads / Верх полностью отдыхает', exercises: [createEx('squat', 3, '5-6', 7.5), createEx('leg_press', 3, '8-10', 8.0), createEx('leg_curl', 3, '10-12', 8.0), createEx('calf_raises', 3, '12-15', 8.5), createEx('hanging_leg_raises', 3, '12-15', 8.0)] },
      { day_number: 3, title: 'День 3: Силовая тяга + Плечи + Бицепс', day_of_week: 'Пятница', focus: 'Deadlift & Shoulders / Задняя цепь и плечи', exercises: [createEx('deadlift', 3, '4-5', 7.5), createEx('overhead_press', 3, '6-8', 7.5), createEx('seated_cable_row', 3, '10-12', 8.0), createEx('face_pulls', 3, '12-15', 8.5), createEx('barbell_biceps_curl', 3, '8-12', 8.5)] }
    ];
  } else if (splitType === 'sbd_3d') {
    splitName = 'SBD Троеборье: Присед / Жим / Тяга + Подсобка (3 дня)';
    daysLayout = [
      { day_number: 1, title: 'День 1: Squat Power (Присед + Квадрицепс + Кор)', day_of_week: 'Понедельник', focus: 'Squat Strength & Quads', exercises: [createEx('squat', 4, '3-5', 8.0), createEx('romanian_deadlift', 3, '6-8', 7.5), createEx('leg_press', 3, '8-10', 8.0), createEx('calf_raises', 4, '12-15', 8.5), createEx('hanging_leg_raises', 3, '12-15', 8.0)] },
      { day_number: 2, title: 'День 2: Bench Power (Жим лёжа + Плечи + Трицепс)', day_of_week: 'Среда', focus: 'Bench Strength & Upper Push', exercises: [createEx('bench_press', 4, '3-5', 8.0), createEx('incline_dumbbell_press', 3, '6-8', 8.0), createEx('overhead_press', 3, '6-8', 7.5), createEx('close_grip_bench_press', 3, '6-8', 8.0), createEx('lateral_raises', 4, '12-15', 8.5)] },
      { day_number: 3, title: 'День 3: Deadlift Power (Становая тяга + Спина + Бицепс)', day_of_week: 'Пятница', focus: 'Deadlift Strength & Posterior Pull', exercises: [createEx('deadlift', 3, '3-5', 8.0), createEx('barbell_row', 4, '5-6', 7.5), createEx('lat_pulldown', 3, '8-10', 8.0), createEx('face_pulls', 3, '12-15', 8.5), createEx('barbell_biceps_curl', 3, '8-10', 8.0)] }
    ];
  } else if (splitType === 'arnold_3d') {
    splitName = 'Arnold Split: Грудь+Спина / Плечи+Руки / Ноги (3 дня)';
    daysLayout = [
      { day_number: 1, title: 'День 1: Chest & Back (Грудь + Спина Антагонисты)', day_of_week: 'Понедельник', focus: 'Chest & Back Hypertrophy', exercises: [createEx('bench_press', 4, '6-8', 7.5), createEx('barbell_row', 4, '6-8', 7.5), createEx('incline_dumbbell_press', 3, '8-12', 8.0), createEx('lat_pulldown', 3, '8-12', 8.0), createEx('dips_chest', 3, '8-12', 8.0)] },
      { day_number: 2, title: 'День 2: Shoulders & Arms (Плечи + Бицепс + Трицепс)', day_of_week: 'Среда', focus: 'Delts & Arms Pump', exercises: [createEx('overhead_press', 4, '6-8', 7.5), createEx('lateral_raises', 4, '12-15', 8.5), createEx('barbell_biceps_curl', 3, '8-12', 8.0), createEx('skull_crushers', 3, '8-12', 8.0), createEx('hammer_curls', 3, '10-12', 8.5), createEx('tricep_rope_pushdown', 3, '10-15', 8.5)] },
      { day_number: 3, title: 'День 3: Legs & Abs (Квадрицепс + Бицепс бедра + Пресс)', day_of_week: 'Пятница', focus: 'Legs & Core Volume', exercises: [createEx('squat', 4, '6-8', 7.5), createEx('romanian_deadlift', 3, '8-10', 7.5), createEx('leg_press', 3, '10-12', 8.0), createEx('leg_curl', 3, '10-12', 8.5), createEx('calf_raises', 4, '12-15', 8.5), createEx('hanging_leg_raises', 3, '12-15', 8.0)] }
    ];
  } else if (splitType === 'ppl_3d') {
    splitName = 'Push / Pull / Legs (3 дня — Доказательный MAV объём)';
    daysLayout = [
      { day_number: 1, title: 'День 1: Push (Грудь, Плечи, Трицепс)', day_of_week: 'Понедельник', focus: 'Push Compound & Stretch', exercises: [createEx('bench_press', 4, '6-8', 7.5), createEx('overhead_press', 3, '8-10', 8.0), createEx('incline_dumbbell_press', 3, '8-12', 8.0), createEx('lateral_raises', 4, '12-15', 8.5), createEx('tricep_rope_pushdown', 3, '10-12', 8.5)] },
      { day_number: 2, title: 'День 2: Pull (Спина, Задняя дельта, Бицепс)', day_of_week: 'Среда', focus: 'Pull Compound & Width', exercises: [createEx('deadlift', 3, '4-5', 8.0), createEx('barbell_row', 4, '6-8', 7.5), createEx('lat_pulldown', 3, '8-12', 8.0), createEx('face_pulls', 3, '12-15', 8.5), createEx('barbell_biceps_curl', 3, '8-12', 8.0)] },
      { day_number: 3, title: 'День 3: Legs (Квадрицепсы, Бицепс бедра, Икры, Пресс)', day_of_week: 'Пятница', focus: 'Legs & Core Power', exercises: [createEx('squat', 4, '6-8', 7.5), createEx('romanian_deadlift', 3, '8-10', 7.5), createEx('leg_press', 3, '10-12', 8.0), createEx('leg_curl', 3, '12-15', 8.5), createEx('calf_raises', 4, '12-15', 8.5), createEx('hanging_leg_raises', 3, '12-15', 8.0)] }
    ];
  } else if (splitType === 'sbd_power_4d') {
    splitName = 'SBD Powerbuilding (4 дня — Сила 1ПМ + Рельеф)';
    daysLayout = [
      { day_number: 1, title: 'День 1: Squat & Quad Focus', day_of_week: 'Понедельник', focus: 'Squat 1RM Peak', exercises: [createEx('squat', 4, '3-5', 8.0), createEx('leg_press', 3, '8-10', 8.0), createEx('leg_curl', 3, '10-12', 8.5), createEx('calf_raises', 4, '12-15', 8.5), createEx('hanging_leg_raises', 3, '12-15', 8.0)] },
      { day_number: 2, title: 'День 2: Bench & Chest Strength', day_of_week: 'Вторник', focus: 'Bench 1RM Peak', exercises: [createEx('bench_press', 4, '3-5', 8.0), createEx('incline_dumbbell_press', 3, '6-8', 8.0), createEx('barbell_row', 4, '6-8', 7.5), createEx('close_grip_bench_press', 3, '6-8', 8.0), createEx('barbell_biceps_curl', 3, '8-12', 8.0)] },
      { day_number: 3, title: 'День 3: Deadlift & Back Power', day_of_week: 'Четверг', focus: 'Deadlift 1RM Peak', exercises: [createEx('deadlift', 3, '3-5', 8.0), createEx('pullups', 3, '6-8', 8.0), createEx('seated_cable_row', 3, '8-10', 8.0), createEx('face_pulls', 3, '12-15', 8.5), createEx('hammer_curls', 3, '10-12', 8.5)] },
      { day_number: 4, title: 'День 4: Overhead Press & Arms Hypertrophy', day_of_week: 'Пятница', focus: 'Shoulders & Arms Hypertrophy', exercises: [createEx('overhead_press', 4, '5-6', 7.5), createEx('dips_chest', 3, '8-10', 8.0), createEx('lateral_raises', 4, '12-15', 8.5), createEx('skull_crushers', 3, '8-12', 8.0), createEx('incline_dumbbell_curl', 3, '8-12', 8.0)] }
    ];
  } else if (splitType === 'ppl_upper_4d') {
    splitName = 'Push / Pull / Legs + Upper (4 дня)';
    daysLayout = [
      { day_number: 1, title: 'День 1: Push (Грудь, Плечи, Трицепс)', day_of_week: 'Понедельник', focus: 'Heavy Push', exercises: [createEx('bench_press', 4, '5-6', 7.5), createEx('overhead_press', 3, '8-10', 8.0), createEx('incline_dumbbell_press', 3, '8-10', 8.0), createEx('lateral_raises', 4, '12-15', 8.5), createEx('tricep_rope_pushdown', 3, '10-12', 8.5)] },
      { day_number: 2, title: 'День 2: Pull (Спина, Задняя дельта, Бицепс)', day_of_week: 'Вторник', focus: 'Heavy Pull', exercises: [createEx('deadlift', 3, '4-5', 8.0), createEx('barbell_row', 4, '6-8', 7.5), createEx('lat_pulldown', 3, '8-12', 8.0), createEx('face_pulls', 3, '12-15', 8.5), createEx('barbell_biceps_curl', 3, '8-12', 8.0)] },
      { day_number: 3, title: 'День 3: Legs (Присед, Квадрицепс, Бицепс бедра)', day_of_week: 'Четверг', focus: 'Legs Power', exercises: [createEx('squat', 4, '6-8', 7.5), createEx('romanian_deadlift', 3, '8-10', 7.5), createEx('leg_press', 3, '10-12', 8.0), createEx('calf_raises', 4, '12-15', 8.5), createEx('hanging_leg_raises', 3, '12-15', 8.0)] },
      { day_number: 4, title: 'День 4: Upper Volume (Плечи, Руки, Памп верха)', day_of_week: 'Пятница', focus: 'Upper Hypertrophy Pump', exercises: [createEx('dips_chest', 3, '8-12', 8.0), createEx('pullups', 3, '6-10', 8.0), createEx('seated_cable_row', 3, '10-12', 8.0), createEx('lateral_raises', 4, '12-15', 8.5), createEx('incline_dumbbell_curl', 3, '10-12', 8.5), createEx('skull_crushers', 3, '10-12', 8.5)] }
    ];
  } else if (splitType === 'upper_lower_4d') {
    splitName = 'Upper / Lower A & B (4 дня — Золотой стандарт PubMed)';
    daysLayout = [
      { day_number: 1, title: 'День 1: Верх А (Сила / Грудь + Спина)', day_of_week: 'Понедельник', focus: 'Upper Strength & Heavy Compound', exercises: [createEx('bench_press', 4, '5-6', 7.5), createEx('barbell_row', 4, '6-8', 7.5), createEx('incline_dumbbell_press', 3, '8-10', 8.0), createEx('lat_pulldown', 3, '8-12', 8.0), createEx('lateral_raises', 4, '12-15', 8.5), createEx('skull_crushers', 3, '8-12', 8.0), createEx('barbell_biceps_curl', 3, '8-12', 8.0)] },
      { day_number: 2, title: 'День 2: Низ А (Присед + Квадрицепс)', day_of_week: 'Вторник', focus: 'Lower Squat & Quad Emphasis', exercises: [createEx('squat', 4, '5-6', 7.5), createEx('romanian_deadlift', 3, '8-10', 7.5), createEx('leg_press', 3, '10-12', 8.0), createEx('leg_curl', 3, '10-12', 8.5), createEx('calf_raises', 4, '12-15', 8.5), createEx('hanging_leg_raises', 3, '12-15', 8.0)] },
      { day_number: 3, title: 'День 3: Верх B (Плечи + Спина + Руки)', day_of_week: 'Четверг', focus: 'Upper Hypertrophy & Delts', exercises: [createEx('overhead_press', 4, '6-8', 7.5), createEx('pullups', 3, '6-10', 8.0), createEx('dips_chest', 3, '8-12', 8.0), createEx('seated_cable_row', 3, '10-12', 8.0), createEx('face_pulls', 3, '12-15', 8.5), createEx('incline_dumbbell_curl', 3, '10-12', 8.5), createEx('tricep_rope_pushdown', 3, '10-12', 8.5)] },
      { day_number: 4, title: 'День 4: Низ B (Становая тяга + Задняя цепь)', day_of_week: 'Пятница', focus: 'Posterior Chain & Deadlift', exercises: [createEx('deadlift', 3, '3-5', 8.0), createEx('bulgarian_split_squat', 3, '8-10', 8.0), createEx('leg_extension', 3, '12-15', 8.5), createEx('leg_curl', 3, '12-15', 8.5), createEx('calf_raises', 4, '12-15', 8.5), createEx('cable_woodchopper', 3, '12-15', 8.0)] }
    ];
  } else if (splitType === 'upper_lower_ppl_5d') {
    splitName = 'Upper / Lower + Push / Pull / Legs (5 дней)';
    daysLayout = [
      { day_number: 1, title: 'День 1: Upper Power', day_of_week: 'Понедельник', focus: 'Upper Strength', exercises: [createEx('bench_press', 4, '5', 7.5), createEx('barbell_row', 4, '6', 7.5), createEx('overhead_press', 3, '6', 8.0), createEx('skull_crushers', 3, '8', 8.0), createEx('barbell_biceps_curl', 3, '8', 8.0)] },
      { day_number: 2, title: 'День 2: Lower Power', day_of_week: 'Вторник', focus: 'Lower Strength', exercises: [createEx('squat', 4, '5', 7.5), createEx('romanian_deadlift', 3, '6', 7.5), createEx('leg_press', 3, '8', 8.0), createEx('calf_raises', 4, '12', 8.5), createEx('hanging_leg_raises', 3, '12', 8.0)] },
      { day_number: 3, title: 'День 3: Push Hypertrophy', day_of_week: 'Четверг', focus: 'Chest & Delts', exercises: [createEx('incline_dumbbell_press', 4, '8-12', 8.0), createEx('dips_chest', 3, '8-12', 8.0), createEx('lateral_raises', 4, '12-15', 8.5), createEx('tricep_rope_pushdown', 3, '10-15', 8.5)] },
      { day_number: 4, title: 'День 4: Pull Hypertrophy', day_of_week: 'Пятница', focus: 'Back & Biceps', exercises: [createEx('deadlift', 3, '4', 8.0), createEx('lat_pulldown', 4, '8-12', 8.0), createEx('seated_cable_row', 3, '10-12', 8.0), createEx('face_pulls', 3, '12-15', 8.5), createEx('incline_dumbbell_curl', 3, '10-12', 8.5)] },
      { day_number: 5, title: 'День 5: Legs Hypertrophy', day_of_week: 'Суббота', focus: 'Quads & Hamstrings', exercises: [createEx('bulgarian_split_squat', 3, '8-12', 8.0), createEx('leg_extension', 3, '12-15', 8.5), createEx('leg_curl', 3, '12-15', 8.5), createEx('calf_raises', 4, '15', 8.5), createEx('cable_woodchopper', 3, '15', 8.0)] }
    ];
  } else if (splitType === 'bro_split_5d') {
    splitName = 'Classic Bro Split (5 дней: Грудь/Спина/Плечи/Руки/Ноги)';
    daysLayout = [
      { day_number: 1, title: 'День 1: Chest', day_of_week: 'Понедельник', focus: 'Chest Obliteration', exercises: [createEx('bench_press', 4, '6-8', 7.5), createEx('incline_dumbbell_press', 4, '8-10', 8.0), createEx('dips_chest', 3, '8-12', 8.0), createEx('pushups', 3, '12-15', 8.5)] },
      { day_number: 2, title: 'День 2: Back', day_of_week: 'Вторник', focus: 'Back Width & Thickness', exercises: [createEx('deadlift', 3, '4-5', 8.0), createEx('barbell_row', 4, '6-8', 7.5), createEx('pullups', 3, '6-10', 8.0), createEx('lat_pulldown', 3, '10-12', 8.0), createEx('face_pulls', 3, '12-15', 8.5)] },
      { day_number: 3, title: 'День 3: Shoulders', day_of_week: 'Среда', focus: '3D Delts', exercises: [createEx('overhead_press', 4, '6-8', 7.5), createEx('lateral_raises', 5, '12-15', 8.5), createEx('face_pulls', 3, '12-15', 8.5), createEx('hanging_leg_raises', 3, '12-15', 8.0)] },
      { day_number: 4, title: 'День 4: Legs', day_of_week: 'Пятница', focus: 'Legs Mass', exercises: [createEx('squat', 4, '6-8', 7.5), createEx('romanian_deadlift', 3, '8-10', 7.5), createEx('leg_press', 3, '10-12', 8.0), createEx('leg_curl', 3, '12-15', 8.5), createEx('calf_raises', 4, '15', 8.5)] },
      { day_number: 5, title: 'День 5: Arms', day_of_week: 'Суббота', focus: 'Arms Hypertrophy', exercises: [createEx('barbell_biceps_curl', 4, '8-10', 8.0), createEx('skull_crushers', 4, '8-10', 8.0), createEx('incline_dumbbell_curl', 3, '10-12', 8.5), createEx('tricep_rope_pushdown', 3, '10-12', 8.5), createEx('hammer_curls', 3, '10-12', 8.5)] }
    ];
  } else {
    // Default 3d fullbody fallback
    splitName = 'Full Body A / B / C (3 дня — Высокочастотный стимул)';
    daysLayout = [
      { day_number: 1, title: 'День 1: Full Body A (Присед + Жим)', day_of_week: 'Понедельник', focus: 'Heavy Compound Push', exercises: [createEx('squat', 4, '5-6', 7.5), createEx('bench_press', 4, '5-6', 7.5), createEx('barbell_row', 4, '6-8', 7.5), createEx('lateral_raises', 3, '12-15', 8.0), createEx('skull_crushers', 3, '8-12', 8.0), createEx('hanging_leg_raises', 3, '12-15', 8.0)] },
      { day_number: 2, title: 'День 2: Full Body B (Тяга + Плечи)', day_of_week: 'Среда', focus: 'Pull & Overhead Press', exercises: [createEx('deadlift', 3, '4-5', 8.0), createEx('overhead_press', 4, '6-8', 7.5), createEx('lat_pulldown', 3, '8-12', 8.0), createEx('incline_dumbbell_press', 3, '8-10', 8.0), createEx('barbell_biceps_curl', 3, '8-12', 8.0), createEx('calf_raises', 4, '12-15', 8.5)] },
      { day_number: 3, title: 'День 3: Full Body C (Объем + Руки)', day_of_week: 'Пятница', focus: 'Legs & Upper Hypertrophy', exercises: [createEx('romanian_deadlift', 3, '8-10', 7.5), createEx('leg_press', 3, '10-12', 8.0), createEx('dips_chest', 3, '8-12', 8.0), createEx('pullups', 3, '6-10', 8.0), createEx('face_pulls', 3, '12-15', 8.5), createEx('hammer_curls', 3, '10-12', 8.5)] }
    ];
  }

  // Calculate weekly volume
  const weeklyVol = {};
  daysLayout.forEach(d => {
    d.exercises.forEach(ex => {
      weeklyVol[ex.muscle_group] = (weeklyVol[ex.muscle_group] || 0) + ex.sets;
    });
  });

  // 6-Week Wave Matrix
  const matrixWeeks = [
    { week: 1, phase: 'Вкатывание', pct: 75, rpe: 7.0, desc: 'Адаптация связок, техника' },
    { week: 2, phase: 'Накопление', pct: 80, rpe: 7.5, desc: 'Рост тоннажа и выносливости' },
    { week: 3, phase: 'Интенсификация', pct: 85, rpe: 8.0, desc: 'Повышение рабочих весов' },
    { week: 4, phase: 'Пик объема', pct: 88, rpe: 8.5, desc: 'Пиковый стимул гипертрофии' },
    { week: 5, phase: 'Рекорды (PR)', pct: 93, rpe: 9.0, desc: 'Установка личных рекордов' },
    { week: 6, phase: 'Deload (Разгрузка)', pct: 55, rpe: 5.0, desc: 'Сброс утомления ЦНС' }
  ];

  const waveMatrix = matrixWeeks.map(w => {
    return {
      week_number: w.week,
      phase: w.phase,
      intensity_pct: w.pct,
      target_rpe: w.rpe,
      desc: w.desc,
      completed: false
    };
  });

  return {
    program_id: `prog_${goal}_${daysCount}d_${splitType}_${level}`,
    title: `Научная программа: ${splitName}`,
    goal,
    level,
    days_per_week: daysCount,
    split_type: splitType,
    split_name: splitName,
    athlete_diagnosis: analysis,
    current_week: 1,
    weekly_volume_sets: weeklyVol,
    days: daysLayout,
    wave_matrix: waveMatrix
  };
}

function setProgramWeek(weekNum) {
  if (!hasValidProgram(DB.program)) return;
  DB.program.current_week = weekNum;

  // Scale weights for new week's intensity
  const matrix = DB.program.wave_matrix || [];
  const currentWeekInfo = matrix.find(m => m.week_number === weekNum);
  const intensityFactor = currentWeekInfo ? (currentWeekInfo.intensity_pct / 75.0) : 1.0;

  DB.program.days.forEach(day => {
    day.exercises.forEach(ex => {
      if (ex.base_weight && ex.base_weight > 0) {
        const scaled = Math.round((ex.base_weight * intensityFactor) / 2.5) * 2.5;
        ex.working_weight = Math.max(20.0, scaled);
        ex.warmup_ladder = getWarmupLadder(ex.key || 'bench_press', ex.working_weight);
      }
      if (currentWeekInfo) {
        ex.target_rpe = currentWeekInfo.target_rpe;
        ex.target_rir = Math.max(0, Math.round(10 - currentWeekInfo.target_rpe));
      }
    });
  });

  saveData();
  showToast(`📈 Переключено на Неделю ${weekNum} (${currentWeekInfo ? currentWeekInfo.phase : ''})!`);
  renderProgramTab();
  renderDashboard();
}

function renderProgramTab() {
  const container = $('program-container');
  const rebBtn = $('prog-rebuild-btn');
  if (!container) return;

  if (!hasValidProgram(DB.program)) {
    if (rebBtn) rebBtn.style.display = 'none';
    container.innerHTML = renderProgramWizardHTML();
  } else {
    if (rebBtn) rebBtn.style.display = 'block';
    container.innerHTML = renderActiveProgramHTML();
  }
}

function renderActiveProgramHTML() {
  if (!hasValidProgram(DB.program)) return renderProgramWizardHTML();
  const p = DB.program;
  if (selectedProgramDay >= p.days.length) selectedProgramDay = 0;
  const currentWeek = p.current_week || 1;
  const day = p.days[selectedProgramDay] || p.days[0];
  if (!day) return renderProgramWizardHTML();

  const gName = p.goal === 'hypertrophy' ? '💪 Гипертрофия' : p.goal === 'strength' ? '🏋️ Сила (SBD)' : p.goal === 'recomp' ? '⚖️ Рекомпозиция' : '⚡ Выносливость';
  const lName = p.level === 'beginner' ? '🌱 Новичок' : p.level === 'advanced' ? '👑 Опытный' : '🚀 Средний';

  return `
    <div class="prog-hero-card glass">
      <div class="prog-hero-header">
        <div>
          <div class="prog-badge-row">
            <span class="badge" style="background:rgba(124,92,255,0.25); color:#c4b5fd; border:1px solid rgba(124,92,255,0.4);">${gName}</span>
            <span class="badge" style="background:rgba(0,229,200,0.2); color:#5eead4; border:1px solid rgba(0,229,200,0.35);">${lName}</span>
            <span class="badge" style="background:rgba(255,255,255,0.1);">${p.days_per_week} дн/нед</span>
          </div>
          <h2 class="prog-hero-title">${p.split_name}</h2>
        </div>
      </div>
      
      ${p.athlete_diagnosis && p.athlete_diagnosis.recommendation ? `
        <div style="margin-top:10px; padding:8px 12px; background:rgba(124,92,255,0.12); border-left:3px solid var(--accent); border-radius:6px; font-size:0.75rem; color:#ddd6fe;">
          <strong>🔍 Персональная адаптация ИИ:</strong> ${p.athlete_diagnosis.recommendation}
        </div>
      ` : ''}
      
      <!-- Week Stepper Chips -->
      <div style="margin-top:12px;">
        <div style="font-size:0.75rem; color:var(--text2); margin-bottom:6px; display:flex; justify-content:space-between; align-items:center;">
          <span>📈 Текущая неделя мезоцикла:</span>
          <button class="chip" style="padding:2px 8px; font-size:0.7rem;" onclick="openMatrixModal()">📊 Вся матрица</button>
        </div>
        <div style="display:flex; gap:5px; overflow-x:auto; padding-bottom:4px;">
          ${[1, 2, 3, 4, 5, 6].map(w => `
            <button class="chip ${w===currentWeek?'active':''}" style="flex:1; padding:6px 4px; font-size:0.72rem; font-weight:700; text-align:center;" onclick="setProgramWeek(${w})">
              Нед ${w} ${w===5?'🔥':w===6?'🍃':''}
            </button>
          `).join('')}
        </div>
      </div>
    </div>

    <!-- Volume Distribution -->
    <div class="volume-card glass">
      <div style="font-size:0.85rem; font-weight:700; margin-bottom:8px;">📊 Недельный объём (Сеты vs Schoenfeld MAV)</div>
      ${Object.entries(p.weekly_volume_sets || {}).slice(0, 5).map(([m, sets]) => {
        const pct = Math.min(100, Math.round((sets / 18) * 100));
        return `
          <div class="volume-bar-row">
            <div class="volume-bar-label">
              <span>${m}</span>
              <strong>${sets} подх / нед</strong>
            </div>
            <div class="volume-bar-track">
              <div class="volume-bar-fill" style="width: ${pct}%;"></div>
            </div>
          </div>
        `;
      }).join('')}
    </div>

    <!-- Day Chips Carousel -->
    <div class="section-title">📅 Выбери день тренировки</div>
    <div class="day-chips-scroll">
      ${p.days.map((d, i) => `
        <button class="day-chip ${i===selectedProgramDay?'active':''}" onclick="selectProgramDay(${i})">
          ${d.day_of_week ? d.day_of_week.slice(0,2) : `Д${i+1}`}: ${d.title.split(':')[1] || d.title}
        </button>
      `).join('')}
    </div>

    <!-- Active Day Exercises -->
    <div class="glass" style="padding:16px; margin-bottom:16px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:12px;">
        <div>
          <h3 style="font-size:1.05rem; font-weight:800;">${day.title}</h3>
          <p style="font-size:0.75rem; color:var(--text2);">${day.focus || 'Силовой блок'}</p>
        </div>
        <button class="btn-primary" style="padding:8px 14px; font-size:0.78rem;" onclick="launchWorkoutFromProgram(${selectedProgramDay})">
          ▶️ Начать
        </button>
      </div>

      <div class="plan-exercises-list">
        ${(day.exercises || []).map((ex, idx) => {
          const hasWarmup = ex.warmup_ladder && ex.warmup_ladder.length > 0;
          return `
            <div class="plan-ex-card">
              <div class="plan-ex-header">
                <span class="plan-ex-name">${idx + 1}. ${ex.name}</span>
                <span class="plan-ex-muscle">${ex.muscle_group}</span>
              </div>
              <div class="plan-ex-meta">
                <div class="plan-meta-item">🎯 <strong>${ex.sets}</strong> подх × <strong>${ex.reps}</strong></div>
                <div class="plan-meta-item">⚡ RPE <strong>${ex.target_rpe}</strong> (RIR ${ex.target_rir})</div>
                ${ex.working_weight > 0 ? `<div class="plan-meta-item">⚖️ <strong>${ex.working_weight} кг</strong></div>` : ''}
                <button class="timer-mini-btn" onclick="startRestTimer(${ex.rest_sec || 120}, '${ex.name}')">⏳ Отдых ${Math.round((ex.rest_sec||120)/60)}м</button>
              </div>
              
              ${hasWarmup ? `
                <div class="warmup-accordion">
                  <div class="warmup-summary" onclick="toggleWarmup('warmup-${selectedProgramDay}-${idx}')">
                    <span>🧮 Разминочная пирамида (${ex.warmup_ladder.length} шага) ▾</span>
                  </div>
                  <div class="warmup-ladder-list" id="warmup-${selectedProgramDay}-${idx}" style="display:none;">
                    ${ex.warmup_ladder.map(w => `
                      <div class="warmup-step-row">
                        <span>Шаг ${w.step}: <strong>${w.weight} кг</strong> × ${w.reps} повт.</span>
                        <small style="color:var(--text2);">${w.note}</small>
                      </div>
                    `).join('')}
                  </div>
                </div>
              ` : ''}

              ${ex.pubmed_tip ? `<div class="plan-ex-tip">💡 <em>${ex.pubmed_tip}</em></div>` : ''}
            </div>
          `;
        }).join('')}
      </div>

      <button class="btn-primary" onclick="launchWorkoutFromProgram(${selectedProgramDay})" style="width:100%; margin-top:10px;">
        ▶️ Запустить эту тренировку в Запись
      </button>
    </div>
  `;
}

function selectProgramDay(idx) {
  selectedProgramDay = idx;
  renderProgramTab();
}

function toggleWarmup(id) {
  const el = $(id);
  if (el) el.style.display = el.style.display === 'none' ? 'flex' : 'none';
}

function launchWorkoutFromProgram(dayIdx) {
  if (!hasValidProgram(DB.program)) return;
  const p = DB.program;
  if (!p.days || !p.days[dayIdx]) return;
  const day = p.days[dayIdx];
  if (!day.exercises || !day.exercises.length) return;

  const firstEx = day.exercises[0];
  workout.exercise = firstEx.name;
  workout.weight = firstEx.working_weight || 80;
  workout.reps = parseInt(firstEx.reps) || 8;
  workout.date = fmtDate(new Date());
  workout.sets = [];

  $('selected-ex-name').textContent = firstEx.name;
  $('selected-exercise-display').style.display = 'flex';
  $('weight-input').value = workout.weight;
  $('weight-slider').value = workout.weight;
  $('reps-input').value = workout.reps;

  switchTab('workout');
  showToast(`🏋️ Тренировка «${day.title.split(':')[1] || day.title}» загружена!`);
}

// ═══════════════════════ REST TIMER FLOATING HUD ═══════════════════════
let restTimerInterval = null;
let restTimerSeconds = 0;
let restTimerTotal = 0;

function startRestTimer(seconds, exName = 'Отдых') {
  stopRestTimer();
  restTimerSeconds = seconds;
  restTimerTotal = seconds;
  
  const hud = $('rest-timer-hud');
  if (hud) hud.style.display = 'flex';
  const exEl = $('timer-hud-ex');
  if (exEl) exEl.textContent = exName;
  updateRestTimerDisplay();

  restTimerInterval = setInterval(() => {
    restTimerSeconds--;
    updateRestTimerDisplay();
    if (restTimerSeconds <= 0) {
      stopRestTimer();
      playTimerBeep();
      showToast('🔔 Пора делать следующий подход!');
      if (tg && tg.HapticFeedback) {
        try { tg.HapticFeedback.notificationOccurred('success'); } catch(e){}
      }
    }
  }, 1000);
}

function updateRestTimerDisplay() {
  const m = Math.floor(restTimerSeconds / 60);
  const s = restTimerSeconds % 60;
  const str = `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  const textEl = $('timer-hud-text');
  if (textEl) textEl.textContent = str;

  const circle = $('timer-hud-circle');
  if (circle && restTimerTotal > 0) {
    const totalLength = 163;
    const progress = restTimerSeconds / restTimerTotal;
    circle.style.strokeDashoffset = totalLength * (1 - progress);
  }
}

function addRestTime(sec) {
  restTimerSeconds += sec;
  restTimerTotal += sec;
  updateRestTimerDisplay();
  showToast(`+${sec} сек к отдыху`);
}

function stopRestTimer() {
  if (restTimerInterval) {
    clearInterval(restTimerInterval);
    restTimerInterval = null;
  }
  const hud = $('rest-timer-hud');
  if (hud) hud.style.display = 'none';
}

function playTimerBeep() {
  try {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'sine';
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    gain.gain.setValueAtTime(0.3, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.5);
  } catch (e) { }
}

// ═══════════════════════ MATRIX MODAL ═══════════════════════
function openMatrixModal() {
  renderMatrixModal();
  const m = $('matrix-modal');
  if (m) m.style.display = 'flex';
}

function closeMatrixModal() {
  const m = $('matrix-modal');
  if (m) m.style.display = 'none';
}

function renderMatrixModal() {
  const content = $('matrix-modal-content');
  if (!content) return;
  if (!hasValidProgram(DB.program) || !Array.isArray(DB.program.wave_matrix)) {
    content.innerHTML = '<p class="empty-state">Сначала создайте программу в мастере.</p>';
    return;
  }

  const p = DB.program;
  content.innerHTML = p.wave_matrix.map(w => {
    const isCurrent = (p.current_week || 1) === w.week_number;
    return `
      <div class="matrix-week-card" style="${isCurrent ? 'border-color:var(--accent); background:rgba(124,92,255,0.12);' : ''}">
        <div class="matrix-week-header">
          <span class="matrix-week-title">Неделя ${w.week_number}: ${w.phase}</span>
          <span class="badge" style="background:rgba(0,229,200,0.2); color:#5eead4;">${w.intensity_pct}% 1ПМ</span>
        </div>
        <div class="matrix-week-desc">${w.desc} · Целевой RPE ${w.target_rpe}</div>
      </div>
    `;
  }).join('');
}

// ── Start ──
document.addEventListener('DOMContentLoaded', () => {
  loadChartJS(() => { loadData(); });
  selectDate('today', document.querySelector('.date-chips .chip'));
  updateE1RM();
});

