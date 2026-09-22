import csv
import os
from datetime import datetime
from io import StringIO
from typing import Optional

from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

app = FastAPI(title="Control de Asistencia QR")

# Configuración de rutas y archivos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

EMPLEADOS_FILE = os.path.join(BASE_DIR, "empleados.csv")
ASISTENCIAS_FILE = os.path.join(BASE_DIR, "asistencias.csv")

# Token de seguridad configurado para el cartel QR
VALID_TOKEN = "c4a8b7e2-89f1-4d33-bc12-9901ef234567"


def inicializar_archivos():
    """Asegura que existan los archivos CSV con sus encabezados base."""
    if not os.path.exists(EMPLEADOS_FILE):
        with open(EMPLEADOS_FILE, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "nombre", "cedula"])

    if not os.path.exists(ASISTENCIAS_FILE):
        with open(ASISTENCIAS_FILE, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Nombre", "Cedula", "Fecha", "Hora Entrada", "Hora Salida", "Horas Trabajadas"
            ])


inicializar_archivos()


def obtener_empleados():
    """Lee la lista de empleados registrados."""
    empleados = []
    if os.path.exists(EMPLEADOS_FILE):
        with open(EMPLEADOS_FILE, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("nombre"):
                    empleados.append(row)
    return empleados


def registrar_nuevo_empleado(nombre: str, cedula: str):
    """Guarda un empleado nuevo en empleados.csv para futuras ocasiones."""
    empleados = obtener_empleados()
    nuevo_id = str(len(empleados) + 1)
    with open(EMPLEADOS_FILE, mode="a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([nuevo_id, nombre.strip(), cedula.strip()])


# ==========================================
# RUTAS DE LA APLICACIÓN
# ==========================================

@app.get("/", response_class=HTMLResponse)
def root():
    return RedirectResponse(url=f"/marcar?t={VALID_TOKEN}")


@app.get("/marcar", response_class=HTMLResponse)
def vista_marcar(request: Request, t: Optional[str] = Query(None)):
    if t != VALID_TOKEN:
        raise HTTPException(
            status_code=403,
            detail="Acceso no autorizado. Debe escanear el código QR oficial de la obra."
        )

    empleados = obtener_empleados()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "empleados": empleados,
            "token": t,
            "mensaje": None,
            "tipo_mensaje": None,
        }
    )


@app.post("/marcar", response_class=HTMLResponse)
def procesar_marcado(
    request: Request,
    token: str = Form(...),
    tipo_accion: str = Form(...),  # 'entrada' o 'salida'
    empleado_select: str = Form(...),
    nombre_nuevo: Optional[str] = Form(None),
    cedula_nueva: Optional[str] = Form(None),
):
    if token != VALID_TOKEN:
        raise HTTPException(status_code=403, detail="Token no válido")

    # Determinar identidad del trabajador
    if empleado_select == "nuevo":
        if not nombre_nuevo or not nombre_nuevo.strip():
            empleados = obtener_empleados()
            return templates.TemplateResponse(
                request=request,
                name="index.html",
                context={
                    "empleados": empleados,
                    "token": token,
                    "mensaje": "Debes ingresar tu nombre si seleccionas personal nuevo.",
                    "tipo_mensaje": "error",
                }
            )
        nombre = nombre_nuevo.strip().title()
        cedula = (cedula_nueva or "").strip()
        registrar_nuevo_empleado(nombre, cedula)
    else:
        partes = empleado_select.split("|")
        nombre = partes[0]
        cedula = partes[1] if len(partes) > 1 else ""

    ahora = datetime.now()
    fecha_hoy = ahora.strftime("%Y-%m-%d")
    hora_actual = ahora.strftime("%H:%M:%S")

    # Leer registros existentes
    registros = []
    encontrado = False
    mensaje_exito = ""

    if os.path.exists(ASISTENCIAS_FILE):
        with open(ASISTENCIAS_FILE, mode="r", encoding="utf-8") as f:
            reader = csv.reader(f)
            registros = list(reader)

    if not registros:
        registros.append(["Nombre", "Cedula", "Fecha", "Hora Entrada", "Hora Salida", "Horas Trabajadas"])

    # Lógica de Entrada / Salida
    if tipo_accion == "entrada":
        # Verificar si ya marcó entrada hoy
        for fila in registros[1:]:
            if len(fila) >= 3 and fila[0] == nombre and fila[2] == fecha_hoy:
                encontrado = True
                break

        if encontrado:
            empleados = obtener_empleados()
            return templates.TemplateResponse(
                request=request,
                name="index.html",
                context={
                    "empleados": empleados,
                    "token": token,
                    "mensaje": f"Hola {nombre}, ya tienes una entrada registrada el día de hoy.",
                    "tipo_mensaje": "advertencia",
                }
            )

        registros.append([nombre, cedula, fecha_hoy, hora_actual, "", ""])
        mensaje_exito = f"¡Entrada registrada con éxito a las {hora_actual}!"

    elif tipo_accion == "salida":
        # Buscar el registro de hoy para asentar salida y calcular horas
        for fila in reversed(registros[1:]):
            if len(fila) >= 3 and fila[0] == nombre and fila[2] == fecha_hoy:
                if fila[4]:  # Ya tenía salida
                    empleados = obtener_empleados()
                    return templates.TemplateResponse(
                        request=request,
                        name="index.html",
                        context={
                            "empleados": empleados,
                            "token": token,
                            "mensaje": f"{nombre}, ya habías registrado tu salida anteriormente.",
                            "tipo_mensaje": "advertencia",
                        }
                    )

                fila[4] = hora_actual
                try:
                    t_ent = datetime.strptime(fila[3], "%H:%M:%S")
                    t_sal = datetime.strptime(hora_actual, "%H:%M:%S")
                    dif_segundos = (t_sal - t_ent).total_seconds()
                    horas = round(max(0, dif_segundos / 3600), 2)
                    fila[5] = str(horas)
                except Exception:
                    fila[5] = "0.0"

                encontrado = True
                mensaje_exito = f"¡Salida registrada a las {hora_actual}! Total: {fila[5]} horas trabajadas."
                break

        if not encontrado:
            empleados = obtener_empleados()
            return templates.TemplateResponse(
                request=request,
                name="index.html",
                context={
                    "empleados": empleados,
                    "token": token,
                    "mensaje": f"No se encontró un registro de entrada previo para {nombre} el día de hoy.",
                    "tipo_mensaje": "error",
                }
            )

    # Guardar en asistencias.csv
    with open(ASISTENCIAS_FILE, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(registros)

    empleados = obtener_empleados()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "empleados": empleados,
            "token": token,
            "mensaje": mensaje_exito,
            "tipo_mensaje": "exito",
        }
    )


# ==========================================
# DESCARGA DE REPORTE COMPATIBLE CON EXCEL
# ==========================================

@app.get("/descargar-reporte")
def descargar_reporte():
    """
    Genera un archivo CSV con delimitador ';' y marca UTF-8 BOM (\ufeff)
    para que Excel en español lo abra en columnas y con acentos correctos al hacer doble clic.
    """
    if not os.path.exists(ASISTENCIAS_FILE):
        raise HTTPException(
            status_code=404,
            detail="No se encontraron registros de asistencias para exportar."
        )

    output = StringIO()
    output.write("\ufeff")  # BOM UTF-8 para Excel en español
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

    writer.writerow([
        "Nombre y Apellido",
        "Cédula",
        "Fecha",
        "Hora Entrada",
        "Hora Salida",
        "Horas Trabajadas"
    ])

    try:
        with open(ASISTENCIAS_FILE, mode="r", encoding="utf-8") as f:
            reader = csv.reader(f)
            primera_fila = next(reader, None)

            if primera_fila and "nombre" not in primera_fila[0].lower():
                writer.writerow(primera_fila)

            for fila in reader:
                if fila and any(campo.strip() for campo in fila):
                    writer.writerow(fila)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al leer asistencias: {str(e)}")

    contenido = output.getvalue()
    output.close()

    return Response(
        content=contenido,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=reporte_asistencias.csv"
        }
    )