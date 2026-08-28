from datetime import datetime, timedelta

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
    role = db.Column(db.String(32), default="visualizador", nullable=False)
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
    def is_super_admin(self) -> bool:
        return self.role == "super_admin"

    @property
    def is_vgs_owner(self) -> bool:
        return self.role == "vgs_owner"

    @property
    def is_proati(self) -> bool:
        return self.role == "proati"

    @property
    def is_coordenador(self) -> bool:
        return self.role == "coordenador"

    @property
    def is_professor(self) -> bool:
        return self.role == "professor"

    @property
    def is_visualizador(self) -> bool:
        return self.role == "visualizador"

    @property
    def role_label(self) -> str:
        return config.role_label(self.role)

    def can_view_inventory(self) -> bool:
        return self.role in config.VIEWER_ROLES

    def can_edit_inventory(self) -> bool:
        return self.role in config.EDITOR_ROLES

    def can_manage_users(self) -> bool:
        return self.role in config.STAFF_ROLES

    def can_access_tab(self, tab: str) -> bool:
        return config.can_access_tab(self.role, tab)

    def can_edit_tab(self, tab: str) -> bool:
        return config.can_edit_tab(self.role, tab)

    def can_write_reports(self) -> bool:
        return self.is_professor or self.can_manage_users()


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
            "level_label": "1 dia" if self.strike_level >= 6 else "5 min",
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


class Relatorio(db.Model):
    __tablename__ = "relatorios"

    id = db.Column(db.Integer, primary_key=True)
    tab = db.Column(db.String(40), nullable=False, index=True)
    modelos = db.Column(db.String(200), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False)
    quantidade_atual = db.Column(db.Integer, nullable=False)
    sala = db.Column(db.String(80), nullable=False)
    professor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    professor_nome = db.Column(db.String(80), nullable=False)
    status = db.Column(db.String(40), default="Em uso", nullable=False)
    alterado = db.Column(db.Boolean, default=False, nullable=False)
    destinatario = db.Column(db.String(120), nullable=True)
    remetente = db.Column(db.String(120), nullable=True)
    sala_destino = db.Column(db.String(80), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self, *, viewer=None) -> dict:
        mine = bool(viewer and self.professor_id == viewer.id)
        can_write = bool(viewer and viewer.can_write_reports())
        can_alter = mine and can_write and self.status == "Em uso"
        can_delete = bool(viewer and viewer.can_manage_users())
        movimentos = [
            movimento.to_dict()
            for movimento in sorted(self.movimentos, key=lambda row: row.created_at or datetime.utcnow())
        ]
        return {
            "id": self.id,
            "tab": self.tab,
            "modelos": self.modelos,
            "quantidade": self.quantidade,
            "quantidade_atual": self.quantidade_atual,
            "sala": self.sala,
            "professor_id": self.professor_id,
            "professor": self.professor_nome,
            "status": self.status,
            "alterado": bool(self.alterado),
            "destinatario": self.destinatario or "",
            "remetente": self.remetente or "",
            "sala_destino": self.sala_destino or "",
            "mine": mine,
            "can_alter": can_alter,
            "can_delete": can_delete,
            "movimentos": movimentos,
        }


class RelatorioMovimento(db.Model):
    __tablename__ = "relatorio_movimentos"

    id = db.Column(db.Integer, primary_key=True)
    relatorio_id = db.Column(
        db.Integer,
        db.ForeignKey("relatorios.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipo = db.Column(db.String(40), nullable=False)
    quantidade = db.Column(db.Integer, nullable=True)
    destinatario = db.Column(db.String(120), nullable=True)
    sala_destino = db.Column(db.String(80), nullable=True)
    usuario_id = db.Column(db.Integer, nullable=True)
    usuario_nome = db.Column(db.String(80), nullable=False)
    usuario_cargo = db.Column(db.String(40), nullable=False, default="")
    detalhe = db.Column(db.String(240), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    relatorio = db.relationship(
        "Relatorio",
        backref=db.backref(
            "movimentos",
            cascade="all, delete-orphan",
            passive_deletes=True,
        ),
    )

    def to_dict(self) -> dict:
        when = self.created_at
        return {
            "id": self.id,
            "tipo": self.tipo,
            "quantidade": self.quantidade,
            "destinatario": self.destinatario or "",
            "sala_destino": self.sala_destino or "",
            "usuario_id": self.usuario_id,
            "usuario": self.usuario_nome,
            "cargo": self.usuario_cargo or "",
            "detalhe": self.detalhe or "",
            "quando": when.strftime("%d/%m/%Y %H:%M") if when else "",
        }


def purge_expired_relatorios() -> int:
    inspector = inspect(db.engine)
    if "relatorios" not in inspector.get_table_names():
        return 0
    cutoff = datetime.utcnow() - timedelta(days=config.RELATORIO_TTL_DAYS)
    expired_ids = [
        item_id
        for (item_id,) in db.session.query(Relatorio.id).filter(Relatorio.created_at < cutoff)
    ]
    if not expired_ids:
        return 0
    if "relatorio_movimentos" in inspector.get_table_names():
        RelatorioMovimento.query.filter(
            RelatorioMovimento.relatorio_id.in_(expired_ids)
        ).delete(synchronize_session=False)
    deleted = Relatorio.query.filter(Relatorio.id.in_(expired_ids)).delete(
        synchronize_session=False
    )
    if deleted:
        db.session.commit()
    return deleted


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
                "UPDATE equipment SET status = 'Danos periféricos' "
                "WHERE status IN ('Inoperante', 'Danos físicos', 'Danos perifericos')"
            )
        )
        db.session.commit()

    if "relatorios" in inspector.get_table_names():
        relatorio_cols = {column["name"] for column in inspector.get_columns("relatorios")}
        if "remetente" not in relatorio_cols:
            db.session.execute(text("ALTER TABLE relatorios ADD COLUMN remetente VARCHAR(120)"))
            db.session.commit()
    purge_expired_relatorios()


def init_default_data():
    try:
        bootstrap = User.query.filter(
            (User.username == config.ADMIN_USERNAME) | (User.email == config.ADMIN_EMAIL)
        ).first()
        has_owner = User.query.filter_by(role="vgs_owner").first() is not None
        if not has_owner:
            if bootstrap:
                bootstrap.role = "vgs_owner"
                db.session.commit()
            elif config.ADMIN_PASSWORD:
                owner = User(
                    username=config.ADMIN_USERNAME,
                    email=config.ADMIN_EMAIL,
                    role="vgs_owner",
                )
                owner.set_password(config.ADMIN_PASSWORD)
                db.session.add(owner)
                db.session.commit()
    except IntegrityError:
        db.session.rollback()
    except Exception:
        db.session.rollback()
