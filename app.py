import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="Workout Tracker", page_icon="💪")

# Инициализация подключения
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    admin_pass = st.secrets["ADMIN_PASSWORD"]
    supabase: Client = create_client(url, key)
except Exception:
    st.error("Настройте Secrets!")
    st.stop()

if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# --- КОНФИГ ИГР ---
GAMES_CONFIG = {
    "Игра 1: Отжимания (50)": {"ex": "Отжимания", "val": 50, "type": "count"},
    "Игра 2: Приседания (100)": {"ex": "Приседания", "val": 100, "type": "count"},
    "Игра 3: Планка (3 мин)": {"ex": "Планка", "val": "3:00", "type": "time"},
    "Игра 4: Гантели (50)": {"ex": "Гантели", "val": 50, "type": "count"},
    "Игра 5: Вис (2 мин)": {"ex": "Вис", "val": "2:00", "type": "time"}
}

# --- УТИЛИТЫ ---
def time_to_seconds(t_str):
    try:
        if ":" in str(t_str):
            m, s = map(int, str(t_str).split(":"))
            return m * 60 + s
        return int(t_str)
    except: return 0

def seconds_to_str(sec):
    m, s = abs(int(sec)) // 60, abs(int(sec)) % 60
    return f"{'-' if int(sec) < 0 else ''}{m}:{s:02d}"

def add_entry(p_id, ex_name, val, is_time=False, is_writeoff=False, silent=False):
    amount = time_to_seconds(val) if is_time else int(val)
    if amount == 0: return
    if is_writeoff: amount = -amount
    supabase.table("workout_logs").insert({
        "profile_id": p_id, "exercise_type": ex_name, "amount": amount
    }).execute()
    if not silent: st.rerun()

# --- ЗАГРУЗКА ---
profiles = supabase.table("profiles").select("*").order("name").execute().data
# Пытаемся получить типы из базы
try:
    ex_types_data = supabase.table("exercise_types").select("name, unit_type").execute().data
    ex_unit_map = {ex['name']: ex['unit_type'] for ex in ex_types_data}
except:
    ex_unit_map = {"Планка": "time", "Вис": "time"} # Запасной вариант

logs = supabase.table("workout_logs").select("amount, exercise_type, profiles(name)").execute().data

# --- SIDEBAR ---
with st.sidebar:
    st.title("⚙️ Настройки")
    
    if not st.session_state.authenticated:
        pwd = st.text_input("Пароль", type="password")
        if pwd == admin_pass:
            st.session_state.authenticated = True
            st.rerun()
    else:
        if st.button("🔴 Выйти"):
            st.session_state.authenticated = False
            st.rerun()

    if st.session_state.authenticated:
        st.divider()
        with st.expander("🎲 ИТОГИ ИГРЫ", expanded=True):
            game_choice = st.selectbox("Игра:", list(GAMES_CONFIG.keys()))
            winner_name = st.selectbox("Победитель:", [p['name'] for p in profiles])
            if st.button("🔥 Раздать долги", use_container_width=True):
                g = GAMES_CONFIG[game_choice]
                winner_id = next(p['id'] for p in profiles if p['name'] == winner_name)
                for p in profiles:
                    if p['id'] != winner_id:
                        add_entry(p['id'], g['ex'], g['val'], is_time=(g['type']=="time"), silent=True)
                st.success("Начислено!")
                st.rerun()

# --- ГЛАВНЫЙ ЭКРАН ---
st.title("💪 Долги по тренировкам")

if st.session_state.authenticated:
    st.subheader("📝 Добавить вручную")
    user_name = st.selectbox("Кому?", [p['name'] for p in profiles])
    uid = next(p['id'] for p in profiles if p['name'] == user_name)
    
    cols = st.columns(3)
    for i, name in enumerate(ex_unit_map.keys()):
        with cols[i % 3]:
            if st.button(name, use_container_width=True, key=f"btn_{name}"):
                st.session_state.active_ex = name
    
    if "active_ex" in st.session_state:
        active = st.session_state.active_ex
        u_type = ex_unit_map.get(active, "count")
        with st.container(border=True):
            val = st.text_input(f"Значение для {active}", placeholder="50 или 1:30")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("➕ Добавить", type="primary", use_container_width=True):
                    add_entry(uid, active, val, is_time=(u_type=="time"))
            with c2:
                if st.button("✅ Списать", use_container_width=True):
                    add_entry(uid, active, val, is_time=(u_type=="time"), is_writeoff=True)

st.divider()

# --- ТАБЛИЦА ---
st.subheader("📊 Текущие долги")
if logs:
    summary = {}
    for l in logs:
        name, ex, amt = l['profiles']['name'], l['exercise_type'], l['amount']
        # Чистим данные от старых багов (типа ["Отжимания","count"])
        if "[" in ex or ex == "Списание": continue
        summary.setdefault(name, {}).setdefault(ex, 0)
        summary[name][ex] += amt

    for name, debts in summary.items():
        active_debts = {k: v for k, v in debts.items() if v != 0}
        if active_debts:
            with st.expander(f"👤 {name}", expanded=True):
                for ex, total in active_debts.items():
                    # ПРИНУДИТЕЛЬНОЕ форматирование времени для Виса и Планки
                    if ex in ["Вис", "Планка"] or ex_unit_map.get(ex) == "time":
                        st.write(f"**{ex}**: {seconds_to_str(total)}")
                    else:
                        st.write(f"**{ex}**: {total}")
else:
    st.write("Долгов нет.")
