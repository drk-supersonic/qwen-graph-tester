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
st.markdown("Вставь **весь JSON-ответ** из терминала → приложение вытащит код и отрендерит графики.")

raw_json = st.text_area("Вставь весь JSON-ответ", height=400)

if st.button("Обработать и показать"):
    if raw_json.strip():
        try:
            data = json.loads(raw_json)
            full_text = data['choices'][0]['message']['content']

            # Вытаскиваем самый большой блок кода
            code_blocks = re.findall(r'```python\s*(.*?)```', full_text, re.DOTALL | re.IGNORECASE)
            code = max(code_blocks, key=len).strip() if code_blocks else full_text.strip()

            # Убираем мусор в конце (инструкции, """ и т.д.)
            code = re.split(r'# Инструкции|# Как запустить|"""|if st.checkbox|Установите|Запустите', code)[0].strip()

            st.subheader("Вытащенный код")
            st.code(code, language="python")

            # Авто-рендер — ищем и выполняем только фрагмент графика
            st.subheader("Автоматический рендер")
            graph_code = re.search(r'(fig\s*=|plt\.figure|px\.|sns\.|st\.plotly_chart|plt\.show).*?(plt\.show\(\)|st\.plotly_chart\(|fig\.show\(\))', code, re.DOTALL | re.IGNORECASE)
            if graph_code:
                graph_snippet = graph_code.group(0).strip()
                fig = plt.figure(figsize=(12, 8))
                try:
                    exec_globals = {"plt": plt, "sns": sns, "pd": pd, "px": px, "st": st}
                    exec(graph_snippet, exec_globals)
                    buf = io.BytesIO()
                    fig.savefig(buf, format="png", bbox_inches="tight")
                    buf.seek(0)
                    img_str = base64.b64encode(buf.read()).decode()
                    st.image(f"data:image/png;base64,{img_str}", caption="Автоматический график")
                except Exception as e:
                    st.error(f"Авто-рендер фрагмента не сработал: {str(e)}")
                finally:
                    plt.close(fig)
            else:
                st.warning("Не нашёл фрагмент графика (plt.figure...plt.show или st.plotly_chart). Попробуй ручной режим ниже.")

            # Ручной режим
            st.subheader("Ручной рендер (если авто не сработал)")
            manual_code = st.text_area("Вставь только код графика (от fig = ... до plt.show() или st.plotly_chart)", height=200)
            if st.button("Ручной рендер"):
                if manual_code.strip():
                    fig_manual = plt.figure(figsize=(10, 6))
                    try:
                        exec(manual_code, {"plt": plt, "sns": sns, "pd": pd, "px": px, "st": st})
                        buf = io.BytesIO()
                        fig_manual.savefig(buf, format="png", bbox_inches="tight")
                        buf.seek(0)
                        img_str = base64.b64encode(buf.read()).decode()
                        st.image(f"data:image/png;base64,{img_str}", caption="Ручной результат")
                    except Exception as e:
                        st.error(f"Ошибка ручного рендера: {str(e)}")
                    finally:
                        plt.close(fig_manual)
                else:
                    st.warning("Вставь код графика.")

        except json.JSONDecodeError:
            st.error("Не удалось распарсить JSON.")
        except Exception as e:
            st.error(f"Общая ошибка: {str(e)}")
    else:
        st.warning("Вставь JSON сначала.")
