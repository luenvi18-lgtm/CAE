import pytest

from app import create_app
from app.models import (
    ROL_AGENTE,
    ROL_SUPERUSUARIO,
    Equipo,
    Movimiento,
    Usuario,
    db,
)


@pytest.fixture
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "WTF_CSRF_ENABLED": False,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
        }
    )
    with app.app_context():
        for cedula, rol in (("2000000", ROL_AGENTE), ("3000000", ROL_SUPERUSUARIO)):
            u = Usuario(
                cedula=cedula,
                nombres="Nombre",
                apellidos=rol.title(),
                division="Cobertura",
                rol=rol,
            )
            u.set_password("clave123")
            db.session.add(u)
        db.session.commit()
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


def registrar(client, cedula="1000000", **extra):
    datos = {
        "cedula": cedula,
        "nombres": "Ana",
        "apellidos": "Pérez",
        "division": "Salud Pública",
        "password": "clave123",
        "confirmar": "clave123",
    }
    datos.update(extra)
    return client.post("/registro", data=datos)


def login(client, cedula, password="clave123"):
    return client.post("/login", data={"cedula": cedula, "password": password})


def logout(client):
    return client.post("/logout")


def nuevo_equipo(client, **extra):
    datos = {"tipo": "Laptop", "marca": "Lenovo", "modelo": "ThinkPad E14"}
    datos.update(extra)
    return client.post("/mis-equipos/nuevo", data=datos)


def test_registro_crea_usuario_con_rol_usuario(client, app):
    resp = registrar(client, rol=ROL_SUPERUSUARIO)
    assert resp.status_code == 302
    with app.app_context():
        u = db.session.get(Usuario, "1000000")
        assert u.rol == "usuario"
        assert u.division == "Salud Pública"


def test_registro_rechaza_division_invalida_y_cedula_duplicada(client):
    assert registrar(client, division="Otra").status_code == 400
    assert registrar(client, cedula="12ab").status_code == 400
    assert registrar(client).status_code == 302
    logout(client)
    assert registrar(client).status_code == 400


def test_usuario_registra_equipo_y_ve_estado(client, app):
    registrar(client)
    assert nuevo_equipo(client).status_code == 302
    assert nuevo_equipo(client, tipo="Celular").status_code == 400
    resp = client.get("/mis-equipos/")
    assert "ThinkPad E14" in resp.get_data(as_text=True)
    with app.app_context():
        equipo = Equipo.query.one()
        assert equipo.cedula_usuario == "1000000"
        assert equipo.estado == "salida"


def test_usuario_no_accede_a_vistas_de_agente_ni_admin(client):
    registrar(client)
    for url in (
        "/agente/",
        "/agente/consultar",
        "/agente/inventario/entrada",
        "/agente/historial",
        "/agente/usuarios",
        "/admin/usuarios",
        "/admin/equipos",
    ):
        assert client.get(url).status_code == 403, url
    assert client.post("/agente/equipos/1/movimiento", data={"tipo": "entrada"}).status_code == 403


def test_agente_registra_entrada_y_salida(client, app):
    registrar(client)
    nuevo_equipo(client)
    logout(client)

    login(client, "2000000")
    resp = client.get("/agente/consultar?cedula=1000000")
    assert "ThinkPad E14" in resp.get_data(as_text=True)
    with app.app_context():
        equipo_id = Equipo.query.one().id

    url = f"/agente/equipos/{equipo_id}/movimiento"
    client.post(url, data={"tipo": "entrada", "observacion": "Con cargador"})
    with app.app_context():
        assert db.session.get(Equipo, equipo_id).estado == "entrada"
    assert "ThinkPad" in client.get("/agente/inventario/entrada").get_data(as_text=True)
    assert "ThinkPad" not in client.get("/agente/inventario/salida").get_data(as_text=True)

    # Un segundo ingreso consecutivo no se registra.
    client.post(url, data={"tipo": "entrada"})
    client.post(url, data={"tipo": "salida"})
    with app.app_context():
        equipo = db.session.get(Equipo, equipo_id)
        assert equipo.estado == "salida"
        assert [m.tipo for m in equipo.movimientos] == ["salida", "entrada"]
        assert equipo.movimientos[1].cedula_agente == "2000000"
    assert "ThinkPad" in client.get("/agente/inventario/salida").get_data(as_text=True)

    historial = client.get("/agente/historial?cedula=1000000&tipo=entrada").get_data(as_text=True)
    assert "Con cargador" in historial
    assert "Ana Pérez" in client.get("/agente/usuarios").get_data(as_text=True)


def test_agente_no_puede_administrar(client):
    login(client, "2000000")
    assert client.get("/admin/usuarios").status_code == 403
    assert client.post("/admin/usuarios/1000000/eliminar").status_code == 403


def test_usuario_ve_estado_actualizado_por_agente(client, app):
    registrar(client)
    nuevo_equipo(client)
    logout(client)
    login(client, "2000000")
    with app.app_context():
        equipo_id = Equipo.query.one().id
    client.post(f"/agente/equipos/{equipo_id}/movimiento", data={"tipo": "entrada"})
    logout(client)
    login(client, "1000000")
    html = client.get("/mis-equipos/").get_data(as_text=True)
    assert "bi-box-arrow-in-right" in html


def test_superusuario_crud_usuarios(client, app):
    login(client, "3000000")
    resp = client.post(
        "/admin/usuarios/nuevo",
        data={
            "cedula": "4000000",
            "nombres": "Luis",
            "apellidos": "Gómez",
            "division": "Cobertura",
            "rol": "agente",
            "password": "clave123",
        },
    )
    assert resp.status_code == 302
    client.post(
        "/admin/usuarios/4000000/editar",
        data={
            "nombres": "Luis Carlos",
            "apellidos": "Gómez",
            "division": "Prestaciones de Servicios",
            "rol": "usuario",
            "password": "",
        },
    )
    with app.app_context():
        u = db.session.get(Usuario, "4000000")
        assert (u.nombres, u.division, u.rol) == (
            "Luis Carlos",
            "Prestaciones de Servicios",
            "usuario",
        )
        assert u.check_password("clave123")

    client.post("/admin/usuarios/4000000/eliminar")
    with app.app_context():
        assert db.session.get(Usuario, "4000000") is None


def test_superusuario_no_se_elimina_ni_se_degrada(client, app):
    login(client, "3000000")
    client.post("/admin/usuarios/3000000/eliminar")
    resp = client.post(
        "/admin/usuarios/3000000/editar",
        data={
            "nombres": "Nombre",
            "apellidos": "X",
            "division": "Cobertura",
            "rol": "usuario",
        },
    )
    assert resp.status_code == 400
    with app.app_context():
        assert db.session.get(Usuario, "3000000").rol == ROL_SUPERUSUARIO


def test_superusuario_edita_y_elimina_equipos_y_movimientos(client, app):
    registrar(client)
    nuevo_equipo(client)
    logout(client)
    login(client, "3000000")
    with app.app_context():
        equipo_id = Equipo.query.one().id

    url = f"/agente/equipos/{equipo_id}/movimiento"
    client.post(url, data={"tipo": "entrada"})
    client.post(url, data={"tipo": "salida"})

    client.post(
        f"/admin/equipos/{equipo_id}/editar",
        data={
            "cedula_usuario": "1000000",
            "tipo": "Tablet",
            "marca": "Samsung",
            "modelo": "Galaxy Tab A8",
            "serial": "SN123",
            "estado": "salida",
        },
    )
    with app.app_context():
        equipo = db.session.get(Equipo, equipo_id)
        assert (equipo.tipo, equipo.marca, equipo.serial) == ("Tablet", "Samsung", "SN123")
        ultimo = equipo.movimientos[0]
        assert ultimo.tipo == "salida"
        ultimo_id = ultimo.id

    # Al eliminar la salida, el equipo vuelve a quedar adentro.
    client.post(f"/admin/movimientos/{ultimo_id}/eliminar")
    with app.app_context():
        assert db.session.get(Equipo, equipo_id).estado == "entrada"

    client.post(f"/admin/equipos/{equipo_id}/eliminar")
    with app.app_context():
        assert db.session.get(Equipo, equipo_id) is None
        assert Movimiento.query.count() == 0


def test_eliminar_usuario_borra_sus_equipos(client, app):
    registrar(client)
    nuevo_equipo(client)
    logout(client)
    login(client, "3000000")
    client.post("/admin/usuarios/1000000/eliminar")
    with app.app_context():
        assert Equipo.query.count() == 0


def test_login_incorrecto(client):
    resp = login(client, "2000000", "mala")
    assert resp.status_code == 200
    assert "incorrecta" in resp.get_data(as_text=True)


def test_paginas_renderizan(client, app):
    registrar(client)
    nuevo_equipo(client)
    logout(client)
    login(client, "3000000")
    with app.app_context():
        equipo_id = Equipo.query.one().id
    client.post(f"/agente/equipos/{equipo_id}/movimiento", data={"tipo": "entrada"})
    with app.app_context():
        movimiento_id = Movimiento.query.one().id
    for url in (
        "/agente/",
        "/agente/consultar?cedula=1000000",
        "/agente/consultar?cedula=999999",
        "/agente/inventario/entrada?tipo=Laptop&division=Salud+P%C3%BAblica&q=Len",
        "/agente/inventario/salida",
        "/agente/historial?desde=2000-01-01&hasta=2100-01-01",
        "/agente/usuarios?q=Ana",
        "/admin/usuarios",
        "/admin/usuarios?rol=agente",
        "/admin/usuarios/nuevo",
        "/admin/usuarios/1000000/editar",
        "/admin/equipos",
        "/admin/equipos/nuevo?cedula=1000000",
        f"/admin/equipos/{equipo_id}/editar",
        f"/admin/movimientos/{movimiento_id}/editar",
        "/mis-equipos/",
        "/mis-equipos/nuevo",
    ):
        assert client.get(url).status_code == 200, url
