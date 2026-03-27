import streamlit as st
from supabase import create_client, Client

# Настройка страницы
st.set_page_config(page_title="Workout Tracker", page_icon="💪", layout="centered")

# Инициализация подключения к Supabase
try:
    # Используем секреты Streamlit Cloud
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception:
    st.error("Ошибка: Настройте SUPABASE_URL и SUPABASE_KEY в разделе Secrets!")
    st.stop()

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def time_to_seconds(t_str):
    """Преобразует строку 'мин:сек' или секунды в целое число секунд."""
    try:
        if ":" in str(t_str):
            m, s = map(int, str(t_str).split(":"))
            return m * 60 + s
        return int(t_str)
    except Exception:
        return 0

def seconds_to_str(sec):
    """Преобразует секунды обратно в формат 'мин:сек'."""
    m = abs(sec) // 60
    s = abs(sec) % 60
    return f"{'-' if sec < 0 else ''}{m}:{s:02d}"

def add_entry(p_id, ex_name, val, is_time=False, is_writeoff=False):
    """Отправляет запись в базу данных."""
    # Защита от пустых или некорректных названий
    if not ex_name or ex_name == "Списание":
        st.error("Ошибка: Упражнение не выбрано!")
        return

    amount = time_to_seconds(val) if is_time else int(val)
    if amount == 0:
        return
        
    # Если это списание, число становится отрицательным
    if is_writeoff:
        amount = -amount
        
    try:
        supabase.table("workout_logs").insert({
            "profile_id": p_id, 
            "exercise_type": ex_name, 
            "amount": amount
        }).execute()
        st.success(f"Записано: {ex_name}")
        st.rerun()
    except Exception as e:
        st.error(f"Ошибка базы данных: {e}")

# --- ЗАГРУЗКА ДАННЫХ ---

try:
    profiles = supabase.table("profiles").select("*").order("name").execute().data
    ex_types_data = supabase.table("exercise_types").select("*").order("name").execute().data
    # Карта для определения типа упражнения (время или кол-во)
    ex_unit_map = {ex['name']: ex.get('unit_type', 'count') for ex in ex_types_data}
except Exception as e:
    st.error(f"Ошибка при загрузке данных: {e}")
    profiles, ex_unit_map = [], {}

# --- БОКОВОЕ МЕНЮ (НАСТРОЙКИ) ---

with st.sidebar:
    st.header("⚙️ Настройки")
    
    # Управление пользователями
    with st.expander("👤 Участники"):
        with st.form("add_user_form", clear_on_submit=True):
            new_user = st.text_input("Имя нового атлета")
            if st.form_submit_button("Добавить") and new_user:
                supabase.table("profiles").insert({"name": new_user}).execute()
                st.rerun()
        
        for p in profiles:
            if st.button(f"🗑 {p['name']}", key=f"del_u_{p['id']}"):
                supabase.table("profiles").delete().eq("id", p['id']).execute()
                st.rerun()

    # Управление упражнениями
    with st.expander("🏋️ Упражнения"):
        with st.form("add_ex_form", clear_on_submit=True):
            ex_n = st.text_input("Название (напр. Прыжки)")
            ex_t = st.radio("Тип", ["Кол-во (раз)", "Время (мин:сек)"])
            if st.form_submit_button("Создать"):
                u_type = "time" if "Время" in ex_t else "count"
                if ex_n:
                    supabase.table("exercise_types").insert({"name": ex_n, "unit_type": u_type}).execute()
                    st.rerun()

        for ex_name in ex_unit_map.keys():
            if st.button(f"🗑 {ex_name}", key=f"del_ex_{ex_name}"):
                supabase.table("exercise_types").delete().eq("name", ex_name).execute()
                st.rerun()

# --- ОСНОВНОЙ ИНТЕРФЕЙС ---

st.title("💪 Трекер тренировочных долгов")

if not profiles:
    st.info("Добро пожаловать! Сначала добавьте участников в боковом меню слева.")
    st.stop()

# Выбор пользователя
user_name = st.selectbox("Кто сегодня тренируется?", [p['name'] for p in profiles])
user_id = next(p['id'] for p in profiles if p['name'] == user_name)

# Кнопки выбора упражнения
st.subheader("1. Выберите упражнение:")
if ex_unit_map:
    cols = st.columns(3)
    for i, name in enumerate(ex_unit_map.keys()):
        with cols[i % 3]:
            if st.button(name, use_container_width=True):
                st.session_state.active_ex = name
else:
    st.write("Список упражнений пуст.")

# Ввод данных
if "active_ex" in st.session_state:
    active = st.session_state.active_ex
    u_type = ex_unit_map.get(active, "count")
    
    st.markdown(f"---")
    st.info(f"Выбрано упражнение: **{active}**")
    
    if u_type == "time":
        val = st.text_input("Сколько времени? (например, 1:30 или 90)", placeholder="1:30")
    else:
        val = st.number_input("Сколько повторений?", min_value=1, step=5, value=10)

    col_add, col_sub = st.columns(2)
    with col_add:
        if st.button("➕ Добавить в долг", type="primary", use_container_width=True):
            add_entry(user_id, active, val, is_time=(u_type=="time"))
    with col_sub:
        if st.button("✅ Списать (выполнил)", use_container_width=True):
            add_entry(user_id, active, val, is_time=(u_type=="time"), is_writeoff=True)

st.divider()

# --- ТАБЛИЦА РЕЗУЛЬТАТОВ ---

st.subheader("📊 Текущие долги")
try:
    # Загружаем логи и объединяем с именами профилей
    logs = supabase.table("workout_logs").select("amount, exercise_type, profiles(name)").execute().data
    
    if logs:
        # Группируем данные: Имя -> Упражнение -> Сумма
        summary = {}
        for l in logs:
            n = l['profiles']['name']
            ex = l['exercise_type']
            amt = l['amount']
            
            # Пропускаем записи-ошибки "Списание"
            if ex == "Списание": continue
                
            summary.setdefault(n, {}).setdefault(ex, 0)
            summary[n][ex] += amt

        # Отображение
        has_debts = False
        for name, debts in summary.items():
            # Показываем только если есть ненулевые долги
            active_debts = {k: v for k, v in debts.items() if v != 0}
            if active_debts:
                has_debts = True
                with st.expander(f"👤 {name}", expanded=True):
                    for ex, total in active_debts.items():
                        unit = ex_unit_map.get(ex, "count")
                        display_val = seconds_to_str(total) if unit == "time" else total
                        st.write(f"**{ex}**: {display_val}")
        
        if not has_debts:
            st.success("Все долги закрыты! Чисто.")
    else:
        st.write("Логов пока нет. Начните тренировку!")
except Exception as e:
    st.error(f"Не удалось загрузить таблицу долгов: {e}")
