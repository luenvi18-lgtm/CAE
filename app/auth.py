from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from .models import ROL_USUARIO, Usuario, db
from .validaciones import validar_cedula, validar_password, validar_persona

bp = Blueprint("auth", __name__)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("inicio"))
    if request.method == "POST":
        cedula = request.form.get("cedula", "").strip()
        usuario = db.session.get(Usuario, cedula) if cedula else None
        if usuario and usuario.check_password(request.form.get("password", "")):
            login_user(usuario)
            return redirect(url_for("inicio"))
        flash("Cédula o contraseña incorrecta.", "danger")
    return render_template("auth/login.html")


@bp.route("/registro", methods=["GET", "POST"])
def registro():
    """Registro público: siempre crea cuentas con rol de usuario."""
    if current_user.is_authenticated:
        return redirect(url_for("inicio"))
    if request.method == "POST":
        cedula = request.form.get("cedula", "").strip()
        password = request.form.get("password", "")
        datos, errores = validar_persona(request.form)
        errores = validar_cedula(cedula) + errores + validar_password(password)
        if password != request.form.get("confirmar", ""):
            errores.append("Las contraseñas no coinciden.")
        if not errores and db.session.get(Usuario, cedula):
            errores.append("Ya existe un usuario registrado con esa cédula.")
        if errores:
            for error in errores:
                flash(error, "danger")
            return render_template("auth/registro.html", form=request.form), 400

        usuario = Usuario(cedula=cedula, rol=ROL_USUARIO, **datos)
        usuario.set_password(password)
        db.session.add(usuario)
        db.session.commit()
        login_user(usuario)
        flash("Registro exitoso. Ahora registra tus equipos.", "success")
        return redirect(url_for("usuario.mis_equipos"))
    return render_template("auth/registro.html", form={})


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("auth.login"))
