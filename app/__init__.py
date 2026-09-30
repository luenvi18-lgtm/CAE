import os
import secrets

import click
from flask import Flask, redirect, url_for
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import event
from sqlalchemy.engine import Engine

from .models import (
    DIVISIONES,
    ESTADOS,
    ROL_SUPERUSUARIO,
    ROLES,
    TIPOS_EQUIPO,
    Usuario,
    db,
)
from .validaciones import validar_cedula, validar_password

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Inicia sesión para continuar."
login_manager.login_message_category = "warning"
csrf = CSRFProtect()


@event.listens_for(Engine, "connect")
def _activar_claves_foraneas_sqlite(dbapi_connection, connection_record):
    # SQLite no aplica ON DELETE CASCADE / SET NULL si no se activa.
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


@login_manager.user_loader
def cargar_usuario(cedula):
    return db.session.get(Usuario, cedula)


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    os.makedirs(app.instance_path, exist_ok=True)

    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY") or _clave_secreta(app.instance_path),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URL",
            "sqlite:///" + os.path.join(app.instance_path, "cae.db"),
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        POR_PAGINA=25,
    )
    if config:
        app.config.update(config)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from .admin import bp as admin_bp
    from .agente import bp as agente_bp
    from .auth import bp as auth_bp
    from .usuario import bp as usuario_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(usuario_bp)
    app.register_blueprint(agente_bp)
    app.register_blueprint(admin_bp)

    @app.context_processor
    def constantes():
        return {
            "DIVISIONES": DIVISIONES,
            "TIPOS_EQUIPO": TIPOS_EQUIPO,
            "ESTADOS": ESTADOS,
            "ROLES": ROLES,
        }

    @app.template_filter("fecha")
    def formato_fecha(valor):
        return valor.strftime("%d/%m/%Y %I:%M %p") if valor else "—"

    @app.route("/")
    def inicio():
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if current_user.es_agente:
            return redirect(url_for("agente.panel"))
        return redirect(url_for("usuario.mis_equipos"))

    with app.app_context():
        db.create_all()
        _crear_superusuario_desde_entorno()

    _registrar_comandos(app)
    return app


def _clave_secreta(carpeta):
    """Genera una clave secreta aleatoria la primera vez y la reutiliza, para
    que las sesiones sobrevivan a los reinicios sin definir SECRET_KEY."""
    ruta = os.path.join(carpeta, "secret_key")
    if not os.path.exists(ruta):
        with open(ruta, "w") as archivo:
            archivo.write(secrets.token_hex(32))
    with open(ruta) as archivo:
        return archivo.read().strip()


def _crear_superusuario_desde_entorno():
    """Crea el súper usuario inicial si se definen SUPERUSUARIO_CEDULA y
    SUPERUSUARIO_PASSWORD y aún no existe."""
    cedula = os.environ.get("SUPERUSUARIO_CEDULA")
    password = os.environ.get("SUPERUSUARIO_PASSWORD")
    if not cedula or not password or db.session.get(Usuario, cedula):
        return
    usuario = Usuario(
        cedula=cedula,
        nombres=os.environ.get("SUPERUSUARIO_NOMBRES", "Administrador"),
        apellidos=os.environ.get("SUPERUSUARIO_APELLIDOS", "Sistema"),
        division=DIVISIONES[0],
        rol=ROL_SUPERUSUARIO,
    )
    usuario.set_password(password)
    db.session.add(usuario)
    db.session.commit()


def _registrar_comandos(app):
    @app.cli.command("crear-superusuario")
    @click.option("--cedula", prompt="Cédula")
    @click.option("--nombres", prompt="Nombres")
    @click.option("--apellidos", prompt="Apellidos")
    @click.option(
        "--division",
        prompt="División",
        type=click.Choice(DIVISIONES),
        default=DIVISIONES[0],
    )
    @click.password_option("--password", prompt="Contraseña")
    def crear_superusuario(cedula, nombres, apellidos, division, password):
        """Crea (o asciende) un súper usuario."""
        errores = validar_cedula(cedula) + validar_password(password)
        if errores:
            raise click.ClickException(" ".join(errores))
        usuario = db.session.get(Usuario, cedula)
        if usuario is None:
            usuario = Usuario(cedula=cedula)
            db.session.add(usuario)
        usuario.nombres = nombres.strip()
        usuario.apellidos = apellidos.strip()
        usuario.division = division
        usuario.rol = ROL_SUPERUSUARIO
        usuario.set_password(password)
        db.session.commit()
        click.echo(f"Súper usuario {cedula} listo.")
