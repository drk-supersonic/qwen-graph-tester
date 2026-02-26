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
st.markdown("Вставь весь JSON-ответ → приложение вытащит код и отрендерит все графики автоматически.")

raw_json = st.text_area("Вставь весь JSON-ответ", height=400)

if st.button("Обработать и показать"):
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

            # Авто-рендер всех графиков
            st.subheader("Автоматический рендер всех графиков")
            fig_patterns = [
                r'(fig\d*,\s*ax\d*\s*=|fig\s*=|plt\.figure).*?(st\.pyplot|plt\.show|st\.plotly_chart|fig\.show)',
                r'sns\..*?(st\.pyplot|plt\.show)',
                r'px\..*?st\.plotly_chart'
            ]
            for i, pattern in enumerate(fig_patterns):
                matches = re.finditer(pattern, code, re.DOTALL | re.IGNORECASE)
                for match in matches:
                    snippet = match.group(0).strip()
                    fig = plt.figure(figsize=(12, 8))
                    try:
                        exec_globals = {"plt": plt, "sns": sns, "pd": pd, "px": px, "st": st}
                        exec(snippet, exec_globals)
                        buf = io.BytesIO()
                        fig.savefig(buf, format="png", bbox_inches="tight")
                        buf.seek(0)
                        img_str = base64.b64encode(buf.read()).decode()
                        st.image(f"data:image/png;base64,{img_str}", caption=f"График {i+1}", use_column_width=True)
                    except Exception as e:
                        st.error(f"Ошибка рендера графика {i+1}: {str(e)}")
                    finally:
                        plt.close(fig)

            if not any(re.search(p, code, re.DOTALL | re.IGNORECASE) for p in fig_patterns):
                st.warning("Не нашёл графики в коде. Попробуй ручной режим ниже.")

            # Ручной режим
            st.subheader("Ручной рендер")
            manual_code = st.text_area("Вставь только код одного графика", height=200)
            if st.button("Ручной рендер"):
                if manual_code.strip():
                    fig = plt.figure(figsize=(12, 8))
                    try:
                        exec(manual_code, {"plt": plt, "sns": sns, "pd": pd, "px": px, "st": st})
                        buf = io.BytesIO()
                        fig.savefig(buf, format="png", bbox_inches="tight")
                        buf.seek(0)
                        img_str = base64.b64encode(buf.read()).decode()
                        st.image(f"data:image/png;base64,{img_str}", caption="Ручной график")
                    except Exception as e:
                        st.error(f"Ошибка: {str(e)}")
                    finally:
                        plt.close(fig)

        except Exception as e:
            st.error(f"Ошибка обработки: {str(e)}")
    else:
        st.warning("Вставь JSON.")
