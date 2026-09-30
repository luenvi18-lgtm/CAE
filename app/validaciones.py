import re
from functools import wraps

from flask import abort
from flask_login import current_user, login_required

from .models import DIVISIONES, ESTADOS, ROLES, TIPOS_EQUIPO

PATRON_CEDULA = re.compile(r"^\d{5,15}$")


def validar_cedula(cedula):
    if not PATRON_CEDULA.match(cedula or ""):
        return ["La cédula debe tener entre 5 y 15 dígitos, sin puntos ni espacios."]
    return []


def validar_password(password, obligatoria=True):
    if not password and not obligatoria:
        return []
    if len(password or "") < 6:
        return ["La contraseña debe tener al menos 6 caracteres."]
    return []


def validar_persona(form, validar_rol=False):
    """Valida nombres, apellidos, división (y rol) de un formulario.
    Devuelve (datos_limpios, errores)."""
    datos = {
        "nombres": form.get("nombres", "").strip(),
        "apellidos": form.get("apellidos", "").strip(),
        "division": form.get("division", ""),
    }
    errores = []
    if not datos["nombres"] or len(datos["nombres"]) > 100:
        errores.append("Los nombres son obligatorios (máximo 100 caracteres).")
    if not datos["apellidos"] or len(datos["apellidos"]) > 100:
        errores.append("Los apellidos son obligatorios (máximo 100 caracteres).")
    if datos["division"] not in DIVISIONES:
        errores.append("Seleccione una división válida.")
    if validar_rol:
        datos["rol"] = form.get("rol", "")
        if datos["rol"] not in ROLES:
            errores.append("Seleccione un rol válido.")
    return datos, errores


def validar_equipo(form, validar_estado=False):
    """Valida tipo, marca, modelo y serial (y estado) de un equipo.
    Devuelve (datos_limpios, errores)."""
    datos = {
        "tipo": form.get("tipo", ""),
        "marca": form.get("marca", "").strip(),
        "modelo": form.get("modelo", "").strip(),
        "serial": form.get("serial", "").strip() or None,
    }
    errores = []
    if datos["tipo"] not in TIPOS_EQUIPO:
        errores.append("Seleccione el tipo de equipo: Tablet o Laptop.")
    if not datos["marca"] or len(datos["marca"]) > 60:
        errores.append("La marca es obligatoria (máximo 60 caracteres).")
    if not datos["modelo"] or len(datos["modelo"]) > 60:
        errores.append("El modelo es obligatorio (máximo 60 caracteres).")
    if datos["serial"] and len(datos["serial"]) > 60:
        errores.append("El serial admite máximo 60 caracteres.")
    if validar_estado:
        datos["estado"] = form.get("estado", "")
        if datos["estado"] not in ESTADOS:
            errores.append("Seleccione un estado válido.")
    return datos, errores


def requiere_agente(vista):
    """Solo agentes y súper usuarios."""

    @wraps(vista)
    @login_required
    def envoltura(*args, **kwargs):
        if not current_user.es_agente:
            abort(403)
        return vista(*args, **kwargs)

    return envoltura


def requiere_superusuario(vista):
    @wraps(vista)
    @login_required
    def envoltura(*args, **kwargs):
        if not current_user.es_superusuario:
            abort(403)
        return vista(*args, **kwargs)

    return envoltura
