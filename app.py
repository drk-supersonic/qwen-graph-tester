import streamlit as st
import json
import re
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import io
import base64

st.set_page_config(page_title="Qwen Graph Tester", layout="wide")

st.title("Авто-тестер графиков от Qwen2.5-14B-Instruct-AWQ")
st.markdown("Вставь **весь сырой JSON-ответ** из терминала → приложение вытащит код, покажет его и попробует отрендерить графики.")

raw_json = st.text_area("Вставь весь JSON-ответ от curl", height=400)

if st.button("Обработать и показать"):
    if raw_json.strip():
        try:
            # Парсим JSON
            data = json.loads(raw_json)
            full_text = data['choices'][0]['message']['content']

            # Вытаскиваем код между ```python и ```
            code_match = re.search(r'```python\s*(.*?)```', full_text, re.DOTALL | re.IGNORECASE)
            if code_match:
                code = code_match.group(1).strip()
            else:
                # Запасной вариант: ищем начало с import
                code_start = full_text.find('import streamlit')
                code = full_text[code_start:].strip() if code_start != -1 else full_text.strip()

            st.subheader("Вытащенный чистый код")
            st.code(code, language="python")

            # Пытаемся отрендерить
            st.subheader("Автоматический рендер графиков")
            fig = plt.figure(figsize=(12, 8))
            try:
                # Глобальные переменные для exec
                exec_globals = {
                    "plt": plt,
                    "sns": sns,
                    "pd": pd,
                    "px": px,
                    "go": go,
                    "st": st
                }
                exec(code, exec_globals)

                # Если график matplotlib/seaborn — сохраняем как PNG
                buf = io.BytesIO()
                fig.savefig(buf, format="png", bbox_inches="tight")
                buf.seek(0)
                img_str = base64.b64encode(buf.read()).decode()
                st.image(f"data:image/png;base64,{img_str}", caption="Результат (matplotlib/seaborn)", use_column_width=True)

            except Exception as e:
                st.error(f"Авто-рендер не сработал: {str(e)}\n\nПопробуй ниже вставить только фрагмент с plt.figure() ... plt.show() или st.plotly_chart().")
            finally:
                plt.close(fig)

            # Ручной рендер для Plotly или сложных случаев
            st.subheader("Ручной рендер (если авто не получилось)")
            manual_code = st.text_area("Вставь только код графика (от fig = ... до st.plotly_chart или plt.show)", height=200)
            if st.button("Ручной рендер"):
                if manual_code.strip():
                    try:
                        fig_manual = plt.figure(figsize=(10, 6))
                        exec(manual_code, {"plt": plt, "sns": sns, "pd": pd, "px": px, "go": go, "st": st})
                        buf = io.BytesIO()
                        fig_manual.savefig(buf, format="png", bbox_inches="tight")
                        buf.seek(0)
                        img_str = base64.b64encode(buf.read()).decode()
                        st.image(f"data:image/png;base64,{img_str}", caption="Ручной рендер")
                    except Exception as e:
                        st.error(f"Ошибка ручного рендера: {str(e)}")
                    finally:
                        plt.close(fig_manual)
                else:
                    st.warning("Вставь код графика.")

        except json.JSONDecodeError:
            st.error("Не удалось распарсить JSON. Убедись, что вставил весь ответ целиком.")
        except Exception as e:
            st.error(f"Общая ошибка: {str(e)}")
    else:
        st.warning("Вставь JSON сначала.")
