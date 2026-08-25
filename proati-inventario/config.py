import os

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = os.environ.get("SECRET_KEY", "proati-inventario-chave-local-2026")

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
    "prof.educacao.sp.gov.br",
    "professor.educacao.sp.gov.br",
]

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@proati.local")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "adminvgsproati")

SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "ds.vanguards.data@gmail.com")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "xvsjheydhtrapojc")
SMTP_FROM = os.environ.get("SMTP_FROM", "ds.vanguards.data@gmail.com")
SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"

ROLES = ["admin", "proati", "coordenador", "visualizador"]

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
