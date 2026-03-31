import streamlit as st
from supabase import create_client, Client
import requests

# --- АВТО-ОПРЕДЕЛЕНИЕ ССЫЛКИ ---
# Это поможет выводить правильную ссылку после создания комнаты
def get_base_url():
    # Пытаемся достать URL из заголовков или настроек Streamlit
    return f"https://workout.streamlit.app" # Укажи здесь свой основной домен без параметров

st.set_page_config(page_title="Workout Tracker Pro", page_icon="💪", layout="wide")

# --- ПОДКЛЮЧЕНИЕ К БАЗЕ ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Ошибка конфигурации Supabase в Secrets. Убедитесь, что SUPABASE_URL и SUPABASE_KEY добавлены.")
    st.stop()

# --- ЛОГИКА РОУТИНГА ---
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
    token = room_conf.get("tg_token")
    chat_id = room_conf.get("tg_chat_id")
    if not token or not chat_id: return
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    try: requests.post(api_url, json={"chat_id": chat_id, "text": f"📢 @all\n{text}"}, timeout=5)
    except: pass

# --- ЭКРАН СОЗДАНИЯ КОМНАТЫ ---
if not room_slug:
    st.title("🚀 Создать новую комнату")
    with st.container(border=True):
        new_title = st.text_input("Название (напр: Моя Команда)")
        new_slug = st.text_input("ID для ссылки (напр: my-team)")
        new_pass = st.text_input("Пароль админа", type="password")
        
        if st.button("Создать", type="primary", use_container_width=True):
            if new_title and new_slug and new_pass:
                try:
                    supabase.table("rooms").insert({
                        "slug": new_slug.lower().strip(), "title": new_title, "password": new_pass
                    }).execute()
                    
                    # Генерируем правильную ссылку динамически
                    base = get_base_url()
                    final_link = f"{base}/?room={new_slug.lower().strip()}"
                    
                    st.success("✅ Комната создана!")
                    st.write("Твоя постоянная ссылка:")
                    st.code(final_link)
                    st.info("Скопируй эту ссылку и поделись с друзьями.")
                except:
                    st.error("Ошибка: такой ID уже занят.")
    st.stop()

# --- ЗАГРУЗКА ДАННЫХ КОМНАТЫ ---
room = get_room_data(room_slug)
if not room:
    st.error("Комната не найдена.")
    if st.button("На главную"):
        st.query_params.clear()
        st.rerun()
    st.stop()

room_id = room['id']
auth_key = f"auth_{room_id}"

# --- ДАННЫЕ ИЗ БД ---
profiles = supabase.table("profiles").select("*").eq("room_id", room_id).order("name").execute().data
ex_types = supabase.table("exercise_types").select("*").eq("room_id", room_id).execute().data
ex_unit_map = {ex['name']: ex['unit_type'] for ex in ex_types}
games_data = supabase.table("games_presets").select("*").eq("room_id", room_id).order("game_name").execute().data
logs = supabase.table("workout_logs").select("*, profiles(name)").eq("room_id", room_id).order("created_at", desc=True).execute().data

# --- ИНТЕРФЕЙС ---
st.title(f"💪 {room['title']}")

# 1. РЕЙТИНГ
st.subheader("🏆 Зал славы")
wins = {}
for l in logs:
    if l['exercise_type'] == "🏆 ПОБЕДА":
        n = l['profiles']['name']
        wins[n] = wins.get(n, 0) + 1
if wins:
    sorted_wins = sorted(wins.items(), key=lambda x: x[1], reverse=True)
    cols = st.columns(len(sorted_wins))
    for i, (name, count) in enumerate(sorted_wins):
        cols[i].metric(name, f"{count} 🥇")

# 2. АДМИНКА В САЙДБАРЕ
with st.sidebar:
    if not st.session_state.get(auth_key):
        pwd = st.text_input("Пароль админа", type="password")
        if st.button("Войти"):
            if pwd == room['password']:
                st.session_state[auth_key] = True
                st.rerun()
    else:
        st.write("✅ Вы админ")
        if st.button("Выйти"):
            st.session_state[auth_key] = False
            st.rerun()
        
        # Настройки TG, участников и упражнений (как в прошлом коде)
        # Добавь сюда блоки из предыдущего сообщения (expander с настройками)

# 3. ВКЛАДКИ УПРАВЛЕНИЯ
if st.session_state.get(auth_key):
    t1, t2 = st.tabs(["📝 Ввод", "🎲 Игра"])
    with t1:
        # Логика ввода долгов...
        pass
    with t2:
        # Логика мульти-победителей...
        pass

# 4. СПИСОК ДОЛГОВ
st.divider()
st.subheader("📊 Текущие долги")
# ... отрисовка summary как раньше
