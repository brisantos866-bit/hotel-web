import urllib.parse

def generar_ticket_hotel(datos):
    simbolo = {"USD": "$", "HNL": "L", "EUR": "€"}.get(datos.get("moneda", "USD"), datos.get("moneda", "$"))
    lineas = [
        "=" * 40,
        f"  TICKET DE ALQUILER #{datos.get('id', '')}",
        "=" * 40,
        f"Hotel: {datos.get('hotel_nombre', '')}",
        f"Huésped: {datos.get('huesped', '')}",
        f"Habitación: {datos.get('hab_numero', '')} ({datos.get('hab_tipo', '')})",
        f"Periodo: {datos.get('cantidad', '')} {datos.get('periodo_texto', 'día(s)')}",
        f"Tarifa: {simbolo}{datos.get('tarifa', 0):.2f}",
        "-" * 40,
        f"TOTAL: {simbolo}{datos.get('total', 0):.2f} {datos.get('moneda', '')}",
        "=" * 40,
        "¡Gracias por su preferencia!",
    ]
    return "\n".join(lineas)


def generar_enlace_whatsapp(telefono, texto):
    tel = "".join(c for c in (telefono or "") if c.isdigit())
    if not tel:
        return None
    return f"https://wa.me/{tel}?text={urllib.parse.quote(texto)}"


def generar_enlace_sms(telefono, texto):
    tel = "".join(c for c in (telefono or "") if c.isdigit())
    if not tel:
        return None
    return f"sms:{tel}?body={urllib.parse.quote(texto)}"


def generar_mensaje_celular(datos, plantilla=None, hotel_nombre=""):
    simbolo = {"USD": "$", "HNL": "L", "EUR": "€"}.get(datos.get("moneda", "USD"), datos.get("moneda", "$"))
    if not plantilla:
        plantilla = (
            "Hola {huesped}, gracias por hospedarte en {hotel_nombre}. "
            "Tu alquiler en la habitación {hab_numero} por {cantidad} {periodo_texto} "
            "tiene un total de {simbolo}{total} {moneda}. ¡Buen día!"
        )
    return (
        plantilla
        .replace("{huesped}", datos.get("huesped", ""))
        .replace("{hotel_nombre}", hotel_nombre)
        .replace("{hab_numero}", str(datos.get("hab_numero", "")))
        .replace("{hab_tipo}", str(datos.get("hab_tipo", "")))
        .replace("{cantidad}", str(datos.get("cantidad", "")))
        .replace("{periodo_texto}", datos.get("periodo_texto", "día(s)"))
        .replace("{simbolo}", simbolo)
        .replace("{total}", f"{datos.get('total', 0):.2f}")
        .replace("{moneda}", datos.get("moneda", ""))
    )
