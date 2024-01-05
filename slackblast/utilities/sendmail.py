import smtplib
from email.message import EmailMessage


def send(subject, body, email_server, email_server_port, email_user, email_password, email_to):
    msg = EmailMessage()
    msg.set_content(body)

    msg["Subject"] = subject
    msg["From"] = email_user
    msg["To"] = email_to

    if email_server and email_server_port and email_user and email_password and email_to:
        server = smtplib.SMTP(email_server, email_server_port)
        server.starttls()
        server.login(email_user, email_password)
        server.send_message(msg)
        server.close()
