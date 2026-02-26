import streamlit as st
import json
import re
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import plotly.express as px
import io
import base64

st.set_page_config(page_title="Qwen Graph Tester", layout="wide")

st.title("Тестер графиков от Qwen2.5-14B-Instruct-AWQ")
st.markdown("Вставь **весь JSON-ответ** из терминала → приложение вытащит код и попробует отрендерить.")

raw_json = st.text_area("Вставь весь JSON-ответ", height=400)

if st.button("Вытащить код и отрендерить"):
    if raw_json.strip():
        try:
            data = json.loads(raw_json)
            full_text = data['choices'][0]['message']['content']

            # Вытаскиваем код
            code_match = re.search(r'```python\s*(.*?)```', full_text, re.DOTALL | re.IGNORECASE)
            if code_match:
                code = code_match.group(1).strip()
            else:
                code_start = full_text.find('import streamlit')
                code = full_text[code_start:].strip() if code_start != -1 else full_text.strip()

            # Убираем мусор в конце
            code = re.split(r'# Инструкции|# Как запустить|"""|if st.checkbox|Установите|Запустите', code)[0].strip()

            st.subheader("Вытащенный код")
            st.code(code, language="python")

            # Авто-рендер — ищем любой графический фрагмент
            st.subheader("Автоматический рендер")
            graph_patterns = [
                r'(plt\.figure|fig\s*=|sns\.|px\.|st\.plotly_chart).*?(plt\.show\(\)|fig\.show\(\)|st\.plotly_chart\(|st\.pyplot\()',
                r'fig\s*=.*?st\.plotly_chart',
                r'sns\..*?plt\.show',
                r'px\..*?st\.plotly_chart'
            ]
            graph_snippet = None
            for pattern in graph_patterns:
                match = re.search(pattern, code, re.DOTALL | re.IGNORECASE)
                if match:
                    graph_snippet = match.group(0).strip()
                    break

            if graph_snippet:
                fig = plt.figure(figsize=(12, 8))
                try:
                    exec_globals = {"plt": plt, "sns": sns, "pd": pd, "px": px, "st": st}
                    exec(graph_snippet, exec_globals)
                    buf = io.BytesIO()
                    fig.savefig(buf, format="png", bbox_inches="tight")
                    buf.seek(0)
                    img_str = base64.b64encode(buf.read()).decode()
                    st.image(f"data:image/png;base64,{img_str}", caption="Авто-график", use_column_width=True)
                except Exception as e:
                    st.error(f"Авто-рендер не сработал: {str(e)}")
                finally:
                    plt.close(fig)
            else:
                st.warning("Не нашёл явный фрагмент графика. Вставь ниже вручную код от fig = ... до plt.show() или st.plotly_chart.")

            # Ручной режим (самый надёжный)
            st.subheader("Ручной рендер (рекомендую для точности)")
            st.markdown("Выдели из кода **только фрагмент с графиком** (от fig = plt.figure() или px. до plt.show() или st.plotly_chart) и вставь сюда.")
            manual_code = st.text_area("Вставь только код графика", height=300)
            if st.button("Ручной рендер"):
                if manual_code.strip():
                    fig = plt.figure(figsize=(12, 8))
                    try:
                        exec_globals = {"plt": plt, "sns": sns, "pd": pd, "px": px, "st": st}
                        exec(manual_code, exec_globals)
                        buf = io.BytesIO()
                        fig.savefig(buf, format="png", bbox_inches="tight")
                        buf.seek(0)
                        img_str = base64.b64encode(buf.read()).decode()
                        st.image(f"data:image/png;base64,{img_str}", caption="Ручной график", use_column_width=True)
                    except Exception as e:
                        st.error(f"Ошибка ручного рендера: {str(e)}")
                    finally:
                        plt.close(fig)
                else:
                    st.warning("Вставь фрагмент графика.")

        except Exception as e:
            st.error(f"Ошибка обработки: {str(e)}")
    else:
        st.warning("Вставь JSON сначала.")
