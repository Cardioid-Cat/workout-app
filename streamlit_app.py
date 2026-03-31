import streamlit as st
from supabase import create_client, Client
import requests

# --- КОНФИГУРАЦИЯ ---
st.set_page_config(page_title="Workout Tracker Pro", page_icon="💪", layout="wide")

# Авто-определение ссылки:
# Берем адрес твоего приложения напрямую из браузера (через параметры)
def get_base_url():
    # Если у тебя домен workout.streamlit.app, мы будем использовать его
    return "https://workout.streamlit.app"

# --- ПОДКЛЮЧЕНИЕ К SUPABASE ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Ошибка: Проверьте SUPABASE_URL и SUPABASE_KEY в Secrets.")
    st.stop()

# --- РОУТИНГ КОМНАТ ---
query_params = st.query_params
room_slug = query_params.get("room")

def get_room_data(slug):
    res = supabase.table("rooms").select("*").eq("slug", slug).execute()
    return res.data[0] if res.data else None

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
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

def send_tg_notification(room_conf, text):
    token = room_conf.get("tg_token") or st.secrets.get("TELEGRAM_BOT_TOKEN")
    chat_id = room_conf.get("tg_chat_id") or st.secrets.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id: return
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                      json={"chat_id": chat_id, "text": f"📢 @all\n{text}"}, timeout=5)
    except: pass

# --- ЭКРАН 1: СОЗДАНИЕ КОМНАТЫ ---
if not room_slug:
    st.title("🚀 Workout SaaS: Создать комнату")
    with st.container(border=True):
        new_title = st.text_input("Название (напр: Моя Качалка)")
        new_slug = st.text_input("ID для ссылки (напр: matrix, kachalka77)")
        new_pass = st.text_input("Пароль админа", type="password")
        
        if st.button("Создать комнату", type="primary"):
            if new_title and new_slug and new_pass:
                try:
                    supabase.table("rooms").insert({
                        "slug": new_slug.lower().strip(),
                        "title": new_title,
                        "password": new_pass
                    }).execute()
                    
                    final_url = f"{get_base_url()}/?room={new_slug.lower().strip()}"
                    st.success("✅ Готово!")
                    st.write("Твоя ссылка для захода:")
                    st.code(final_url)
                except:
                    st.error("Этот ID уже занят.")
    st.stop()

# --- ЭКРАН 2: РАБОТА В КОМНАТЕ ---
room = get_room_data(room_slug)
if not room:
    st.error(f"Комната '{room_slug}' не найдена.")
    if st.button("На главную"):
        st.query_params.clear()
        st.rerun()
    st.stop()

room_id = room['id']
auth_key = f"auth_{room_id}"

# Загрузка данных
profiles = supabase.table("profiles").select("*").eq("room_id", room_id).order("name").execute().data
ex_types = supabase.table("exercise_types").select("*").eq("room_id", room_id).execute().data
ex_unit_map = {ex['name']: ex['unit_type'] for ex in ex_types}
games_data = supabase.table("games_presets").select("*").eq("room_id", room_id).execute().data
logs = supabase.table("workout_logs").select("*, profiles(name)").eq("room_id", room_id).order("created_at", desc=True).execute().data

st.title(f"💪 {room['title']}")

# РЕЙТИНГ
wins = {}
for l in logs:
    if l['exercise_type'] == "🏆 ПОБЕДА":
        n = l['profiles']['name']
        wins[n] = wins.get(n, 0) + 1

if wins:
    st.subheader("🏆 Зал славы")
    sorted_wins = sorted(wins.items(), key=lambda x: x[1], reverse=True)
    cols = st.columns(len(sorted_wins))
    for i, (name, count) in enumerate(sorted_wins):
        cols[i].metric(name, f"{count} 🥇")

# АДМИНКА (В сайдбаре)
with st.sidebar:
    st.header("⚙️ Настройки")
    if not st.session_state.get(auth_key):
        pwd = st.text_input("Пароль комнаты", type="password")
        if st.button("Войти"):
            if pwd == room['password']:
                st.session_state[auth_key] = True
                st.rerun()
            else: st.error("Неверно")
    else:
        st.success("Вы админ")
        if st.button("Выйти"):
            st.session_state[auth_key] = False
            st.rerun()
        
        with st.expander("👤 Участники"):
            with st.form("p_f", clear_on_submit=True):
                new_p = st.text_input("Имя")
                if st.form_submit_button("Добавить"):
                    supabase.table("profiles").insert({"name": new_p, "room_id": room_id}).execute()
                    st.rerun()
        
        with st.expander("🏋️ Упражнения"):
            with st.form("ex_f", clear_on_submit=True):
                en = st.text_input("Название")
                et = st.selectbox("Тип", ["count", "time"])
                if st.form_submit_button("Добавить"):
                    supabase.table("exercise_types").insert({"name": en, "unit_type": et, "room_id": room_id}).execute()
                    st.rerun()

# ЛОГИКА ДОЛГОВ
if st.session_state.get(auth_key):
    tab1, tab2 = st.tabs(["📝 Ручной ввод", "🎲 Игра"])
    # (Здесь будет логика записи упражнений из предыдущих сообщений)
    # ...

# ТАБЛИЦА ДОЛГОВ (SUMMARY)
st.divider()
st.subheader("📊 Текущие долги")
summary = {}
for l in logs:
    if l['exercise_type'] == "🏆 ПОБЕДА": continue
    n, ex, amt = l['profiles']['name'], l['exercise_type'], l['amount']
    summary.setdefault(n, {}).setdefault(ex, 0)
    summary[n][ex] += amt

for name, debts in summary.items():
    active = {k: v for k, v in debts.items() if v != 0}
    if active:
        with st.expander(f"👤 {name}", expanded=True):
            for ex, val in active.items():
                disp = seconds_to_str(val) if ex_unit_map.get(ex) == "time" else val
                st.write(f"**{ex}**: {disp}")
