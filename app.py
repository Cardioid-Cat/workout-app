import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="Workout Tracker", page_icon="💪")

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    admin_pass = st.secrets["ADMIN_PASSWORD"]
    supabase: Client = create_client(url, key)
except Exception:
    st.error("Ошибка конфигурации! Проверьте Secrets в Streamlit Cloud.")
    st.stop()

# --- СОСТОЯНИЕ (SESSION STATE) ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

if 'games_config' not in st.session_state:
    st.session_state.games_config = {
        "Игра 1: Отжимания (50)": {"ex": "Отжимания", "val": 50, "type": "count"},
        "Игра 2: Приседания (100)": {"ex": "Приседания", "val": 100, "type": "count"},
        "Игра 3: Планка (3 мин)": {"ex": "Планка", "val": "3:00", "type": "time"},
        "Игра 4: Гантели (50)": {"ex": "Гантели", "val": 50, "type": "count"},
        "Игра 5: Вис (2 мин)": {"ex": "Вис", "val": "2:00", "type": "time"}
    }

# --- ПОМОЩНИКИ ---
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

# --- ЗАГРУЗКА ДАННЫХ ---
profiles = supabase.table("profiles").select("*").order("name").execute().data

try:
    ex_types_data = supabase.table("exercise_types").select("name, unit_type").execute().data
    ex_unit_map = {ex['name']: ex['unit_type'] for ex in ex_types_data}
except:
    ex_unit_map = {"Планка": "time", "Вис": "time"}

logs = supabase.table("workout_logs").select("id, amount, exercise_type, profiles(name)").order("created_at", desc=True).execute().data

# --- БОКОВАЯ ПАНЕЛЬ (НАСТРОЙКИ) ---
with st.sidebar:
    st.title("⚙️ Настройки")
    
    if not st.session_state.authenticated:
        # Использование формы предотвращает обновление страницы при каждом символе
        with st.form("login_form"):
            pwd = st.text_input("Пароль админа", type="password")
            if st.form_submit_button("Войти"):
                if pwd == admin_pass:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Неверный пароль")
    else:
        if st.button("🔴 Выйти"):
            st.session_state.authenticated = False
            st.rerun()

    if st.session_state.authenticated:
        st.divider()
        
        # КНОПКА ОТМЕНЫ (Удаляет самую последнюю запись в логах)
        if logs:
            last_log = logs[0]
            st.warning(f"Последнее: {last_log['profiles']['name']} - {last_log['exercise_type']}")
            if st.button("⬅️ Отменить это действие", use_container_width=True):
                supabase.table("workout_logs").delete().eq("id", last_log['id']).execute()
                st.success("Действие отменено!")
                st.rerun()
            st.divider()

        with st.expander("🎲 НАСТРОЙКА ИГР"):
            with st.form("add_game", clear_on_submit=True):
                new_g_name = st.text_input("Название игры")
                new_g_ex = st.selectbox("Упражнение", list(ex_unit_map.keys()))
                new_g_val = st.text_input("Долг (напр. 50 или 1:30)")
                if st.form_submit_button("➕ Добавить"):
                    st.session_state.games_config[new_g_name] = {
                        "ex": new_g_ex, "val": new_g_val, "type": ex_unit_map.get(new_g_ex, "count")
                    }
                    st.rerun()
            for g_key in list(st.session_state.games_config.keys()):
                c1, c2 = st.columns([4, 1])
                c1.write(f"**{g_key}**")
                if c2.button("🗑", key=f"del_{g_key}"):
                    del st.session_state.games_config[g_key]
                    st.rerun()

        with st.expander("👤 УЧАСТНИКИ"):
            with st.form("new_user", clear_on_submit=True):
                n_name = st.text_input("Имя")
                if st.form_submit_button("Добавить"):
                    supabase.table("profiles").insert({"name": n_name}).execute()
                    st.rerun()
            for p in profiles:
                c1, c2 = st.columns([3, 1])
                c1.write(p['name'])
                if c2.button("🗑", key=f"upd_{p['id']}"):
                    supabase.table("profiles").delete().eq("id", p['id']).execute()
                    st.rerun()

# --- ГЛАВНЫЙ ЭКРАН ---
st.title("💪 Долги по тренировкам")

# --- ТОП ПОБЕДИТЕЛЕЙ ---
if logs:
    wins = {}
    for l in logs:
        if l['exercise_type'] == "Победа в игре":
            name = l['profiles']['name']
            wins[name] = wins.get(name, 0) + l['amount']
    
    if wins:
        st.subheader("🏆 Топ победителей")
        sorted_wins = sorted(wins.items(), key=lambda x: x[1], reverse=True)
        cols = st.columns(len(sorted_wins))
        for i, (name, w_count) in enumerate(sorted_wins):
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "🏅"
            cols[i].metric(label=f"{medal} {name}", value=f"{w_count}")
        st.divider()

if st.session_state.authenticated:
    tab1, tab2 = st.tabs(["📝 Ввод долгов", "🎲 Итоги игры"])
    
    with tab1:
        user_name = st.selectbox("Кому?", [p['name'] for p in profiles])
        uid = next(p['id'] for p in profiles if p['name'] == user_name)
        cols = st.columns(3)
        for i, name in enumerate(ex_unit_map.keys()):
            with cols[i % 3]:
                if st.button(name, use_container_width=True, key=f"m_{name}"):
                    st.session_state.active_ex = name
        
        if "active_ex" in st.session_state:
            active = st.session_state.active_ex
            with st.container(border=True):
                st.write(f"Выбрано: **{active}**")
                val = st.text_input("Сколько?", key="manual_val")
                c1, c2 = st.columns(2)
                if c1.button("➕ Добавить долг", type="primary", use_container_width=True):
                    add_entry(uid, active, val, is_time=(ex_unit_map.get(active)=="time"))
                if c2.button("✅ Списать (сделал)", use_container_width=True):
                    add_entry(uid, active, val, is_time=(ex_unit_map.get(active)=="time"), is_writeoff=True)

    with tab2:
        game_choice = st.selectbox("Какая игра?", list(st.session_state.games_config.keys()))
        winner_name = st.selectbox("Кто победил?", [p['name'] for p in profiles])
        if st.button("🔥 Раздать долги", type="primary", use_container_width=True):
            g = st.session_state.games_config[game_choice]
            w_id = next(p['id'] for p in profiles if p['name'] == winner_name)
            # Запись победы
            supabase.table("workout_logs").insert({"profile_id": w_id, "exercise_type": "Победа в игре", "amount": 1}).execute()
            # Начисление долгов
            for p in profiles:
                if p['id'] != w_id:
                    add_entry(p['id'], g['ex'], g['val'], is_time=(g['type']=="time"), silent=True)
            st.rerun()

st.divider()

# --- ТАБЛИЦА ДОЛГОВ ---
st.subheader("📊 Текущие долги")
if logs:
    summary = {}
    for l in logs:
        name, ex, amt = l['profiles']['name'], l['exercise_type'], l['amount']
        if ex in ["Победа в игре", "Списание"] or "[" in ex: continue
        summary.setdefault(name, {}).setdefault(ex, 0)
        summary[name][ex] += amt

    for name, debts in summary.items():
        active = {k: v for k, v in debts.items() if v != 0}
        if active:
            with st.expander(f"👤 {name}", expanded=True):
                for ex, total in active.items():
                    val = seconds_to_str(total) if ex_unit_map.get(ex) == "time" else total
                    st.write(f"**{ex}**: {val}")
else:
    st.write("Долгов нет!") 
