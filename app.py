import streamlit as st
import json
import re
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import io
import base64

st.set_page_config(page_title="Qwen Graph Tester — простой режим", layout="wide")

st.title("Простой тестер графиков от Qwen2.5-14B-Instruct-AWQ")
st.markdown("Вставь **весь сырой ответ из терминала** (JSON с curl) → приложение само вытащит код и попробует отрендерить графики.")

raw_response = st.text_area("Вставь весь JSON-ответ сюда", height=300)

if st.button("Обработать и показать"):
    if raw_response.strip():
        try:
            # Парсим JSON
            data = json.loads(raw_response)
            # Достаём content из choices[0].message.content
            full_text = data['choices'][0]['message']['content']

            # Вытаскиваем код между ```python и ``` (самый надёжный способ)
            code_match = re.search(r'```python\s*(.*?)```', full_text, re.DOTALL)
            if code_match:
                code = code_match.group(1).strip()
            else:
                # Если нет ```python, берём весь текст после первого описания
                code_start = full_text.find('```python')
                if code_start == -1:
                    code_start = full_text.find('import streamlit')
                code = full_text[code_start:].strip() if code_start != -1 else full_text.strip()

            st.subheader("Вытащенный код")
            st.code(code, language="python")

            # Пробуем отрендерить графики
            st.subheader("Рендер графиков")
            fig = plt.figure(figsize=(10, 6))
            try:
                local_vars = {"plt": plt, "sns": sns, "pd": pd, "st": st}
                exec(code, {}, local_vars)

                # Если в коде был plt.show() — график уже нарисован
                buf = io.BytesIO()
                fig.savefig(buf, format="png", bbox_inches="tight")
                buf.seek(0)
                img_str = base64.b64encode(buf.read()).decode()
                st.image(f"data:image/png;base64,{img_str}", caption="Автоматический рендер графика")
            except Exception as e:
                st.error(f"Не удалось отрендерить график: {str(e)}\n\nПопробуй вставить только фрагмент с plt.figure() ... plt.show().")
            finally:
                plt.close(fig)

        except json.JSONDecodeError:
            st.error("Не удалось распарсить JSON. Убедись, что вставил весь ответ из терминала.")
        except Exception as e:
            st.error(f"Общая ошибка: {str(e)}")
    else:
        st.warning("Вставь ответ сначала.")
