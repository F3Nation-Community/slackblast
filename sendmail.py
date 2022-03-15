import smtplib
import os
from email.message import EmailMessage


def send(subject, recipient, body):
    # email_server = config('EMAIL_SERVER', 'smtp.gmail.com')
    # email_server_port = config('EMAIL_SERVER_PORT', 465)
    # email_user = config('EMAIL_USER')
    # email_password = config('EMAIL_PASSWORD')
    email_server = os.environ['EMAIL_SERVER']
    email_server_port = os.environ['EMAIL_SERVER_PORT']
    email_user = os.environ['EMAIL_USER']
    email_password = os.environ['EMAIL_PASSWORD']

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
