import streamlit as st
import json
import re
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import io
import base64

st.set_page_config(page_title="Qwen Graph Tester", layout="wide")

st.title("Тестер графиков от Qwen2.5-14B-Instruct-AWQ")
st.markdown("Вставь **весь сырой JSON-ответ** из терминала (от {'id':... до конца) → приложение само вытащит код и попробует отрендерить график.")

raw_json = st.text_area("Вставь весь JSON-ответ сюда", height=400)

if st.button("Вытащить код и отрендерить"):
    if raw_json.strip():
        try:
            # Парсим JSON
            data = json.loads(raw_json)
            # Берём content из первого choice
            full_text = data['choices'][0]['message']['content']

            # Вытаскиваем код между ```python и ``` (самый надёжный способ)
            code_match = re.search(r'```python\s*(.*?)```', full_text, re.DOTALL | re.IGNORECASE)
            if code_match:
                code = code_match.group(1).strip()
            else:
                # Если нет ```python — ищем начало с import streamlit или plt
                code_start = full_text.find('import streamlit')
                if code_start == -1:
                    code_start = full_text.find('plt.figure')
                code = full_text[code_start:].strip() if code_start != -1 else full_text.strip()

            st.subheader("Вытащенный чистый код")
            st.code(code, language="python")

            # Пытаемся отрендерить
            st.subheader("Автоматический рендер графика")
            fig = plt.figure(figsize=(12, 8))
            try:
                local_vars = {"plt": plt, "sns": sns, "pd": pd, "px": st.plotly, "st": st}
                exec(code, {}, local_vars)

                # Если график был нарисован — сохраняем и показываем
                buf = io.BytesIO()
                fig.savefig(buf, format="png", bbox_inches="tight")
                buf.seek(0)
                img_str = base64.b64encode(buf.read()).decode()
                st.image(f"data:image/png;base64,{img_str}", caption="Результат графика", use_column_width=True)

            except Exception as e:
                st.error(f"Не удалось автоматически отрендерить график:\n{str(e)}\n\nПопробуй ниже вставить только фрагмент с plt.figure() ... plt.show().")
            finally:
                plt.close(fig)

            # Дополнительное поле для ручного рендера (если авто не сработало)
            st.subheader("Ручной рендер (если авто не получилось)")
            manual_render = st.text_area("Вставь только код графика (от plt.figure до plt.show)", height=200)
            if st.button("Ручной рендер"):
                if manual_render.strip():
                    fig_manual = plt.figure(figsize=(10, 6))
                    try:
                        exec(manual_render, {"plt": plt, "sns": sns, "pd": pd})
                        buf = io.BytesIO()
                        fig_manual.savefig(buf, format="png", bbox_inches="tight")
                        buf.seek(0)
                        img_str = base64.b64encode(buf.read()).decode()
                        st.image(f"data:image/png;base64,{img_str}", caption="Ручной рендер")
                    except Exception as e:
                        st.error(f"Ошибка ручного рендера: {str(e)}")
                    finally:
                        plt.close(fig_manual)

        except json.JSONDecodeError:
            st.error("Не удалось распарсить JSON. Убедись, что вставил весь ответ целиком.")
        except Exception as e:
            st.error(f"Общая ошибка: {str(e)}")
    else:
        st.warning("Вставь JSON-ответ сначала.")
