from datetime import datetime, timedelta, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

# Colombia no usa horario de verano: UTC-5 fijo.
ZONA_COLOMBIA = timezone(timedelta(hours=-5))

ROL_USUARIO = "usuario"
ROL_AGENTE = "agente"
ROL_SUPERUSUARIO = "superusuario"
ROLES = {
    ROL_USUARIO: "Usuario",
    ROL_AGENTE: "Agente",
    ROL_SUPERUSUARIO: "Súper usuario",
}

DIVISIONES = ["Salud Pública", "Cobertura", "Prestaciones de Servicios"]
TIPOS_EQUIPO = ["Tablet", "Laptop"]

ESTADO_ENTRADA = "entrada"
ESTADO_SALIDA = "salida"
ESTADOS = {ESTADO_ENTRADA: "Entrada", ESTADO_SALIDA: "Salida"}


def ahora():
    """Fecha y hora actual de Colombia (sin tzinfo, para guardarla en la BD)."""
    return datetime.now(ZONA_COLOMBIA).replace(tzinfo=None)


class Usuario(UserMixin, db.Model):
    __tablename__ = "usuarios"

    cedula = db.Column(db.String(15), primary_key=True)
    nombres = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(100), nullable=False)
    division = db.Column(db.String(50), nullable=False)
    rol = db.Column(db.String(20), nullable=False, default=ROL_USUARIO)
    password_hash = db.Column(db.String(255), nullable=False)
    fecha_registro = db.Column(db.DateTime, nullable=False, default=ahora)

    equipos = db.relationship(
        "Equipo",
        back_populates="usuario",
        cascade="all, delete-orphan",
        order_by="Equipo.id",
    )

    def get_id(self):
        return self.cedula

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def nombre_completo(self):
        return f"{self.nombres} {self.apellidos}"

    @property
    def rol_nombre(self):
        return ROLES.get(self.rol, self.rol)

    @property
    def es_agente(self):
        return self.rol in (ROL_AGENTE, ROL_SUPERUSUARIO)

    @property
    def es_superusuario(self):
        return self.rol == ROL_SUPERUSUARIO


class Equipo(db.Model):
    __tablename__ = "equipos"

    id = db.Column(db.Integer, primary_key=True)
    cedula_usuario = db.Column(
        db.String(15),
        db.ForeignKey("usuarios.cedula", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipo = db.Column(db.String(20), nullable=False)
    marca = db.Column(db.String(60), nullable=False)
    modelo = db.Column(db.String(60), nullable=False)
    serial = db.Column(db.String(60))
    # Un equipo recién registrado está fuera de la Secretaría hasta que un
    # agente registre su entrada.
    estado = db.Column(db.String(10), nullable=False, default=ESTADO_SALIDA)
    fecha_registro = db.Column(db.DateTime, nullable=False, default=ahora)

    usuario = db.relationship("Usuario", back_populates="equipos")
    movimientos = db.relationship(
        "Movimiento",
        back_populates="equipo",
        cascade="all, delete-orphan",
        order_by="Movimiento.fecha.desc()",
    )

    @property
    def estado_nombre(self):
        return ESTADOS.get(self.estado, self.estado)

    @property
    def descripcion(self):
        return f"{self.tipo} {self.marca} {self.modelo}"

    @property
    def ultimo_movimiento(self):
        return self.movimientos[0] if self.movimientos else None


class Movimiento(db.Model):
    __tablename__ = "movimientos"

    id = db.Column(db.Integer, primary_key=True)
    equipo_id = db.Column(
        db.Integer,
        db.ForeignKey("equipos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tipo = db.Column(db.String(10), nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=ahora, index=True)
    cedula_agente = db.Column(
        db.String(15), db.ForeignKey("usuarios.cedula", ondelete="SET NULL")
    )
    observacion = db.Column(db.String(255))

    equipo = db.relationship("Equipo", back_populates="movimientos")
    agente = db.relationship("Usuario", foreign_keys=[cedula_agente])

    @property
    def tipo_nombre(self):
        return ESTADOS.get(self.tipo, self.tipo)
