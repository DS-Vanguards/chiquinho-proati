import os

from dotenv import load_dotenv

from hardening import is_production, load_secret_key

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = load_secret_key(BASE_DIR)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = is_production()
PREFERRED_URL_SCHEME = "https" if is_production() else "http"
WTF_CSRF_SSL_STRICT = is_production()
WTF_CSRF_TIME_LIMIT = 3600

_database_url = (
    os.environ.get("DATABASE_URL")
    or os.environ.get("POSTGRES_URL")
    or os.environ.get("POSTGRES_PRISMA_URL")
    or os.environ.get("NEON_DATABASE_URL")
)

if _database_url:
    if _database_url.startswith("postgres://"):
        _database_url = _database_url.replace("postgres://", "postgresql://", 1)
    SQLALCHEMY_DATABASE_URI = _database_url
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }
elif os.environ.get("VERCEL"):
    raise RuntimeError(
        "Na Vercel, defina a variável DATABASE_URL com a connection string do Neon "
        "(use a conexão pooled e sslmode=require)."
    )
else:
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(BASE_DIR, 'proati.db')}"
    SQLALCHEMY_ENGINE_OPTIONS = {}

SQLALCHEMY_TRACK_MODIFICATIONS = False

ALLOWED_EMAIL_DOMAINS = [
    "al.educacao.sp.gov.br",
    "aluno.educacao.sp.gov.br",
    "prof.educacao.sp.gov.br",
    "professor.educacao.sp.gov.br",
]

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@proati.local")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("SMTP_FROM", "") or SMTP_USER
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"

ROLES = [
    "vgs_owner",
    "super_admin",
    "admin",
    "proati",
    "coordenador",
    "visualizador",
]

ROLE_LABELS = {
    "vgs_owner": "VGS-Owner's",
    "super_admin": "Super Admin",
    "admin": "Admin",
    "proati": "Proati",
    "coordenador": "Coordenador",
    "visualizador": "Visualizador",
}

ROLE_RANK = {
    "vgs_owner": 50,
    "super_admin": 40,
    "admin": 30,
    "proati": 20,
    "coordenador": 10,
    "visualizador": 0,
}

STAFF_ROLES = ("vgs_owner", "super_admin", "admin")
EDITOR_ROLES = ("vgs_owner", "super_admin", "admin", "proati")
VIEWER_ROLES = ("vgs_owner", "super_admin", "admin", "proati", "coordenador")


def role_label(role: str) -> str:
    return ROLE_LABELS.get(role, role)


def role_rank(role: str) -> int:
    return ROLE_RANK.get(role, -1)


def assignable_roles(actor_role: str) -> list[str]:
    if actor_role == "vgs_owner":
        return list(ROLES)
    if actor_role == "super_admin":
        return [role for role in ROLES if role != "vgs_owner"]
    if actor_role == "admin":
        return [role for role in ROLES if role_rank(role) < role_rank("admin")]
    return []


def can_manage_target(actor_role: str, target_role: str) -> bool:
    if actor_role == "vgs_owner":
        return True
    if actor_role == "super_admin":
        return role_rank(target_role) <= role_rank("super_admin")
    if actor_role == "admin":
        return role_rank(target_role) < role_rank("admin")
    return False

INVENTORY_TABS = ["tablets", "regular", "tecnico"]
MAINTENANCE_TABS = ["manutencao", "manutencao_tecnico"]
ALL_TABS = INVENTORY_TABS + MAINTENANCE_TABS

TABLET_MODEL = "Multilaser T2040"

INVENTORY_STATUSES = ["Perfeito estado", "Danos periféricos", "Danos físicos"]
MAINTENANCE_STATUSES = [
    "Aguardando chamado",
    "Chamado realizado",
    "Aguardando inspeção",
]

# Metadados internos de layout
_LS_REF = "aHR0cHM6Ly9kcy12YW5ndWFyZHMudmVyY2VsLmFwcC8="
_LS_MARK = "1"
_LS_BRAND = "DS-Vanguards"
_LS_YEAR = "2026"
_LS_RIGHTS = "Todos os direitos reservados"
