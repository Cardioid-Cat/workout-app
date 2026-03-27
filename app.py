import streamlit as st
from supabase import create_client, Client
import requests

st.set_page_config(page_title="Workout Tracker", page_icon="💪")

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ И БОТА ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    admin_pass = st.secrets["ADMIN_PASSWORD"]
    supabase: Client = create_client(url, key)
    
    # Конфиг телеграма
    tg_token = st.secrets.get("TELEGRAM_BOT_TOKEN")
    tg_chat_id = st.secrets.get("TELEGRAM_CHAT_ID")
except Exception:
    st.error("Ошибка конфигурации! Проверьте Secrets.")
    st.stop()

# --- ФУНКЦИЯ УВЕДОМЛЕНИЙ ---
def send_tg_notification(text):
    if tg_token and tg_chat_id:
        # Добавляем @all (в ТГ это обычно делается через текстовое упоминание, 
        # если бот имеет права админа или если в группе включены теги)
        full_message = f"📢 @all\n{text}"
        url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
        try:
            requests.post(url, json={"chat_id": tg_chat_id, "text": full_message})
        except:
            pass

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
    
    # Получаем имя для уведомления
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
        
        # ОТМЕНА
        if logs:
            last = logs[0]
            st.warning(f"Последнее: {last['profiles']['name']} - {last['exercise_type']}")
            if st.button("⬅️ Отменить это", use_container_width=True):
                supabase.table("workout_logs").delete().eq("id", last['id']).execute()
                send_tg_notification(f"🔙 Ошибочка вышла! Действие '{last['exercise_type']}' для {last['profiles']['name']} отменено.")
                st.rerun()
            st.divider()

        # 1. ИГРЫ
        with st.expander("🎲 НАСТРОЙКА ИГР"):
            with st.form("g_form", clear_on_submit=True):
                n_g = st.text_input("Название")
                n_e = st.selectbox("Упражнение", list(ex_unit_map.keys()))
                n_v = st.text_input("Значение")
                if st.form_submit_button("Добавить"):
                    if 'games_config' not in st.session_state: st.session_state.games_config = {}
                    st.session_state.games_config[n_g] = {"ex": n_e, "val": n_v, "type": ex_unit_map.get(n_e)}
                    st.rerun()
        
        # 2. УПРАЖНЕНИЯ (ВЕРНУЛ!)
        with st.expander("🏋️ УПРАЖНЕНИЯ"):
            with st.form("ex_form", clear_on_submit=True):
                e_name = st.text_input("Название")
                e_type = st.radio("Тип", ["count", "time"], format_func=lambda x: "Раз" if x=="count" else "Время")
                if st.form_submit_button("Добавить"):
                    supabase.table("exercise_types").insert({"name": e_name, "unit_type": e_type}).execute()
                    st.rerun()
            for name in ex_unit_map.keys():
                c1, c2 = st.columns([4,1])
                c1.write(name)
                if c2.button("🗑", key=f"del_ex_{name}"):
                    supabase.table("exercise_types").delete().eq("name", name).execute()
                    st.rerun()

        # 3. УЧАСТНИКИ
        with st.expander("👤 УЧАСТНИКИ"):
            with st.form("p_form", clear_on_submit=True):
                p_n = st.text_input("Имя")
                if st.form_submit_button("Добавить"):
                    supabase.table("profiles").insert({"name": p_n}).execute()
                    st.rerun()

# --- ГЛАВНЫЙ ЭКРАН ---
st.title("💪 Долги по тренировкам")

# РЕЙТИНГ
if logs:
    wins = {}
    for l in logs:
        if l['exercise_type'] == "Победа в игре":
            name = l['profiles']['name']
            wins[name] = wins.get(name, 0) + l['amount']
    if wins:
        st.subheader("🏆 Топ победителей")
        sorted_wins = sorted(wins.items(), key=lambda x: x[1], reverse=True)
        cols = st.columns(len(sorted_wins))
        for i, (name, count) in enumerate(sorted_wins):
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉"
            cols[i].metric(label=f"{medal} {name}", value=count)
        st.divider()

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
        if 'games_config' in st.session_state and st.session_state.games_config:
            g_name = st.selectbox("Игра?", list(st.session_state.games_config.keys()))
            w_name = st.selectbox("Победитель?", [p['name'] for p in profiles])
            if st.button("🔥 Раздать долги", type="primary", use_container_width=True):
                g = st.session_state.games_config[g_name]
                w_id = next(p['id'] for p in profiles if p['name'] == w_name)
                # Победа
                supabase.table("workout_logs").insert({"profile_id": w_id, "exercise_type": "Победа в игре", "amount": 1}).execute()
                # Долги
                for p in profiles:
                    if p['id'] != w_id:
                        add_entry(p['id'], g['ex'], g['val'], is_time=(g['type']=="time"), silent=True)
                send_tg_notification(f"🏆 {w_name} выиграл(а) в '{g_name}'! Всем остальным начислен долг: {g['ex']} {g['val']}.")
                st.rerun()

st.divider()

# ТАБЛИЦА
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
