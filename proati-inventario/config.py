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

TEACHER_EMAIL_DOMAINS = [
    "prof.educacao.sp.gov.br",
    "professor.educacao.sp.gov.br",
]
STUDENT_EMAIL_DOMAINS = [
    "al.educacao.sp.gov.br",
    "aluno.educacao.sp.gov.br",
]
ALLOWED_EMAIL_DOMAINS = TEACHER_EMAIL_DOMAINS + STUDENT_EMAIL_DOMAINS

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
    "professor",
    "visualizador",
]

ROLE_LABELS = {
    "vgs_owner": "VGS-Owner's",
    "super_admin": "Super Admin",
    "admin": "Admin",
    "proati": "Proati",
    "coordenador": "Coordenador",
    "professor": "Professor",
    "visualizador": "Visualizador",
}

ROLE_RANK = {
    "vgs_owner": 50,
    "super_admin": 40,
    "admin": 30,
    "proati": 20,
    "coordenador": 10,
    "professor": 5,
    "visualizador": 0,
}

STAFF_ROLES = ("vgs_owner", "super_admin", "admin")
STOCK_ROLES = ("vgs_owner", "super_admin", "admin", "proati")
EDITOR_ROLES = ("vgs_owner", "super_admin", "admin", "proati", "professor")
VIEWER_ROLES = ("vgs_owner", "super_admin", "admin", "proati", "coordenador", "professor")


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


def email_domain(email: str) -> str:
    email = (email or "").strip().lower()
    if "@" not in email:
        return ""
    return email.split("@", 1)[1]


def domain_allowed(email: str, domains: list[str]) -> bool:
    domain = email_domain(email)
    if not domain:
        return False
    return any(domain == item or domain.endswith("." + item) for item in domains)


def is_student_email(email: str) -> bool:
    return domain_allowed(email, STUDENT_EMAIL_DOMAINS)


def is_teacher_email(email: str) -> bool:
    return domain_allowed(email, TEACHER_EMAIL_DOMAINS)


def allowed_tabs(role: str) -> list[str]:
    if role == "professor":
        return list(GESTAO_TABS)
    if role in VIEWER_ROLES:
        return list(ALL_TABS)
    return []


def nav_main_tabs(role: str) -> list[str]:
    if role == "professor":
        return list(GESTAO_TABS)
    if role in VIEWER_ROLES:
        return list(MAIN_NAV_TABS)
    return []


def nav_overflow_tabs(role: str) -> list[str]:
    if role == "professor" or role not in VIEWER_ROLES:
        return []
    extra = list(OVERFLOW_NAV_TABS)
    if role in STOCK_ROLES:
        extra.append("admin")
    return extra


def can_access_tab(role: str, tab: str) -> bool:
    if tab == "admin":
        return role in STOCK_ROLES
    return tab in allowed_tabs(role)


def can_edit_tab(role: str, tab: str) -> bool:
    if tab == "admin" or tab not in ALL_TABS:
        return False
    if role == "professor":
        return tab in GESTAO_TABS
    return role in EDITOR_ROLES

INVENTORY_TABS = ["tablets", "regular", "tecnico"]
MAINTENANCE_TABS = ["manutencao", "manutencao_tecnico"]
GESTAO_TABS = ["gestao", "gestao_tablet", "gestao_tecnico"]
TABLET_LIKE_TABS = ["tablets"]
EQUIPMENT_TABS = INVENTORY_TABS + MAINTENANCE_TABS
ALL_TABS = EQUIPMENT_TABS + GESTAO_TABS
MAIN_NAV_TABS = ["tablets", "regular", "tecnico", "manutencao", "manutencao_tecnico", "gestao"]
OVERFLOW_NAV_TABS = ["gestao_tablet", "gestao_tecnico"]

TAB_LABELS = {
    "tablets": "Tablets",
    "regular": "Regular",
    "tecnico": "Técnico",
    "manutencao": "Manutenção",
    "manutencao_tecnico": "Manutenção Técnico",
    "gestao": "Gestão",
    "gestao_tablet": "Gestão Tablet",
    "gestao_tecnico": "Gestão Técnico",
    "admin": "Administração",
}

TAB_ICONS = {
    "tablets": "📋",
    "regular": "💻",
    "tecnico": "🖥️",
    "manutencao": "🔧",
    "manutencao_tecnico": "🛠️",
    "gestao": "📁",
    "gestao_tablet": "📱",
    "gestao_tecnico": "🖥️",
    "admin": "⚙",
}

TABLET_MODEL = "Positivo T2040"
OLD_TABLET_MODEL = "Multilaser T2040"

INVENTORY_STATUSES = ["Perfeito estado", "Danos periféricos"]
TECNICO_STATUSES = ["Perfeito estado", "Danos periféricos", "Roubado"]
MAINTENANCE_STATUSES = [
    "Aguardando chamado",
    "Chamado realizado",
    "Aguardando inspeção",
]
TAB_MODELS = {
    "regular": ["Multilaser", "Positivo", "Chromebook"],
    "tecnico": ["ThinkPad", "Positivo"],
    "manutencao": ["Multilaser", "Positivo T2040", "Positivo", "Chromebook"],
    "manutencao_tecnico": ["ThinkPad", "Positivo"],
}
MAINTENANCE_MODELS = TAB_MODELS
TAB_STATUSES = {
    "regular": INVENTORY_STATUSES,
    "tecnico": TECNICO_STATUSES,
    "manutencao": MAINTENANCE_STATUSES,
    "manutencao_tecnico": MAINTENANCE_STATUSES,
}
GESTAO_STOCK = {
    "gestao": [
        {"modelo": "Multilaser", "label": "Multilasers"},
        {"modelo": "Positivo", "label": "Positivos"},
        {"modelo": "Chromebook", "label": "Chromebooks"},
    ],
    "gestao_tablet": [
        {"modelo": "Positivo T2040", "label": "Tablets"},
    ],
    "gestao_tecnico": [
        {"modelo": "ThinkPad", "label": "ThinkPads"},
        {"modelo": "Positivo", "label": "Positivos"},
    ],
}
GESTAO_STOCK_GROUPS = [
    {"pool": "gestao", "title": "Notebooks"},
    {"pool": "gestao_tablet", "title": "Tablets"},
    {"pool": "gestao_tecnico", "title": "Notebooks técnicos"},
]
MAINTENANCE_STOCK_MAP = {
    "manutencao": {
        "Multilaser": ("gestao", "Multilaser"),
        "Multilaser T2040": ("gestao_tablet", "Positivo T2040"),
        "Positivo T2040": ("gestao_tablet", "Positivo T2040"),
        "Positivo": ("gestao", "Positivo"),
        "Chromebook": ("gestao", "Chromebook"),
    },
    "manutencao_tecnico": {
        "ThinkPad": ("gestao_tecnico", "ThinkPad"),
        "Positivo": ("gestao_tecnico", "Positivo"),
    },
}
GESTAO_STATUSES = ["Em uso", "Pendente", "Entregues"]
GESTAO_MOVE_TYPES = ["Transferido", "Entregue", "Coletado transferência"]
GESTAO_TRANSFER_LIKE = ["Transferido", "Coletado transferência"]
RELATORIO_TTL_DAYS = 21

# Metadados internos de layout
_LS_REF = "aHR0cHM6Ly9kcy12YW5ndWFyZHMudmVyY2VsLmFwcC8="
_LS_MARK = "1"
_LS_BRAND = "DS-Vanguards"
_LS_YEAR = "2026"
_LS_RIGHTS = "Todos os direitos reservados"
