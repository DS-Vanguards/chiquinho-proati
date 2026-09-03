from datetime import datetime, timedelta

from flask_login import UserMixin
from sqlalchemy import Index, func, inspect, text
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
    def is_professor_tecnico(self) -> bool:
        return self.role == "professor_tecnico"

    @property
    def is_teacher(self) -> bool:
        return self.role in config.TEACHER_ROLES

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

    def can_manage_stock(self) -> bool:
        return self.role in config.STOCK_ROLES

    def can_access_tab(self, tab: str) -> bool:
        return config.can_access_tab(self.role, tab)

    def can_edit_tab(self, tab: str) -> bool:
        return config.can_edit_tab(self.role, tab)

    def can_write_reports(self) -> bool:
        return self.is_teacher or self.can_manage_users()

    def can_close_other_reports(self) -> bool:
        return self.is_super_admin or self.is_vgs_owner


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
    serie_patrimonio = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index(
            "uq_equipment_tab_serial_filled",
            "tab",
            "serial",
            unique=True,
            sqlite_where=text("serial IS NOT NULL AND serial != ''"),
            postgresql_where=text("serial IS NOT NULL AND serial != ''"),
        ),
        Index(
            "uq_equipment_tab_modelo_numeracao_filled",
            "tab",
            "modelo",
            "numeracao",
            unique=True,
            sqlite_where=text("numeracao IS NOT NULL AND numeracao != ''"),
            postgresql_where=text("numeracao IS NOT NULL AND numeracao != ''"),
        ),
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
            "serie_patrimonio": self.serie_patrimonio or "",
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
        can_return = (
            can_write
            and self.status == "Em uso"
            and (mine or bool(viewer and viewer.can_close_other_reports()))
        )
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
            "can_return": can_return,
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


class SchoolStock(db.Model):
    __tablename__ = "school_stock"

    id = db.Column(db.Integer, primary_key=True)
    pool = db.Column(db.String(40), nullable=False, index=True)
    modelo = db.Column(db.String(120), nullable=False)
    quantidade = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("pool", "modelo", name="uq_school_stock_pool_modelo"),
    )


def gestao_stock_specs():
    specs = []
    for pool, items in config.GESTAO_STOCK.items():
        for item in items:
            specs.append({"pool": pool, "modelo": item["modelo"], "label": item["label"]})
    return specs


def match_gestao_modelo(tab: str, raw: str):
    allowed = [item["modelo"] for item in config.GESTAO_STOCK.get(tab) or []]
    text = (raw or "").strip()
    if not text or not allowed:
        return None
    for modelo in allowed:
        if modelo.lower() == text.lower():
            return modelo
    hits = [modelo for modelo in allowed if modelo.lower() in text.lower()]
    if len(hits) == 1:
        return hits[0]
    return None


def maintenance_stock_key(tab: str, modelo: str):
    mapped = (config.MAINTENANCE_STOCK_MAP.get(tab) or {}).get(modelo)
    if mapped:
        return mapped
    for key, value in (config.MAINTENANCE_STOCK_MAP.get(tab) or {}).items():
        if key.lower() == (modelo or "").lower():
            return value
    return None


def report_units_out(relatorio, entregue_map=None) -> int:
    if relatorio.status == "Entregues":
        return 0
    if entregue_map is not None:
        entregue = int(entregue_map.get(relatorio.id) or 0)
    else:
        entregue = sum(
            int(move.quantidade or 0)
            for move in (relatorio.movimentos or [])
            if move.tipo == "Entregue"
        )
    return max(0, int(relatorio.quantidade or 0) - entregue)


def stock_snapshot(*, ignore_equipment_id=None, ignore_relatorio_id=None):
    totals = {
        (row.pool, row.modelo): int(row.quantidade or 0) for row in SchoolStock.query.all()
    }
    maintenance_used = {}
    query = Equipment.query.filter(Equipment.tab.in_(config.MAINTENANCE_TABS))
    if ignore_equipment_id:
        query = query.filter(Equipment.id != ignore_equipment_id)
    for item in query.all():
        key = maintenance_stock_key(item.tab, item.modelo)
        if not key:
            continue
        maintenance_used[key] = maintenance_used.get(key, 0) + 1

    entregue_map = dict(
        db.session.query(
            RelatorioMovimento.relatorio_id,
            func.coalesce(func.sum(RelatorioMovimento.quantidade), 0),
        )
        .filter(RelatorioMovimento.tipo == "Entregue")
        .group_by(RelatorioMovimento.relatorio_id)
        .all()
    )
    reports_used = {}
    report_query = Relatorio.query.filter(Relatorio.status != "Entregues")
    if ignore_relatorio_id:
        report_query = report_query.filter(Relatorio.id != ignore_relatorio_id)
    for report in report_query.all():
        modelo = match_gestao_modelo(report.tab, report.modelos)
        if not modelo:
            continue
        key = (report.tab, modelo)
        reports_used[key] = reports_used.get(key, 0) + report_units_out(report, entregue_map)

    itens = []
    total = 0
    por_aba = {pool: [] for pool in config.GESTAO_STOCK}
    for spec in gestao_stock_specs():
        key = (spec["pool"], spec["modelo"])
        quantidade_total = totals.get(key, 0)
        em_manutencao = maintenance_used.get(key, 0)
        em_uso = reports_used.get(key, 0)
        restantes = max(0, quantidade_total - em_manutencao - em_uso)
        row = {
            "pool": spec["pool"],
            "modelo": spec["modelo"],
            "label": spec["label"],
            "quantidade_total": quantidade_total,
            "em_manutencao": em_manutencao,
            "em_uso": em_uso,
            "restantes": restantes,
        }
        itens.append(row)
        por_aba[spec["pool"]].append(row)
        total += quantidade_total
    return {"itens": itens, "total": total, "por_aba": por_aba}


def stock_unavailable_error(pool: str, modelo: str, quantidade: int, **ignore):
    if quantidade < 1:
        return None
    snapshot = stock_snapshot(**ignore)
    item = next(
        (row for row in snapshot["itens"] if row["pool"] == pool and row["modelo"] == modelo),
        None,
    )
    if not item:
        return "Modelo sem estoque cadastrado."
    if item["restantes"] < quantidade:
        return (
            f"Não há {item['label']} restantes o suficiente "
            f"({item['restantes']} disponíveis)."
        )
    return None


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
                "WHERE status IN ('Inoperante', 'Danos perifericos') "
                "OR (status = 'Danos físicos' AND tab != 'tablets')"
            )
        )
        db.session.execute(
            text(
                "UPDATE equipment SET status = 'Perfeito estado' "
                "WHERE tab = 'tablets' AND (status IS NULL OR status = '')"
            )
        )
        db.session.commit()
        equip_cols = {column["name"] for column in inspector.get_columns("equipment")}
        if "serie_patrimonio" not in equip_cols:
            db.session.execute(
                text("ALTER TABLE equipment ADD COLUMN serie_patrimonio VARCHAR(120)")
            )
            db.session.commit()
        _migrate_equipment_numeracao_unique()
        _rename_tablet_model()

    if "relatorios" in inspector.get_table_names():
        relatorio_cols = {column["name"] for column in inspector.get_columns("relatorios")}
        if "remetente" not in relatorio_cols:
            db.session.execute(text("ALTER TABLE relatorios ADD COLUMN remetente VARCHAR(120)"))
            db.session.commit()
    purge_expired_relatorios()


def _constraint_names(table: str) -> set:
    inspector = inspect(db.engine)
    names = {item["name"] for item in inspector.get_unique_constraints(table) if item.get("name")}
    names.update(item["name"] for item in inspector.get_indexes(table) if item.get("name"))
    return names


def _drop_named_constraint(table: str, name: str):
    dialect = db.engine.dialect.name
    if dialect == "sqlite":
        db.session.execute(text(f"DROP INDEX IF EXISTS {name}"))
        return
    db.session.execute(text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}"))
    db.session.execute(text(f"DROP INDEX IF EXISTS {name}"))


def _migrate_equipment_numeracao_unique():
    names = _constraint_names("equipment")
    dialect = db.engine.dialect.name
    changed = False
    for name in (
        "uq_equipment_tab_numeracao",
        "uq_equipment_tab_serial",
        "uq_equipment_tab_modelo_numeracao",
    ):
        if name in names:
            _drop_named_constraint("equipment", name)
            changed = True
    if changed:
        db.session.commit()
        names = _constraint_names("equipment")
    if dialect == "sqlite":
        serial_where = "serial IS NOT NULL AND serial != ''"
        numero_where = "numeracao IS NOT NULL AND numeracao != ''"
    else:
        serial_where = "serial IS NOT NULL AND btrim(serial) <> ''"
        numero_where = "numeracao IS NOT NULL AND btrim(numeracao) <> ''"
    if "uq_equipment_tab_serial_filled" not in names:
        db.session.execute(
            text(
                "CREATE UNIQUE INDEX uq_equipment_tab_serial_filled "
                f"ON equipment (tab, serial) WHERE {serial_where}"
            )
        )
        db.session.commit()
    if "uq_equipment_tab_modelo_numeracao_filled" not in names:
        db.session.execute(
            text(
                "CREATE UNIQUE INDEX uq_equipment_tab_modelo_numeracao_filled "
                f"ON equipment (tab, modelo, numeracao) WHERE {numero_where}"
            )
        )
        db.session.commit()


def _rename_tablet_model():
    old = getattr(config, "OLD_TABLET_MODEL", "Multilaser T2040")
    new = config.TABLET_MODEL
    if not old or old == new:
        return
    db.session.execute(
        text("UPDATE equipment SET modelo = :new WHERE modelo = :old"),
        {"new": new, "old": old},
    )
    inspector = inspect(db.engine)
    if "relatorios" in inspector.get_table_names():
        db.session.execute(
            text("UPDATE relatorios SET modelos = :new WHERE modelos = :old"),
            {"new": new, "old": old},
        )
    if "school_stock" in inspector.get_table_names():
        old_rows = SchoolStock.query.filter_by(modelo=old).all()
        for row in old_rows:
            existing = SchoolStock.query.filter_by(pool=row.pool, modelo=new).first()
            if existing:
                existing.quantidade = int(existing.quantidade or 0) + int(row.quantidade or 0)
                db.session.delete(row)
            else:
                row.modelo = new
    db.session.commit()


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
