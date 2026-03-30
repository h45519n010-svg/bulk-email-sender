import streamlit as st
import pandas as pd
import smtplib
import time
import re
import io
import os
import zipfile
from datetime import datetime, timedelta
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
    .stProgress > div > div > div > div {
        background-color: #2e7d32;
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
        return True, "تم بنجاح"
    except Exception as e:
        return False, str(e)

# --- SIDEBAR ---
with st.sidebar:
    st.title("🔐 إعدادات الحساب")
    u_mail = st.text_input("إيميل Gmail", placeholder="example@gmail.com")
    u_pass = st.text_input("كلمة مرور التطبيق", type="password")
    st.divider()
    st.title("⚙️ تحكم الخادم")
    time_delay = st.slider("التأخير بين الرسائل (ثواني)", 0, 10, 2)
    if st.button("🗑️ إعادة تعيين النظام", use_container_width=True):
        reset_all()
        st.rerun()

# --- MAIN INTERFACE ---
st.title("📊 محرك الإرسال المالي الذكي")
st.caption("نظام احترافي لإدارة الحملات البريدية والمرفقات المخصصة")

t1, t2, t3 = st.tabs(["📂 البيانات والمرفقات", "📝 محتوى الرسالة", "🚀 جدولة وإرسال الدفعات"])

with t1:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1️⃣ قائمة المستلمين")
        file = st.file_uploader("رفع Excel/CSV", type=['xlsx', 'csv'])
        manual_entry = st.text_area("أو أضف إيميلات يدوياً (واحد في كل سطر)")
    with col2:
        st.subheader("2️⃣ المرفقات المخصصة")
        zip_file = st.file_uploader("ارفع ملف ZIP للمرفقات المخصصة", type=['zip'])
        st.info("تأكد أن اسم الملف داخل الـ ZIP يطابق الإيميل أو اسم العميل.")

    df = pd.DataFrame()
    if file:
        df = pd.read_csv(file) if file.name.endswith('.csv') else pd.read_excel(file)
    
    if manual_entry:
        m_list = [{"البريد": x.strip(), "الاسم": "عميلنا العزيز"} for x in manual_entry.split('\n') if x.strip()]
        df = pd.concat([df, pd.DataFrame(m_list)], ignore_index=True)

    if not df.empty:
        st.success(f"إجمالي المستلمين: {len(df)}")
        c1, c2 = st.columns(2)
        e_col = c1.selectbox("عمود الإيميل", df.columns)
        n_col = c2.selectbox("عمود الاسم", [None] + list(df.columns))

with t2:
    sub = st.text_input("موضوع البريد")
    m_type = st.radio("تنسيق الرسالة", ["نص عادي", "HTML"], horizontal=True)
    body = st.text_area("نص الرسالة (استخدم {name} للتخصيص)", height=200)
    general_atts = st.file_uploader("مرفقات عامة للجميع", accept_multiple_files=True)

with t3:
    if df.empty:
        st.warning("يرجى إدخال البيانات في التبويب الأول أولاً.")
    else:
        st.subheader("⏱️ جدولة الدفعة الحالية")
        
        col_ctrl1, col_ctrl2, col_ctrl3 = st.columns(3)
        with col_ctrl1:
            start_at = st.number_input("ابدأ من السجل:", 0, len(df)-1, st.session_state.current_idx)
        with col_ctrl2:
            batch_limit = st.number_input("عدد رسائل الدفعة:", 1, 10000, 500)
        with col_ctrl3:
            enable_sched = st.checkbox("تفعيل جدولة الدفعة")
            target_time = st.time_input("وقت بدء الإرسال", value=datetime.now().time(), disabled=not enable_sched)

        st.session_state.current_idx = start_at
        
        btn_run = st.button("▶️ تشغيل الدفعة المجدولة", type="primary", use_container_width=True)
        btn_pause = st.button("⏸️ إيقاف اضطراري", use_container_width=True)

        if btn_pause:
            st.session_state.is_running = False
            st.warning(f"تم الإيقاف. توقفنا عند السجل رقم: {st.session_state.current_idx}")

        if btn_run:
            if not u_mail or not u_pass:
                st.error("يرجى إدخال بيانات SMTP في الشريط الجانبي.")
            else:
                # منطق الانتظار للجدولة
                if enable_sched:
                    placeholder = st.empty()
                    while True:
                        now = datetime.now().time()
                        if now >= target_time:
                            placeholder.success("حان وقت الإرسال! جاري البدء...")
                            break
                        # حساب الوقت المتبقي للعرض
                        placeholder.warning(f"⏳ بانتظار حلول الساعة {target_time.strftime('%H:%M:%S')}... (الوقت الحالي: {now.strftime('%H:%M:%S')})")
                        time.sleep(1)

                st.session_state.is_running = True
                
                # استخراج ملفات الـ ZIP
                custom_files = {}
                if zip_file:
                    with zipfile.ZipFile(zip_file, 'r') as z:
                        for name in z.namelist():
                            key = name.split('.')[0] # اسم الملف بدون امتداد
                            custom_files[key] = {"name": name, "content": z.read(name)}

                try:
                    server = smtplib.SMTP("smtp.gmail.com", 587)
                    server.starttls()
                    server.login(u_mail, u_pass)
                    
                    end_idx = min(st.session_state.current_idx + batch_limit, len(df))
                    pb = st.progress(0.0)
                    status_info = st.empty()
                    
                    for i in range(st.session_state.current_idx, end_idx):
                        if not st.session_state.is_running: break
                        
                        row = df.iloc[i]
                        target = str(row[e_col]).strip()
                        name_val = str(row[n_col]) if n_col else "عميلنا العزيز"
                        final_body = body.replace("{name}", name_val)
                        
                        # المرفقات
                        current_atts = []
                        for ga in general_atts:
                            current_atts.append({"name": ga.name, "content": ga.read()})
                            ga.seek(0)
                        
                        # ربط المرفق المخصص
                        email_prefix = target.split('@')[0]
                        if email_prefix in custom_files:
                            current_atts.append(custom_files[email_prefix])
                        elif target in custom_files:
                            current_atts.append(custom_files[target])

                        status_info.text(f"جاري إرسال البريد ({i+1}/{end_idx}): {target}")
                        ok, res_msg = send_mail(server, u_mail, target, sub, final_body, current_atts, (m_type=="HTML"))
                        
                        st.session_state.logs.append({"الإيميل": target, "الحالة": "✅" if ok else "❌", "التوقيت": datetime.now().strftime('%H:%M:%S'), "ملاحظات": res_msg})
                        
                        st.session_state.current_idx = i + 1
                        pb.progress((i + 1 - start_at) / (end_idx - start_at))
                        time.sleep(time_delay)
                    
                    server.quit()
                    st.session_state.is_running = False
                    st.success(f"✅ اكتمل إرسال الدفعة الحالية بنجاح! تم إرسال {end_idx - start_at} رسالة.")
                except Exception as ex:
                    st.error(f"خطأ في الاتصال: {ex}")
                    st.session_state.is_running = False

        if st.session_state.logs:
            st.divider()
            st.subheader("📋 تقرير الدفعة الحالية")
            st.dataframe(pd.DataFrame(st.session_state.logs).iloc[::-1]) # عرض الأحدث أولاً
