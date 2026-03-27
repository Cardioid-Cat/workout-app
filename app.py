import streamlit as st
from supabase import create_client, Client
import requests

st.set_page_config(page_title="Workout Tracker", page_icon="💪")

# --- ИНИЦИАЛИЗАЦИЯ ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    admin_pass = st.secrets["ADMIN_PASSWORD"]
    supabase: Client = create_client(url, key)
    
    tg_token = st.secrets.get("TELEGRAM_BOT_TOKEN")
    tg_chat_id = st.secrets.get("TELEGRAM_CHAT_ID")
except Exception as e:
    st.error(f"Ошибка конфигурации Secrets: {e}")
    st.stop()

# --- ФУНКЦИЯ УВЕДОМЛЕНИЙ ---
def send_tg_notification(text, is_test=False):
    if not tg_token or not tg_chat_id:
        if is_test: st.error("Токен или ID чата не найдены в Secrets!")
        return
    
    full_message = f"📢 @all\n{text}"
    api_url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
    try:
        response = requests.post(api_url, json={"chat_id": tg_chat_id, "text": full_message}, timeout=5)
        if response.status_code != 200:
            if is_test: st.error(f"Ошибка ТГ: {response.text}")
        elif is_test:
            st.success("Тестовое сообщение отправлено в группу!")
    except Exception as e:
        if is_test: st.error(f"Ошибка запроса: {e}")

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
    actual_amount = -amount if is_writeoff else amount
    
    p_data = supabase.table("profiles").select("name").eq("id", p_id).single().execute()
    u_name = p_data.data['name'] if p_data.data else "Кто-то"

    supabase.table("workout_logs").insert({
        "profile_id": p_id, "exercise_type": ex_name, "amount": actual_amount
    }).execute()
    
    if not silent:
        action = "списал(а)" if is_writeoff else "получил(а) долг"
        display_val = val if is_time else str(val)
        send_tg_notification(f"⚖️ {u_name} {action}: {ex_name} ({display_val})")
        st.rerun()

# --- СОСТОЯНИЕ ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# --- ЗАГРУЗКА ДАННЫХ ---
profiles = supabase.table("profiles").select("*").order("name").execute().data
try:
    ex_types_data = supabase.table("exercise_types").select("name, unit_type").execute().data
    ex_unit_map = {ex['name']: ex['unit_type'] for ex in ex_types_data}
except:
    ex_unit_map = {}

# Загружаем сохраненные игры из базы
try:
    games_data = supabase.table("games_presets").select("*").execute().data
except:
    games_data = []

logs = supabase.table("workout_logs").select("id, amount, exercise_type, profiles(name)").order("created_at", desc=True).execute().data

# --- БОКОВАЯ ПАНЕЛЬ ---
with st.sidebar:
    st.title("⚙️ Настройки")
    
    if not st.session_state.authenticated:
        with st.form("login_form"):
            pwd = st.text_input("Пароль админа", type="password")
            if st.form_submit_button("Войти"):
                if pwd == admin_pass:
                    st.session_state.authenticated = True
                    st.rerun()
                else: st.error("Неверно")
    else:
        if st.button("🔴 Выйти"):
            st.session_state.authenticated = False
            st.rerun()

    if st.session_state.authenticated:
        st.divider()
        
        # 1. ТЕСТ БОТА
        if st.button("🔔 Тест уведомления", use_container_width=True):
            send_tg_notification("Проверка связи! Если вы это видите, всё настроено верно.", is_test=True)

        # 2. ИГРЫ (Теперь сохраняются в базу)
        with st.expander("🎲 НАСТРОЙКА ИГР"):
            with st.form("g_form", clear_on_submit=True):
                n_g = st.text_input("Название (напр. CS2)")
                n_e = st.selectbox("Упражнение", list(ex_unit_map.keys()))
                n_v = st.text_input("Значение (напр. 50 или 1:00)")
                if st.form_submit_button("Сохранить игру"):
                    supabase.table("games_presets").insert({
                        "game_name": n_g, "ex_name": n_e, "val": n_v, "unit_type": ex_unit_map.get(n_e)
                    }).execute()
                    st.rerun()
            for g in games_data:
                c1, c2 = st.columns([4,1])
                c1.write(f"{g['game_name']} ({g['ex_name']})")
                if c2.button("🗑", key=f"del_g_{g['id']}"):
                    supabase.table("games_presets").delete().eq("id", g['id']).execute()
                    st.rerun()
        
        # 3. УПРАЖНЕНИЯ
        with st.expander("🏋️ УПРАЖНЕНИЯ"):
            with st.form("ex_form", clear_on_submit=True):
                e_name = st.text_input("Название")
                e_type = st.radio("Тип", ["count", "time"], format_func=lambda x: "Раз" if x=="count" else "Время")
                if st.form_submit_button("Добавить"):
                    supabase.table("exercise_types").insert({"name": e_name, "unit_type": e_type}).execute()
                    st.rerun()

        # 4. УЧАСТНИКИ
        with st.expander("👤 УЧАСТНИКИ"):
            with st.form("p_form", clear_on_submit=True):
                p_n = st.text_input("Имя")
                if st.form_submit_button("Добавить"):
                    supabase.table("profiles").insert({"name": p_n}).execute()
                    st.rerun()
        
        # --- ОТМЕНА ДЕЙСТВИЯ (В САМОМ НИЗУ) ---
        if logs:
            st.divider()
            last = logs[0]
            st.caption(f"Последнее: {last['profiles']['name']} - {last['exercise_type']}")
            if st.button("⬅️ Отменить"):
                supabase.table("workout_logs").delete().eq("id", last['id']).execute()
                send_tg_notification(f"🔙 Отмена: действие '{last['exercise_type']}' удалено.")
                st.rerun()

# --- ГЛАВНЫЙ ЭКРАН ---
st.title("💪 Долги по тренировкам")

# ВВОД ДАННЫХ
if st.session_state.authenticated:
    tab1, tab2 = st.tabs(["📝 Ввод", "🎲 Игра"])
    
    with tab1:
        u_name = st.selectbox("Кому?", [p['name'] for p in profiles])
        u_id = next(p['id'] for p in profiles if p['name'] == u_name)
        cols = st.columns(3)
        for i, name in enumerate(ex_unit_map.keys()):
            with cols[i % 3]:
                if st.button(name, use_container_width=True, key=f"btn_{name}"):
                    st.session_state.active_ex = name
        
        if "active_ex" in st.session_state:
            active = st.session_state.active_ex
            with st.container(border=True):
                st.write(f"Выбрано: **{active}**")
                val = st.text_input("Сколько?")
                c1, c2 = st.columns(2)
                if c1.button("➕ Добавить", type="primary", use_container_width=True):
                    add_entry(u_id, active, val, is_time=(ex_unit_map.get(active)=="time"))
                if c2.button("✅ Списать", use_container_width=True):
                    add_entry(u_id, active, val, is_time=(ex_unit_map.get(active)=="time"), is_writeoff=True)

    with tab2:
        if games_data:
            g_options = {g['game_name']: g for g in games_data}
            selected_g_name = st.selectbox("Во что играли?", list(g_options.keys()))
            selected_game = g_options[selected_g_name]
            
            w_name = st.selectbox("Кто победил?", [p['name'] for p in profiles])
            if st.button("🔥 Раздать долги всем, кроме победителя", type="primary", use_container_width=True):
                w_id = next(p['id'] for p in profiles if p['name'] == w_name)
                # Логируем победу
                supabase.table("workout_logs").insert({"profile_id": w_id, "exercise_type": "Победа в игре", "amount": 1}).execute()
                # Раздаем долги
                for p in profiles:
                    if p['id'] != w_id:
                        add_entry(p['id'], selected_game['ex_name'], selected_game['val'], 
                                  is_time=(selected_game['unit_type']=="time"), silent=True)
                send_tg_notification(f"🏆 {w_name} выиграл(а) в '{selected_g_name}'! Всем остальным начислен долг: {selected_game['ex_name']} ({selected_game['val']}).")
                st.rerun()
        else:
            st.info("Сначала добавьте игры в настройках (сайдбар слева).")

st.divider()

# ТАБЛИЦА ДОЛГОВ
st.subheader("📊 Текущие долги")
summary = {}
for l in logs:
    name, ex, amt = l['profiles']['name'], l['exercise_type'], l['amount']
    if ex in ["Победа в игре", "Списание"] or "[" in ex: continue
    summary.setdefault(name, {}).setdefault(ex, 0)
    summary[name][ex] += amt

for name, debts in summary.items():
    active = {k: v for k, v in debts.items() if v != 0}
    if active:
        with st.expander(f"👤 {name}", expanded=True):
            for ex, total in active.items():
                val = seconds_to_str(total) if ex_unit_map.get(ex) == "time" else total
                st.write(f"**{ex}**: {val}")
