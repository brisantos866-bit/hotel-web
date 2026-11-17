# hotel_web/app.py
import os
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session
from db import (
    migrar, migrar_mensajes,
    crear_hotel, listar_hoteles, obtener_hotel, obtener_hotel_por_email_pin, regenerar_pin_hotel,
    listar_habitaciones, crear_habitacion, actualizar_habitacion, eliminar_habitacion, obtener_habitacion,
    listar_huespedes, crear_huesped, obtener_huesped,
    registrar_alquiler, obtener_alquiler, cerrar_alquiler, listar_alquileres_activos,
    listar_plantillas, guardar_plantilla, eliminar_plantilla,
)
from tickets import (
    generar_ticket_hotel, generar_enlace_whatsapp, generar_enlace_sms,
    generar_mensaje_celular,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "cambia-esta-clave")

with app.app_context():
    try:
        migrar()
        migrar_mensajes()
    except Exception as e:
        print("⚠️ No se pudo migrar la base de datos:", e)


# ==================== LOGIN ====================

def hotel_requerido(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("hotel_id"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pin = request.form.get("pin", "").strip()
        hotel = obtener_hotel_por_email_pin(email, pin)
        if hotel:
            session["hotel_id"] = hotel["id"]
            session["hotel_nombre"] = hotel["nombre"]
            return redirect(url_for("alquileres"))
        flash("Correo o PIN incorrecto", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ==================== INICIO ====================

@app.route("/")
@hotel_requerido
def index():
    return redirect(url_for("alquileres"))


# ==================== HABITACIONES ====================

@app.route("/habitaciones", methods=["GET", "POST"])
@hotel_requerido
def habitaciones():
    hid = session["hotel_id"]
    if request.method == "POST":
        try:
            crear_habitacion(
                hid,
                request.form["numero"].strip(),
                request.form["tipo"].strip(),
                int(request.form["capacidad"]),
                float(request.form["precio_dia"]),
                request.form.get("notas", "").strip(),
            )
            flash("Habitación creada.", "ok")
        except Exception as e:
            flash(f"Error: {e}", "error")
        return redirect(url_for("habitaciones"))
    return render_template("habitaciones.html",
                           habitaciones=listar_habitaciones(hid),
                           hotel_nombre=session.get("hotel_nombre", ""))


@app.route("/habitaciones/<int:hid>/editar", methods=["GET", "POST"])
@hotel_requerido
def editar_habitacion(hid):
    hotel_id = session["hotel_id"]
    hab = obtener_habitacion(hotel_id, hid)
    if not hab:
        flash("Habitación no encontrada.", "error")
        return redirect(url_for("habitaciones"))
    if request.method == "POST":
        try:
            actualizar_habitacion(
                hotel_id, hid,
                request.form["numero"].strip(),
                request.form["tipo"].strip(),
                int(request.form["capacidad"]),
                float(request.form["precio_dia"]),
                request.form["estado"].strip(),
                request.form.get("notas", "").strip(),
            )
            flash("Habitación actualizada.", "ok")
            return redirect(url_for("habitaciones"))
        except Exception as e:
            flash(f"Error: {e}", "error")
    return render_template("editar_habitacion.html", hab=hab)


@app.route("/habitaciones/<int:hid>/eliminar", methods=["POST"])
@hotel_requerido
def borrar_habitacion(hid):
    try:
        eliminar_habitacion(session["hotel_id"], hid)
        flash("Habitación eliminada.", "ok")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("habitaciones"))


# ==================== HUÉSPEDES ====================

@app.route("/huespedes", methods=["GET", "POST"])
@hotel_requerido
def huespedes():
    hid = session["hotel_id"]
    if request.method == "POST":
        try:
            crear_huesped(
                hid,
                request.form["nombre"].strip(),
                request.form.get("documento", "").strip(),
                request.form.get("telefono", "").strip(),
                request.form.get("correo", "").strip(),
            )
            flash("Huésped creado.", "ok")
        except Exception as e:
            flash(f"Error: {e}", "error")
        return redirect(url_for("huespedes"))
    return render_template("huespedes.html",
                           huespedes=listar_huespedes(hid),
                           hotel_nombre=session.get("hotel_nombre", ""))


# ==================== ALQUILERES ====================

@app.route("/alquileres", methods=["GET", "POST"])
@hotel_requerido
def alquileres():
    hid = session["hotel_id"]
    if request.method == "POST":
        try:
            aid, total = registrar_alquiler(
                hid,
                int(request.form["habitacion_id"]),
                int(request.form["huesped_id"]),
                int(request.form["cantidad_periodos"]),
                float(request.form["tarifa"]),
                request.form.get("moneda", "USD"),
                request.form.get("periodo", "dia"),
                request.form.get("observaciones", ""),
            )
            flash(f"Alquiler #{aid} registrado. Total: {total:.2f}", "ok")
            return redirect(url_for("ver_ticket", aid=aid))
        except Exception as e:
            flash(f"Error: {e}", "error")
        return redirect(url_for("alquileres"))
    return render_template("alquileres.html",
                           alquileres=listar_alquileres_activos(hid),
                           habitaciones=listar_habitaciones(hid, solo_libres=True),
                           huespedes=listar_huespedes(hid),
                           hotel_nombre=session.get("hotel_nombre", ""))


@app.route("/alquileres/<int:aid>/cerrar", methods=["POST"])
@hotel_requerido
def cerrar_alquiler_ruta(aid):
    try:
        cerrar_alquiler(aid, session["hotel_id"])
        flash("Alquiler cerrado.", "ok")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("alquileres"))


# ==================== TICKET ====================

@app.route("/ticket/<int:aid>")
@hotel_requerido
def ver_ticket(aid):
    hid = session["hotel_id"]
    datos = obtener_alquiler(aid, hid)
    if not datos:
        flash("Ticket no encontrado.", "error")
        return redirect(url_for("alquileres"))
    texto = generar_ticket_hotel(datos)
    tel = datos.get("telefono") or ""
    wa_link = generar_enlace_whatsapp(tel, texto)
    sms_link = generar_enlace_sms(tel, texto)
    return render_template("ticket.html",
                           texto=texto, aid=aid,
                           wa_link=wa_link, sms_link=sms_link)


# ==================== MENSAJES ====================

@app.route("/mensajes", methods=["GET", "POST"])
@hotel_requerido
def mensajes():
    hid = session["hotel_id"]
    if request.method == "POST":
        try:
            guardar_plantilla(
                request.form["nombre"].strip(),
                request.form["contenido"].strip(),
            )
            flash("Plantilla guardada.", "ok")
        except Exception as e:
            flash(f"Error: {e}", "error")
        return redirect(url_for("mensajes"))
    return render_template("mensajes.html",
                           plantillas=listar_plantillas(),
                           alquileres=listar_alquileres_activos(hid),
                           hotel_nombre=session.get("hotel_nombre", ""))


@app.route("/mensajes/<int:pid>/eliminar", methods=["POST"])
@hotel_requerido
def borrar_plantilla(pid):
    try:
        eliminar_plantilla(pid)
        flash("Plantilla eliminada.", "ok")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("mensajes"))


@app.route("/api/mensaje/<int:aid>")
@hotel_requerido
def api_mensaje(aid):
    hid = session["hotel_id"]
    datos = obtener_alquiler(aid, hid)
    if not datos:
        return {"ok": False, "error": "Alquiler no encontrado"}, 404
    plantilla_id = request.args.get("plantilla")
    plantilla = None
    if plantilla_id:
        for p in listar_plantillas():
            if str(p["id"]) == str(plantilla_id):
                plantilla = p["contenido"]
                break
    texto = generar_mensaje_celular(datos, plantilla, session.get("hotel_nombre", ""))
    tel = "".join(c for c in (datos.get("telefono") or "") if c.isdigit())
    return {
        "ok": True,
        "texto": texto,
        "telefono": tel,
        "huesped": datos["huesped"],
        "wa_link": f"https://wa.me/{tel}?text={urllib.parse.quote(texto)}" if tel else None,
        "sms_link": generar_enlace_sms(tel, texto) if tel else None,
    }


# ==================== ADMIN DE HOTELES ====================

@app.route("/admin/hoteles", methods=["GET", "POST"])
def admin_hoteles():
    if request.method == "POST":
        try:
            hid, pin = crear_hotel(
                request.form["nombre"].strip(),
                request.form["email"].strip(),
                request.form.get("telefono", "").strip(),
                request.form.get("direccion", "").strip(),
            )
            flash(f"Hotel creado. PIN: {pin}", "ok")
        except Exception as e:
            flash(f"Error: {e}", "error")
        return redirect(url_for("admin_hoteles"))
    return render_template("admin_hoteles.html", hoteles=listar_hoteles())


@app.route("/admin/hoteles/<int:hid>/regenerar-pin", methods=["POST"])
def regenerar_pin(hid):
    try:
        nuevo_pin = regenerar_pin_hotel(hid)
        flash(f"Nuevo PIN: {nuevo_pin}", "ok")
    except Exception as e:
        flash(f"Error: {e}", "error")
    return redirect(url_for("admin_hoteles"))


# ==================== INICIO ====================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)