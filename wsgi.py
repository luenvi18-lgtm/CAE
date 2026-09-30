import getpass
import os

from app import create_app
from app.models import DIVISIONES, ROL_SUPERUSUARIO, Usuario, db
from app.validaciones import validar_cedula, validar_password

app = create_app()


def _pedir(mensaje, validar=None):
    while True:
        valor = input(mensaje).strip()
        errores = validar(valor) if validar else ([] if valor else ["Campo obligatorio."])
        if not errores:
            return valor
        print("  " + " ".join(errores))


def asegurar_superusuario():
    """Si aún no hay súper usuario, lo pide por consola en el primer arranque."""
    with app.app_context():
        if Usuario.query.filter_by(rol=ROL_SUPERUSUARIO).first():
            return
        print("\nNo hay ningún súper usuario. Vamos a crear el primero.\n")
        cedula = _pedir("Cédula: ", validar_cedula)
        nombres = _pedir("Nombres: ")
        apellidos = _pedir("Apellidos: ")
        while True:
            password = getpass.getpass("Contraseña (mínimo 6 caracteres): ")
            errores = validar_password(password)
            if not errores and password != getpass.getpass("Confirmar contraseña: "):
                errores = ["Las contraseñas no coinciden."]
            if not errores:
                break
            print("  " + " ".join(errores))
        usuario = db.session.get(Usuario, cedula) or Usuario(cedula=cedula)
        usuario.nombres, usuario.apellidos = nombres, apellidos
        usuario.division = usuario.division or DIVISIONES[0]
        usuario.rol = ROL_SUPERUSUARIO
        usuario.set_password(password)
        db.session.add(usuario)
        db.session.commit()
        print(f"\nSúper usuario {cedula} creado.\n")


if __name__ == "__main__":
    asegurar_superusuario()
    puerto = int(os.environ.get("PORT", 5000))
    print(f"CAE disponible en http://localhost:{puerto}")
    print("Otros equipos de la red pueden entrar con la IP de este computador.")
    print("Presione Ctrl+C para detener.\n")
    # Escucha en toda la red local para que los agentes accedan desde otros
    # equipos; sin modo debug, que expondría el depurador de Werkzeug.
    app.run(host="0.0.0.0", port=puerto, debug=False)
