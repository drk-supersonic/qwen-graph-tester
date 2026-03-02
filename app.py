import streamlit as st
import requests
import json
import re
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import plotly.express as px
import io
import base64

# VLLM сервер (публичный IP твоего сервера iivm)
VLLM_URL = "https://humor-johnston-sponsorship-contributions.trycloudflare.com/v1/chat/completions"

st.set_page_config(page_title="Qwen Graph Tester", layout="wide")

st.title("Qwen Graph Tester — с прямой связью к модели")

# Поле для промпта
prompt = st.text_area("Вставь промпт для модели (текстовая задача)", height=200, value="Напиши код Streamlit для графика продаж по месяцам из CSV с date, sales, region.")

if st.button("Отправить промпт на модель и отрендерить графики"):
    if prompt.strip():
        try:
            # Отправляем запрос к vLLM
            payload = {
                "model": "Qwen/Qwen2.5-14B-Instruct-AWQ",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.7,
                "max_tokens": 1200
            }
            response = requests.post(VLLM_URL, json=payload, headers={"Content-Type": "application/json"})
            response.raise_for_status()

            data = response.json()
            full_text = data['choices'][0]['message']['content']

            # Вытаскиваем код между ```python и ```
            code_match = re.search(r'```python\s*(.*?)```', full_text, re.DOTALL | re.IGNORECASE)
            if code_match:
                code = code_match.group(1).strip()
            else:
                code = full_text.strip()

            st.subheader("Вытащенный код от модели")
            st.code(code, language="python")

            # Авто-рендер графиков
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

            # Ручной режим
            st.subheader("Ручной рендер (если авто не получилось)")
            manual_code = st.text_area("Вставь только код графика", height=200)
            if st.button("Ручной рендер"):
                if manual_code.strip():
                    fig = plt.figure(figsize=(12, 8))
                    try:
                        exec(manual_code, {"plt": plt, "sns": sns, "pd": pd, "px": px, "st": st})
                        buf = io.BytesIO()
                        fig.savefig(buf, format="png", bbox_inches="tight")
                        buf.seek(0)
                        img_str = base64.b64encode(buf.read()).decode()
                        st.image(f"data:image/png;base64,{img_str}", caption="Ручной результат")
                    except Exception as e:
                        st.error(f"Ошибка: {str(e)}")
                    finally:
                        plt.close(fig)
                else:
                    st.warning("Вставь код графика.")
        except requests.RequestException as e:
            st.error(f"Ошибка подключения к vLLM серверу: {str(e)}")
        except Exception as e:
            st.error(f"Общая ошибка: {str(e)}")
    else:
        st.warning("Вставь промпт сначала.")
