import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="Workout Tracker", page_icon="💪")

# Инициализация подключения
try:
    supabase: Client = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
except:
    st.error("Ошибка подключения! Проверьте Secrets.")
    st.stop()

# --- ФУНКЦИИ ---
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
    amount = time_to_seconds(val) if is_time else int(val)
    if amount == 0: return
    if is_writeoff: amount = -amount
    
    supabase.table("workout_logs").insert({
        "profile_id": p_id, 
        "exercise_type": ex_name, # Записываем только строку-название
        "amount": amount
    }).execute()
    st.toast(f"Обновлено: {ex_name}")
    st.rerun()

# --- ДАННЫЕ ---
profiles = supabase.table("profiles").select("*").execute().data
ex_types = supabase.table("exercise_types").select("*").execute().data
# Словарь для быстрого поиска типа упражнения по его названию
ex_unit_map = {ex['name']: ex['unit_type'] for ex in ex_types}

# --- САЙДБАР ---
with st.sidebar:
    st.header("⚙️ Настройки")
    with st.expander("👤 Участники"):
        new_name = st.text_input("Новое имя", key="new_user_input")
        if st.button("Добавить") and new_name:
            supabase.table("profiles").insert({"name": new_name}).execute()
            st.rerun()
            
    with st.expander("🏋️ Упражнения"):
        ex_n = st.text_input("Название (напр. Пресс)")
        ex_t = st.radio("Тип", ["Кол-во", "Время"])
        if st.button("Создать") and ex_n:
            u = "time" if ex_t == "Время" else "count"
            supabase.table("exercise_types").insert({"name": ex_n, "unit_type": u}).execute()
            st.rerun()

# --- ИНТЕРФЕЙС ---
st.title("💪 Долги по тренировкам")

if not profiles:
    st.warning("Добавьте людей в настройки!")
    st.stop()

user_name = st.selectbox("Кто тренируется?", [p['name'] for p in profiles])
user_id = next(p['id'] for p in profiles if p['name'] == user_name)

st.subheader("Упражнение:")
cols = st.columns(3)
for i, name in enumerate(ex_unit_map.keys()):
    with cols[i % 3]:
        if st.button(name, use_container_width=True):
            st.session_state.active_ex = name

if "active_ex" in st.session_state:
    active = st.session_state.active_ex
    unit = ex_unit_map.get(active, "count")
    
    st.info(f"Выбрано: **{active}**")
    if unit == "time":
        val = st.text_input("Время (мин:сек)", placeholder="1:30")
    else:
        val = st.number_input("Количество", min_value=1, step=5)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("➕ Добавить долг", type="primary"):
            add_entry(user_id, active, val, is_time=(unit=="time"))
    with c2:
        if st.button("✅ Списать"):
            add_entry(user_id, active, val, is_time=(unit=="time"), is_writeoff=True)

st.divider()

# --- СВОДНАЯ ТАБЛИЦА ---
st.subheader("📊 Текущие долги")
logs = supabase.table("workout_logs").select("amount, exercise_type, profiles(name)").execute().data

if logs:
    summary = {}
    for l in logs:
        name = l['profiles']['name']
        ex = l['exercise_type']
        amt = l['amount']
        
        summary.setdefault(name, {}).setdefault(ex, 0)
        summary[name][ex] += amt

    for name, debts in summary.items():
        # Показываем только тех, у кого сумма не равна 0
        active_debts = {k: v for k, v in debts.items() if v != 0}
        if active_debts:
            with st.expander(f"👤 {name}", expanded=True):
                for ex, total in active_debts.items():
                    # Определяем как отображать (как время или как число)
                    u = ex_unit_map.get(ex, "count")
                    val_str = seconds_to_str(total) if u == "time" else str(total)
                    st.write(f"**{ex}**: {val_str}")
else:
    st.write("Чисто! Долгов нет.")
