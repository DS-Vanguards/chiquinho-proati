from datetime import datetime

from flask_login import UserMixin
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

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


def init_default_data():
    try:
        admin = User.query.filter(
            (User.username == config.ADMIN_USERNAME) | (User.email == config.ADMIN_EMAIL)
        ).first()
        if not admin:
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
