import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from fpdf import FPDF
import io

# --- 1. KONU TANIMLAMALARI (Burayı Kendi Konularına Göre Düzenle) ---
TOPIC_MAP = {
    "1": "Security and Risk Management",
    "2": "Asset Security",
    "3": "Security Architecture and Engineering",
    "4": "Communication and Network Security",
    "5": "Identity and Access Management (IAM)",
    "6": "Security Assessment and Testing",
    "7": "Security Operations",
    "8": "Software Development Security"
}

# --- 2. TASARIM ---
st.set_page_config(page_title="AI Exam Mentor Pro", layout="wide")
st.markdown("""
    <style>
    * { -webkit-user-select: none; user-select: none; }
    .q-card { background: white; padding: 2rem; border-radius: 20px; box-shadow: 0 10px 30px rgba(0,0,0,0.05); border-top: 5px solid #007bff; }
    .explanation-box { background-color: #fff9db; padding: 15px; border-radius: 12px; border-left: 5px solid #fcc419; margin-top: 15px; }
    .timer-box { font-size: 22px; font-weight: bold; color: #d32f2f; text-align: center; background: #ffebee; border-radius: 10px; padding: 10px; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. SESSION STATE ---
if 'q_idx' not in st.session_state: st.session_state.q_idx = 0
if 'view' not in st.session_state: st.session_state.view = 'Main'
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False
if 'smart_list' not in st.session_state: st.session_state.smart_list = None

# --- 4. ANALİZ FONKSİYONU (TOPIC DESTEKLİ) ---
def show_topic_analytics(stats_df, questions_df):
    # Verileri birleştir
    stats_df['question_id'] = stats_df['question_id'].astype(str)
    questions_df['id'] = questions_df['id'].astype(str)
    
    merged_df = pd.merge(stats_df, questions_df[['id', 'topic_id']], left_on='question_id', right_on='id')
    
    # Topic ID'leri isimlere çevir
    merged_df['Topic Name'] = merged_df['topic_id'].astype(str).map(TOPIC_MAP).fillna("Tanımlanmamış")
    merged_df['is_correct'] = merged_df['is_correct'].astype(str).str.upper().replace({'0':'FALSE','1':'TRUE'})
    
    # Konu bazlı başarı hesapla
    topic_stats = merged_df.groupby(['Topic Name', 'is_correct']).size().reset_index(name='Count')
    
    fig = px.bar(topic_stats, x='Topic Name', y='Count', color='is_correct',
                 title="Konulara Göre Başarı Durumu",
                 color_discrete_map={'TRUE':'#2ecc71', 'FALSE':'#e74c3c'},
                 barmode='group')
    st.plotly_chart(fig, use_container_width=True)

# --- 5. SIDEBAR ---
with st.sidebar:
    st.title("🏆 AI Mentor Pro")
    if st.button("🚀 Yeni Sprint Başlat"):
        q_df = conn.read(worksheet="Questions", ttl=0)
        st.session_state.smart_list = q_df.sample(frac=1).reset_index(drop=True)
        st.session_state.q_idx = 0
        st.session_state.start_time = datetime.now()
        st.session_state.view = 'Study'
        st.rerun()
    
    st.write("---")
    if st.button("📊 Gelişmiş Analizler"): st.session_state.view = 'Analytics'
    if st.button("🔑 Admin Paneli"): st.session_state.view = 'Admin'

# --- 6. GÖRÜNÜMLER ---

# STUDY MODE (Soru çözerken konuyu da gösterelim)
if st.session_state.view == 'Study' and st.session_state.smart_list is not None:
    curr = st.session_state.smart_list.iloc[st.session_state.q_idx]
    topic_name = TOPIC_MAP.get(str(curr['topic_id']), "Genel")
    
    st.caption(f"📍 Konu: {topic_name}")
    st.markdown(f'<div class="q-card"><h3>{curr["content_text"]}</h3></div>', unsafe_allow_html=True)
    # ... (Soru butonları ve geri bildirim kodları buraya gelecek - Önceki kodla aynı)
    # Not: Hızlı olması için buton kısımlarını önceki mesajındaki gibi kullanabilirsin.

# ANALYTICS MODE
elif st.session_state.view == 'Analytics':
    st.header("📊 Konu Bazlı Performans Analizi")
    stats = conn.read(worksheet="User_Stats", ttl=0)
    questions = conn.read(worksheet="Questions", ttl=0)
    
    if not stats.empty and not questions.empty:
        col1, col2 = st.columns([1, 2])
        with col1:
            stats['is_correct'] = stats['is_correct'].astype(str).str.upper().replace({'0':'FALSE','1':'TRUE'})
            st.plotly_chart(px.pie(stats, names='is_correct', hole=0.4, title="Genel Başarı"))
        
        with col2:
            show_topic_analytics(stats, questions)
    else:
        st.info("Henüz analiz edilecek veri yok.")

# ADMIN MODE
elif st.session_state.view == 'Admin':
    if not st.session_state.admin_auth:
        pw = st.text_input("Şifre", type="password")
        if pw == "1234": st.session_state.admin_auth = True; st.rerun()
    else:
        st.subheader("📤 Toplu Soru Yükleme")
        uploaded_file = st.file_uploader("Excel Dosyası Seç", type=['xlsx'])
        if uploaded_file:
            new_data = pd.read_excel(uploaded_file)
            st.dataframe(new_data.head())
            if st.button("Veritabanını Güncelle"):
                old_data = conn.read(worksheet="Questions", ttl=0)
                final_df = pd.concat([old_data, new_data], ignore_index=True)
                conn.update(worksheet="Questions", data=final_df)
                st.success("Sorular başarıyla eklendi!")
