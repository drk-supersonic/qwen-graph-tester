import streamlit as st
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import plotly.express as px
import io
import base64

st.set_page_config(page_title="Qwen Graph Tester", layout="wide")

# Сайдбар навигация
page = st.sidebar.selectbox("Страница", ["1. Ввод кода от Qwen", "2. Просмотр кода", "3. Рендер графика"])

if page == "1. Ввод кода от Qwen":
    st.title("Вставь ответ от Qwen2.5-14B-Instruct-AWQ")
    st.markdown("Скопируй **весь код**, который выдала модель (включая ```python ... ```), и вставь ниже.")

    code_input = st.text_area("Вставь полный код сюда", height=500, key="input_code")

    if st.button("Сохранить код"):
        if code_input.strip():
            with open("last_code.py", "w", encoding="utf-8") as f:
                f.write(code_input)
            st.success("Код сохранён! Перейди на страницу 2 для просмотра.")
        else:
            st.warning("Вставь код сначала.")

elif page == "2. Просмотр кода":
    st.title("Просмотр сохранённого кода от Qwen")

    try:
        with open("last_code.py", "r", encoding="utf-8") as f:
            code = f.read()
        st.code(code, language="python")
    except FileNotFoundError:
        st.info("Пока нет сохранённого кода. Вернись на страницу 1 и вставь ответ модели.")

elif page == "3. Рендер графика":
    st.title("Рендер графика из кода")
    st.markdown("""
    Вставь **только часть кода**, которая строит график (от plt.figure() до plt.show() или fig.show()).
    Поддерживаются matplotlib, seaborn, plotly.express.
    """)

    render_code = st.text_area("Вставь код графика сюда", height=400, key="render_code")

    if st.button("Отрендерить график"):
        if render_code.strip():
            fig = None
            try:
                # Для matplotlib/seaborn
                if 'plt.' in render_code or 'sns.' in render_code:
                    fig = plt.figure(figsize=(10, 6))
                    exec(render_code, {"plt": plt, "sns": sns, "pd": pd, "px": px})
                    buf = io.BytesIO()
                    fig.savefig(buf, format="png", bbox_inches="tight")
                    buf.seek(0)
                    img_str = base64.b64encode(buf.read()).decode()
                    st.image(f"data:image/png;base64,{img_str}", caption="Результат matplotlib/seaborn", use_column_width=True)

                # Для plotly
                elif 'px.' in render_code:
                    exec(render_code, {"px": px, "pd": pd})
                    st.plotly_chart(fig, use_container_width=True)

                else:
                    st.warning("Код не содержит plt., sns. или px. — попробуй вставить правильный фрагмент.")

            except Exception as e:
                st.error(f"Ошибка при выполнении: {str(e)}")

            finally:
                if fig is not None:
                    plt.close(fig)
        else:
            st.warning("Вставь код графика сначала.")
