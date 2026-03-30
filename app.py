import streamlit as st
import pandas as pd
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# --- إعدادات الصفحة واللغة ---
st.set_page_config(page_title="مُرسل البريد الجماعي الذكي", layout="wide", page_icon="📧")

# دعم العربية (RTL) وتنسيق الواجهة
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');
    html, body, [data-testid="stSidebar"], .main {
        font-family: 'Tajawal', sans-serif;
        direction: RTL;
        text-align: right;
    }
    .stTextInput input, .stTextArea textarea, [data-testid="stSelectbox"] {
        direction: RTL;
        text-align: right;
    }
    </style>
    """, unsafe_allow_html=True)

def send_email(server, sender_email, recipient_email, subject, body, attachments):
    """وظيفة بناء وإرسال رسالة بريد واحدة."""
    try:
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        for attachment in attachments:
            part = MIMEBase('application', "octet-stream")
            part.set_payload(attachment.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={attachment.name}')
            msg.attach(part)
            attachment.seek(0)

        server.send_message(msg)
        return True, "Success"
    except Exception as e:
        return False, str(e)

# --- الشريط الجانبي: إعدادات SMTP ---
with st.sidebar:
    st.header("⚙️ إعدادات الخادم (SMTP)")
    smtp_server = st.text_input("خادم SMTP", value="smtp.gmail.com")
    smtp_port = st.number_input("المنفذ (Port)", value=587)
    user_email = st.text_input("بريد المرسل", placeholder="example@gmail.com")
    app_password = st.text_input("كلمة مرور التطبيق", type="password", help="استخدم 16 حرفاً من App Passwords")
    st.markdown("---")
    delay = st.slider("زمن التأخير (ثواني)", 0, 10, 2)

# --- الواجهة الرئيسية ---
st.title("📧 أداة إرسال البريد الجماعي")
col1, col2 = st.columns([1, 1.2], gap="large")

with col1:
    st.subheader("1️⃣ البيانات")
    uploaded_file = st.file_uploader("ارفع ملف Excel أو CSV", type=['xlsx', 'csv'])
    df, email_col, name_col = None, None, None

    if uploaded_file:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        st.dataframe(df.head(3), use_container_width=True)
        cols = df.columns.tolist()
        email_col = st.selectbox("عمود البريد الإلكتروني:", cols)
        name_col = st.selectbox("عمود الاسم (اختياري):", [None] + cols)

with col2:
    st.subheader("2️⃣ الرسالة")
    subject_input = st.text_input("موضوع الرسالة")
    message_input = st.text_area("النص (استخدم {name} للتخصيص)", height=200)
    files = st.file_uploader("المرفقات", accept_multiple_files=True)

# --- منطق الإرسال ---
st.divider()
if st.button("🚀 بدء الإرسال الآن", use_container_width=True):
    if not uploaded_file or not user_email or not app_password:
        st.warning("الرجاء إكمال البيانات وإعدادات SMTP.")
    else:
        success_list, failure_list = [], []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            # الاتصال بالخادم
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(user_email, app_password)
            
            total = len(df)
            for index, row in df.iterrows():
                recipient = str(row[email_col]).strip()
                p_name = str(row[name_col]) if name_col else "عزيزي العميل"
                final_body = message_input.replace("{name}", p_name)
                
                status_text.text(f"إرسال إلى: {recipient} ({index+1}/{total})")
                is_sent, err = send_email(server, user_email, recipient, subject_input, final_body, files)
                
                if is_sent:
                    success_list.append(recipient)
                else:
                    failure_list.append({"email": recipient, "error": err})
                
                progress_bar.progress((index + 1) / total)
                time.sleep(delay)
            
            server.quit()
            st.success(f"اكتمل! نجاح: {len(success_list)} | فشل: {len(failure_list)}")
            if failure_list:
                with st.expander("تقرير الأخطاء"):
                    st.table(pd.DataFrame(failure_list))
        except Exception as e:
            st.error(f"خطأ في الاتصال بالخادم: {e}")

# دليل الاستخدام
with st.expander("📖 دليل استخراج App Password"):
    st.write("1. فعل 'التحقق بخطوتين' في حساب جوجل. 2. ابحث عن 'App Passwords'. 3. اختر 'Other' وسمه 'MailApp'. 4. انسخ الـ 16 حرفاً.")
