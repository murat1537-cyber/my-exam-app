import streamlit as st

# theorieexamen.nl tarzı modern tasarım için CSS [cite: 7, 164, 237]
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        background-color: #007bff;
        color: white;
        font-weight: bold;
        border: none;
    }
    .question-card {
        background-color: white;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    </style>
    """, unsafe_allow_status=True)

# Başlık ve Dashboard [cite: 166-173]
st.title("🚀 Exam Prep Master")
st.subheader("Welcome! Ready to boost your score today?")

# Login Paneli [cite: 11]
with st.container():
    st.markdown('<div class="question-card">', unsafe_allow_html=True)
    email = st.text_input("Email Address")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        st.success(f"Welcome back, {email}!")
    st.markdown('</div>', unsafe_allow_html=True)
