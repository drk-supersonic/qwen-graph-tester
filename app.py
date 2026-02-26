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

st.title("🧪 Qwen Graph Tester")
st.markdown("Вставь **весь сырой JSON-ответ** из терминала — приложение вытащит Python-код и отрендерит графики напрямую.")

# ── helpers ──────────────────────────────────────────────────────────────────

def extract_code(raw_json: str) -> str | None:
    """
    Достаём Python-код из JSON-ответа OpenAI-совместимого API.
    Пробуем несколько стратегий по убыванию надёжности.
    """
    try:
        data = json.loads(raw_json)
        content = data["choices"][0]["message"]["content"]
    except Exception as e:
        st.error(f"Не удалось распарсить JSON: {e}")
        return None

    # 1. Есть ```python … ``` блок?
    match = re.search(r"```python\s*(.*?)```", content, re.DOTALL)
    if match:
        return sanitize_code(match.group(1).strip())

    # 2. Просто ``` … ``` блок?
    match = re.search(r"```\s*(.*?)```", content, re.DOTALL)
    if match:
        return sanitize_code(match.group(1).strip())

    # 3. Весь content — берём как есть
    return sanitize_code(content.strip())


def sanitize_code(code: str) -> str:
    """
    Чиним типичные артефакты кода от LLM перед exec():
    - незакрытые тройные кавычки ("""  или ''')
    - незакрытые обычные строки в конце файла
    - оборванные инструкции в конце
    """
    # 1. Убираем trailing строки с незакрытыми тройными кавычками
    #    Стратегия: если число """ нечётное — добавляем закрывающую
    triple_dq = code.count('"""')
    triple_sq = code.count("'''")

    if triple_dq % 2 != 0:
        # Находим последнее вхождение """ и обрезаем код до него
        last_idx = code.rfind('"""')
        code = code[:last_idx].rstrip()

    if triple_sq % 2 != 0:
        last_idx = code.rfind("'''")
        code = code[:last_idx].rstrip()

    # 2. Убираем строки-хвосты, которые содержат только частичный строковый литерал
    #    (например: `    st.text("""` без закрывающей кавычки)
    lines = code.splitlines()
    # Идём с конца — убираем строки пока компиляция не пройдёт
    for i in range(len(lines), 0, -1):
        candidate = "\n".join(lines[:i])
        try:
            compile(candidate, "<string>", "exec")
            code = candidate
            break
        except SyntaxError:
            continue
    else:
        # Ничего не помогло — вернём как есть
        pass

    return code


def make_sample_df() -> pd.DataFrame:
    """Генерируем демо-данные, чтобы код модели мог их использовать."""
    rng = np.random.default_rng(42)
    n = 300
    dates = pd.date_range("2023-01-01", periods=n, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "sales": rng.integers(100, 5000, n).astype(float),
        "region": rng.choice(["Север", "Юг", "Запад", "Восток"], n),
        "product": rng.choice([f"Продукт {i}" for i in range(1, 16)], n),
        "category": rng.choice(["Электроника", "Одежда", "Еда", "Спорт"], n),
        "customer_type": rng.choice(["Розница", "Оптовик", "VIP"], n),
        "price": rng.uniform(10, 500, n).round(2),
        "discount": rng.uniform(0, 0.4, n).round(2),
        "quantity": rng.integers(1, 50, n),
    })
    df["date"] = df["date"].astype(str)   # как в реальном CSV
    return df


def try_load_csv(uploaded_file) -> pd.DataFrame | None:
    if uploaded_file is None:
        return None
    try:
        return pd.read_csv(uploaded_file)
    except Exception as e:
        st.warning(f"Не удалось загрузить CSV: {e}")
        return None


# ── sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.header("⚙️ Настройки")
    use_real_csv = st.checkbox("Загрузить реальный CSV вместо демо-данных", value=False)
    csv_file = None
    if use_real_csv:
        csv_file = st.file_uploader("CSV файл", type=["csv"])
    st.divider()
    st.caption("Демо-данные генерируются автоматически, если CSV не загружен.")

# ── main ──────────────────────────────────────────────────────────────────────

raw_json = st.text_area("Вставь весь JSON-ответ модели", height=300, placeholder='{"choices": [{"message": {"content": "```python\\n...```"}}]}')

col_run, col_clear = st.columns([1, 5])
run = col_run.button("▶ Запустить", type="primary")
if col_clear.button("🗑 Очистить"):
    st.rerun()

if run and raw_json.strip():
    code = extract_code(raw_json)
    if not code:
        st.stop()

    with st.expander("📄 Извлечённый код", expanded=False):
        st.code(code, language="python")
        # Проверяем компилируется ли итоговый код
        try:
            compile(code, "<string>", "exec")
            st.success("✅ Синтаксис Python валиден")
        except SyntaxError as se:
            st.warning(f"⚠️ После санитизации остались синтаксические проблемы: {se}")

    st.divider()
    st.subheader("📊 Результат рендера")

    # Подготовим DataFrame — реальный или демо
    real_df = try_load_csv(csv_file) if use_real_csv else None
    sample_df = real_df if real_df is not None else make_sample_df()

    # Пространство имён для exec
    exec_ns = {
        # stdlib / io
        "io": io,
        "base64": base64,
        "re": re,
        # data
        "pd": pd,
        "np": np,
        # viz
        "plt": plt,
        "sns": sns,
        "px": px,
        "go": go,
        "matplotlib": matplotlib,
        # streamlit
        "st": st,
        # удобные данные прямо в пространстве имён
        "df": sample_df,
        "uploaded_df": sample_df,
    }

    # Патчим st.file_uploader чтобы он не ломал выполнение
    # (модель часто вызывает его внутри кода — перехватываем)
    class _FakeUploader:
        def __call__(self, *a, **kw):
            # возвращаем буфер с демо-CSV
            buf = io.BytesIO()
            sample_df.to_csv(buf, index=False)
            buf.seek(0)
            buf.name = "sample.csv"
            return buf
    exec_ns["_fake_uploader"] = _FakeUploader()

    # Заменяем st.file_uploader в коде на наш фейк
    patched_code = re.sub(
        r"\bst\.file_uploader\s*\(",
        "_fake_uploader(",
        code,
    )

    # Убираем st.set_page_config — на Streamlit Cloud вызов второй раз падает
    patched_code = re.sub(r"st\.set_page_config\([^)]*\)\s*\n?", "", patched_code)

    try:
        exec(textwrap.dedent(patched_code), exec_ns)
    except Exception as e:
        st.error(f"❌ Ошибка при выполнении кода: {e}")
        st.info("💡 Совет: проверь, что модель сгенерировала корректный Python. "
                "Открой «Извлечённый код» выше и посмотри на синтаксис.")

elif run:
    st.warning("Вставь JSON-ответ модели перед запуском.")
