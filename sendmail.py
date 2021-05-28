import smtplib
from email.message import EmailMessage
from decouple import config

def send(subject, recipient, body):
    gmail_user = config('GMAIL_USER')
    gmail_password = config('GMAIL_PWD')

    msg = EmailMessage()
    msg.set_content(body)

    msg['Subject'] = subject
    msg['From'] = gmail_user
    msg['To'] = recipient

    server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
    server.ehlo()
    server.login(gmail_user, gmail_password)
    server.send_message(msg)
    server.close()