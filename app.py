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
    st.error("Настройте Secrets (URL, KEY и ADMIN_PASSWORD)!")
    st.stop()

# --- СОСТОЯНИЕ (SESSION STATE) ---
if 'dev_mode' not in st.session_state:
    st.session_state.dev_mode = False
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def time_to_seconds(t_str):
    try:
        if ":" in str(t_str):
            m, s = map(int, str(t_str).split(":"))
            return m * 60 + s
        return int(t_str)
    except: return 0

def seconds_to_str(sec):
    m, s = abs(sec) // 60, abs(sec) % 60
    return f"{'-' if sec < 0 else ''}{m}:{s:02d}"

def add_entry(p_id, ex_name, val, is_time=False, is_writeoff=False):
    if not st.session_state.authenticated: return
    amount = time_to_seconds(val) if is_time else int(val)
    if amount == 0: return
    if is_writeoff: amount = -amount
    supabase.table("workout_logs").insert({
        "profile_id": p_id, "exercise_type": ex_name, "amount": amount
    }).execute()
    st.rerun()

# --- ЗАГРУЗКА ДАННЫХ ---
profiles = supabase.table("profiles").select("*").order("name").execute().data
ex_types = supabase.table("exercise_types").select("*").order("name").execute().data
ex_unit_map = {ex['name']: ex.get('unit_type', 'count') for ex in ex_types}

# --- БОКОВОЕ МЕНЮ ---
with st.sidebar:
    st.header("📋 Меню")
    st.write("Здесь будет статистика (скоро)")
    
    # Скрытое управление участниками и упражнениями
    if st.session_state.authenticated:
        st.divider()
        st.subheader("⚙️ Управление")
        
        with st.expander("👤 Участники"):
            with st.form("add_user", clear_on_submit=True):
                new_u = st.text_input("Имя")
                if st.form_submit_button("Добавить"):
                    if new_u:
                        supabase.table("profiles").insert({"name": new_u}).execute()
                        st.rerun()
            for p in profiles:
                if st.button(f"🗑 {p['name']}", key=f"u_{p['id']}"):
                    supabase.table("profiles").delete().eq("id", p['id']).execute()
                    st.rerun()

        with st.expander("🏋️ Упражнения"):
            with st.form("add_ex", clear_on_submit=True):
                en = st.text_input("Название")
                et = st.radio("Тип", ["Раз", "Время"])
                if st.form_submit_button("Создать"):
                    u = "time" if et == "Время" else "count"
                    if en:
                        supabase.table("exercise_types").insert({"name": en, "unit_type": u}).execute()
                        st.rerun()
            for name in ex_unit_map.keys():
                if st.button(f"🗑 {name}", key=f"ex_{name}"):
                    supabase.table("exercise_types").delete().eq("name", name).execute()
                    st.rerun()

    # Футер сайдбара с кнопкой активации
    st.divider()
    if not st.session_state.authenticated:
        if st.button("🛠 Режим разработчика"):
            st.session_state.dev_mode = not st.session_state.dev_mode
        
        if st.session_state.dev_mode:
            pwd = st.text_input("Введите пароль", type="password")
            if pwd == admin_pass:
                st.session_state.authenticated = True
                st.session_state.dev_mode = False
                st.rerun()
            elif pwd:
                st.error("Неверный пароль")
    else:
        if st.button("🔴 Выйти из режима админа"):
            st.session_state.authenticated = False
            st.rerun()

# --- ГЛАВНЫЙ ИНТЕРФЕЙС ---
st.title("💪 Трекер долгов")

# Интерфейс внесения долгов (только для админа)
if st.session_state.authenticated:
    st.subheader("📝 Внести изменения")
    user_name = st.selectbox("Кто тренируется?", [p['name'] for p in profiles])
    user_id = next(p['id'] for p in profiles if p['name'] == user_name)

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
            if u_type == "time":
                val = st.text_input("Время (мин:сек)", placeholder="1:30")
            else:
                val = st.number_input("Количество", min_value=1, step=5)

            c1, c2 = st.columns(2)
            with c1:
                if st.button("➕ Добавить", type="primary", use_container_width=True):
                    add_entry(user_id, active, val, is_time=(u_type=="time"))
            with c2:
                if st.button("✅ Списать", use_container_width=True):
                    add_entry(user_id, active, val, is_time=(u_type=="time"), is_writeoff=True)
else:
    st.info("ℹ️ Режим просмотра. Список актуальных долгов представлен ниже.")

st.divider()

# --- ТАБЛИЦА ДОЛГОВ (ВИДНА ВСЕМ) ---
st.subheader("📊 Текущие долги")
logs = supabase.table("workout_logs").select("amount, exercise_type, profiles(name)").execute().data

if logs:
    summary = {}
    for l in logs:
        n, ex, amt = l['profiles']['name'], l['exercise_type'], l['amount']
        if ex == "Списание": continue
        summary.setdefault(n, {}).setdefault(ex, 0)
        summary[n][ex] += amt

    for name, debts in summary.items():
        active_debts = {k: v for k, v in debts.items() if v != 0}
        if active_debts:
            with st.expander(f"👤 {name}", expanded=True):
                for ex, total in active_debts.items():
                    u = ex_unit_map.get(ex, "count")
                    disp = seconds_to_str(total) if u == "time" else total
                    st.write(f"**{ex}**: {disp}")
else:
    st.write("Долгов нет. Все красавчики!")
