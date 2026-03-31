import streamlit as st
from supabase import create_client, Client
import requests

# --- КОНФИГУРАЦИЯ СТРАНИЦЫ ---
st.set_page_config(page_title="Workout Tracker Pro", page_icon="💪", layout="wide")

# --- ПОДКЛЮЧЕНИЕ К БАЗЕ ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Ошибка конфигурации Supabase в Secrets. Проверьте настройки на Streamlit Cloud.")
    st.stop()

# --- ЛОГИКА РОУТИНГА (КОМНАТЫ) ---
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
    full_message = f"📢 @all\n{text}"
    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(api_url, json={"chat_id": chat_id, "text": full_message}, timeout=5)
    except: pass

# --- ЭКРАН СОЗДАНИЯ КОМНАТЫ (ЕСЛИ НЕТ СЛУГА В URL) ---
if not room_slug:
    st.title("🚀 Workout Tracker SaaS")
    st.subheader("Создайте свою уникальную комнату для тренировок")
    
    with st.container(border=True):
        new_title = st.text_input("Название комнаты (например: Качалка 2.0)")
        new_slug = st.text_input("ID для ссылки (латиница, без пробелов, например: my-gym-2024)")
        new_pass = st.text_input("Придумайте пароль админа", type="password")
        
        if st.button("Создать комнату", type="primary", use_container_width=True):
            if new_title and new_slug and new_pass:
                try:
                    supabase.table("rooms").insert({
                        "slug": new_slug.lower().strip(),
                        "title": new_title,
                        "password": new_pass
                    }).execute()
                    st.success(f"Комната создана! Теперь перейдите по ссылке:")
                    st.code(f"https://{st.secrets.get('STREAMLIT_APP_URL', 'your-app')}.streamlit.app/?room={new_slug}")
                    st.info("Скопируйте ссылку и сохраните её.")
                except:
                    st.error("Этот ID уже занят или произошла ошибка. Попробуйте другой.")
            else:
                st.warning("Заполните все поля!")
    st.stop()

# --- ЗАГРУЗКА ДАННЫХ КОНКРЕТНОЙ КОМНАТЫ ---
room = get_room_data(room_slug)
if not room:
    st.error(f"Комната '{room_slug}' не найдена.")
    if st.button("На главную"):
        st.query_params.clear()
        st.rerun()
    st.stop()

room_id = room['id']

# --- СОСТОЯНИЕ АВТОРИЗАЦИИ ---
auth_key = f"auth_{room_id}"
if auth_key not in st.session_state:
    st.session_state[auth_key] = False

# --- ПОЛУЧЕНИЕ ДАННЫХ ИЗ ТАБЛИЦ ---
profiles = supabase.table("profiles").select("*").eq("room_id", room_id).order("name").execute().data
ex_types = supabase.table("exercise_types").select("*").eq("room_id", room_id).execute().data
ex_unit_map = {ex['name']: ex['unit_type'] for ex in ex_types}
games_data = supabase.table("games_presets").select("*").eq("room_id", room_id).order("game_name").execute().data
logs = supabase.table("workout_logs").select("*, profiles(name)").eq("room_id", room_id).order("created_at", desc=True).execute().data

# --- ФУНКЦИЯ ДОБАВЛЕНИЯ ЗАПИСИ ---
def add_entry(p_id, ex_name, val, is_time=False, is_writeoff=False, silent=False):
    amount = time_to_seconds(val) if is_time else int(val)
    if amount == 0: return
    actual_amount = -amount if is_writeoff else amount
    
    supabase.table("workout_logs").insert({
        "profile_id": p_id, "exercise_type": ex_name, "amount": actual_amount, "room_id": room_id
    }).execute()
    
    if not silent:
        p_name = next(p['name'] for p in profiles if p['id'] == p_id)
        action = "списал(а)" if is_writeoff else "получил(а) долг"
        send_tg_notification(room, f"⚖️ {p_name} {action}: {ex_name} ({val})")
        st.rerun()

# --- БОКОВАЯ ПАНЕЛЬ (НАСТРОЙКИ) ---
with st.sidebar:
    st.title(f"🏠 {room['title']}")
    if not st.session_state[auth_key]:
        pwd = st.text_input("Пароль админа", type="password")
        if st.button("Войти"):
            if pwd == room['password']:
                st.session_state[auth_key] = True
                st.rerun()
            else: st.error("Неверно")
    else:
        if st.button("🔴 Выйти"):
            st.session_state[auth_key] = False
            st.rerun()
        
        st.divider()
        with st.expander("🤖 Настройка Telegram"):
            new_tg_token = st.text_input("Bot Token", value=room.get('tg_token') or "")
            new_tg_chat = st.text_input("Chat ID", value=room.get('tg_chat_id') or "")
            if st.button("Сохранить TG"):
                supabase.table("rooms").update({"tg_token": new_tg_token, "tg_chat_id": new_tg_chat}).eq("id", room_id).execute()
                st.success("Обновлено! Перезагрузите страницу.")

        with st.expander("🏋️ УПРАЖНЕНИЯ"):
            with st.form("ex_form", clear_on_submit=True):
                en = st.text_input("Название")
                et = st.radio("Тип", ["count", "time"], format_func=lambda x: "Раз" if x=="count" else "Время")
                if st.form_submit_button("Добавить"):
                    supabase.table("exercise_types").insert({"name": en, "unit_type": et, "room_id": room_id}).execute()
                    st.rerun()
            for ex in ex_types:
                c1, c2 = st.columns([4,1])
                c1.write(ex['name'])
                if c2.button("🗑", key=f"del_ex_{ex['id']}"):
                    supabase.table("exercise_types").delete().eq("id", ex['id']).execute()
                    st.rerun()

        with st.expander("👤 УЧАСТНИКИ"):
            with st.form("p_form", clear_on_submit=True):
                pn = st.text_input("Имя")
                if st.form_submit_button("Добавить"):
                    supabase.table("profiles").insert({"name": pn, "room_id": room_id}).execute()
                    st.rerun()
            for p in profiles:
                c1, c2 = st.columns([4,1])
                c1.write(p['name'])
                if c2.button("🗑", key=f"del_p_{p['id']}"):
                    supabase.table("profiles").delete().eq("id", p['id']).execute()
                    st.rerun()

        with st.expander("🎲 НАСТРОЙКА ИГР"):
            with st.form("g_form", clear_on_submit=True):
                gn = st.text_input("Название игры")
                ge = st.selectbox("Упражнение", list(ex_unit_map.keys()))
                gv = st.text_input("Значение (напр. 50 или 2:00)")
                if st.form_submit_button("Добавить игру"):
                    supabase.table("games_presets").insert({"game_name": gn, "ex_name": ge, "val": gv, "unit_type": ex_unit_map.get(ge), "room_id": room_id}).execute()
                    st.rerun()

# --- ГЛАВНЫЙ ЭКРАН ---
st.title(f"💪 {room['title']}")

# 1. РЕЙТИНГ (HALL OF FAME)
st.subheader("🏆 Рейтинг чемпионов")
wins_data = {}
for l in logs:
    if l['exercise_type'] == "🏆 ПОБЕДА":
        n = l['profiles']['name']
        wins_data[n] = wins_data.get(n, 0) + 1

if wins_data:
    sorted_wins = sorted(wins_data.items(), key=lambda x: x[1], reverse=True)
    cols = st.columns(min(len(sorted_wins), 5))
    for i, (name, count) in enumerate(sorted_wins):
        with cols[i % 5]:
            st.metric(label=name, value=f"{count} 🥇")
else:
    st.info("Побед пока нет. Начните игру!")

st.divider()

# 2. УПРАВЛЕНИЕ ДОЛГАМИ
if st.session_state[auth_key]:
    tab1, tab2 = st.tabs(["📝 Ввод долга", "🎲 Результат игры"])
    
    with tab1:
        if profiles:
            u_names = [p['name'] for p in profiles]
            u_name = st.selectbox("Кому записываем?", u_names)
            u_id = next(p['id'] for p in profiles if p['name'] == u_name)
            
            st.write("Выберите упражнение:")
            cols = st.columns(3)
            for i, name in enumerate(ex_unit_map.keys()):
                if cols[i % 3].button(name, use_container_width=True, key=f"btn_{name}"):
                    st.session_state.active_ex = name
            
            if "active_ex" in st.session_state:
                active = st.session_state.active_ex
                with st.container(border=True):
                    st.write(f"Выбрано: **{active}**")
                    val = st.text_input("Сколько? (раз или минуты:секунды)")
                    c1, c2 = st.columns(2)
                    if c1.button("➕ Начислить долг", type="primary", use_container_width=True):
                        add_entry(u_id, active, val, is_time=(ex_unit_map.get(active)=="time"))
                    if c2.button("✅ Списать (отработал)", use_container_width=True):
                        add_entry(u_id, active, val, is_time=(ex_unit_map.get(active)=="time"), is_writeoff=True)
        else:
            st.warning("Сначала добавьте участников в настройках.")

    with tab2:
        if games_data and profiles:
            g_options = {g['game_name']: g for g in games_data}
            sel_g = st.selectbox("Во что играли?", list(g_options.keys()))
            game = g_options[sel_g]
            
            # ВЫБОР НЕСКОЛЬКИХ ПОБЕДИТЕЛЕЙ
            winners = st.multiselect("Кто победил? (им долг не идет)", [p['name'] for p in profiles])
            
            if st.button("🔥 Раздать долги проигравшим", type="primary", use_container_width=True):
                if not winners:
                    st.error("Выберите хотя бы одного победителя!")
                else:
                    winner_ids = [p['id'] for p in profiles if p['name'] in winners]
                    # Записываем победу в лог
                    for w_id in winner_ids:
                        supabase.table("workout_logs").insert({
                            "profile_id": w_id, "exercise_type": "🏆 ПОБЕДА", "amount": 1, "room_id": room_id
                        }).execute()
                    # Начисляем долг всем остальным
                    for p in profiles:
                        if p['id'] not in winner_ids:
                            add_entry(p['id'], game['ex_name'], game['val'], is_time=(game['unit_type']=="time"), silent=True)
                    
                    send_tg_notification(room, f"🏆 В игре '{sel_g}' победили: {', '.join(winners)}! Остальные получают долг: {game['ex_name']} ({game['val']}).")
                    st.success("Долги розданы!")
                    st.rerun()
        else:
            st.info("Настройте игры и участников в сайдбаре.")
else:
    st.info("🔐 Войдите в настройки как админ, чтобы управлять долгами.")

# 3. ТАБЛИЦА ДОЛГОВ
st.divider()
st.subheader("📊 Текущие долги")
summary = {}
for l in logs:
    name, ex, amt = l['profiles']['name'], l['exercise_type'], l['amount']
    if ex == "🏆 ПОБЕДА": continue
    summary.setdefault(name, {}).setdefault(ex, 0)
    summary[name][ex] += amt

cols_summary = st.columns(2)
for i, (name, debts) in enumerate(summary.items()):
    active_debts = {k: v for k, v in debts.items() if v != 0}
    if active_debts:
        with cols_summary[i % 2].expander(f"👤 {name}", expanded=True):
            for ex, total in active_debts.items():
                val = seconds_to_str(total) if ex_unit_map.get(ex) == "time" else total
                st.write(f"**{ex}**: {val}")
