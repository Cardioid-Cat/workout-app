import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="Workout Tracker", page_icon="💪")

# --- ИНИЦИАЛИЗАЦИЯ ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    admin_pass = st.secrets["ADMIN_PASSWORD"]
    supabase: Client = create_client(url, key)
except Exception:
    st.error("Ошибка конфига! Проверьте Secrets.")
    st.stop()

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
# Грузим все типы упражнений из базы (чтобы кнопки не пропадали)
ex_types_data = supabase.table("exercise_types").select("name, unit_type").execute().data
ex_unit_map = {ex['name']: ex['unit_type'] for ex in ex_types_data}
logs = supabase.table("workout_logs").select("amount, exercise_type, profiles(name)").execute().data

# --- БОКОВАЯ ПАНЕЛЬ (SIDEBAR) ---
with st.sidebar:
    st.title("⚙️ Настройки")
    
    if not st.session_state.authenticated:
        pwd = st.text_input("Пароль админа", type="password")
        if pwd == admin_pass:
            st.session_state.authenticated = True
            st.rerun()
    else:
        if st.button("🔴 Выйти"):
            st.session_state.authenticated = False
            st.rerun()

    if st.session_state.authenticated:
        st.divider()
        
        # 1. ИТОГИ ИГРЫ
        with st.expander("🎲 ИТОГИ ИГРЫ", expanded=False):
            game_choice = st.selectbox("Игра:", list(GAMES_CONFIG.keys()))
            winner_name = st.selectbox("Кто победил?", [p['name'] for p in profiles], key="game_winner")
            if st.button("🔥 Раздать долги всем кроме победителя", use_container_width=True):
                g = GAMES_CONFIG[game_choice]
                winner_id = next(p['id'] for p in profiles if p['name'] == winner_name)
                for p in profiles:
                    if p['id'] != winner_id:
                        add_entry(p['id'], g['ex'], g['val'], is_time=(g['type']=="time"), silent=True)
                st.success("Готово!")
                st.rerun()

        # 2. УПРАВЛЕНИЕ УЧАСТНИКАМИ
        with st.expander("👤 УЧАСТНИКИ"):
            with st.form("add_user", clear_on_submit=True):
                new_name = st.text_input("Имя нового героя")
                if st.form_submit_button("Добавить"):
                    supabase.table("profiles").insert({"name": new_name}).execute()
                    st.rerun()
            st.write("---")
            for p in profiles:
                col1, col2 = st.columns([3, 1])
                col1.write(p['name'])
                if col2.button("🗑", key=f"del_u_{p['id']}"):
                    supabase.table("profiles").delete().eq("id", p['id']).execute()
                    st.rerun()

        # 3. УПРАВЛЕНИЕ УПРАЖНЕНИЯМИ
        with st.expander("🏋️ УПРАЖНЕНИЯ"):
            with st.form("add_ex", clear_on_submit=True):
                new_ex = st.text_input("Название (напр. Гантели)")
                new_type = st.radio("Тип", ["count", "time"], format_func=lambda x: "Раз" if x=="count" else "Время (мм:сс)")
                if st.form_submit_button("Добавить упражнение"):
                    supabase.table("exercise_types").insert({"name": new_ex, "unit_type": new_type}).execute()
                    st.rerun()
            st.write("---")
            for name in ex_unit_map.keys():
                col1, col2 = st.columns([3, 1])
                col1.write(name)
                if col2.button("🗑", key=f"del_ex_{name}"):
                    supabase.table("exercise_types").delete().eq("name", name).execute()
                    st.rerun()

    st.divider()
    if logs:
        total = sum(l['amount'] for l in logs)
        st.metric("Общий долг банды", f"{total} ед.")

# --- ГЛАВНЫЙ ЭКРАН ---
st.title("💪 Долги по тренировкам")

if st.session_state.authenticated:
    st.subheader("📝 Добавить вручную")
    user_name = st.selectbox("Кому?", [p['name'] for p in profiles], key="manual_user")
    uid = next(p['id'] for p in profiles if p['name'] == user_name)
    
    # Кнопки упражнений (динамически из базы)
    cols = st.columns(3)
    for i, name in enumerate(ex_unit_map.keys()):
        with cols[i % 3]:
            if st.button(name, use_container_width=True):
                st.session_state.active_ex = name
    
    if "active_ex" in st.session_state:
        active = st.session_state.active_ex
        u_type = ex_unit_map.get(active, "count")
        with st.container(border=True):
            st.write(f"Выбрано: **{active}**")
            val = st.text_input("Сколько?", placeholder="Напр: 50 или 2:30", key="val_input")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("➕ Добавить долг", type="primary", use_container_width=True):
                    add_entry(uid, active, val, is_time=(u_type=="time"))
            with c2:
                if st.button("✅ Списать (сделал)", use_container_width=True):
                    add_entry(uid, active, val, is_time=(u_type=="time"), is_writeoff=True)

st.divider()

# --- ТАБЛИЦА ДОЛГОВ ---
st.subheader("📊 Текущие долги")
if logs:
    summary = {}
    for l in logs:
        name, ex, amt = l['profiles']['name'], l['exercise_type'], l['amount']
        if "[" in ex or ex == "Списание": continue
        summary.setdefault(name, {}).setdefault(ex, 0)
        summary[name][ex] += amt

    for name, debts in summary.items():
        active_debts = {k: v for k, v in debts.items() if v != 0}
        if active_debts:
            with st.expander(f"👤 {name}", expanded=True):
                for ex, total in active_debts.items():
                    # Принудительно ставим время для Виса, Планки или того, что помечено как time
                    if ex in ["Вис", "Планка"] or ex_unit_map.get(ex) == "time":
                        st.write(f"**{ex}**: {seconds_to_str(total)}")
                    else:
                        st.write(f"**{ex}**: {total}")
else:
    st.write("Чисто! Все всё отработали.")
