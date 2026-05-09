import streamlit as st
import requests

# --------------------------
# 【最重要】你的后端接口地址
# --------------------------
API_URL = "http://192.168.217.128:8000/api/chat"

# 页面配置
st.set_page_config(
    page_title="AI智能学习答疑助手",
    page_icon="📚",
    layout="wide"
)

# 初始化聊天记录
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# 标题
st.title("📚 AI 全科辅导答疑助手")
st.divider()

# 侧边栏
with st.sidebar:
    st.header("📖 学科选择")
    subject = st.selectbox("选择学科", ["数学", "语文", "英语", "物理", "化学"])
    
    if st.button("清空对话记录"):
        st.session_state.chat_history = []
        st.success("已清空！")

# 显示历史聊天
for q, a in st.session_state.chat_history:
    with st.chat_message("user"):
        st.write(f"【{subject}】{q}")
    with st.chat_message("assistant"):
        st.write(a)

# 输入框
user_input = st.chat_input("请输入你的问题...")

if user_input:
    # --------------------------
    # 调用你的后端 main.py
    # --------------------------
    try:
        response = requests.post(
            API_URL,
            json={
                "question": user_input,
                "subject": subject,
                "history": []
            },
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            answer = data["data"]["answer"]
        else:
            answer = f"请求失败，错误码：{response.status_code}"

    except Exception as e:
        answer = f"连接后端失败：{str(e)}"

    # 保存聊天记录
    st.session_state.chat_history.append((user_input, answer))
    st.rerun()