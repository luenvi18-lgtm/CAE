# CAE · Control de Acceso de Equipos

Aplicación web para registrar el ingreso y la salida de equipos (tablets y
laptops) de la **Secretaría de Salud del Departamento del Caquetá**.

Construida con Python + Flask, SQLAlchemy (SQLite por defecto; también
MySQL/PostgreSQL) y Bootstrap 5 incluido localmente, así que funciona en una
intranet sin acceso a internet.

## Roles

| Rol | Qué puede hacer |
| --- | --- |
| **Usuario** | Se registra con cédula, nombres, apellidos, división y contraseña. Registra sus equipos (tipo, marca, modelo y serial opcional) y ve si cada uno está en **Entrada** o **Salida**. |
| **Agente** | Consulta a un usuario por cédula y registra la entrada o la salida de sus equipos. Ve los equipos que están adentro y los que se retiraron, el historial de ingresos y salidas (con filtros) y los equipos registrados por cada usuario. |
| **Súper usuario** | Todo lo del agente, y además crea, modifica y elimina usuarios (incluido su rol y contraseña), equipos y movimientos del historial. |

El registro público siempre crea cuentas con rol de **usuario**. Los agentes
y los súper usuarios los crea un súper usuario desde *Administración →
Gestionar usuarios*.

## Base de datos

- **usuarios**: `cedula` (clave primaria), `nombres`, `apellidos`, `division`
  (Salud Pública, Cobertura o Prestaciones de Servicios), `rol`,
  `password_hash`, `fecha_registro`.
- **equipos**: `id`, `cedula_usuario` → usuarios, `tipo` (Tablet o Laptop),
  `marca`, `modelo`, `serial`, `estado` (`entrada` o `salida`),
  `fecha_registro`.
- **movimientos**: `id`, `equipo_id` → equipos, `tipo` (`entrada` o
  `salida`), `fecha`, `cedula_agente` → usuarios, `observacion`.

Reglas:

- Un equipo recién registrado queda en **salida** hasta que un agente
  registra su entrada.
- Solo se alterna entre los dos estados: no se registran dos entradas (ni dos
  salidas) seguidas.
- *Retirados* lista los equipos cuyo último movimiento fue una salida.
- Al eliminar un usuario se eliminan sus equipos y su historial. Al editar o
  eliminar un movimiento, el estado del equipo se recalcula a partir de su
  movimiento más reciente.
- Las horas se guardan en hora de Colombia (UTC-5).

## Inicio rápido

Requisito: [Python 3.10 o superior](https://www.python.org/downloads/). En
Windows, marque la casilla **Add Python to PATH** al instalarlo.

1. Descargue el proyecto (botón **Code → Download ZIP** en GitHub) y
   descomprímalo.
2. Ejecute el script de inicio:
   - **Windows:** doble clic en `iniciar.bat`.
   - **Linux / macOS:** `./iniciar.sh` en una terminal.
3. La primera vez instala las dependencias y le pide los datos del primer
   **súper usuario** (cédula, nombres, apellidos y contraseña).
4. Abra http://localhost:5000 en el navegador.

Los agentes de la portería pueden entrar desde otros computadores de la
misma red con `http://IP-DE-ESTE-COMPUTADOR:5000`. Si no carga, permita el
puerto 5000 en el firewall de Windows. Para detener el servidor, presione
`Ctrl+C` en la ventana negra.

## Instalación manual

```bash
python3 -m venv .venv
source .venv/bin/activate          # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
python wsgi.py                     # http://localhost:5000
```

Para crear o ascender un súper usuario en cualquier momento:

```bash
flask --app wsgi crear-superusuario
```

O con variables de entorno (se crea al iniciar si no existe):
`SUPERUSUARIO_CEDULA` y `SUPERUSUARIO_PASSWORD`.

Las tablas se crean automáticamente. Por defecto se usa SQLite en
`instance/cae.db` (haga copias de seguridad de ese archivo). La clave
secreta de las sesiones se genera sola en `instance/secret_key`; también
puede definirla con la variable `SECRET_KEY`. Para otro motor, defina `DATABASE_URL` e instale su
controlador, por ejemplo:

```bash
pip install pymysql
export DATABASE_URL='mysql+pymysql://usuario:clave@localhost/cae'
```

En producción use un servidor WSGI, por ejemplo
`pip install gunicorn && gunicorn -w 3 -b 0.0.0.0:8000 wsgi:app`.

## Pruebas

```bash
python -m pytest
```
