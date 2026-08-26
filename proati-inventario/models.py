from datetime import datetime

from flask_login import UserMixin
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

import config
from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default="visualizador", nullable=False)
    must_reset_password = db.Column(db.Boolean, default=False, nullable=False)
    session_version = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def get_id(self):
        return f"{self.id}:{int(self.session_version or 0)}"

    def bump_session(self) -> None:
        self.session_version = int(self.session_version or 0) + 1

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)
        self.must_reset_password = False
        self.bump_session()

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_proati(self) -> bool:
        return self.role == "proati"

    @property
    def is_coordenador(self) -> bool:
        return self.role == "coordenador"

    @property
    def is_visualizador(self) -> bool:
        return self.role == "visualizador"

    def can_view_inventory(self) -> bool:
        return self.role in ("admin", "proati", "coordenador")

    def can_edit_inventory(self) -> bool:
        return self.role in ("admin", "proati")

    def can_manage_users(self) -> bool:
        return self.role == "admin"


class DeviceBlock(db.Model):
    __tablename__ = "device_blocks"

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    ip = db.Column(db.String(64), default="", nullable=False, index=True)
    attempt_count = db.Column(db.Integer, default=0, nullable=False)
    strike_level = db.Column(db.Integer, default=0, nullable=False)
    blocked_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def is_blocked(self) -> bool:
        return bool(self.blocked_until and self.blocked_until > datetime.utcnow())

    def to_dict(self) -> dict:
        until = self.blocked_until
        return {
            "id": self.id,
            "token": self.token[:12],
            "ip": self.ip or "—",
            "attempt_count": self.attempt_count,
            "strike_level": self.strike_level,
            "blocked_until": until.strftime("%d/%m/%Y %H:%M") if until else "",
            "level_label": "1 mês" if self.strike_level >= 2 else "1 dia",
        }


class Equipment(db.Model):
    __tablename__ = "equipment"

    id = db.Column(db.Integer, primary_key=True)
    tab = db.Column(db.String(40), nullable=False, index=True)
    modelo = db.Column(db.String(120), nullable=False)
    serial = db.Column(db.String(120), nullable=False)
    numeracao = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(40), nullable=True)
    problema = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("tab", "serial", name="uq_equipment_tab_serial"),
        db.UniqueConstraint("tab", "numeracao", name="uq_equipment_tab_numeracao"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "tab": self.tab,
            "modelo": self.modelo,
            "serial": self.serial,
            "numeracao": self.numeracao,
            "status": self.status or "",
            "problema": self.problema or "",
        }


def ensure_schema():
    inspector = inspect(db.engine)
    if "users" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("users")}
    if "must_reset_password" not in columns:
        db.session.execute(
            text(
                "ALTER TABLE users ADD COLUMN must_reset_password BOOLEAN NOT NULL DEFAULT FALSE"
            )
        )
        db.session.commit()
    if "session_version" not in columns:
        db.session.execute(
            text("ALTER TABLE users ADD COLUMN session_version INTEGER NOT NULL DEFAULT 0")
        )
        db.session.commit()

    if "equipment" in inspector.get_table_names():
        db.session.execute(
            text(
                "UPDATE equipment SET status = 'Perfeito estado' WHERE status = 'Operante'"
            )
        )
        db.session.execute(
            text(
                "UPDATE equipment SET status = 'Danos físicos' WHERE status = 'Inoperante'"
            )
        )
        db.session.execute(
            text(
                "UPDATE equipment SET status = 'Danos periféricos' "
                "WHERE status = 'Danos perifericos'"
            )
        )
        db.session.commit()


def init_default_data():
    try:
        admin = User.query.filter(
            (User.username == config.ADMIN_USERNAME) | (User.email == config.ADMIN_EMAIL)
        ).first()
        if not admin and config.ADMIN_PASSWORD:
            admin = User(
                username=config.ADMIN_USERNAME,
                email=config.ADMIN_EMAIL,
                role="admin",
            )
            admin.set_password(config.ADMIN_PASSWORD)
            db.session.add(admin)
            db.session.commit()
    except IntegrityError:
        db.session.rollback()
    except Exception:
        db.session.rollback()
