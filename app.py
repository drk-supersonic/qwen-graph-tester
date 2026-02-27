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

# ── patch Period columns: convert to str so Plotly can serialize ───────────
def patch_period_columns(code: str) -> str:
    prefix = """
def _fix_periods(d):
    # convert any Period-dtype columns to str so Plotly can serialize them
    for _c in list(d.columns):
        try:
            if hasattr(d[_c], 'dt') and hasattr(d[_c].dt, 'to_timestamp'):
                d[_c] = d[_c].astype(str)
        except Exception:
            pass
    return d

_fix_periods(df)

# patch df.corr() to always use only numeric columns
import pandas as _pd_orig
_orig_corr = _pd_orig.DataFrame.corr
def _safe_corr(self, method='pearson', min_periods=1, **kw):
    numeric_df = self.select_dtypes(include='number')
    return _orig_corr(numeric_df, method=method, min_periods=min_periods, **kw)
_pd_orig.DataFrame.corr = _safe_corr


import plotly.express as _px_orig
_px_real_bar     = _px_orig.bar
_px_real_line    = _px_orig.line
_px_real_box     = _px_orig.box
_px_real_scatter = _px_orig.scatter

def _safe_px(fn):
    import numpy as _np
    import pandas as _pd
    def _w(data_frame=None, *a, **kw):
        # 1. fix Period columns
        if data_frame is not None:
            try:
                _fix_periods(data_frame)
            except Exception:
                pass
        # 2. fix size= — handle column name, list, Series, or expression result
        size_val = kw.get("size")
        if size_val is not None:
            # column name → check it's numeric, clip, or drop if not
            if isinstance(size_val, str) and data_frame is not None:
                try:
                    col = data_frame[size_val]
                    if _pd.api.types.is_numeric_dtype(col):
                        data_frame[size_val] = col.clip(lower=0)
                    else:
                        # non-numeric column passed as size — remove the arg
                        del kw["size"]
                except Exception:
                    kw.pop("size", None)
            else:
                # Series, array, list, or computed expression — clip to >= 0
                try:
                    if isinstance(size_val, _pd.Series):
                        arr = _np.asarray(size_val.values, dtype=float)
                        kw["size"] = list(_np.clip(arr, 0, None))
                    else:
                        arr = _np.asarray(size_val, dtype=float)
                        kw["size"] = list(_np.clip(arr, 0, None))
                except Exception:
                    # if conversion to float fails entirely — just drop size
                    kw.pop("size", None)
        return fn(data_frame, *a, **kw)
    return _w

px.bar     = _safe_px(_px_real_bar)
px.line    = _safe_px(_px_real_line)
px.box     = _safe_px(_px_real_box)
px.scatter = _safe_px(_px_real_scatter)
"""
    return prefix + code

code = patch_period_columns(code)

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

    # show lines from model code with context
    code_lines = code.splitlines()
    model_lines = [l for l in tb.splitlines() if "<string>" in l or type(e).__name__ in l]
    if model_lines:
        st.code("\n".join(model_lines), language="text")

    # extract error line number and show code context
    import re as _re
    line_nums = [int(m) for m in _re.findall(r'<string>, line (\d+)', tb)]
    if line_nums:
        err_line = line_nums[-1]
        start = max(0, err_line - 4)
        end = min(len(code_lines), err_line + 2)
        snippet = []
        for i, l in enumerate(code_lines[start:end], start=start+1):
            marker = ">>>" if i == err_line else "   "
            snippet.append(f"{marker} {i:3d} | {l}")
        st.markdown("**Код вокруг ошибки:**")
        st.code("\n".join(snippet), language="python")

    # ── helpful hints ──────────────────────────────────────────────────────
    if isinstance(e, KeyError):
        st.warning(f"Колонка `{e}` не найдена. Доступные колонки df:")
        st.code(str(list(df.columns)))
    elif isinstance(e, ValueError) and "could not convert string to float" in str(e):
        st.warning("Модель передала текстовую колонку туда где ожидается число. Смотри строку выше.")
    elif isinstance(e, AttributeError) and "has no attribute" in str(e):
        st.warning("Модель обратилась к несуществующему методу или переменной.")

    # always show df schema at the bottom so the user can judge the model
    with st.expander("📊 Схема demo-датафрейма", expanded=False):
        st.dataframe(df.head())
        st.text(str(df.dtypes))
