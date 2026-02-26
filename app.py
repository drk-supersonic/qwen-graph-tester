import streamlit as st
import json
import re
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import io
import base64
import textwrap

st.set_page_config(page_title="Qwen Graph Tester", layout="wide")

st.title("Qwen Graph Tester")
st.markdown("Вставь **весь сырой JSON-ответ** из терминала — приложение вытащит Python-код и отрендерит графики напрямую.")

# ---------- sanitize & extract (оставил как было) -------------------------
def sanitize_code(code: str) -> str:
    tq_d = '"' + '"' + '"'
    tq_s = "'" + "'" + "'"
    if code.count(tq_d) % 2 != 0:
        idx = code.rfind(tq_d)
        code = code[:idx].rstrip()
    if code.count(tq_s) % 2 != 0:
        idx = code.rfind(tq_s)
        code = code[:idx].rstrip()

    lines = code.splitlines()
    for i in range(len(lines), 0, -1):
        candidate = "\n".join(lines[:i])
        try:
            compile(candidate, "<string>", "exec")
            return candidate
        except SyntaxError:
            continue
    return code

def extract_code(raw_json: str):
    try:
        data = json.loads(raw_json)
        content = data["choices"][0]["message"]["content"]
    except Exception as e:
        st.error(f"Не удалось распарсить JSON: {e}")
        return None

    match = re.search(r"```python\s*(.*?)```", content, re.DOTALL)
    if match:
        return sanitize_code(match.group(1).strip())
    match = re.search(r"```\s*(.*?)```", content, re.DOTALL)
    if match:
        return sanitize_code(match.group(1).strip())
    return sanitize_code(content.strip())

# ---------- sample data ----------------------------------------------------
def make_sample_df() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n = 300
    dates = pd.date_range("2023-01-01", periods=n, freq="D")
    df = pd.DataFrame({
        "date": dates.astype(str),
        "sales": rng.integers(100, 5000, n).astype(float),
        "region": rng.choice(["Север", "Юг", "Запад", "Восток"], n),
        "product": rng.choice([f"Продукт {i}" for i in range(1, 16)], n),
        "category": rng.choice(["Электроника", "Одежда", "Еда", "Спорт"], n),
        "customer_type": rng.choice(["Розница", "Оптовик", "VIP"], n),
        "price": rng.uniform(10, 500, n).round(2),
        "discount": rng.uniform(0, 0.4, n).round(2),
        "quantity": rng.integers(1, 50, n),
    })
    return df

def try_load_csv(uploaded_file):
    if uploaded_file is None:
        return None
    try:
        return pd.read_csv(uploaded_file)
    except Exception as e:
        st.warning(f"Не удалось загрузить CSV: {e}")
        return None

# ---------- sidebar --------------------------------------------------------
with st.sidebar:
    st.header("Настройки")
    use_real_csv = st.checkbox("Загрузить реальный CSV вместо демо-данных", value=False)
    csv_file = None
    if use_real_csv:
        csv_file = st.file_uploader("CSV файл", type=["csv"])

    st.divider()
    disable_autofix = st.checkbox("🚫 Отключить авто-фикс колонок (для тестов Qwen)", value=True)
    st.caption("Когда включено — видишь настоящие ошибки модели, а не белый экран.")

    st.divider()
    st.caption("Демо-данные генерируются автоматически, если CSV не загружен.")

# ---------- main -----------------------------------------------------------
raw_json = st.text_area(
    "Вставь весь JSON-ответ модели",
    height=300,
    placeholder='{"choices": [{"message": {"content": "...код..."}}]}'
)

col_run, col_clear = st.columns([1, 5])
run = col_run.button("Запустить", type="primary")
if col_clear.button("Очистить"):
    st.rerun()

if run and raw_json.strip():
    code = extract_code(raw_json)
    if not code:
        st.stop()

    with st.expander("Извлечённый код", expanded=False):
        st.code(code, language="python")
        try:
            compile(code, "<string>", "exec")
            st.success("Синтаксис Python валиден ✅")
        except SyntaxError as se:
            st.warning(f"После санитизации остались проблемы: {se}")

    st.divider()
    st.subheader("Результат рендера")

    real_df = try_load_csv(csv_file) if use_real_csv else None
    sample_df = real_df if real_df is not None else make_sample_df()

    exec_ns = { ... }  # (весь словарь как был — я не стал его копировать, он не менялся)

    # === ВСЁ ОСТАЛЬНОЕ БЕЗ ИЗМЕНЕНИЙ ДО try: exec ===

    # ... (весь твой код до try: exec(textwrap.dedent(patched), exec_ns)  оставь как есть)

    try:
        exec(textwrap.dedent(patched), exec_ns)
    except KeyError as e:
        missing_col = str(e).strip("'\"")
        st.error(f'KeyError: {e} — типичная ошибка Qwen')

        if disable_autofix:
            st.info("Авто-фикс отключён. Это нормально для тестирования Qwen.")
            found_dfs = {k:v for k,v in exec_ns.items() if isinstance(v, pd.DataFrame) and not k.startswith('_')}
            if found_dfs:
                st.warning('Доступные DataFrame и их колонки:')
                for nm, fr in found_dfs.items():
                    st.code(f'{nm}: {list(fr.columns)}', language='python')
        else:
            # старый автофикс (оставил на случай, если будешь тестировать с CSV)
            # ... твой старый блок ...
            pass

    except Exception as e:
        err_type = type(e).__name__
        st.error(f'Ошибка: {err_type}: {e}')
        import traceback as _tb
        tb_str = _tb.format_exc()
        model_lines = [l for l in tb_str.splitlines() if '<string>' in l]
        if model_lines:
            st.code('\n'.join(model_lines), language='text')

else:
    st.warning("Вставь JSON-ответ модели перед запуском.")
