# hotel_web/db.py
import os
import datetime
import secrets
import psycopg2
import psycopg2.extras


def get_conn():
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError(
            "Falta la variable DATABASE_URL (PostgreSQL). "
            "Verifica que el archivo .env exista y no tenga BOM."
        )
    return psycopg2.connect(url, sslmode="require")


# ==================== MIGRACIONES ====================

def migrar():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS hoteles (
            id SERIAL PRIMARY KEY,
            nombre TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            pin TEXT NOT NULL,
            telefono TEXT DEFAULT '',
            direccion TEXT DEFAULT ''
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS habitaciones (
            id SERIAL PRIMARY KEY,
            hotel_id INTEGER REFERENCES hoteles(id) ON DELETE CASCADE,
            numero TEXT NOT NULL,
            tipo TEXT NOT NULL DEFAULT 'hotel',
            capacidad INTEGER DEFAULT 1,
            precio_dia REAL NOT NULL,
            estado TEXT DEFAULT 'libre',
            notas TEXT DEFAULT ''
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS huespedes (
            id SERIAL PRIMARY KEY,
            hotel_id INTEGER REFERENCES hoteles(id) ON DELETE CASCADE,
            nombre TEXT NOT NULL,
            documento TEXT DEFAULT '',
            telefono TEXT DEFAULT '',
            correo TEXT DEFAULT ''
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alquileres (
            id SERIAL PRIMARY KEY,
            hotel_id INTEGER REFERENCES hoteles(id) ON DELETE CASCADE,
            habitacion_id INTEGER REFERENCES habitaciones(id) ON DELETE RESTRICT,
            huesped_id INTEGER REFERENCES huespedes(id) ON DELETE RESTRICT,
            fecha_entrada TIMESTAMP NOT NULL,
            fecha_salida TIMESTAMP,
            dias INTEGER DEFAULT 1,
            tarifa REAL NOT NULL,
            total REAL NOT NULL,
            estado TEXT DEFAULT 'activo',
            observaciones TEXT DEFAULT '',
            moneda TEXT DEFAULT 'USD',
            periodo TEXT DEFAULT 'dia',
            cantidad_periodos INTEGER DEFAULT 1
        );
    """)
    # Agregar columnas nuevas por si la tabla ya existía
    columnas = [
        ("alquileres", "moneda", "TEXT DEFAULT 'USD'"),
        ("alquileres", "periodo", "TEXT DEFAULT 'dia'"),
        ("alquileres", "cantidad_periodos", "INTEGER DEFAULT 1"),
        ("alquileres", "hotel_id", "INTEGER REFERENCES hoteles(id) ON DELETE CASCADE"),
        ("habitaciones", "hotel_id", "INTEGER REFERENCES hoteles(id) ON DELETE CASCADE"),
        ("huespedes", "hotel_id", "INTEGER REFERENCES hoteles(id) ON DELETE CASCADE"),
    ]
    for tabla, columna, tipo in columnas:
        cur.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name='{tabla}' AND column_name='{columna}'
                ) THEN
                    ALTER TABLE {tabla} ADD COLUMN {columna} {tipo};
                END IF;
            END $$;
        """)
    conn.commit()
    cur.close()
    conn.close()


def migrar_mensajes():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS mensajes_plantilla (
            id SERIAL PRIMARY KEY,
            nombre TEXT NOT NULL,
            contenido TEXT NOT NULL
        );
    """)
    cur.execute("SELECT COUNT(*) FROM mensajes_plantilla")
    if cur.fetchone()[0] == 0:
        plantillas = [
            ("Bienvenida (check-in)",
             "Hola {huesped} 👋\n\nBienvenido(a) a {hotel_nombre}.\n"
             "Habitación: {hab_numero} ({hab_tipo})\n"
             "Período: {cantidad} {periodo_texto}\n"
             "Total: {simbolo}{total} {moneda}\n\n"
             "¡Disfrute su estadía!"),
            ("Recordatorio de pago",
             "Hola {huesped} 👋\n\nLe recordamos su alojamiento:\n"
             "Habitación: {hab_numero}\n"
             "Total: {simbolo}{total} {moneda}\n\n"
             "Gracias por su preferencia 🙏"),
            ("Check-out (despedida)",
             "Hola {huesped} 👋\n\nEsperamos que haya tenido una excelente estadía en "
             "{hotel_nombre}.\n\n¡Gracias por visitarnos! Vuelva pronto 🙌"),
            ("Agradecimiento general",
             "Hola 👋\n\nGracias por hospedarse con nosotros. "
             "Cualquier consulta estamos a la orden. 🙌"),
        ]
        for nombre, contenido in plantillas:
            cur.execute(
                "INSERT INTO mensajes_plantilla (nombre, contenido) VALUES (%s,%s)",
                (nombre, contenido)
            )
    conn.commit()
    cur.close()
    conn.close()


# ==================== HOTELES ====================

def crear_hotel(nombre, email, telefono="", direccion=""):
    pin = "".join(secrets.choice("0123456789") for _ in range(6))
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO hoteles (nombre, email, pin, telefono, direccion)
           VALUES (%s, %s, %s, %s, %s) RETURNING id, pin""",
        (nombre, email.lower().strip(), pin, telefono, direccion)
    )
    hid, pin_generado = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return hid, pin_generado

def listar_hoteles():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    # Agregamos el campo pin a la consulta
    cur.execute("SELECT id, nombre, email, pin, telefono, direccion FROM hoteles ORDER BY nombre")
    filas = cur.fetchall()
    cur.close()
    conn.close()
    return filas

def obtener_hotel(hotel_id):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM hoteles WHERE id=%s", (hotel_id,))
    fila = cur.fetchone()
    cur.close()
    conn.close()
    return fila

def obtener_hotel_por_email_pin(email, pin):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM hoteles WHERE email=%s AND pin=%s",
        (email.lower().strip(), pin.strip())
    )
    fila = cur.fetchone()
    cur.close()
    conn.close()
    return fila


def regenerar_pin_hotel(hotel_id):
    nuevo_pin = "".join(secrets.choice("0123456789") for _ in range(6))
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("UPDATE hoteles SET pin=%s WHERE id=%s", (nuevo_pin, hotel_id))
    conn.commit()
    cur.close()
    conn.close()
    return nuevo_pin


# ==================== HABITACIONES ====================

def listar_habitaciones(hotel_id, solo_libres=False):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    sql = "SELECT * FROM habitaciones WHERE hotel_id=%s"
    params = [hotel_id]
    if solo_libres:
        sql += " AND estado='libre'"
    sql += " ORDER BY numero"
    cur.execute(sql, params)
    filas = cur.fetchall()
    cur.close()
    conn.close()
    return filas


def crear_habitacion(hotel_id, numero, tipo, capacidad, precio_dia, notas=""):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO habitaciones (hotel_id, numero, tipo, capacidad, precio_dia, notas)
           VALUES (%s, %s, %s, %s, %s, %s)""",
        (hotel_id, numero, tipo, capacidad, precio_dia, notas)
    )
    conn.commit()
    cur.close()
    conn.close()


def actualizar_habitacion(hotel_id, hab_id, numero, tipo, capacidad, precio_dia, estado, notas):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """UPDATE habitaciones SET numero=%s, tipo=%s, capacidad=%s,
           precio_dia=%s, estado=%s, notas=%s WHERE id=%s AND hotel_id=%s""",
        (numero, tipo, capacidad, precio_dia, estado, notas, hab_id, hotel_id)
    )
    conn.commit()
    cur.close()
    conn.close()


def eliminar_habitacion(hotel_id, hab_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM alquileres WHERE habitacion_id=%s AND estado='activo' AND hotel_id=%s",
        (hab_id, hotel_id)
    )
    if cur.fetchone()[0] > 0:
        cur.close()
        conn.close()
        raise ValueError("La habitación tiene un alquiler activo.")
    cur.execute("DELETE FROM habitaciones WHERE id=%s AND hotel_id=%s", (hab_id, hotel_id))
    conn.commit()
    cur.close()
    conn.close()


def obtener_habitacion(hotel_id, hab_id):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM habitaciones WHERE id=%s AND hotel_id=%s",
        (hab_id, hotel_id)
    )
    fila = cur.fetchone()
    cur.close()
    conn.close()
    return fila


# ==================== HUÉSPEDES ====================

def listar_huespedes(hotel_id):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM huespedes WHERE hotel_id=%s ORDER BY nombre",
        (hotel_id,)
    )
    filas = cur.fetchall()
    cur.close()
    conn.close()
    return filas


def crear_huesped(hotel_id, nombre, documento="", telefono="", correo=""):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO huespedes (hotel_id, nombre, documento, telefono, correo)
           VALUES (%s, %s, %s, %s, %s)""",
        (hotel_id, nombre, documento, telefono, correo)
    )
    conn.commit()
    cur.close()
    conn.close()


def obtener_huesped(hotel_id, hues_id):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        "SELECT * FROM huespedes WHERE id=%s AND hotel_id=%s",
        (hues_id, hotel_id)
    )
    fila = cur.fetchone()
    cur.close()
    conn.close()
    return fila


# ==================== ALQUILERES ====================

def registrar_alquiler(hotel_id, hab_id, hues_id, cantidad, tarifa,
                       moneda="USD", periodo="dia", obs=""):
    total = cantidad * tarifa
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT estado FROM habitaciones WHERE id=%s AND hotel_id=%s",
        (hab_id, hotel_id)
    )
    fila = cur.fetchone()
    if not fila or fila[0] != "libre":
        cur.close()
        conn.close()
        raise ValueError("La habitación no está libre.")
    cur.execute(
        """INSERT INTO alquileres
           (hotel_id, habitacion_id, huesped_id, fecha_entrada, dias, tarifa, total,
            moneda, periodo, cantidad_periodos, observaciones)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id""",
        (hotel_id, hab_id, hues_id, datetime.datetime.now(), cantidad, tarifa, total,
         moneda, periodo, cantidad, obs)
    )
    aid = cur.fetchone()[0]
    cur.execute("UPDATE habitaciones SET estado='ocupada' WHERE id=%s", (hab_id,))
    conn.commit()
    cur.close()
    conn.close()
    return aid, total


def obtener_alquiler(aid, hotel_id=None):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    sql = """SELECT a.*, h.numero AS hab_numero, h.tipo AS hab_tipo,
                    g.nombre AS huesped, g.telefono, g.documento,
                    ho.nombre AS hotel_nombre, ho.email AS hotel_email
             FROM alquileres a
             JOIN habitaciones h ON a.habitacion_id = h.id
             JOIN huespedes g ON a.huesped_id = g.id
             JOIN hoteles ho ON a.hotel_id = ho.id
             WHERE a.id=%s"""
    params = [aid]
    if hotel_id is not None:
        sql += " AND a.hotel_id=%s"
        params.append(hotel_id)
    cur.execute(sql, params)
    fila = cur.fetchone()
    cur.close()
    conn.close()
    return fila


def cerrar_alquiler(aid, hotel_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "SELECT habitacion_id FROM alquileres WHERE id=%s AND hotel_id=%s",
        (aid, hotel_id)
    )
    fila = cur.fetchone()
    if not fila:
        cur.close()
        conn.close()
        raise ValueError("Alquiler no encontrado.")
    hab_id = fila[0]
    cur.execute(
        "UPDATE alquileres SET fecha_salida=%s, estado='cerrado' WHERE id=%s",
        (datetime.datetime.now(), aid)
    )
    cur.execute("UPDATE habitaciones SET estado='libre' WHERE id=%s", (hab_id,))
    conn.commit()
    cur.close()
    conn.close()


def listar_alquileres_activos(hotel_id):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(
        """SELECT a.id, h.numero AS hab_numero, g.nombre AS huesped,
                  a.fecha_entrada, a.dias, a.tarifa, a.total,
                  a.moneda, a.periodo, a.cantidad_periodos, a.observaciones
           FROM alquileres a
           JOIN habitaciones h ON a.habitacion_id = h.id
           JOIN huespedes g ON a.huesped_id = g.id
           WHERE a.estado='activo' AND a.hotel_id=%s
           ORDER BY a.fecha_entrada DESC""",
        (hotel_id,)
    )
    filas = cur.fetchall()
    cur.close()
    conn.close()
    return filas


# ==================== MENSAJES ====================

def listar_plantillas():
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT * FROM mensajes_plantilla ORDER BY id")
    filas = cur.fetchall()
    cur.close()
    conn.close()
    return filas


def guardar_plantilla(nombre, contenido):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO mensajes_plantilla (nombre, contenido) VALUES (%s,%s)",
        (nombre, contenido)
    )
    conn.commit()
    cur.close()
    conn.close()


def eliminar_plantilla(pid):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("DELETE FROM mensajes_plantilla WHERE id=%s", (pid,))
    conn.commit()
    cur.close()
    conn.close()