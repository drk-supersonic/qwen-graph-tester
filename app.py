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

    import traceback as _tb

    # Разбиваем код на секции: виджеты (sidebar/filters) и графики
    # При KeyError перезапускаем только секцию графиков с пофикшенными данными
    def run_patched(code_str, ns):
        exec(textwrap.dedent(code_str), ns)

    def run_patched_skip_widgets(code_str, ns):
        # Заменяем виджеты-дубли на заглушки при повторном запуске
        widget_re = re.compile(
            r'\bst\.(multiselect|selectbox|radio|checkbox|slider|date_input|text_input|number_input)\s*\('
        )
        safe_lines = []
        for ln in code_str.splitlines():
            if widget_re.search(ln):
                # Превращаем присвоение виджета в no-op через уже существующее значение
                m = re.match(r'(\s*)(\w+)\s*=\s*st\.', ln)
                if m:
                    indent, var = m.group(1), m.group(2)
                    # Если переменная уже есть в ns — пропускаем
                    if var in ns:
                        safe_lines.append(f'{indent}pass  # skipped widget {var}')
                        continue
            safe_lines.append(ln)
        exec(textwrap.dedent('\n'.join(safe_lines)), ns)

    try:
        run_patched(patched, exec_ns)
    except KeyError as e:
        missing_col = str(e).strip(chr(39)).strip(chr(34))
        st.error(f'Ошибка при выполнении кода: KeyError {e}')
        base_df = exec_ns.get('filtered_df', exec_ns.get('df', sample_df))
        if missing_col in base_df.columns:
            st.warning(f'Колонка `{missing_col}` найдена. Добавляю в промежуточные DataFrame и перезапускаю графики...')
            for k in list(exec_ns.keys()):
                v = exec_ns[k]
                if isinstance(v, pd.DataFrame) and missing_col not in v.columns:
                    for join_col in ['project_name', 'date', 'region']:
                        if join_col in v.columns and join_col in base_df.columns:
                            try:
                                lookup = base_df[[join_col, missing_col]].drop_duplicates(join_col)
                                exec_ns[k] = v.merge(lookup, on=join_col, how='left')
                                break
                            except Exception:
                                pass
            try:
                run_patched_skip_widgets(patched, exec_ns)
                st.success('Автоисправление сработало!')
            except Exception as e2:
                st.error(f'Автоисправление не помогло: {e2}')
        found_dfs = {k: v for k, v in exec_ns.items() if isinstance(v, pd.DataFrame) and not k.startswith('_')}
        if found_dfs:
            st.warning('Колонки доступных DataFrame:')
            for name, frame in found_dfs.items():
                st.code(f'{name}: {list(frame.columns)}', language='python')
    except Exception as e:
        err_type = type(e).__name__
        st.error(f'Ошибка при выполнении кода: {err_type}: {e}')
        tb_str = _tb.format_exc()
        model_lines = [l for l in tb_str.splitlines() if '<string>' in l]
        if model_lines:
            st.code('\n'.join(model_lines), language='text')
        st.info('Открой Извлечённый код выше и проверь синтаксис.')
elif run:
    st.warning("Вставь JSON-ответ модели перед запуском.")
