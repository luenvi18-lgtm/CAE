from datetime import datetime, timedelta

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user
from sqlalchemy import func, or_

from .models import (
    ESTADO_ENTRADA,
    ESTADO_SALIDA,
    ESTADOS,
    Equipo,
    Movimiento,
    Usuario,
    ahora,
    db,
)
from .validaciones import requiere_agente

bp = Blueprint("agente", __name__, url_prefix="/agente")


@bp.route("/")
@requiere_agente
def panel():
    inicio_dia = ahora().replace(hour=0, minute=0, second=0, microsecond=0)
    resumen = {
        "adentro": Equipo.query.filter_by(estado=ESTADO_ENTRADA).count(),
        "retirados": _consulta_retirados().count(),
        "equipos": Equipo.query.count(),
        "usuarios": Usuario.query.count(),
        "movimientos_hoy": Movimiento.query.filter(
            Movimiento.fecha >= inicio_dia
        ).count(),
    }
    recientes = Movimiento.query.order_by(Movimiento.fecha.desc()).limit(10).all()
    return render_template("agente/panel.html", resumen=resumen, recientes=recientes)


@bp.route("/consultar")
@requiere_agente
def consultar():
    """Consulta un usuario por cédula para registrar entradas y salidas."""
    cedula = request.args.get("cedula", "").strip()
    usuario = db.session.get(Usuario, cedula) if cedula else None
    if cedula and usuario is None:
        flash(f"No existe un usuario con la cédula {cedula}.", "warning")
    return render_template("agente/consultar.html", cedula=cedula, usuario=usuario)


@bp.route("/equipos/<int:equipo_id>/movimiento", methods=["POST"])
@requiere_agente
def registrar_movimiento(equipo_id):
    equipo = db.session.get(Equipo, equipo_id) or abort(404)
    tipo = request.form.get("tipo", "")
    if tipo not in ESTADOS:
        flash("Tipo de movimiento no válido.", "danger")
    elif tipo == equipo.estado:
        flash(
            f"El equipo ya tiene estado de {equipo.estado_nombre.lower()}; "
            "no se registró el movimiento.",
            "warning",
        )
    else:
        observacion = request.form.get("observacion", "").strip()[:255] or None
        db.session.add(
            Movimiento(
                equipo=equipo,
                tipo=tipo,
                cedula_agente=current_user.cedula,
                observacion=observacion,
            )
        )
        equipo.estado = tipo
        db.session.commit()
        flash(
            f"{ESTADOS[tipo]} registrada: {equipo.descripcion} de "
            f"{equipo.usuario.nombre_completo}.",
            "success",
        )
    return redirect(url_for("agente.consultar", cedula=equipo.cedula_usuario))


def _consulta_retirados():
    """Equipos cuyo último movimiento fue una salida (ya estuvieron adentro
    y fueron retirados de la Secretaría)."""
    return Equipo.query.filter(
        Equipo.estado == ESTADO_SALIDA, Equipo.movimientos.any()
    )


@bp.route("/inventario/<estado>")
@requiere_agente
def inventario(estado):
    if estado == ESTADO_ENTRADA:
        consulta = Equipo.query.filter_by(estado=ESTADO_ENTRADA)
        titulo = "Equipos dentro de la Secretaría"
    elif estado == ESTADO_SALIDA:
        consulta = _consulta_retirados()
        titulo = "Equipos retirados de la Secretaría"
    else:
        abort(404)

    tipo = request.args.get("tipo", "")
    division = request.args.get("division", "")
    texto = request.args.get("q", "").strip()
    consulta = consulta.join(Usuario)
    if tipo:
        consulta = consulta.filter(Equipo.tipo == tipo)
    if division:
        consulta = consulta.filter(Usuario.division == division)
    if texto:
        patron = f"%{texto}%"
        consulta = consulta.filter(
            or_(
                Usuario.cedula.like(patron),
                Usuario.nombres.like(patron),
                Usuario.apellidos.like(patron),
                Equipo.marca.like(patron),
                Equipo.modelo.like(patron),
                Equipo.serial.like(patron),
            )
        )
    equipos = consulta.order_by(Usuario.apellidos, Usuario.nombres, Equipo.id).all()
    return render_template(
        "agente/inventario.html",
        equipos=equipos,
        estado=estado,
        titulo=titulo,
        filtros={"tipo": tipo, "division": division, "q": texto},
    )


def _fecha(valor):
    try:
        return datetime.strptime(valor, "%Y-%m-%d")
    except (TypeError, ValueError):
        return None


@bp.route("/historial")
@requiere_agente
def historial():
    filtros = {
        "cedula": request.args.get("cedula", "").strip(),
        "tipo": request.args.get("tipo", ""),
        "desde": request.args.get("desde", ""),
        "hasta": request.args.get("hasta", ""),
        "equipo": request.args.get("equipo", type=int),
    }
    consulta = Movimiento.query.join(Equipo)
    if filtros["cedula"]:
        consulta = consulta.filter(Equipo.cedula_usuario == filtros["cedula"])
    if filtros["equipo"]:
        consulta = consulta.filter(Movimiento.equipo_id == filtros["equipo"])
    if filtros["tipo"] in ESTADOS:
        consulta = consulta.filter(Movimiento.tipo == filtros["tipo"])
    desde, hasta = _fecha(filtros["desde"]), _fecha(filtros["hasta"])
    if desde:
        consulta = consulta.filter(Movimiento.fecha >= desde)
    if hasta:
        consulta = consulta.filter(Movimiento.fecha < hasta + timedelta(days=1))

    pagina = consulta.order_by(Movimiento.fecha.desc(), Movimiento.id.desc()).paginate(
        page=request.args.get("pagina", 1, type=int),
        per_page=current_app.config["POR_PAGINA"],
        error_out=False,
    )
    return render_template("agente/historial.html", pagina=pagina, filtros=filtros)


@bp.route("/usuarios")
@requiere_agente
def usuarios():
    """Usuarios con la cantidad de equipos registrados por cada uno."""
    texto = request.args.get("q", "").strip()
    division = request.args.get("division", "")
    total_equipos = func.count(Equipo.id).label("total_equipos")
    adentro = func.count(Equipo.id).filter(Equipo.estado == ESTADO_ENTRADA)
    consulta = (
        db.session.query(Usuario, total_equipos, adentro.label("adentro"))
        .outerjoin(Equipo)
        .group_by(Usuario.cedula)
    )
    if texto:
        patron = f"%{texto}%"
        consulta = consulta.filter(
            or_(
                Usuario.cedula.like(patron),
                Usuario.nombres.like(patron),
                Usuario.apellidos.like(patron),
            )
        )
    if division:
        consulta = consulta.filter(Usuario.division == division)
    filas = consulta.order_by(Usuario.apellidos, Usuario.nombres).all()
    return render_template(
        "agente/usuarios.html",
        filas=filas,
        filtros={"q": texto, "division": division},
    )
