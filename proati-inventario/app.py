from functools import wraps
import os
import re
from datetime import datetime

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_wtf.csrf import CSRFError, CSRFProtect, generate_csrf
from sqlalchemy.exc import IntegrityError

import config
from core.layout_sig import bind as _layout_bind
from email_check import verify_mailbox
from extensions import db
from hardening import (
    LOGIN_ERROR,
    add_security_headers,
    apply_proxy_fix,
    clear_password_reset,
    pending_reset_user_id,
    start_password_reset,
    too_many_requests,
)
from models import (
    DeviceBlock,
    Equipment,
    Relatorio,
    User,
    ensure_schema,
    init_default_data,
    purge_expired_relatorios,
)
from device_guard import (
    blocked_page_context,
    identify_device,
    parse_block_duration,
    refresh_block_state,
    register_attempt,
    with_device_cookie,
)

app = Flask(__name__)
app.config.from_object(config)
apply_proxy_fix(app)
CSRFProtect(app)
_layout_bind(app)

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = "login"
login_manager.login_message = "Faça login para continuar."
login_manager.login_message_category = "error"

with app.app_context():
    db.create_all()
    ensure_schema()
    init_default_data()


@app.errorhandler(CSRFError)
def handle_csrf_error(_error):
    if request.path.startswith("/api/"):
        return jsonify({"erro": "Sessão expirada. Recarregue a página."}), 400
    flash("Sessão expirada. Tente de novo.", "error")
    return redirect(url_for("login"))


@login_manager.user_loader
def load_user(user_id):
    raw = str(user_id or "")
    try:
        if ":" in raw:
            uid, version = raw.split(":", 1)
            user = db.session.get(User, int(uid))
            if user is None:
                return None
            if str(int(user.session_version or 0)) != str(version):
                return None
            return user
        return db.session.get(User, int(raw))
    except (TypeError, ValueError):
        return None


def validate_institutional_email(email: str) -> bool:
    return config.is_teacher_email(email) or config.is_student_email(email)


def validate_email_format(email: str) -> bool:
    email = (email or "").strip().lower()
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email)) and len(email) <= 120


def inventory_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.can_view_inventory():
            if request.path.startswith("/api/"):
                return jsonify({"erro": "Acesso restrito."}), 403
            return redirect(url_for("restrito"))
        return view(*args, **kwargs)

    return wrapped


def editor_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.can_edit_inventory():
            return jsonify({"erro": "Sem permissão para alterar equipamentos."}), 403
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.can_manage_users():
            if request.path.startswith("/api/"):
                return jsonify({"erro": "Apenas administradores."}), 403
            flash("Apenas administradores acessam esta área.", "error")
            return redirect(url_for("painel"))
        return view(*args, **kwargs)

    return wrapped


def last_vgs_owner(user) -> bool:
    if user.role != "vgs_owner":
        return False
    return User.query.filter_by(role="vgs_owner").count() <= 1


def manage_user_error(target, *, action: str):
    if target.id == current_user.id:
        if action == "excluir":
            return "Você não pode excluir a própria conta."
        if action == "cargo":
            return "Você não pode alterar o próprio cargo."
        return None
    if not config.can_manage_target(current_user.role, target.role):
        if current_user.role == "admin":
            return "Admin só pode gerenciar cargos abaixo de Admin."
        if current_user.role == "super_admin":
            return "Super Admin não pode gerenciar VGS-Owner's."
        return "Você não pode gerenciar este usuário."
    return None


def home_for(user) -> str:
    if user.is_visualizador:
        return "restrito"
    return "painel"


def is_inventory_tab(tab: str) -> bool:
    return tab in config.INVENTORY_TABS


def is_maintenance_tab(tab: str) -> bool:
    return tab in config.MAINTENANCE_TABS


def is_gestao_tab(tab: str) -> bool:
    return tab in config.GESTAO_TABS


def is_tablet_like_tab(tab: str) -> bool:
    return tab in config.TABLET_LIKE_TABS


def parse_positive_int(value):
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    if number < 1:
        return None
    return number


def deny_tab(tab: str):
    if not current_user.can_access_tab(tab):
        return jsonify({"erro": "Aba indisponível para o seu cargo."}), 403
    return None


def deny_edit_tab(tab: str):
    if not current_user.can_edit_tab(tab):
        return jsonify({"erro": "Sem permissão para alterar esta aba."}), 403
    return None


def normalize_payload(tab: str, data: dict, existing=None):
    serial = (data.get("serial") or "").strip()
    numeracao = (data.get("numeracao") or "").strip()
    problema = (data.get("problema") or "").strip()
    status = (data.get("status") or "").strip()

    if is_tablet_like_tab(tab):
        modelo = config.TABLET_MODEL
        status = None
    else:
        modelo = (data.get("modelo") or "").strip()

    if not serial or not numeracao or not modelo:
        return None, "Preencha modelo, serial e numeração."

    if is_inventory_tab(tab) and not is_tablet_like_tab(tab):
        if status not in config.INVENTORY_STATUSES:
            return None, "Selecione um status válido."
    elif is_maintenance_tab(tab):
        if not problema:
            return None, "Informe a descrição do problema."
        if status not in config.MAINTENANCE_STATUSES:
            return None, "Selecione um status válido."
    else:
        status = existing.status if existing else None

    return {
        "modelo": modelo,
        "serial": serial,
        "numeracao": numeracao,
        "status": status,
        "problema": problema if is_maintenance_tab(tab) else None,
    }, None


@app.context_processor
def inject_globals():
    assignable = []
    if getattr(current_user, "is_authenticated", False):
        assignable = config.assignable_roles(current_user.role)
    return {
        "ROLES": config.ROLES,
        "ROLE_LABELS": config.ROLE_LABELS,
        "ASSIGNABLE_ROLES": assignable,
        "ALLOWED_EMAIL_DOMAINS": config.ALLOWED_EMAIL_DOMAINS,
        "TABLET_MODEL": config.TABLET_MODEL,
        "TAB_LABELS": config.TAB_LABELS,
        "TAB_ICONS": config.TAB_ICONS,
        "INVENTORY_STATUSES": config.INVENTORY_STATUSES,
        "MAINTENANCE_STATUSES": config.MAINTENANCE_STATUSES,
        "GESTAO_MOVE_TYPES": config.GESTAO_MOVE_TYPES,
        "csrf_token": generate_csrf,
    }


@app.after_request
def set_security_headers(response):
    return add_security_headers(response)


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for(home_for(current_user)))
    return redirect(url_for("login"))


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(home_for(current_user)))

    if request.method == "POST":
        if too_many_requests("login", 8, 15 * 60):
            flash("Muitas tentativas. Aguarde alguns minutos e tente de novo.", "error")
            return render_template("login.html")

        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()

        if not user:
            flash(LOGIN_ERROR, "error")
            return render_template("login.html")

        if user.must_reset_password or not user.password_hash:
            start_password_reset(user.id)
            return render_template("set_password.html", user=user, forced=True)

        if not password or not user.check_password(password):
            flash(LOGIN_ERROR, "error")
            return render_template("login.html")

        login_user(user)
        return redirect(url_for(home_for(user)))

    return render_template("login.html")


@app.before_request
def force_password_reset():
    if request.endpoint in (
        None,
        "static",
        "set_password",
        "logout",
        "login",
        "register",
        "favicon",
    ):
        return
    if current_user.is_authenticated and getattr(current_user, "must_reset_password", False):
        return redirect(url_for("set_password"))


def blocked_response(device):
    ctx = blocked_page_context(device)
    return with_device_cookie(
        render_template("bloqueio.html", **ctx),
        device,
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for(home_for(current_user)))

    device = identify_device(persist=False)
    refresh_block_state(device)
    if device.is_blocked():
        return blocked_response(device)

    if request.method == "POST":
        if too_many_requests("register", 8, 15 * 60):
            flash("Muitas tentativas. Aguarde alguns minutos e tente de novo.", "error")
            return with_device_cookie(render_template("register.html"), device)

        device = identify_device(persist=True)
        device = register_attempt(device)
        if device.is_blocked():
            return blocked_response(device)

        username = request.form.get("username", "").strip()[:80]
        email = request.form.get("email", "").strip().lower()[:120]
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if len(username) < 3:
            flash("O nome de usuário deve ter pelo menos 3 caracteres.", "error")
        elif not validate_institutional_email(email):
            flash(
                "Use um e-mail institucional @prof.educacao.sp.gov.br, "
                "@professor.educacao.sp.gov.br, @al.educacao.sp.gov.br ou "
                "@aluno.educacao.sp.gov.br.",
                "error",
            )
        elif len(password) < 6:
            flash("A senha deve ter pelo menos 6 caracteres.", "error")
        elif password != confirm:
            flash("As senhas não coincidem.", "error")
        elif User.query.filter_by(username=username).first():
            flash("Este nome de usuário já está em uso.", "error")
        elif User.query.filter_by(email=email).first():
            flash("Este e-mail já está cadastrado.", "error")
        else:
            try:
                if config.is_student_email(email):
                    exists = True
                else:
                    exists, _detail = verify_mailbox(email)
            except Exception:
                exists = True
            if not exists:
                flash("Este e-mail não existe.", "error")
            else:
                if config.is_teacher_email(email):
                    role = "professor"
                else:
                    role = "visualizador"
                user = User(username=username, email=email, role=role)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                if role == "professor":
                    flash("Conta de professor criada. Entre para continuar.", "success")
                elif config.is_student_email(email):
                    flash("Conta de aluno criada. Entre para continuar.", "success")
                else:
                    flash("Conta criada. Aguarde um administrador liberar o acesso.", "success")
                return with_device_cookie(redirect(url_for("login")), device)

    return with_device_cookie(render_template("register.html"), device)


@app.route("/set-password", methods=["GET", "POST"])
def set_password():
    def resolve_reset_user():
        if current_user.is_authenticated and getattr(current_user, "must_reset_password", False):
            return current_user
        uid = pending_reset_user_id()
        if not uid:
            return None
        user = db.session.get(User, uid)
        if not user or not (user.must_reset_password or not user.password_hash):
            return None
        return user

    user = resolve_reset_user()
    if request.method == "POST":
        if too_many_requests("set-password", 8, 15 * 60):
            flash("Muitas tentativas. Aguarde alguns minutos e tente de novo.", "error")
            return redirect(url_for("login"))
        if not user:
            flash("Esta conta não está aguardando redefinição de senha.", "error")
            return redirect(url_for("login"))
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        if len(password) < 6:
            flash("A senha deve ter pelo menos 6 caracteres.", "error")
            return render_template("set_password.html", user=user, forced=True)
        if password != confirm:
            flash("As senhas não coincidem.", "error")
            return render_template("set_password.html", user=user, forced=True)
        user.set_password(password)
        db.session.commit()
        clear_password_reset()
        login_user(user)
        flash("Senha definida com sucesso.", "success")
        return redirect(url_for(home_for(user)))

    if user:
        return render_template("set_password.html", user=user, forced=True)
    return redirect(url_for("login"))


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Você saiu do sistema.", "info")
    return redirect(url_for("login"))


@app.route("/restrito")
@login_required
def restrito():
    if current_user.can_view_inventory():
        return redirect(url_for("painel"))
    return render_template("restrito.html")


@app.route("/painel")
@inventory_required
def painel():
    main_tabs = config.nav_main_tabs(current_user.role)
    overflow_tabs = config.nav_overflow_tabs(current_user.role)
    return render_template(
        "painel.html",
        can_edit=current_user.can_edit_inventory(),
        is_admin=current_user.can_manage_users(),
        is_professor=current_user.is_professor,
        user_id=current_user.id,
        main_tabs=main_tabs,
        overflow_tabs=overflow_tabs,
        default_tab=main_tabs[0] if main_tabs else "tablets",
    )


@app.route("/api/equipamentos")
@inventory_required
def api_list_equipment():
    tab = request.args.get("tab", "")
    if tab not in config.EQUIPMENT_TABS:
        return jsonify({"erro": "Aba inválida."}), 400
    denied = deny_tab(tab)
    if denied:
        return denied
    items = (
        Equipment.query.filter_by(tab=tab)
        .order_by(Equipment.numeracao.asc(), Equipment.id.asc())
        .all()
    )
    return jsonify({"itens": [item.to_dict() for item in items]})


@app.route("/api/equipamentos", methods=["POST"])
@editor_required
def api_create_equipment():
    data = request.get_json(silent=True) or {}
    tab = (data.get("tab") or "").strip()
    if tab not in config.EQUIPMENT_TABS:
        return jsonify({"erro": "Aba inválida."}), 400
    denied = deny_edit_tab(tab)
    if denied:
        return denied

    payload, error = normalize_payload(tab, data)
    if error:
        return jsonify({"erro": error}), 400

    item = Equipment(tab=tab, **payload)
    db.session.add(item)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"erro": "Serial ou numeração já cadastrados nesta aba."}), 400
    return jsonify({"item": item.to_dict()}), 201


@app.route("/api/equipamentos/<int:item_id>", methods=["PUT"])
@editor_required
def api_update_equipment(item_id):
    item = db.session.get(Equipment, item_id)
    if not item:
        return jsonify({"erro": "Equipamento não encontrado."}), 404
    denied = deny_edit_tab(item.tab)
    if denied:
        return denied

    data = request.get_json(silent=True) or {}
    payload, error = normalize_payload(item.tab, data, existing=item)
    if error:
        return jsonify({"erro": error}), 400

    item.modelo = payload["modelo"]
    item.serial = payload["serial"]
    item.numeracao = payload["numeracao"]
    item.status = payload["status"]
    item.problema = payload["problema"]
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"erro": "Serial ou numeração já cadastrados nesta aba."}), 400
    return jsonify({"item": item.to_dict()})


@app.route("/api/equipamentos/<int:item_id>", methods=["DELETE"])
@editor_required
def api_delete_equipment(item_id):
    item = db.session.get(Equipment, item_id)
    if not item:
        return jsonify({"erro": "Equipamento não encontrado."}), 404
    denied = deny_edit_tab(item.tab)
    if denied:
        return denied
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})


def load_relatorio_or_error(item_id):
    item = db.session.get(Relatorio, item_id)
    if not item:
        return None, (jsonify({"erro": "Relatório não encontrado."}), 404)
    denied = deny_tab(item.tab)
    if denied:
        return None, denied
    return item, None


@app.route("/api/relatorios")
@inventory_required
def api_list_reports():
    tab = request.args.get("tab", "")
    if not is_gestao_tab(tab):
        return jsonify({"erro": "Aba inválida."}), 400
    denied = deny_tab(tab)
    if denied:
        return denied
    purge_expired_relatorios()
    items = (
        Relatorio.query.filter_by(tab=tab)
        .order_by(Relatorio.created_at.desc(), Relatorio.id.desc())
        .all()
    )
    return jsonify({"itens": [item.to_dict(viewer=current_user) for item in items]})


@app.route("/api/relatorios", methods=["POST"])
@inventory_required
def api_create_report():
    if not current_user.is_professor:
        return jsonify({"erro": "Apenas professores podem adicionar relatórios."}), 403
    data = request.get_json(silent=True) or {}
    tab = (data.get("tab") or "").strip()
    if not is_gestao_tab(tab):
        return jsonify({"erro": "Aba inválida."}), 400
    denied = deny_tab(tab)
    if denied:
        return denied

    modelos = (data.get("modelos") or "").strip()[:200]
    sala = (data.get("sala") or "").strip()[:80]
    quantidade = parse_positive_int(data.get("quantidade"))
    if not modelos or not sala or not quantidade:
        return jsonify({"erro": "Preencha modelos, quantidade e sala."}), 400

    purge_expired_relatorios()
    item = Relatorio(
        tab=tab,
        modelos=modelos,
        quantidade=quantidade,
        quantidade_atual=quantidade,
        sala=sala,
        professor_id=current_user.id,
        professor_nome=current_user.username,
        status="Em uso",
        alterado=False,
    )
    db.session.add(item)
    db.session.commit()
    return jsonify({"item": item.to_dict(viewer=current_user)}), 201


@app.route("/api/relatorios/<int:item_id>/alterar", methods=["POST"])
@inventory_required
def api_alter_report(item_id):
    if not current_user.is_professor:
        return jsonify({"erro": "Apenas o professor do relatório pode alterá-lo."}), 403
    item, error = load_relatorio_or_error(item_id)
    if error:
        return error
    if item.professor_id != current_user.id:
        return jsonify({"erro": "Só o professor que criou o relatório pode alterá-lo."}), 403
    if item.status != "Em uso":
        return jsonify({"erro": "Este relatório já foi finalizado."}), 400

    data = request.get_json(silent=True) or {}
    quantidade = parse_positive_int(data.get("quantidade"))
    tipo = (data.get("tipo") or "").strip()
    if not quantidade:
        return jsonify({"erro": "Informe uma quantidade válida."}), 400
    if quantidade > int(item.quantidade_atual or 0):
        return jsonify({"erro": "A quantidade não pode ser maior que a quantidade atual."}), 400
    if tipo not in config.GESTAO_MOVE_TYPES:
        return jsonify({"erro": "Selecione Transferido ou Entregue."}), 400

    destinatario = (data.get("destinatario") or "").strip()[:120]
    sala_destino = (data.get("sala_destino") or "").strip()[:80]
    if tipo == "Transferido":
        if not destinatario or not sala_destino:
            return jsonify({"erro": "Informe o destinatário e a sala de destino."}), 400
        item.destinatario = destinatario
        item.sala_destino = sala_destino
    item.quantidade_atual = int(item.quantidade_atual) - quantidade
    item.alterado = True
    item.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"item": item.to_dict(viewer=current_user)})


@app.route("/api/relatorios/<int:item_id>/finalizar", methods=["POST"])
@inventory_required
def api_finish_report(item_id):
    if not current_user.is_professor:
        return jsonify({"erro": "Apenas o professor do relatório pode finalizá-lo."}), 403
    item, error = load_relatorio_or_error(item_id)
    if error:
        return error
    if item.professor_id != current_user.id:
        return jsonify({"erro": "Só o professor que criou o relatório pode finalizá-lo."}), 403
    if not item.alterado:
        return jsonify({"erro": "Finalize somente após alterar o relatório."}), 400
    if item.status != "Em uso":
        return jsonify({"erro": "Este relatório já foi finalizado."}), 400

    data = request.get_json(silent=True) or {}
    todos_entregues = bool(data.get("todos_entregues"))
    item.status = "Entregues" if todos_entregues else "Pendente"
    item.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"item": item.to_dict(viewer=current_user)})


@app.route("/api/relatorios/<int:item_id>", methods=["DELETE"])
@admin_required
def api_delete_report(item_id):
    item = db.session.get(Relatorio, item_id)
    if not item:
        return jsonify({"erro": "Relatório não encontrado."}), 404
    denied = deny_tab(item.tab)
    if denied:
        return denied
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/usuarios")
@admin_required
def api_list_users():
    users = User.query.order_by(User.created_at.asc()).all()
    assignable = config.assignable_roles(current_user.role)
    return jsonify(
        {
            "assignable_roles": assignable,
            "usuarios": [
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "is_self": user.id == current_user.id,
                    "must_reset_password": bool(user.must_reset_password),
                    "can_edit_role": (
                        user.id != current_user.id
                        and config.can_manage_target(current_user.role, user.role)
                    ),
                    "can_manage": (
                        user.id != current_user.id
                        and config.can_manage_target(current_user.role, user.role)
                    ),
                    "can_reset": (
                        user.id == current_user.id
                        or config.can_manage_target(current_user.role, user.role)
                    ),
                }
                for user in users
            ]
        }
    )


@app.route("/api/usuarios", methods=["POST"])
@admin_required
def api_create_user():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()[:80]
    email = (data.get("email") or "").strip().lower()[:120]
    password = data.get("password") or ""
    confirm = data.get("confirm_password") or ""
    role = (data.get("role") or "visualizador").strip()

    if len(username) < 3:
        return jsonify({"erro": "O nome de usuário deve ter pelo menos 3 caracteres."}), 400
    if not validate_email_format(email):
        return jsonify({"erro": "Informe um e-mail válido."}), 400
    if len(password) < 6:
        return jsonify({"erro": "A senha deve ter pelo menos 6 caracteres."}), 400
    if password != confirm:
        return jsonify({"erro": "As senhas não coincidem."}), 400
    if config.is_student_email(email):
        role = "visualizador"
    elif role not in config.assignable_roles(current_user.role):
        return jsonify({"erro": "Você não pode atribuir este cargo."}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"erro": "Este nome de usuário já está em uso."}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"erro": "Este e-mail já está cadastrado."}), 400

    user = User(username=username, email=email, role=role)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "usuario": {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role,
            },
        }
    ), 201


@app.route("/api/usuarios/<int:user_id>/cargo", methods=["POST"])
@admin_required
def api_update_role(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"erro": "Usuário não encontrado."}), 404
    blocked = manage_user_error(user, action="cargo")
    if blocked:
        return jsonify({"erro": blocked}), 400

    data = request.get_json(silent=True) or {}
    role = (data.get("role") or "").strip()
    if role not in config.assignable_roles(current_user.role):
        return jsonify({"erro": "Você não pode atribuir este cargo."}), 400

    if last_vgs_owner(user) and role != "vgs_owner":
        return jsonify({"erro": "Não é possível remover o último VGS-Owner's."}), 400

    user.role = role
    db.session.commit()
    return jsonify({"ok": True, "role": user.role})


@app.route("/api/usuarios/<int:user_id>/redefinir-senha", methods=["POST"])
@admin_required
def api_reset_password(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"erro": "Usuário não encontrado."}), 404
    blocked = manage_user_error(user, action="senha")
    if blocked:
        return jsonify({"erro": blocked}), 400
    user.must_reset_password = True
    user.bump_session()
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/usuarios/<int:user_id>", methods=["DELETE"])
@admin_required
def api_delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"erro": "Usuário não encontrado."}), 404
    blocked = manage_user_error(user, action="excluir")
    if blocked:
        return jsonify({"erro": blocked}), 400
    if last_vgs_owner(user):
        return jsonify({"erro": "Não é possível excluir o último VGS-Owner's."}), 400
    db.session.delete(user)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/bloqueios")
@admin_required
def api_list_blocks():
    now = datetime.utcnow()
    rows = (
        DeviceBlock.query.filter(DeviceBlock.blocked_until.isnot(None))
        .filter(DeviceBlock.blocked_until > now)
        .order_by(DeviceBlock.blocked_until.desc())
        .all()
    )
    return jsonify({"bloqueios": [row.to_dict() for row in rows]})


@app.route("/api/bloqueios/<int:block_id>/tempo", methods=["POST"])
@admin_required
def api_set_block_duration(block_id):
    row = db.session.get(DeviceBlock, block_id)
    if not row:
        return jsonify({"erro": "Bloqueio não encontrado."}), 404
    data = request.get_json(silent=True) or {}
    delta = parse_block_duration(data.get("amount"), data.get("unit"))
    if not delta:
        return jsonify({"erro": "Informe um número válido e a unidade de tempo."}), 400
    row.blocked_until = datetime.utcnow() + delta
    row.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True, "bloqueio": row.to_dict()})


@app.route("/api/bloqueios/<int:block_id>", methods=["DELETE"])
@admin_required
def api_remove_block(block_id):
    row = db.session.get(DeviceBlock, block_id)
    if not row:
        return jsonify({"erro": "Bloqueio não encontrado."}), 404
    row.blocked_until = None
    row.attempt_count = 0
    row.updated_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(
        debug=os.environ.get("FLASK_DEBUG", "").lower() in ("1", "true", "yes"),
        host="127.0.0.1",
        port=5000,
    )
