import streamlit as st
import pandas as pd
import smtplib
import time
import re
import io
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
        color: #333;
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
def extract_emails(text):
    """استخراج جميع الإيميلات من النص بغض النظر عن الفواصل."""
    return re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', text)

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
        return True, "Success"
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
    if st.button("🗑️ إعادة تعيين العملية"):
        reset_all()
        st.rerun()

# --- MAIN INTERFACE ---
st.title("📊 نظام الإرسال الذكي - نسخة المحترفين")

t1, t2, t3 = st.tabs(["📂 مصادر البيانات والمرفقات", "📝 تصميم الرسالة", "🚀 التنفيذ والتقارير"])

with t1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1️⃣ قائمة المستلمين")
        file = st.file_uploader("رفع ملف Excel أو CSV", type=['xlsx', 'csv'])
        manual_text = st.text_area("أو أضف الإيميلات هنا (بأي تنسيق: فواصل، متباعدة، إلخ)", height=100)
    with col2:
        st.subheader("2️⃣ المرفقات الذكية")
        zip_file = st.file_uploader("ارفع ملف ZIP (للمرفقات المخصصة لكل عميل)", type=['zip'])
        if zip_file:
            st.info("سيتم ربط الملفات تلقائياً إذا كان اسم الملف داخل ZIP يطابق إيميل المستلم.")

    # معالجة البيانات
    final_df = pd.DataFrame()
    if file:
        final_df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
    
    if manual_text:
        found_emails = extract_emails(manual_text)
        if found_emails:
            manual_df = pd.DataFrame(found_emails, columns=['البريد'])
            manual_df['الاسم'] = "عميلنا العزيز"
            final_df = pd.concat([final_df, manual_df], ignore_index=True)

    if not final_df.empty:
        st.success(f"إجمالي المستلمين المكتشفين: {len(final_df)}")
        c1, c2 = st.columns(2)
        cols = final_df.columns.tolist()
        e_col = c1.selectbox("اختر عمود البريد الإلكتروني", cols)
        n_col = c2.selectbox("اختر عمود الاسم (اختياري)", [None] + cols)

with t2:
    subj = st.text_input("موضوع البريد")
    m_mode = st.radio("تنسيق المحتوى", ["نص عادي", "HTML"], horizontal=True)
    msg_body = st.text_area("نص الرسالة (استخدم {name} للتخصيص)", height=200)
    general_atts = st.file_uploader("المرفقات العامة (للجميع)", accept_multiple_files=True)
    
    with st.expander("👁️ معاينة الرسالة"):
        processed = msg_body.replace("{name}", "محمد")
        if m_mode == "HTML":
            st.markdown(f'<div class="preview-box">{processed}</div>', unsafe_allow_html=True)
        else:
            st.code(processed, language="text")

with t3:
    st.subheader("⚙️ التحكم في العملية")
    if not final_df.empty:
        ca, cb = st.columns(2)
        start_from = ca.number_input("نقطة البداية (رقم السجل):", 0, len(final_df)-1, st.session_state.current_idx)
        batch_size = cb.number_input("حجم الدفعة الحالية:", 1, 50000, 500)
        
        launch_btn = st.button("▶️ تشغيل الآن / استكمال", type="primary", use_container_width=True)
        
        if launch_btn:
            if enable_schedule:
                st.warning(f"في حالة انتظار للجدولة: {sched_time}")
                while datetime.now().time() < sched_time:
                    time.sleep(5)
            
            st.session_state.is_running = True
            st.session_state.current_idx = start_from
            
            # معالجة ملفات ZIP
            custom_map = {}
            if zip_file:
                with zipfile.ZipFile(zip_file, 'r') as z:
                    for name in z.namelist():
                        clean_name = name.split('.')[0]
                        custom_map[clean_name] = {"name": name, "content": z.read(name)}

            try:
                server = smtplib.SMTP("smtp.gmail.com", 587)
                server.starttls()
                server.login(u_mail, u_pass)
                
                limit = min(st.session_state.current_idx + batch_size, len(final_df))
                p_bar = st.progress(0.0)
                
                for i in range(st.session_state.current_idx, limit):
                    row = final_df.iloc[i]
                    addr = str(row[e_col]).strip()
                    nm = str(row[n_col]) if n_col else "عميلنا العزيز"
                    f_body = msg_body.replace("{name}", nm)
                    
                    # تجميع المرفقات
                    current_files = []
                    for ga in general_atts:
                        current_files.append({"name": ga.name, "content": ga.read()})
                        ga.seek(0)
                    
                    # ربط المرفق المخصص
                    prefix = addr.split('@')[0]
                    if addr in custom_map: current_files.append(custom_map[addr])
                    elif prefix in custom_map: current_files.append(custom_map[prefix])

                    status, info = send_mail(server, u_mail, addr, subj, f_body, current_files, (m_mode=="HTML"))
                    st.session_state.logs.append({"السجل": i+1, "المستلم": addr, "الحالة": "✅" if status else "❌", "التفاصيل": info})
                    
                    st.session_state.current_idx = i + 1
                    p_bar.progress((i + 1 - start_from) / (limit - start_from))
                    time.sleep(2)
                
                server.quit()
                st.success("تم إنهاء المهمة المحددة.")
            except Exception as e:
                st.error(f"خطأ تقني: {e}")

        if st.session_state.logs:
            st.divider()
            st.subheader("📋 تقرير النتائج")
            st.table(pd.DataFrame(st.session_state.logs).tail(10))
