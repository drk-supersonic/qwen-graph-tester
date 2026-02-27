import streamlit as st
import json
import re
import io
import sys
import textwrap
import traceback

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Qwen Graph Tester", layout="wide")
st.title("🧪 Qwen Graph Tester")
st.markdown("Вставь **сырой JSON-ответ** из терминала — приложение извлечёт Python-код и отрендерит графики.")

# ── sample dataframe ───────────────────────────────────────────────────────
@st.cache_data
def make_sample_df() -> pd.DataFrame:
    rng = np.random.default_rng(42)
    n = 300
    dates = pd.date_range("2023-01-01", periods=n, freq="D")
    return pd.DataFrame({
        "date":          dates.astype(str),
        "sales":         rng.integers(100, 5000, n).astype(float),
        "region":        rng.choice(["Север", "Юг", "Запад", "Восток"], n),
        "product":       rng.choice([f"Продукт {i}" for i in range(1, 16)], n),
        "category":      rng.choice(["Электроника", "Одежда", "Еда", "Спорт"], n),
        "customer_type": rng.choice(["Розница", "Оптовик", "VIP"], n),
        "price":         rng.uniform(10, 500, n).round(2),
        "discount":      rng.uniform(0, 0.4, n).round(2),
        "quantity":      rng.integers(1, 50, n),
    })

# ── code extraction ────────────────────────────────────────────────────────
def extract_code(raw: str) -> str | None:
    """Pull Python code from a vLLM JSON response."""
    try:
        data = json.loads(raw)
        content = data["choices"][0]["message"]["content"]
    except Exception as e:
        st.error(f"Не удалось распарсить JSON: {e}")
        return None

    # prefer ```python ... ``` block
    m = re.search(r"```python\s*(.*?)```", content, re.DOTALL)
    if m:
        return m.group(1).strip()
    # fallback: any fenced block
    m = re.search(r"```\s*(.*?)```", content, re.DOTALL)
    if m:
        return m.group(1).strip()
    # fallback: whole content
    return content.strip()

def fix_syntax(code: str) -> str:
    """Try to trim trailing broken lines until the code compiles."""
    lines = code.splitlines()
    for i in range(len(lines), 0, -1):
        candidate = "\n".join(lines[:i])
        try:
            compile(candidate, "<string>", "exec")
            return candidate
        except SyntaxError:
            continue
    return code

# ── main UI ────────────────────────────────────────────────────────────────
raw_json = st.text_area(
    "JSON-ответ модели",
    height=280,
    placeholder='{"choices": [{"message": {"content": "```python\\n...код...\\n```"}}]}',
)

col1, col2 = st.columns([1, 6])
run    = col1.button("▶ Запустить", type="primary")
clear  = col2.button("🗑 Очистить")

if clear:
    st.rerun()

if not (run and raw_json.strip()):
    st.info("Вставь JSON-ответ и нажми **Запустить**.")
    st.stop()

# ── extract + show code ────────────────────────────────────────────────────
code = extract_code(raw_json)
if not code:
    st.stop()

code = fix_syntax(code)

with st.expander("📄 Извлечённый код", expanded=False):
    st.code(code, language="python")
    try:
        compile(code, "<string>", "exec")
        st.success("Синтаксис валиден ✅")
    except SyntaxError as se:
        st.error(f"Синтаксическая ошибка: {se}")

st.divider()
st.subheader("Результат")

# ── patch duplicate plotly_chart keys ─────────────────────────────────────
def patch_plotly_keys(code: str) -> str:
    counter = [0]
    def replacer(m):
        counter[0] += 1
        inner = m.group(1).rstrip().rstrip(",")
        if "key=" in inner:
            return m.group(0)
        return f"st.plotly_chart({inner}, key='_plotly_{counter[0]}')"
    return re.sub(r"st\.plotly_chart\((.+?)\)", replacer, code, flags=re.DOTALL)

code = patch_plotly_keys(code)

# ── execution namespace ────────────────────────────────────────────────────
df = make_sample_df()

exec_ns: dict = {
    # data
    "df": df,
    "sample_df": df,
    # libs
    "pd": pd,
    "np": np,
    "plt": plt,
    "sns": sns,
    "px": px,
    "go": go,
    "io": io,
    # streamlit
    "st": st,
}

# ── run ────────────────────────────────────────────────────────────────────
try:
    exec(textwrap.dedent(code), exec_ns)

    # render any matplotlib figures the code created but didn't show
    for fig_obj in map(plt.figure, plt.get_fignums()):
        st.pyplot(fig_obj)
    plt.close("all")

except Exception as e:
    st.error(f"**{type(e).__name__}**: {e}")

    tb = traceback.format_exc()
    # show only lines pointing at the model's code
    model_lines = [l for l in tb.splitlines() if "<string>" in l or type(e).__name__ in l]
    if model_lines:
        st.code("\n".join(model_lines), language="text")
    else:
        st.code(tb, language="text")

    # ── helpful hints ──────────────────────────────────────────────────────
    if isinstance(e, KeyError):
        st.warning(f"Колонка `{e}` не найдена. Доступные колонки df:")
        st.code(str(list(df.columns)))

    elif isinstance(e, AttributeError) and "has no attribute" in str(e):
        st.warning("Возможно, модель обратилась к несуществующему методу или переменной.")

    # always show df schema at the bottom so the user can judge the model
    with st.expander("📊 Схема demo-датафрейма", expanded=False):
        st.dataframe(df.head())
        st.text(str(df.dtypes))
