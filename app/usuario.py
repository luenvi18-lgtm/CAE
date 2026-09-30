from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .models import Equipo, db
from .validaciones import validar_equipo

bp = Blueprint("usuario", __name__, url_prefix="/mis-equipos")


@bp.route("/")
@login_required
def mis_equipos():
    return render_template("usuario/mis_equipos.html", equipos=current_user.equipos)


@bp.route("/nuevo", methods=["GET", "POST"])
@login_required
def nuevo_equipo():
    if request.method == "POST":
        datos, errores = validar_equipo(request.form)
        if errores:
            for error in errores:
                flash(error, "danger")
            return render_template("usuario/nuevo_equipo.html", form=request.form), 400
        db.session.add(Equipo(cedula_usuario=current_user.cedula, **datos))
        db.session.commit()
        flash("Equipo registrado correctamente.", "success")
        return redirect(url_for("usuario.mis_equipos"))
    return render_template("usuario/nuevo_equipo.html", form={})
