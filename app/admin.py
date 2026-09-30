from datetime import datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user

from .models import ESTADO_SALIDA, ESTADOS, Equipo, Movimiento, Usuario, db
from .validaciones import (
    requiere_superusuario,
    validar_cedula,
    validar_equipo,
    validar_password,
    validar_persona,
)

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _mostrar_errores(errores):
    for error in errores:
        flash(error, "danger")


def _recalcular_estado(equipo):
    """El estado del equipo es el tipo de su movimiento más reciente."""
    db.session.flush()
    ultimo = (
        Movimiento.query.filter_by(equipo_id=equipo.id)
        .order_by(Movimiento.fecha.desc(), Movimiento.id.desc())
        .first()
    )
    equipo.estado = ultimo.tipo if ultimo else ESTADO_SALIDA


# ----------------------------------------------------------------- Usuarios


@bp.route("/usuarios")
@requiere_superusuario
def usuarios():
    rol = request.args.get("rol", "")
    consulta = Usuario.query
    if rol:
        consulta = consulta.filter_by(rol=rol)
    lista = consulta.order_by(Usuario.apellidos, Usuario.nombres).all()
    return render_template("admin/usuarios.html", usuarios=lista, rol=rol)


@bp.route("/usuarios/nuevo", methods=["GET", "POST"])
@requiere_superusuario
def nuevo_usuario():
    if request.method == "POST":
        cedula = request.form.get("cedula", "").strip()
        password = request.form.get("password", "")
        datos, errores = validar_persona(request.form, validar_rol=True)
        errores = validar_cedula(cedula) + errores + validar_password(password)
        if not errores and db.session.get(Usuario, cedula):
            errores.append("Ya existe un usuario registrado con esa cédula.")
        if errores:
            _mostrar_errores(errores)
            return (
                render_template(
                    "admin/usuario_form.html", form=request.form, usuario=None
                ),
                400,
            )
        usuario = Usuario(cedula=cedula, **datos)
        usuario.set_password(password)
        db.session.add(usuario)
        db.session.commit()
        flash(f"Usuario {usuario.nombre_completo} creado.", "success")
        return redirect(url_for("admin.usuarios"))
    return render_template("admin/usuario_form.html", form={}, usuario=None)


@bp.route("/usuarios/<cedula>/editar", methods=["GET", "POST"])
@requiere_superusuario
def editar_usuario(cedula):
    usuario = db.session.get(Usuario, cedula) or abort(404)
    if request.method == "POST":
        password = request.form.get("password", "")
        datos, errores = validar_persona(request.form, validar_rol=True)
        errores += validar_password(password, obligatoria=False)
        if usuario.cedula == current_user.cedula and datos.get("rol") != usuario.rol:
            errores.append("No puede cambiar su propio rol.")
        if errores:
            _mostrar_errores(errores)
            return (
                render_template(
                    "admin/usuario_form.html", form=request.form, usuario=usuario
                ),
                400,
            )
        for campo, valor in datos.items():
            setattr(usuario, campo, valor)
        if password:
            usuario.set_password(password)
        db.session.commit()
        flash("Usuario actualizado.", "success")
        return redirect(url_for("admin.usuarios"))
    form = {
        "nombres": usuario.nombres,
        "apellidos": usuario.apellidos,
        "division": usuario.division,
        "rol": usuario.rol,
    }
    return render_template("admin/usuario_form.html", form=form, usuario=usuario)


@bp.route("/usuarios/<cedula>/eliminar", methods=["POST"])
@requiere_superusuario
def eliminar_usuario(cedula):
    usuario = db.session.get(Usuario, cedula) or abort(404)
    if usuario.cedula == current_user.cedula:
        flash("No puede eliminar su propia cuenta.", "danger")
    else:
        db.session.delete(usuario)
        db.session.commit()
        flash(
            f"Usuario {usuario.nombre_completo} eliminado junto con sus equipos.",
            "success",
        )
    return redirect(url_for("admin.usuarios"))


# ------------------------------------------------------------------ Equipos


@bp.route("/equipos")
@requiere_superusuario
def equipos():
    lista = Equipo.query.join(Usuario).order_by(
        Usuario.apellidos, Usuario.nombres, Equipo.id
    )
    return render_template("admin/equipos.html", equipos=lista.all())


def _validar_propietario(form, errores):
    cedula = form.get("cedula_usuario", "").strip()
    if not db.session.get(Usuario, cedula):
        errores.append("La cédula del propietario no corresponde a ningún usuario.")
    return cedula


@bp.route("/equipos/nuevo", methods=["GET", "POST"])
@requiere_superusuario
def nuevo_equipo():
    if request.method == "POST":
        datos, errores = validar_equipo(request.form)
        cedula = _validar_propietario(request.form, errores)
        if errores:
            _mostrar_errores(errores)
            return (
                render_template(
                    "admin/equipo_form.html", form=request.form, equipo=None
                ),
                400,
            )
        db.session.add(Equipo(cedula_usuario=cedula, **datos))
        db.session.commit()
        flash("Equipo registrado.", "success")
        return redirect(url_for("agente.consultar", cedula=cedula))
    form = {"cedula_usuario": request.args.get("cedula", "")}
    return render_template("admin/equipo_form.html", form=form, equipo=None)


@bp.route("/equipos/<int:equipo_id>/editar", methods=["GET", "POST"])
@requiere_superusuario
def editar_equipo(equipo_id):
    equipo = db.session.get(Equipo, equipo_id) or abort(404)
    if request.method == "POST":
        datos, errores = validar_equipo(request.form, validar_estado=True)
        cedula = _validar_propietario(request.form, errores)
        if errores:
            _mostrar_errores(errores)
            return (
                render_template(
                    "admin/equipo_form.html", form=request.form, equipo=equipo
                ),
                400,
            )
        for campo, valor in datos.items():
            setattr(equipo, campo, valor)
        equipo.cedula_usuario = cedula
        db.session.commit()
        flash("Equipo actualizado.", "success")
        return redirect(url_for("agente.consultar", cedula=cedula))
    form = {
        "cedula_usuario": equipo.cedula_usuario,
        "tipo": equipo.tipo,
        "marca": equipo.marca,
        "modelo": equipo.modelo,
        "serial": equipo.serial or "",
        "estado": equipo.estado,
    }
    return render_template("admin/equipo_form.html", form=form, equipo=equipo)


@bp.route("/equipos/<int:equipo_id>/eliminar", methods=["POST"])
@requiere_superusuario
def eliminar_equipo(equipo_id):
    equipo = db.session.get(Equipo, equipo_id) or abort(404)
    cedula = equipo.cedula_usuario
    db.session.delete(equipo)
    db.session.commit()
    flash("Equipo eliminado junto con su historial.", "success")
    if request.form.get("volver") == "equipos":
        return redirect(url_for("admin.equipos"))
    return redirect(url_for("agente.consultar", cedula=cedula))


# -------------------------------------------------------------- Movimientos


@bp.route("/movimientos/<int:movimiento_id>/editar", methods=["GET", "POST"])
@requiere_superusuario
def editar_movimiento(movimiento_id):
    movimiento = db.session.get(Movimiento, movimiento_id) or abort(404)
    if request.method == "POST":
        errores = []
        tipo = request.form.get("tipo", "")
        if tipo not in ESTADOS:
            errores.append("Seleccione un tipo de movimiento válido.")
        try:
            fecha = datetime.strptime(request.form.get("fecha", ""), "%Y-%m-%dT%H:%M")
        except ValueError:
            errores.append("La fecha no es válida.")
        if errores:
            _mostrar_errores(errores)
            return (
                render_template(
                    "admin/movimiento_form.html",
                    movimiento=movimiento,
                    form=request.form,
                ),
                400,
            )
        movimiento.tipo = tipo
        movimiento.fecha = fecha
        movimiento.observacion = request.form.get("observacion", "").strip()[:255] or None
        _recalcular_estado(movimiento.equipo)
        db.session.commit()
        flash("Movimiento actualizado.", "success")
        return redirect(url_for("agente.historial"))
    form = {
        "tipo": movimiento.tipo,
        "fecha": movimiento.fecha.strftime("%Y-%m-%dT%H:%M"),
        "observacion": movimiento.observacion or "",
    }
    return render_template(
        "admin/movimiento_form.html", movimiento=movimiento, form=form
    )


@bp.route("/movimientos/<int:movimiento_id>/eliminar", methods=["POST"])
@requiere_superusuario
def eliminar_movimiento(movimiento_id):
    movimiento = db.session.get(Movimiento, movimiento_id) or abort(404)
    equipo = movimiento.equipo
    db.session.delete(movimiento)
    _recalcular_estado(equipo)
    db.session.commit()
    flash("Movimiento eliminado.", "success")
    return redirect(url_for("agente.historial"))
