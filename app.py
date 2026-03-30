import streamlit as st
import pandas as pd
import smtplib
import time
import re
import io
import os
import zipfile
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="نظام الإرسال المالي الذكي", layout="wide", page_icon="📊")

# --- RTL SUPPORT & CUSTOM STYLING ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    html, body, [data-testid="stSidebar"], .main {
        font-family: 'Tajawal', sans-serif;
        direction: RTL; text-align: right;
    }
    .stTextInput input, .stTextArea textarea, [data-testid="stSelectbox"], .stNumberInput input {
        direction: RTL; text-align: right;
    }
    .preview-box {
        border: 1px solid #e6e9ef;
        padding: 15px;
        border-radius: 8px;
        background-color: #f8f9fa;
    }
    </style>
    """, unsafe_allow_html=True)

# --- SESSION STATE ---
if 'current_idx' not in st.session_state: st.session_state.current_idx = 0
if 'is_running' not in st.session_state: st.session_state.is_running = False
if 'logs' not in st.session_state: st.session_state.logs = []

def reset_all():
    st.session_state.current_idx = 0
    st.session_state.is_running = False
    st.session_state.logs = []

# --- CORE FUNCTIONS ---
def send_mail(server, sender, to, subject, body, atts, is_html):
    try:
        msg = MIMEMultipart()
        msg['From'], msg['To'], msg['Subject'] = sender, to, subject
        msg.attach(MIMEText(body, 'html' if is_html else 'plain'))
        for a in atts:
            part = MIMEBase('application', "octet-stream")
            part.set_payload(a['content'])
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={a["name"]}')
            msg.attach(part)
        server.send_message(msg)
        return True, "تم"
    except Exception as e:
        return False, str(e)

# --- SIDEBAR ---
with st.sidebar:
    st.title("🔐 إعدادات الوصول")
    u_mail = st.text_input("إيميل Gmail", placeholder="example@gmail.com")
    u_pass = st.text_input("كلمة مرور التطبيق", type="password")
    st.divider()
    st.title("🕒 جدولة الإرسال")
    enable_schedule = st.checkbox("تفعيل الجدولة")
    sched_time = st.time_input("وقت الانطلاق", value=datetime.now().time(), disabled=not enable_schedule)
    st.divider()
    if st.button("🗑️ إعادة تعيين"):
        reset_all()
        st.rerun()

# --- MAIN INTERFACE ---
st.title("📊 محرك الإرسال المالي المتقدم")

t1, t2, t3 = st.tabs(["📂 البيانات والمرفقات الذكية", "📝 تصميم الحملة", "🚀 التحكم والتقارير"])

with t1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1️⃣ قائمة المستلمين")
        file = st.file_uploader("رفع Excel/CSV", type=['xlsx', 'csv'])
    with col2:
        st.subheader("2️⃣ المرفقات المخصصة (اختياري)")
        zip_file = st.file_uploader("ارفع ملف ZIP (يجب أن يكون اسم الملف هو إيميل العميل)", type=['zip'])
        if zip_file:
            st.info("سيقوم النظام تلقائياً بربط كل ملف داخل الـ ZIP بالإيميل المطابق لاسمه.")

    df = pd.DataFrame()
    if file:
        df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
    if not df.empty:
        st.success(f"تم تحميل {len(df)} سجل")
        c1, c2 = st.columns(2)
        e_col = c1.selectbox("عمود الإيميل", df.columns)
        n_col = c2.selectbox("عمود الاسم", [None] + list(df.columns))

with t2:
    sub = st.text_input("موضوع الرسالة")
    m_type = st.radio("نوع التنسيق", ["نص عادي", "HTML"], horizontal=True)
    body = st.text_area("نص الرسالة (استخدم {name} للتخصيص)", height=200)
    general_atts = st.file_uploader("مرفقات عامة (ترسل للكل)", accept_multiple_files=True)

with t3:
    st.subheader("⚡ التحكم في التدفق")
    if not df.empty:
        c_a, c_b = st.columns(2)
        start_at = c_a.number_input("ابدأ من السجل:", 0, len(df)-1, st.session_state.current_idx)
        batch_limit = c_b.number_input("حجم الدفعة:", 1, 10000, 500)
        
        btn_start = st.button("▶️ إطلاق العملية", type="primary", use_container_width=True)
        
        if btn_start:
            if enable_schedule:
                st.warning(f"النظام في حالة انتظار حتى الساعة {sched_time}...")
                while datetime.now().time() < sched_time:
                    time.sleep(10)
            
            st.session_state.is_running = True
            st.session_state.current_idx = start_at
            
            # استخراج ملفات الـ ZIP إذا وجدت
            custom_files = {}
            if zip_file:
                with zipfile.ZipFile(zip_file, 'r') as z:
                    for name in z.namelist():
                        custom_files[name.split('.')[0]] = {"name": name, "content": z.read(name)}

            try:
                server = smtplib.SMTP("smtp.gmail.com", 587)
                server.starttls()
                server.login(u_mail, u_pass)
                
                end_idx = min(st.session_state.current_idx + batch_limit, len(df))
                pb = st.progress(0.0)
                
                for i in range(st.session_state.current_idx, end_idx):
                    row = df.iloc[i]
                    target = str(row[e_col]).strip()
                    name_val = str(row[n_col]) if n_col else "عميلنا العزيز"
                    final_body = body.replace("{name}", name_val)
                    
                    # تجهيز المرفقات (عامة + مخصصة)
                    current_atts = []
                    for ga in general_atts:
                        current_atts.append({"name": ga.name, "content": ga.read()})
                        ga.seek(0)
                    
                    # بحث عن ملف مخصص لهذا الإيميل
                    email_prefix = target.split('@')[0]
                    if email_prefix in custom_files:
                        current_atts.append(custom_files[email_prefix])
                    elif target in custom_files:
                        current_atts.append(custom_files[target])

                    ok, msg = send_mail(server, u_mail, target, sub, final_body, current_atts, (m_type=="HTML"))
                    st.session_state.logs.append({"الإيميل": target, "الحالة": "✅" if ok else "❌", "التفاصيل": msg})
                    
                    st.session_state.current_idx = i + 1
                    pb.progress((i + 1 - start_at) / (end_idx - start_at))
                    time.sleep(2)
                
                server.quit()
                st.success("تم الانتهاء من الدفعة!")
            except Exception as e:
                st.error(f"خطأ: {e}")

        if st.session_state.logs:
            st.divider()
            st.subheader("📋 تقرير العملية")
            st.dataframe(pd.DataFrame(st.session_state.logs))
