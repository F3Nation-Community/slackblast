import smtplib
import urllib.request
import requests
from email.message import EmailMessage

def send(subject, body, email_server, email_server_port, email_user, email_password, email_to, attachments):
    msg = EmailMessage()
    msg.set_content(body)

    msg["Subject"] = subject
    msg["From"] = email_user
    msg["To"] = email_to
    
    for file in attachments:
        with urllib.request.urlopen(file) as response:
            info = response.info()
            mainType = info.get_content_maintype()
            subType = info.get_content_subtype()
            filename = response.get_filename()

            f = requests.get(file, allow_redirects=True)

            msg.add_attachment(
                f.content,
                filename=filename,
                maintype=mainType,
                subtype=subType
            )

    if email_server and email_server_port and email_user and email_password and email_to:
        server = smtplib.SMTP(email_server, email_server_port)
        server.starttls()
        server.login(email_user, email_password)
        server.send_message(msg)
        server.close()