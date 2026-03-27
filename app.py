import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="Workout Tracker Pro", page_icon="💪")

# Подключение к Supabase
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception:
    st.error("Настройте Secrets в Streamlit Cloud!")
    st.stop()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def time_to_seconds(t_str):
    try:
        if ":" in str(t_str):
            m, s = map(int, str(t_str).split(":"))
            return m * 60 + s
        return int(t_str)
    except: return 0

def seconds_to_str(sec):
    m = abs(sec) // 60
    s = abs(sec) % 60
    return f"{'-' if sec < 0 else ''}{m}:{s:02d}"

def add_entry(p_id, ex_name, val, is_time=False, is_writeoff=False):
    amount = time_to_seconds(val) if is_time else int(val)
    if amount == 0: return
    if is_writeoff: amount = -amount
        
    supabase.table("workout_logs").insert({
        "profile_id": p_id, "exercise_type": ex_name, "amount": amount
    }).execute()
    st.rerun()

# --- ЗАГРУЗКА ДАННЫХ ---
profiles = supabase.table("profiles").select("*").execute().data
ex_types = supabase.table("exercise_types").select("*").execute().data
ex_dict = {ex['name']: ex['unit_type'] for ex in ex_types}

# --- БОКОВОЕ МЕНЮ (УПРАВЛЕНИЕ) ---
with st.sidebar:
    st.header("👥 Участники")
    with st.form("add_user", clear_on_submit=True):
        new_name = st.text_input("Имя нового героя")
        if st.form_submit_button("Добавить") and new_name:
            supabase.table("profiles").insert({"name": new_name}).execute()
            st.rerun()
    
    with st.expander("Удалить участников"):
        for p in profiles:
            if st.button(f"🗑 {p['name']}", key=f"up_{p['id']}"):
                supabase.table("profiles").delete().eq("id", p['id']).execute()
                st.rerun()

    st.divider()
    st.header("🏋️‍♂️ Упражнения")
    with st.form("add_ex", clear_on_submit=True):
        ex_n = st.text_input("Название (напр. Пресс)")
        ex_t = st.radio("Тип", ["Раз (кол-во)", "Время (мин:сек)"])
        if st.form_submit_button("Создать упражнение") and ex_n:
            u_type = "time" if "Время" in ex_t else "count"
            supabase.table("exercise_types").insert({"name": ex_n, "unit_type": u_type}).execute()
            st.rerun()

    with st.expander("Удалить упражнения"):
        for ex in ex_types:
            if st.button(f"🗑 {ex['name']}", key=f"ex_{ex['id']}"):
                supabase.table("exercise_types").delete().eq("id", ex['id']).execute()
                st.rerun()

# --- ГЛАВНЫЙ ИНТЕРФЕЙС ---
st.title("🏋️‍♂️ Трекер долгов")

if not profiles:
    st.info("Добавьте участников в боковом меню слева!")
    st.stop()

user_name = st.selectbox("Кто тренируется?", [p['name'] for p in profiles])
user_id = next(p['id'] for p in profiles if p['name'] == user_name)

st.subheader("Выберите упражнение:")
cols = st.columns(3)
for i, name in enumerate(ex_dict.keys()):
    with cols[i % 3]:
        if st.button(name, use_container_width=True):
            st.session_state.active_ex = name

if "active_ex" in st.session_state:
    active = st.session_state.active_ex
    u_type = ex_dict.get(active, "count")
    
    st.info(f"Ввод для: **{active}**")
    if u_type == "time":
        val = st.text_input("Сколько (мин:сек)?", placeholder="1:30")
    else:
        val = st.number_input("Сколько раз?", min_value=1, step=5)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("➕ Добавить долг", type="primary"):
            add_entry(user_id, active, val, is_time=(u_type=="time"))
    with c2:
        if st.button("✅ Выполнил (списать)"):
            add_entry(user_id, active, val, is_time=(u_type=="time"), is_writeoff=True)

st.divider()

# --- ТАБЛИЦА ДОЛГОВ ---
st.subheader("📊 Текущие долги")
logs = supabase.table("workout_logs").select("amount, exercise_type, profiles(name)").execute().data

if logs:
    summary = {}
    for l in logs:
        n, ex, amt = l['profiles']['name'], l['exercise_type'], l['amount']
        summary.setdefault(n, {}).setdefault(ex, 0)
        summary[n][ex] += amt

    for name, debts in summary.items():
        # Показываем только тех, у кого сумма долгов не ноль
        active_debts = {k: v for k, v in debts.items() if v != 0}
        if active_debts:
            with st.expander(f"👤 {name}", expanded=True):
                for ex, total in active_debts.items():
                    unit = ex_dict.get(ex, "count")
                    display = seconds_to_str(total) if unit == "time" else total
                    st.write(f"**{ex}**: {display}")
else:
    st.write("Чисто! Долгов нет.")
