import streamlit as st
import pandas as pd
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# إعدادات الصفحة واللغة العربية
st.set_page_config(page_title="مُرسل البريد الجماعي الذكي", layout="wide")

# تنسيق واجهة المستخدم لتدعم العربية (RTL)
st.markdown("""
    <style>
    .main { text-align: right; direction: rtl; }
    div[data-testid="stSidebarNav"] { text-align: right; direction: rtl; }
    label { text-align: right; width: 100%; }
    .stAlert { direction: rtl; }
    </style>
    """, unsafe_allow_html=True)

## --- الشريط الجانبي: إعدادات SMTP ---
with st.sidebar:
    st.header("⚙️ إعدادات الخادم (SMTP)")
    smtp_server = st.text_input("خادم SMTP", value="smtp.gmail.com")
    smtp_port = st.number_input("المنفذ (Port)", value=587)
    user_email = st.text_input("بريدك الإلكتروني (المرسل)")
    app_password = st.text_input("كلمة مرور التطبيق (App Password)", type="password")
    
    st.markdown("---")
    delay_seconds = st.slider("زمن التأخير بين الرسائل (ثواني)", 1, 10, 2)

## --- الواجهة الرئيسية ---
st.title("📧 أداة إرسال البريد الجماعي الذكية")
st.info("ارفع ملف الإكسل، صمم رسالتك، وأرسلها بلمسة واحدة.")

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("1️⃣ البيانات والمستقبلون")
    uploaded_file = st.file_uploader("ارفع ملف Excel أو CSV", type=['xlsx', 'csv'])
    
    if uploaded_file:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
        st.write("معاينة البيانات:")
        st.dataframe(df.head(5))
        
        columns = df.columns.tolist()
        email_col = st.selectbox("اختر عمود البريد الإلكتروني:", columns)
        name_col = st.selectbox("اختر عمود الاسم (للتخصيص الذكي):", [None] + columns)

with col2:
    st.subheader("2️⃣ محتوى الرسالة")
    subject = st.text_input("موضوع الرسالة")
    message_body = st.text_area("نص الرسالة (استخدم {name} للتخصيص)", height=200)
    attachments = st.file_uploader("أضف مرفقات (اختياري)", accept_multiple_files=True)

    if st.button("🚀 بدء عملية الإرسال الجماعي"):
        if not uploaded_file or not user_email or not app_password:
            st.error("الرجاء إكمال كافة الإعدادات ورفع الملف أولاً.")
        else:
            success_count = 0
            fail_count = 0
            failed_emails = []

            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                # إنشاء اتصال بالخادم مرة واحدة لتحسين الأداء
                try:
    server = smtplib.SMTP(smtp_server, smtp_port, timeout=30)
    server.ehlo() # تَحِيَّةُ الخادِمِ
    server.starttls() # تَنْشيطُ التَّشْفيرِ
    server.ehlo()
    server.login(user_email, app_password)
except Exception as e:
    st.error(f"فَشَلَ الاتِّصالُ: {e}")
    st.stop() # إِيْقافُ التَّنْفيذِ عِنْدَ الخَطَأِ


                for index, row in df.iterrows():
                    recipient = row[email_col]
                    recipient_name = str(row[name_col]) if name_col else "عميلنا العزيز"
                    
                    # تخصيص الرسالة
                    personalized_msg = message_body.replace("{name}", recipient_name)
                    
                    # إنشاء هيكل الإيميل
                    msg = MIMEMultipart()
                    msg['From'] = user_email
                    msg['To'] = recipient
                    msg['Subject'] = subject
                    msg.attach(MIMEText(personalized_msg, 'plain'))

                    # إضافة المرفقات
                    for uploaded_attach in attachments:
                        part = MIMEBase('application', "octet-stream")
                        part.set_payload(uploaded_attach.read())
                        encoders.encode_base64(part)
                        part.add_header('Content-Disposition', f'attachment; filename={uploaded_attach.name}')
                        msg.attach(part)
                        uploaded_attach.seek(0) # إعادة المؤشر لقراءة الملف للرسالة التالية

                    try:
                        server.send_message(msg)
                        success_count += 1
                    except Exception as e:
                        fail_count += 1
                        failed_emails.append(f"{recipient}: {str(e)}")

                    # تحديث التقدم
                    progress = (index + 1) / len(df)
                    progress_bar.progress(progress)
                    status_text.text(f"جاري الإرسال إلى: {recipient}")
                    
                    time.sleep(delay_seconds)

                server.quit()
                
                # تقرير النهاية
                st.success(f"✅ اكتملت العملية! الناجحة: {success_count} | الفاشلة: {fail_count}")
                if failed_emails:
                    with st.expander("عرض تفاصيل الرسائل الفاشلة"):
                        for err in failed_emails:
                            st.write(err)
                            
            except Exception as e:
                st.error(f"خطأ في الاتصال بالخادم: {e}")
