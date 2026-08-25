import smtplib
import time
from email.utils import parseaddr

try:
    import dns.resolver as dns_resolver
except ImportError:  # pragma: no cover
    dns_resolver = None

GOOGLE_DOMAINS = {"gmail.com", "googlemail.com"}
MICROSOFT_DOMAINS = {
    "hotmail.com",
    "hotmail.com.br",
    "outlook.com",
    "outlook.com.br",
    "live.com",
    "live.com.br",
    "msn.com",
}
SMTP_TIMEOUT = 8


def normalize_email(email: str) -> str:
    _, addr = parseaddr((email or "").strip().lower())
    return addr


def email_provider(domain: str, mx_hosts: list[str]) -> str:
    domain = (domain or "").lower()
    mx_blob = " ".join(mx_hosts).lower()
    if domain in GOOGLE_DOMAINS or "google.com" in mx_blob or "googlemail.com" in mx_blob:
        return "gmail"
    if (
        domain in MICROSOFT_DOMAINS
        or domain.endswith(".educacao.sp.gov.br")
        or "outlook.com" in mx_blob
        or "hotmail.com" in mx_blob
        or "protection.outlook.com" in mx_blob
    ):
        return "hotmail"
    return "outro"


def lookup_mx(domain: str) -> tuple[list[str], str]:
    if not domain or dns_resolver is None:
        return [], "unavailable"
    try:
        answers = dns_resolver.resolve(domain, "MX", lifetime=5)
        records = sorted(
            [(int(r.preference), str(r.exchange).rstrip(".").lower()) for r in answers],
            key=lambda item: item[0],
        )
        hosts = [host for _, host in records if host]
        if not hosts:
            return [], "missing"
        return hosts, "ok"
    except (dns_resolver.NXDOMAIN, dns_resolver.NoAnswer, dns_resolver.NoNameservers):
        return [], "missing"
    except Exception:
        return [], "timeout"


def _rcpt_status(mx_host: str, email: str) -> int | None:
    try:
        with smtplib.SMTP(timeout=SMTP_TIMEOUT) as smtp:
            smtp.connect(mx_host, 25)
            smtp.helo("proati-inventario.local")
            smtp.mail("noreply@proati.local")
            code, _ = smtp.rcpt(email)
            try:
                smtp.rset()
            except Exception:
                pass
            return int(code)
    except Exception:
        return None


def verify_mailbox(email: str) -> tuple[bool, str]:
    """Confere se o domínio recebe e-mail e, quando o servidor informa, se a caixa existe."""
    email = normalize_email(email)
    if "@" not in email:
        return False, "Informe um e-mail válido."

    domain = email.split("@", 1)[1]
    mx_hosts, mx_state = lookup_mx(domain)
    if mx_state == "missing":
        return False, "Este e-mail não existe: o domínio não recebe mensagens no Gmail/Hotmail/Outlook."
    if mx_state in ("timeout", "unavailable") and not mx_hosts:
        return True, "outro"

    provider = email_provider(domain, mx_hosts)
    last_code = None
    for host in mx_hosts[:2]:
        last_code = _rcpt_status(host, email)
        if last_code is not None:
            break
        time.sleep(0.2)

    if last_code is None:
        if provider in ("gmail", "hotmail"):
            return True, provider
        return True, "outro"

    if last_code == 250:
        return True, provider

    if last_code in (550, 551, 552, 553, 554):
        if provider == "gmail":
            return False, "Este e-mail não existe no Gmail."
        if provider == "hotmail":
            return False, "Este e-mail não existe no Hotmail/Outlook."
        return False, "Esta caixa de e-mail não existe."

    return True, provider
