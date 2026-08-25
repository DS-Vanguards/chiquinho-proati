import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config


def smtp_configured() -> bool:
    return bool(config.SMTP_HOST and config.SMTP_USER and config.SMTP_PASSWORD)


def send_verification_code(email: str, code: str) -> bool:
    subject = "Código de verificação — Proati"
    body = (
        "Olá,\n\n"
        f"Seu código para criar a conta no Proati é: {code}\n\n"
        "Ele vale por 15 minutos. Se você não pediu este cadastro, ignore este e-mail.\n"
    )

    if not smtp_configured():
        print("\n=== CÓDIGO DE VERIFICAÇÃO (SMTP não configurado) ===")
        print(f"Para: {email}")
        print(f"Código: {code}")
        print("====================================================\n")
        return True

    msg = MIMEMultipart()
    msg["From"] = config.SMTP_FROM
    msg["To"] = email
    msg["Subject"] = f"[{config._LS_BRAND}] {subject}"
    msg.attach(MIMEText(body, "plain", "utf-8"))

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as server:
            if config.SMTP_USE_TLS:
                server.starttls()
            if config.SMTP_USER and config.SMTP_PASSWORD:
                server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.sendmail(config.SMTP_FROM, [email], msg.as_string())
        return True
    except Exception as exc:
        print(f"Erro ao enviar e-mail de verificação: {exc}")
        return False
