import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="Workout Tracker Pro", page_icon="💪")

# Подключение
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception:
    st.error("Настройте Secrets в Streamlit Cloud!")
    st.stop()

# --- ПОМОЩНИКИ ---
def time_to_seconds(t_str):
    """Превращает 1:30 в 90 секунд"""
    try:
        if ":" in str(t_str):
            m, s = map(int, str(t_str).split(":"))
            return m * 60 + s
        return int(t_str)
    except: return 0

def seconds_to_str(sec):
    """Превращает 90 в 1:30"""
    m = abs(sec) // 60
    s = abs(sec) % 60
    return f"{'-' if sec < 0 else ''}{m}:{s:02d}"

def add_entry(p_id, ex_type, val, is_time=False, is_writeoff=False):
    # Если это списание, делаем число отрицательным
    amount = time_to_seconds(val) if is_time else int(val)
    if amount == 0: return
    if is_writeoff:
        amount = -amount
        
    supabase.table("workout_logs").insert({
        "profile_id": p_id, "exercise_type": ex_type, "amount": amount
    }).execute()
    
    action = "Списано" if is_writeoff else "Записано"
    st.toast(f"{action}: {ex_type}")
    st.rerun()

# --- САЙДБАР: УПРАВЛЕНИЕ УЧАСТНИКАМИ ---
with st.sidebar:
    st.header("👥 Участники")
    
    # Использование st.form позволяет очищать поле после ввода (clear_on_submit=True)
    with st.form("add_user_form", clear_on_submit=True):
        new_user = st.text_input("Имя нового героя")
        if st.form_submit_button("Добавить") and new_user:
            supabase.table("profiles").insert({"name": new_user}).execute()
            st.rerun()
    
    st.divider()
    res = supabase.table("profiles").select("*").execute()
    all_profiles = res.data
    
    st.subheader("Удалить:")
    for p in all_profiles:
        if st.button(f"🗑 {p['name']}", key=f"del_{p['id']}"):
            supabase.table("profiles").delete().eq("id", p['id']).execute()
            st.rerun()

# --- ГЛАВНЫЙ ЭКРАН ---
st.title("🏋️‍♂️ Долги по тренировкам")

if not all_profiles:
    st.warning("Добавьте участников в боковом меню!")
    st.stop()

names = {p['name']: p['id'] for p in all_profiles}
user = st.selectbox("Кто тренируется?", list(names.keys()))
user_id = names[user]

# --- КНОПКИ УПРАЖНЕНИЙ ---
st.subheader("Выбери упражнение:")
col1, col2 = st.columns(2)

exercises = {
    "Отжимания": "count",
    "Подтягивания": "count",
    "Гантели": "count",
    "Планка": "time",
    "Вис": "time"
}

with col1:
    for ex_name, ex_type in list(exercises.items())[:3]:
        if st.button(ex_name, use_container_width=True):
            st.session_state.active_ex = (ex_name, ex_type)

with col2:
    for ex_name, ex_type in list(exercises.items())[3:]:
        if st.button(ex_name, use_container_width=True):
            st.session_state.active_ex = (ex_name, ex_type)

if "active_ex" in st.session_state:
    ex_name, ex_type = st.session_state.active_ex
    st.info(f"Ввод для: **{ex_name}**")
    
    if ex_type == "time":
        val = st.text_input("Введите время (например 1:30)", placeholder="1:30")
    else:
        val = st.number_input("Введите количество", min_value=1, step=1)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("➕ Добавить долг", type="primary"):
            if val:
                add_entry(user_id, ex_name, val, is_time=(ex_type=="time"), is_writeoff=False)
    with c2:
        if st.button("➖ Списать (выполнил)"):
            if val:
                add_entry(user_id, ex_name, val, is_time=(ex_type=="time"), is_writeoff=True)

st.divider()

# --- ТАБЛИЦА РЕЗУЛЬТАТОВ ---
st.subheader("📊 Текущие долги")
logs_res = supabase.table("workout_logs").select("amount, exercise_type, profiles(name)").execute()

if logs_res.data:
    summary = {}
    for l in logs_res.data:
        n = l['profiles']['name']
        ex = l['exercise_type']
        amt = l['amount']
        
        # Группируем долги по людям, а внутри — по конкретному упражнению
        if n not in summary:
            summary[n] = {}
        summary[n][ex] = summary[n].get(ex, 0) + amt
            
    for name, ex_data in summary.items():
        with st.expander(f"👤 {name}"):
            has_debts = False
            for ex_n, total in ex_data.items():
                # Игнорируем старые записи "Списание" (если они остались в базе) и нулевые долги
                if ex_n == "Списание" or total == 0: 
                    continue 
                
                has_debts = True
                is_time_type = exercises.get(ex_n) == "time"
                
                if is_time_type:
                    st.write(f"⏱ **{ex_n}**: {seconds_to_str(total)}")
                else:
                    st.write(f"🔢 **{ex_n}**: {total}")
            
            if not has_debts:
                st.success("Все долги закрыты! 🎉")
else:
    st.write("Все чисты!")
