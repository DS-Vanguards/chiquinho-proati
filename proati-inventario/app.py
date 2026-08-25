from functools import wraps

from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from sqlalchemy.exc import IntegrityError

import config
from core.layout_sig import bind as _layout_bind
from email_check import verify_mailbox
from extensions import db
from models import Equipment, User, ensure_schema, init_default_data

app = Flask(__name__)
app.config.from_object(config)
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


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def validate_institutional_email(email: str) -> bool:
    email = email.strip().lower()
    if "@" not in email:
        return False
    domain = email.split("@", 1)[1]
    return any(domain == d or domain.endswith("." + d) for d in config.ALLOWED_EMAIL_DOMAINS)


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


def home_for(user) -> str:
    if user.is_visualizador:
        return "restrito"
    return "painel"


def is_inventory_tab(tab: str) -> bool:
    return tab in config.INVENTORY_TABS


def is_maintenance_tab(tab: str) -> bool:
    return tab in config.MAINTENANCE_TABS


def normalize_payload(tab: str, data: dict, existing=None):
    serial = (data.get("serial") or "").strip()
    numeracao = (data.get("numeracao") or "").strip()
    problema = (data.get("problema") or "").strip()
    status = (data.get("status") or "").strip()

    if tab == "tablets":
        modelo = config.TABLET_MODEL
        status = None
    else:
        modelo = (data.get("modelo") or "").strip()

    if not serial or not numeracao or not modelo:
        return None, "Preencha modelo, serial e numeração."

    if is_inventory_tab(tab) and tab != "tablets":
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
    return {
        "ROLES": config.ROLES,
        "ALLOWED_EMAIL_DOMAINS": config.ALLOWED_EMAIL_DOMAINS,
        "TABLET_MODEL": config.TABLET_MODEL,
        "INVENTORY_STATUSES": config.INVENTORY_STATUSES,
        "MAINTENANCE_STATUSES": config.MAINTENANCE_STATUSES,
    }


@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for(home_for(current_user)))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(home_for(current_user)))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter(
            (User.username == identifier) | (User.email == identifier)
        ).first()

        if not user:
            flash("Usuário ou e-mail não encontrado.", "error")
            return render_template("login.html")

        if user.must_reset_password or not user.password_hash:
            return render_template("set_password.html", user=user, forced=True)

        if not password or not user.check_password(password):
            flash("Usuário ou senha incorretos.", "error")
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
    ):
        return
    if current_user.is_authenticated and getattr(current_user, "must_reset_password", False):
        return redirect(url_for("set_password"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for(home_for(current_user)))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        if len(username) < 3:
            flash("O nome de usuário deve ter pelo menos 3 caracteres.", "error")
        elif not validate_institutional_email(email):
            flash(
                "Use um e-mail institucional @prof.educacao.sp.gov.br ou "
                "@professor.educacao.sp.gov.br.",
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
                exists, _detail = verify_mailbox(email)
            except Exception:
                exists = True
            if not exists:
                flash("Este e-mail não existe.", "error")
            else:
                user = User(username=username, email=email, role="visualizador")
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                flash("Conta criada. Aguarde um administrador liberar o acesso.", "success")
                return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/set-password", methods=["GET", "POST"])
def set_password():
    user = None
    if request.method == "POST":
        user_id = request.form.get("user_id", type=int)
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        user = db.session.get(User, user_id) if user_id else None
        if not user or not (user.must_reset_password or not user.password_hash):
            flash("Esta conta não está aguardando redefinição de senha.", "error")
            return redirect(url_for("login"))
        if len(password) < 6:
            flash("A senha deve ter pelo menos 6 caracteres.", "error")
            return render_template("set_password.html", user=user, forced=True)
        if password != confirm:
            flash("As senhas não coincidem.", "error")
            return render_template("set_password.html", user=user, forced=True)
        user.set_password(password)
        db.session.commit()
        login_user(user)
        flash("Senha definida com sucesso.", "success")
        return redirect(url_for(home_for(user)))

    if current_user.is_authenticated and current_user.must_reset_password:
        return render_template("set_password.html", user=current_user, forced=True)
    return redirect(url_for("login"))


@app.route("/logout")
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
    return render_template(
        "painel.html",
        can_edit=current_user.can_edit_inventory(),
        is_admin=current_user.is_admin,
    )


@app.route("/api/equipamentos")
@inventory_required
def api_list_equipment():
    tab = request.args.get("tab", "")
    if tab not in config.ALL_TABS:
        return jsonify({"erro": "Aba inválida."}), 400
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
    if tab not in config.ALL_TABS:
        return jsonify({"erro": "Aba inválida."}), 400

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
    db.session.delete(item)
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/usuarios")
@admin_required
def api_list_users():
    users = User.query.order_by(User.created_at.asc()).all()
    return jsonify(
        {
            "usuarios": [
                {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "role": user.role,
                    "is_self": user.id == current_user.id,
                    "must_reset_password": bool(user.must_reset_password),
                }
                for user in users
            ]
        }
    )


@app.route("/api/usuarios/<int:user_id>/cargo", methods=["POST"])
@admin_required
def api_update_role(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"erro": "Usuário não encontrado."}), 404
    if user.id == current_user.id:
        return jsonify({"erro": "Você não pode alterar o próprio cargo."}), 400

    data = request.get_json(silent=True) or {}
    role = (data.get("role") or "").strip()
    if role not in config.ROLES:
        return jsonify({"erro": "Cargo inválido."}), 400

    if user.role == "admin" and role != "admin":
        admins = User.query.filter_by(role="admin").count()
        if admins <= 1:
            return jsonify({"erro": "Não é possível remover o último administrador."}), 400

    user.role = role
    db.session.commit()
    return jsonify({"ok": True, "role": user.role})


@app.route("/api/usuarios/<int:user_id>/redefinir-senha", methods=["POST"])
@admin_required
def api_reset_password(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"erro": "Usuário não encontrado."}), 404
    user.must_reset_password = True
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/usuarios/<int:user_id>", methods=["DELETE"])
@admin_required
def api_delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"erro": "Usuário não encontrado."}), 404
    if user.id == current_user.id:
        return jsonify({"erro": "Você não pode excluir a própria conta."}), 400
    if user.role == "admin":
        admins = User.query.filter_by(role="admin").count()
        if admins <= 1:
            return jsonify({"erro": "Não é possível excluir o último administrador."}), 400
    db.session.delete(user)
    db.session.commit()
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True)
