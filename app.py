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

# --- СОСТОЯНИЕ ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# --- НАСТРОЙКИ ИГР ---
GAMES_CONFIG = {
    "Игра 1: Отжимания (50)": {"ex": "Отжимания", "val": 50, "type": "count"},
    "Игра 2: Приседания (100)": {"ex": "Приседания", "val": 100, "type": "count"},
    "Игра 3: Планка (3 мин)": {"ex": "Планка", "val": "3:00", "type": "time"},
    "Игра 4: Гантели (50)": {"ex": "Гантели", "val": 50, "type": "count"},
    "Игра 5: Вис (2 мин)": {"ex": "Вис", "val": "2:00", "type": "time"}
}

# --- ФУНКЦИИ ---
def time_to_seconds(t_str):
    """Конвертирует ММ:СС или секунды в целое число секунд"""
    try:
        if ":" in str(t_str):
            m, s = map(int, str(t_str).split(":"))
            return m * 60 + s
        return int(t_str)
    except: return 0

def seconds_to_str(sec):
    """Конвертирует секунды в формат ММ:СС для отображения"""
    m, s = abs(sec) // 60, abs(sec) % 60
    return f"{'-' if sec < 0 else ''}{m}:{s:02d}"

def add_entry(p_id, ex_name, val, is_time=False, is_writeoff=False, silent=False):
    amount = time_to_seconds(val) if is_time else int(val)
    if amount == 0: return
    if is_writeoff: amount = -amount
    
    supabase.table("workout_logs").insert({
        "profile_id": p_id, "exercise_type": ex_name, "amount": amount
    }).execute()
    if not silent: st.rerun()

# --- ЗАГРУЗКА ДАННЫХ ---
profiles = supabase.table("profiles").select("*").order("name").execute().data
# Получаем типы упражнений, чтобы знать, где время, а где разы
ex_types_data = supabase.table("exercise_types").select("name, unit_type").execute().data
ex_unit_map = {ex['name']: ex['unit_type'] for ex in ex_types_data}
logs = supabase.table("workout_logs").select("amount, exercise_type, profiles(name)").execute().data

# --- БОКОВОЕ МЕНЮ ---
with st.sidebar:
    st.title("⚙️ Панель")
    
    # Авторизация
    if not st.session_state.authenticated:
        pwd = st.text_input("Пароль администратора", type="password")
        if pwd == admin_pass:
            st.session_state.authenticated = True
            st.rerun()
    else:
        if st.button("🔴 Выйти"):
            st.session_state.authenticated = False
            st.rerun()

    if st.session_state.authenticated:
        st.divider()
        # НОВАЯ КНОПКА ИГРЫ СЛЕВА
        with st.expander("🎲 ИТОГИ ИГРЫ", expanded=True):
            game_choice = st.selectbox("Какая игра?", list(GAMES_CONFIG.keys()))
            winner_name = st.selectbox("Кто победил?", [p['name'] for p in profiles])
            
            if st.button("🔥 Начислить всем долги", use_container_width=True):
                game = GAMES_CONFIG[game_choice]
                winner_id = next(p['id'] for p in profiles if p['name'] == winner_name)
                losers = [p for p in profiles if p['id'] != winner_id]
                
                for loser in losers:
                    add_entry(loser['id'], game['ex'], game['val'], 
                              is_time=(game['type']=="time"), silent=True)
                st.success("Готово!")
                st.rerun()

        st.divider()
        with st.expander("👤 Участники"):
            with st.form("add_user", clear_on_submit=True):
                n = st.text_input("Имя")
                if st.form_submit_button("Добавить") and n:
                    supabase.table("profiles").insert({"name": n}).execute()
                    st.rerun()
    
    st.divider()
    # Статистика
    if logs:
        total_debt = sum(l['amount'] for l in logs)
        st.metric("Общий долг системы", f"{total_debt} ед.")

# --- ГЛАВНЫЙ ЭКРАН ---
st.title("💪 Трекер долгов")

if st.session_state.authenticated:
    st.subheader("📝 Ручной ввод")
    user_name = st.selectbox("Кому?", [p['name'] for p in profiles])
    user_id = next(p['id'] for p in profiles if p['name'] == user_name)
    
    # Сетка кнопок упражнений
    cols = st.columns(3)
    for i, name in enumerate(ex_unit_map.keys()):
        with cols[i % 3]:
            if st.button(name, use_container_width=True):
                st.session_state.active_ex = name
    
    if "active_ex" in st.session_state:
        active = st.session_state.active_ex
        u_type = ex_unit_map.get(active, "count")
        with st.container(border=True):
            st.write(f"Упражнение: **{active}**")
            val = st.text_input("Сколько?", placeholder="Пример: 50 или 2:30")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("➕ Добавить долг", type="primary", use_container_width=True):
                    add_entry(user_id, active, val, is_time=(u_type=="time"))
            with c2:
                if st.button("✅ Списать", use_container_width=True):
                    add_entry(user_id, active, val, is_time=(u_type=="time"), is_writeoff=True)

st.divider()

# --- ТАБЛИЦА ТЕКУЩИХ ДОЛГОВ ---
st.subheader("📊 Текущие долги")
if logs:
    summary = {}
    for l in logs:
        n, ex, amt = l['profiles']['name'], l['exercise_type'], l['amount']
        # Пропускаем системные записи, если они вдруг попали в лог
        if ex == "Списание" or "[" in ex: continue 
        summary.setdefault(n, {}).setdefault(ex, 0)
        summary[n][ex] += amt

    for name, debts in summary.items():
        # Показываем только если сумма долгов не нулевая
        active_debts = {k: v for k, v in debts.items() if v != 0}
        if active_debts:
            with st.expander(f"👤 {name}", expanded=True):
                for ex, total in active_debts.items():
                    # ПРОВЕРКА ТИПА: Если в базе unit_type = 'time', форматируем как ММ:СС
                    is_time = ex_unit_map.get(ex) == "time"
                    disp_value = seconds_to_str(total) if is_time else total
                    st.write(f"**{ex}**: {disp_value}")
else:
    st.write("Чисто! Долгов нет.")
