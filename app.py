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
st.markdown("Вставь **весь сырой JSON-ответ** из терминала → приложение вытащит код и попробует отрендерить.")

raw_json = st.text_area("Вставь весь JSON-ответ", height=400)

if st.button("Вытащить код и отрендерить"):
    if raw_json.strip():
        try:
            data = json.loads(raw_json)
            full_text = data['choices'][0]['message']['content']

            # Берём весь content после "content": — это самый надёжный способ
            code = full_text.strip()

            # Убираем инструкции в конце (всё после # Инструкции, """ или Установите)
            code = re.split(r'# Инструкции|# Как запустить|"""|if st.checkbox|Установите|Запустите|if __name__', code)[0].strip()

            st.subheader("Вытащенный чистый код")
            st.code(code, language="python")

            # Авто-рендер (попробуем выполнить весь код)
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
                st.error(f"Авто-рендер не сработал: {str(e)}\n\nИспользуй ручной режим ниже (вставь фрагмент от fig = ... до st.pyplot или st.plotly_chart).")
            finally:
                plt.close(fig)

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
                else:
                    st.warning("Вставь код графика.")

        except json.JSONDecodeError:
            st.error("Не удалось распарсить JSON.")
        except Exception as e:
            st.error(f"Ошибка: {str(e)}")
    else:
        st.warning("Вставь JSON.")
