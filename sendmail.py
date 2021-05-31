import smtplib
from email.message import EmailMessage
from decouple import config


def send(subject, recipient, body):
    # was older gmail variables set?
    gmail_user = config('GMAIL_USER')
    gmail_password = config('GMAIL_PWD')

    email_server = config('EMAIL_SERVER')
    email_server_port = config('EMAIL_SERVER_PORT')
    email_user = config('EMAIL_USER')
    email_password = config('EMAIL_PASSWORD')

    if gmail_user:
        email_server = 'smtp.gmail.com'
        email_server_port = 465
        email_user = gmail_user
        email_password = gmail_password

    msg = EmailMessage()
    msg.set_content(body)

    msg['Subject'] = subject
    msg['From'] = email_user
    msg['To'] = recipient

    if email_server and email_server_port and email_user and email_password and recipient:
        server = smtplib.SMTP_SSL(email_server, email_server_port)
        server.ehlo()
        server.login(email_user, email_password)
        server.send_message(msg)
        server.close()
