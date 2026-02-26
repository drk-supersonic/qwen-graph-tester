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
st.markdown("Вставь **весь сырой JSON-ответ** из терминала → приложение вытащит код и отрендерит графики.")

raw_json = st.text_area("Вставь весь JSON-ответ", height=400)

if st.button("Вытащить код и отрендерить"):
    if raw_json.strip():
        try:
            # Парсим JSON
            data = json.loads(raw_json)
            full_text = data['choices'][0]['message']['content']

            # Улучшенное вытаскивание кода — ищем любой блок с ```python
            code_match = re.search(r'```python\s*([\s\S]*?)```', full_text, re.IGNORECASE)
            if code_match:
                code = code_match.group(1).strip()
            else:
                # Запасной вариант: берём всё после первого import streamlit
                code_start = full_text.find('import streamlit')
                if code_start != -1:
                    code = full_text[code_start:].strip()
                else:
                    code = full_text.strip()

            # Убираем всё после инструкций (""" или # Инструкции)
            code = re.split(r'"""|# Инструкции|# Как запустить|Установите|Запустите|if __name__', code)[0].strip()

            st.subheader("Вытащенный чистый код")
            st.code(code, language="python")

            # Авто-рендер
            st.subheader("Автоматический рендер графиков")
            fig = plt.figure(figsize=(12, 8))
            try:
                exec_globals = {"plt": plt, "sns": sns, "pd": pd, "px": px, "st": st}
                exec(code, exec_globals)

                buf = io.BytesIO()
                fig.savefig(buf, format="png", bbox_inches="tight")
                buf.seek(0)
                img_str = base64.b64encode(buf.read()).decode()
                st.image(f"data:image/png;base64,{img_str}", caption="Результат графика", use_column_width=True)

            except Exception as e:
                st.error(f"Авто-рендер не сработал: {str(e)}\n\nПопробуй ручной режим ниже.")
            finally:
                plt.close(fig)

            # Ручной режим (самый надёжный)
            st.subheader("Ручной рендер (рекомендую для точности)")
            st.markdown("Выдели из кода **только фрагмент с графиком** (от fig = plt.figure() или px. до plt.show() или st.plotly_chart) и вставь сюда.")
            manual_code = st.text_area("Вставь только код графика", height=300)
            if st.button("Ручной рендер"):
                if manual_code.strip():
                    fig = plt.figure(figsize=(12, 8))
                    try:
                        exec(manual_code, {"plt": plt, "sns": sns, "pd": pd, "px": px, "st": st})
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
                    st.warning("Вставь код графика.")

        except json.JSONDecodeError:
            st.error("Не удалось распарсить JSON. Убедись, что вставил весь ответ целиком.")
        except Exception as e:
            st.error(f"Общая ошибка: {str(e)}")
    else:
        st.warning("Вставь JSON сначала.")
