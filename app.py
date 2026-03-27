import streamlit as st
from supabase import create_client, Client

# Настройка страницы для мобилок
st.set_page_config(page_title="Workout Tracker", page_icon="🏋️‍♂️")

# Подключение через секреты Streamlit
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception:
    st.error("Настройте SUPABASE_URL и SUPABASE_KEY в Secrets!")
    st.stop()

# Функция добавления записи
def add_entry(p_id, ex_type, val):
    supabase.table("workout_logs").insert({
        "profile_id": p_id,
        "exercise_type": ex_type,
        "amount": val
    }).execute()
    st.toast(f"Добавлено: {ex_type} {val}")
    st.rerun()

st.title("💪 Долги по тренировкам")

# Список участников из базы
res = supabase.table("profiles").select("*").execute()
profiles = {p['name']: p['id'] for p in res.data}

user = st.selectbox("Кто это сделал?", list(profiles.keys()))
user_id = profiles[user]

# Интерфейс с кнопками
st.subheader("Добавить долг:")
c1, c2, c3 = st.columns(3)
with c1:
    if st.button("Отжим +10"): add_entry(user_id, "Отжимания", 10)
with c2:
    if st.button("Присед +10"): add_entry(user_id, "Приседания", 10)
with c3:
    if st.button("Пресс +10"): add_entry(user_id, "Пресс", 10)

st.divider()

if st.button("✅ Списать 10 повторов", use_container_width=True):
    add_entry(user_id, "Списание", -10)

# Сводная таблица
st.subheader("📊 Общий зачет")
logs = supabase.table("workout_logs").select("amount, profiles(name)").execute()

if logs.data:
    totals = {}
    for l in logs.data:
        name = l['profiles']['name']
        totals[name] = totals.get(name, 0) + l['amount']
    
    for name, score in totals.items():
        color = "red" if score > 0 else "green"
        st.markdown(f"**{name}**: :{color}[{score} повторов]")
else:
    st.write("Чисто! Долгов нет.")