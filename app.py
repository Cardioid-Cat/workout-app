import streamlit as st
from supabase import create_client, Client
import requests
from postgrest.exceptions import APIError 

st.set_page_config(page_title="Workout Tracker", page_icon="💪", layout="wide")

# --- ИСПРАВЛЕННЫЙ БЛОК СКРЫТИЯ (Стрелочка меню теперь видна!) ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            .stAppDeployButton {display:none;}
            /* Скрываем только ссылки в хедере, но оставляем сам хедер для кнопки меню */
            header > div:nth-child(3) {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- ИНИЦИАЛИЗАЦИЯ ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
    tg_token = st.secrets.get("TELEGRAM_BOT_TOKEN")
except Exception as e:
    st.error(f"Ошибка конфигурации Secrets: {e}")
    st.stop()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_room_data(slug):
    res = supabase.table("rooms").select("*").eq("slug", slug).execute()
    return res.data[0] if res.data else None

def plural_wins(n):
    n = abs(n) % 100
    n1 = n % 10
    if 10 < n < 20: return f"{n} побед"
    if n1 > 1 and n1 < 5: return f"{n} победы"
    if n1 == 1: return f"{n} победа"
    return f"{n} побед"

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

# --- ЛОГИКА КОМНАТ ---
room_slug = st.query_params.get("room")

if not room_slug:
    st.title("🚀 Workout SaaS: Создать комнату")
    with st.container(border=True):
        new_title = st.text_input("Название (напр: Моя Качалка)")
        new_slug = st.text_input("Придумайте адрес для ссылки (напр: matrix)")
        new_pass = st.text_input("Пароль админа", type="password")
        new_tg_chat = st.text_input("ID чата в Telegram (необязательно)")
        
        if st.button("Создать комнату", type="primary"):
            if not new_title.strip() or not new_slug.strip() or not new_pass.strip():
                st.warning("⚠️ Поля 'Название', 'Адрес' и 'Пароль' не могут быть пустыми.")
            else:
                try:
                    clean_slug = new_slug.lower().strip()
                    supabase.table("rooms").insert({
                        "slug": clean_slug, "title": new_title.strip(), 
                        "password": new_pass, "tg_chat_id": new_tg_chat.strip() if new_tg_chat.strip() else None
                    }).execute()
                    st.success("✅ Комната создана!")
                    st.code(f"https://workout-app-o8dt87vxa4t4a8nsr49oc3.streamlit.app/?room={clean_slug}")
                except Exception: 
                    st.error("Этот адрес уже занят.")
    st.stop()

room = get_room_data(room_slug)
if not room:
    st.error("Комната не найдена.")
    st.stop()

room_id = room['id']
auth_key = f"auth_{room_id}"

# --- ФУНКЦИИ И ЛОГИКА ---
def send_tg_notification(text):
    current_chat_id = room.get("tg_chat_id")
    if not tg_token or not current_chat_id: return
    full_message = f"📢 @all ({room['title']})\n{text}"
    api_url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
    try: requests.post(api_url, json={"chat_id": current_chat_id, "text": full_message}, timeout=5)
    except: pass

def add_entry(p_id, ex_name, val, is_time=False, is_writeoff=False, silent=False):
    if not str(val).strip():
        st.warning("⚠️ Введите значение.")
        return
    amount = time_to_seconds(val) if is_time else int(val)
    if amount == 0: return
    actual_amount = -amount if is_writeoff else amount
    supabase.table("workout_logs").insert({
        "profile_id": p_id, "exercise_type": ex_name, "amount": actual_amount, "room_id": room_id
    }).execute()
    if not silent:
        p_data = supabase.table("profiles").select("name").eq("id", p_id).single().execute()
        u_name = p_data.data['name']
        action = "списал(а)" if is_writeoff else "получил(а) долг"
        send_tg_notification(f"⚖️ {u_name} {action}: {ex_name} ({val})")
        st.rerun()

profiles = supabase.table("profiles").select("*").eq("room_id", room_id).order("name").execute().data
ex_types_data = supabase.table("exercise_types").select("name, unit_type").eq("room_id", room_id).execute().data
ex_unit_map = {ex['name']: ex['unit_type'] for ex in ex_types_data}
games_data = supabase.table("games_presets").select("*").eq("room_id", room_id).order("game_name").execute().data
logs = supabase.table("workout_logs").select("id, amount, exercise_type, profiles(name)").eq("room_id", room_id).order("created_at", desc=True).execute().data

st.title(f"💪 {room['title']}")

with st.sidebar:
    st.title("⚙️ Настройки")
    if not st.session_state.get(auth_key):
        with st.form("login_form"):
            pwd = st.text_input("Пароль админа", type="password")
            if st.form_submit_button("Войти"):
                if pwd == room['password']:
                    st.session_state[auth_key] = True
                    st.rerun()
                else: st.error("Неверно")
    else:
        if st.button("🔴 Выйти"):
            st.session_state[auth_key] = False
            st.rerun()

        st.divider()
        with st.expander("🎲 НАСТРОЙКА ИГР"):
            with st.form("g_form", clear_on_submit=True):
                n_g = st.text_input("Название игры")
                n_e = st.selectbox("Упражнение наказания", list(ex_unit_map.keys()))
                n_v = st.text_input("Значение (кол-во или мин:сек)")
                if st.form_submit_button("Сохранить игру"):
                    if not n_g.strip() or not n_v.strip():
                        st.warning("⚠️ Название игры и значение не могут быть пустыми.")
                    else:
                        try:
                            supabase.table("games_presets").insert({
                                "game_name": n_g.strip(), "ex_name": n_e, "val": n_v.strip(), 
                                "unit_type": ex_unit_map.get(n_e), "room_id": room_id
                            }).execute()
                            st.rerun()
                        except: st.error("Ошибка добавления.")

        with st.expander("🏋️ УПРАЖНЕНИЯ"):
            with st.form("ex_form", clear_on_submit=True):
                e_name = st.text_input("Название")
                e_type = st.radio("Тип", ["count", "time"])
                if st.form_submit_button("Добавить"):
                    if not e_name.strip():
                        st.warning("⚠️ Название не может быть пустым.")
                    else:
                        try:
                            supabase.table("exercise_types").insert({"name": e_name.strip(), "unit_type": e_type, "room_id": room_id}).execute()
                            st.rerun()
                        except: st.error("Уже есть.")

        with st.expander("👤 УЧАСТНИКИ"):
            with st.form("p_form", clear_on_submit=True):
                p_n = st.text_input("Имя")
                if st.form_submit_button("Добавить"):
                    if not p_n.strip():
                        st.warning("⚠️ Имя не может быть пустым.")
                    else:
                        try:
                            supabase.table("profiles").insert({"name": p_n.strip(), "room_id": room_id}).execute()
                            st.rerun()
                        except: st.error("Уже есть.")

# --- ГЛАВНЫЙ ЭКРАН ---
if st.session_state.get(auth_key):
    tab1, tab2 = st.tabs(["📝 Ввод", "🎲 Игра"])
    with tab1:
        u_names = [p['name'] for p in profiles]
        if u_names:
            u_name = st.selectbox("Кому?", u_names)
            u_id = next(p['id'] for p in profiles if p['name'] == u_name)
            cols = st.columns(3)
            for i, name in enumerate(ex_unit_map.keys()):
                if cols[i % 3].button(name, key=f"btn_{name}"):
                    st.session_state.active_ex = name
            if "active_ex" in st.session_state:
                active = st.session_state.active_ex
                with st.container(border=True):
                    st.write(f"Выбрано: **{active}**")
                    val = st.text_input("Сколько?", key="val_input")
                    c1, c2 = st.columns(2)
                    if c1.button("➕ Добавить", type="primary"):
                        add_entry(u_id, active, val, is_time=(ex_unit_map.get(active)=="time"))
                    if c2.button("✅ Списать"):
                        add_entry(u_id, active, val, is_time=(ex_unit_map.get(active)=="time"), is_writeoff=True)

    with tab2:
        if games_data:
            g_options = {g['game_name']: g for g in games_data}
            sel_g = st.selectbox("Игра?", list(g_options.keys()))
            game = g_options[sel_g]
            winners = st.multiselect("Кто победил?", [p['name'] for p in profiles])
            if st.button("🔥 Раздать долги", type="primary"):
                if winners:
                    winner_ids = [p['id'] for p in profiles if p['name'] in winners]
                    for w_id in winner_ids:
                        supabase.table("workout_logs").insert({"profile_id": w_id, "exercise_type": f"🏆 Победа: {sel_g}", "amount": 1, "room_id": room_id}).execute()
                    for p in profiles:
                        if p['id'] not in winner_ids:
                            add_entry(p['id'], game['ex_name'], game['val'], is_time=(game['unit_type']=="time"), silent=True)
                    send_tg_notification(f"🏆 {', '.join(winners)} победили!")
                    st.rerun()
                else: st.warning("Выберите победителей!")

st.divider()
st.subheader("🥇 Рейтинг чемпионов")
hof = {}
for l in logs:
    if "🏆" in l['exercise_type']:
        n = l['profiles']['name']
        hof[n] = hof.get(n, 0) + 1
if hof:
    for i, (name, count) in enumerate(sorted(hof.items(), key=lambda x: x[1], reverse=True)):
        st.write(f"{'🥇' if i==0 else '👤'} **{name}**: {plural_wins(count)}")

st.subheader("📊 Текущие долги")
summary = {}
for l in logs:
    if "🏆" in l['exercise_type']: continue
    name, ex, amt = l['profiles']['name'], l['exercise_type'], l['amount']
    summary.setdefault(name, {}).setdefault(ex, 0)
    summary[name][ex] += amt

for name, debts in summary.items():
    active = {k: v for k, v in debts.items() if v != 0}
    if active:
        with st.expander(f"👤 {name}", expanded=True):
            for ex, total in active.items():
                val = seconds_to_str(total) if ex_unit_map.get(ex) == "time" else total
                st.write(f"**{ex}**: {val}")
