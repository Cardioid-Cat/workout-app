import streamlit as st
from supabase import create_client, Client

st.set_page_config(page_title="Workout Tracker", page_icon="💪")

# --- ИНИЦИАЛИЗАЦИЯ БАЗЫ ---
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    admin_pass = st.secrets["ADMIN_PASSWORD"]
    supabase: Client = create_client(url, key)
except Exception:
    st.error("Ошибка конфига! Проверьте Secrets.")
    st.stop()

# --- СОСТОЯНИЕ (SESSION STATE) ---
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

# Базовые игры (хранятся в сессии)
if 'games_config' not in st.session_state:
    st.session_state.games_config = {
        "Игра 1: Отжимания (50)": {"ex": "Отжимания", "val": 50, "type": "count"},
        "Игра 2: Приседания (100)": {"ex": "Приседания", "val": 100, "type": "count"},
        "Игра 3: Планка (3 мин)": {"ex": "Планка", "val": "3:00", "type": "time"},
        "Игра 4: Гантели (50)": {"ex": "Гантели", "val": 50, "type": "count"},
        "Игра 5: Вис (2 мин)": {"ex": "Вис", "val": "2:00", "type": "time"}
    }

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
    if is_writeoff: amount = -amount
    supabase.table("workout_logs").insert({
        "profile_id": p_id, "exercise_type": ex_name, "amount": amount
    }).execute()
    if not silent: st.rerun()

# --- ЗАГРУЗКА ДАННЫХ ИЗ БАЗЫ ---
profiles = supabase.table("profiles").select("*").order("name").execute().data

try:
    ex_types_data = supabase.table("exercise_types").select("name, unit_type").execute().data
    ex_unit_map = {ex['name']: ex['unit_type'] for ex in ex_types_data}
except:
    ex_unit_map = {"Планка": "time", "Вис": "time"}

logs = supabase.table("workout_logs").select("amount, exercise_type, profiles(name)").execute().data

# --- БОКОВАЯ ПАНЕЛЬ (НАСТРОЙКИ) ---
with st.sidebar:
    st.title("⚙️ Настройки")
    
    if not st.session_state.authenticated:
        pwd = st.text_input("Пароль админа", type="password")
        if pwd == admin_pass:
            st.session_state.authenticated = True
            st.rerun()
    else:
        if st.button("🔴 Выйти"):
            st.session_state.authenticated = False
            st.rerun()

    if st.session_state.authenticated:
        st.divider()
        
        # 1. НАСТРОЙКА ИГР
        with st.expander("🎲 НАСТРОЙКА ИГР"):
            with st.form("add_game", clear_on_submit=True):
                st.write("Создать новую:")
                new_g_name = st.text_input("Название (напр. Игра 6)")
                new_g_ex = st.selectbox("Упражнение", list(ex_unit_map.keys()))
                new_g_val = st.text_input("Долг (50 или 1:30)")
                
                if st.form_submit_button("➕ Добавить игру"):
                    if new_g_name and new_g_val:
                        u_type = ex_unit_map.get(new_g_ex, "count")
                        st.session_state.games_config[new_g_name] = {
                            "ex": new_g_ex, "val": new_g_val, "type": u_type
                        }
                        st.rerun()
            
            st.write("---")
            st.write("Существующие игры:")
            for g_key in list(st.session_state.games_config.keys()):
                col1, col2 = st.columns([4, 1])
                g_info = st.session_state.games_config[g_key]
                col1.write(f"**{g_key}** ({g_info['ex']} - {g_info['val']})")
                if col2.button("🗑", key=f"del_game_{g_key}"):
                    del st.session_state.games_config[g_key]
                    st.rerun()

        # 2. УЧАСТНИКИ
        with st.expander("👤 УЧАСТНИКИ"):
            with st.form("add_user", clear_on_submit=True):
                new_name = st.text_input("Имя нового героя")
                if st.form_submit_button("Добавить"):
                    supabase.table("profiles").insert({"name": new_name}).execute()
                    st.rerun()
            st.write("---")
            for p in profiles:
                col1, col2 = st.columns([3, 1])
                col1.write(p['name'])
                if col2.button("🗑", key=f"del_u_{p['id']}"):
                    supabase.table("profiles").delete().eq("id", p['id']).execute()
                    st.rerun()

        # 3. УПРАЖНЕНИЯ
        with st.expander("🏋️ УПРАЖНЕНИЯ"):
            with st.form("add_ex", clear_on_submit=True):
                new_ex = st.text_input("Название (напр. Гантели)")
                new_type = st.radio("Тип", ["count", "time"], format_func=lambda x: "Раз" if x=="count" else "Время (мм:сс)")
                if st.form_submit_button("Добавить упражнение"):
                    supabase.table("exercise_types").insert({"name": new_ex, "unit_type": new_type}).execute()
                    st.rerun()
            st.write("---")
            for name in ex_unit_map.keys():
                col1, col2 = st.columns([3, 1])
                col1.write(name)
                if col2.button("🗑", key=f"del_ex_{name}"):
                    supabase.table("exercise_types").delete().eq("name", name).execute()
                    st.rerun()

# --- ГЛАВНЫЙ ЭКРАН ---
st.title("💪 Долги по тренировкам")

# --- ТОП ПОБЕДИТЕЛЕЙ ---
if logs:
    wins = {}
    for l in logs:
        if l['exercise_type'] == "Победа в игре":
            name = l['profiles']['name']
            wins[name] = wins.get(name, 0) + l['amount']
    
    if wins:
        st.subheader("🏆 Топ победителей")
        # Сортируем по количеству побед
        sorted_wins = sorted(wins.items(), key=lambda x: x[1], reverse=True)
        
        # Создаем красивые колонки с медалями
        cols = st.columns(len(sorted_wins))
        for i, (name, w_count) in enumerate(sorted_wins):
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else "🏅"
            cols[i].metric(label=f"{medal} {name}", value=f"{w_count}")
        st.divider()

if st.session_state.authenticated:
    tab1, tab2 = st.tabs(["📝 Ручной ввод", "🎲 Итоги игры"])
    
    # --- ВКЛАДКА 1: РУЧНОЙ ВВОД ---
    with tab1:
        user_name = st.selectbox("Кому?", [p['name'] for p in profiles], key="manual_user")
        uid = next(p['id'] for p in profiles if p['name'] == user_name)
        
        cols = st.columns(3)
        for i, name in enumerate(ex_unit_map.keys()):
            with cols[i % 3]:
                if st.button(name, use_container_width=True, key=f"btn_{name}"):
                    st.session_state.active_ex = name
        
        if "active_ex" in st.session_state:
            active = st.session_state.active_ex
            u_type = ex_unit_map.get(active, "count")
            with st.container(border=True):
                st.write(f"Выбрано: **{active}**")
                val = st.text_input("Сколько?", placeholder="Напр: 50 или 2:30", key="val_input")
                c1, c2 = st.columns(2)
                with c1:
                    if st.button("➕ Добавить долг", type="primary", use_container_width=True):
                        add_entry(uid, active, val, is_time=(u_type=="time"))
                with c2:
                    if st.button("✅ Списать (сделал)", use_container_width=True):
                        add_entry(uid, active, val, is_time=(u_type=="time"), is_writeoff=True)

    # --- ВКЛАДКА 2: ИТОГИ ИГРЫ ---
    with tab2:
        if not st.session_state.games_config:
            st.warning("Нет добавленных игр. Добавьте их в настройках слева!")
        else:
            st.write("Выберите игру и победителя. Долги автоматически начислятся всем остальным участникам.")
            game_choice = st.selectbox("Какая игра была?", list(st.session_state.games_config.keys()))
            winner_name = st.selectbox("Кто победил?", [p['name'] for p in profiles], key="game_winner")
            
            if st.button("🔥 Записать победу и раздать долги", type="primary", use_container_width=True):
                g = st.session_state.games_config[game_choice]
                winner_id = next(p['id'] for p in profiles if p['name'] == winner_name)
                
                # 1. Записываем победу победителю
                supabase.table("workout_logs").insert({
                    "profile_id": winner_id, "exercise_type": "Победа в игре", "amount": 1
                }).execute()

                # 2. Раздаем долги остальным
                for p in profiles:
                    if p['id'] != winner_id:
                        add_entry(p['id'], g['ex'], g['val'], is_time=(g['type']=="time"), silent=True)
                
                st.success(f"🏆 {winner_name} получает победу! Всем остальным добавлен долг: {g['ex']} {g['val']}.")
                st.rerun()

st.divider()

# --- ТАБЛИЦА ДОЛГОВ ---
st.subheader("📊 Текущие долги")
if logs:
    summary = {}
    for l in logs:
        name, ex, amt = l['profiles']['name'], l['exercise_type'], l['amount']
        
        # Скрываем системные записи (Списания, старые баги и Победы)
        if "[" in ex or ex == "Списание" or ex == "Победа в игре": 
            continue
            
        summary.setdefault(name, {}).setdefault(ex, 0)
        summary[name][ex] += amt

    for name, debts in summary.items():
        active_debts = {k: v for k, v in debts.items() if v != 0}
        if active_debts:
            with st.expander(f"👤 {name}", expanded=True):
                for ex, total in active_debts.items():
                    if ex in ["Вис", "Планка"] or ex_unit_map.get(ex) == "time":
                        st.write(f"**{ex}**: {seconds_to_str(total)}")
                    else:
                        st.write(f"**{ex}**: {total}")
else:
    st.write("Чисто! Все всё отработали.")
