import smtplib
from email.message import EmailMessage
from decouple import config


def send(subject, recipient, body):
    # defaults to gmail
    gmail_user = config('GMAIL_USER')
    gmail_password = config('GMAIL_PWD')

    # overrides
    email_server = config('EMAIL_SERVER', default='smtp.gmail.com')
    email_server_port = config('EMAIL_SERVER_PORT', default=465)
    email_user = config('EMAIL_USER', default=gmail_user)
    email_password = config('EMAIL_PASSWORD', default=gmail_password)

    msg = EmailMessage()
    msg.set_content(body)

    msg['Subject'] = subject
    msg['From'] = gmail_user
    msg['To'] = recipient

    server = smtplib.SMTP_SSL(email_server, email_server_port)
    server.ehlo()

    server.login(email_user, email_password)
    server.send_message(msg)
    server.close()
