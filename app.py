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


# ---------- sanitize --------------------------------------------------------

def sanitize_code(code: str) -> str:
    # Маркеры строим через конкатенацию символов, чтобы не ломать сам app.py
    tq_d = '"' + '"' + '"'
    tq_s = "'" + "'" + "'"

    # Если тройных кавычек нечётное число — обрезаем до последнего вхождения
    if code.count(tq_d) % 2 != 0:
        idx = code.rfind(tq_d)
        code = code[:idx].rstrip()

    if code.count(tq_s) % 2 != 0:
        idx = code.rfind(tq_s)
        code = code[:idx].rstrip()

    # Итеративно убираем строки с конца пока compile() не пройдёт
    lines = code.splitlines()
    for i in range(len(lines), 0, -1):
        candidate = "\n".join(lines[:i])
        try:
            compile(candidate, "<string>", "exec")
            return candidate
        except SyntaxError:
            continue

    return code


# ---------- extract ---------------------------------------------------------

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


# ---------- sample data -----------------------------------------------------

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


# ---------- sidebar ---------------------------------------------------------

with st.sidebar:
    st.header("Настройки")
    use_real_csv = st.checkbox("Загрузить реальный CSV вместо демо-данных", value=False)
    csv_file = None
    if use_real_csv:
        csv_file = st.file_uploader("CSV файл", type=["csv"])
    st.divider()
    st.caption("Демо-данные генерируются автоматически, если CSV не загружен.")


# ---------- main ------------------------------------------------------------

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

    # Проверяем — модель могла ответить текстом вместо кода
    python_keywords = ["import ", "def ", "st.", "pd.", "plt.", "px."]
    looks_like_code = any(kw in code for kw in python_keywords)
    if not looks_like_code:
        st.warning(
            "Модель ответила текстом, а не кодом. "
            "Попробуй переформулировать промт: например добавь 'Ответь только Python-кодом внутри ```python ... ```'."
        )
        st.text_area("Ответ модели", code, height=200)
        st.stop()

    with st.expander("Извлечённый код", expanded=False):
        st.code(code, language="python")
        try:
            compile(code, "<string>", "exec")
            st.success("Синтаксис Python валиден")
        except SyntaxError as se:
            st.warning(f"После санитизации остались проблемы: {se}")

    st.divider()
    st.subheader("Результат рендера")

    real_df = try_load_csv(csv_file) if use_real_csv else None
    sample_df = real_df if real_df is not None else make_sample_df()

    exec_ns = {
        "io": io,
        "base64": base64,
        "re": re,
        "pd": pd,
        "np": np,
        "plt": plt,
        "sns": sns,
        "px": px,
        "go": go,
        "matplotlib": matplotlib,
        "st": st,
        "df": sample_df,
        "uploaded_df": sample_df,
        "StringIO": io.StringIO,
        "datetime": __import__("datetime"),
    }

    class _FakeUploader:
        def __call__(self, *a, **kw):
            buf = io.BytesIO()
            sample_df.to_csv(buf, index=False)
            buf.seek(0)
            buf.name = "sample.csv"
            return buf

    exec_ns["_fake_uploader"] = _FakeUploader()

    patched = re.sub(r"\bst\.file_uploader\s*\(", "_fake_uploader(", code)
    patched = re.sub(r"st\.set_page_config\s*\(.*?\)\s*\n?", "", patched, flags=re.DOTALL)

    # Патч для дат: после каждого st.date_input вставляем строку конвертации в pd.Timestamp
    # Ищем паттерн: var1, var2 = st.date_input(...)
    # и добавляем после него: var1, var2 = pd.Timestamp(var1), pd.Timestamp(var2)
    date_lines = []
    for line in patched.splitlines():
        date_lines.append(line)
        m = re.match(r"(\s*)(\w+)\s*,\s*(\w+)\s*=\s*st\.date_input\s*\(", line)
        if m:
            indent, v1, v2 = m.group(1), m.group(2), m.group(3)
            date_lines.append(f"{indent}{v1}, {v2} = pd.Timestamp({v1}), pd.Timestamp({v2})")
        else:
            m2 = re.match(r"(\s*)(\w+)\s*=\s*st\.date_input\s*\(", line)
            if m2:
                indent, v1 = m2.group(1), m2.group(2)
                date_lines.append(f"{indent}{v1} = pd.Timestamp({v1})")
    patched = "\n".join(date_lines)

    # Патч: заменяем импорты недоступных модулей на заглушки
    missing_modules = []
    def _safe_import(name, *a, **kw):
        try:
            return _real_import(name, *a, **kw)
        except ImportError:
            missing_modules.append(name)
            import types
            stub = types.ModuleType(name)
            stub.__all__ = []
            return stub
    _real_import = __builtins__.__import__ if hasattr(__builtins__, "__import__") else __import__
    exec_ns["__builtins__"] = dict(__builtins__) if isinstance(__builtins__, dict) else vars(__builtins__).copy()
    exec_ns["__builtins__"]["__import__"] = _safe_import

    try:
        exec(textwrap.dedent(patched), exec_ns)
        if missing_modules:
            unique = list(dict.fromkeys(missing_modules))
            st.warning(
                "Некоторые модули не установлены и заменены заглушками: "
                + ", ".join(f"`{m}`" for m in unique)
                + ". Графики, зависящие от них, могут не работать."
            )
    except Exception as e:
        err = str(e)
        st.error(f"Ошибка при выполнении кода: {err}")
        if "No module named" in err:
            mod = err.split('No module named')[-1].strip().strip(chr(39)).strip(chr(34))
            st.info(f"Установи модуль командой: `pip install {mod}`")
        else:
            st.info("Открой 'Извлечённый код' выше и проверь синтаксис.")

elif run:
    st.warning("Вставь JSON-ответ модели перед запуском.")
