import csv
import os
from datetime import datetime
from io import StringIO
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

app = FastAPI(title="Control de Asistencia QR")

# Configuración de directorios y archivos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

EMPLEADOS_FILE = os.path.join(BASE_DIR, "empleados.csv")
ASISTENCIAS_FILE = os.path.join(BASE_DIR, "asistencias.csv")

TEMPLATE_NAME = "checkin.html"
VALID_TOKEN = "c4a8b7e2-89f1-4d33-bc12-9901ef234567"


def inicializar_archivos():
    """Crea los archivos CSV si no existen."""
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
                    empleados.append({
                        "id": row.get("id", ""),
                        "nombre": row.get("nombre", "").strip(),
                        "cedula": row.get("cedula", "").strip(),
                    })
    return empleados


def registrar_nuevo_empleado(nombre: str, cedula: str):
    """Agrega un empleado nuevo a empleados.csv."""
    empleados = obtener_empleados()
    nuevo_id = str(len(empleados) + 1)
    with open(EMPLEADOS_FILE, mode="a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([nuevo_id, nombre.strip(), cedula.strip()])


# Modelo del payload recibido en /api/asistencia
class AsistenciaPayload(BaseModel):
    token: str
    tipo_marca: str  # 'entrada' o 'salida'
    nombre_completo: str
    cedula: Optional[str] = ""
    es_nuevo: Optional[bool] = False


# ==========================================
# RUTAS DE INTERFAZ HTML
# ==========================================

@app.get("/", response_class=HTMLResponse)
def root():
    return RedirectResponse(url=f"/marcar?t={VALID_TOKEN}")


@app.get("/marcar", response_class=HTMLResponse)
def vista_marcar(request: Request, t: Optional[str] = Query(None)):
    return templates.TemplateResponse(
        request=request,
        name=TEMPLATE_NAME,
        context={
            "token": t or "",
            "VALID_TOKEN": VALID_TOKEN,
        }
    )


# ==========================================
# ENDPOINTS API REST (CONSUMIDOS POR CHECKIN.HTML)
# ==========================================

@app.get("/api/scan/{token}")
def api_scan(token: str):
    if token != VALID_TOKEN:
        raise HTTPException(status_code=403, detail="Cartel QR no válido o vencido")
    return obtener_empleados()


@app.post("/api/asistencia")
def api_asistencia(data: AsistenciaPayload):
    if data.token != VALID_TOKEN:
        raise HTTPException(status_code=403, detail="Cartel QR no válido o vencido")

    nombre = data.nombre_completo.strip().title()
    cedula = (data.cedula or "").strip()
    tipo = data.tipo_marca.lower().strip()

    if not nombre:
        raise HTTPException(status_code=400, detail="El nombre del empleado es obligatorio")

    if data.es_nuevo:
        # Registrar si no existe en la lista
        empleados_actuales = [e["nombre"].lower() for e in obtener_empleados()]
        if nombre.lower() not in empleados_actuales:
            registrar_nuevo_empleado(nombre, cedula)

    ahora = datetime.now()
    fecha_hoy = ahora.strftime("%Y-%m-%d")
    hora_actual = ahora.strftime("%H:%M:%S")

    registros = []
    if os.path.exists(ASISTENCIAS_FILE):
        with open(ASISTENCIAS_FILE, mode="r", encoding="utf-8") as f:
            registros = list(csv.reader(f))

    if not registros:
        registros.append(["Nombre", "Cedula", "Fecha", "Hora Entrada", "Hora Salida", "Horas Trabajadas"])

    encontrado = False
    mensaje = ""

    if tipo == "entrada":
        for fila in registros[1:]:
            if len(fila) >= 3 and fila[0].lower() == nombre.lower() and fila[2] == fecha_hoy:
                encontrado = True
                break

        if encontrado:
            raise HTTPException(
                status_code=400,
                detail=f"Hola {nombre}, ya registraste tu entrada el día de hoy."
            )

        registros.append([nombre, cedula, fecha_hoy, hora_actual, "", ""])
        mensaje = f"¡Entrada registrada a las {hora_actual}!"

    elif tipo == "salida":
        for fila in reversed(registros[1:]):
            if len(fila) >= 3 and fila[0].lower() == nombre.lower() and fila[2] == fecha_hoy:
                if fila[4]:
                    raise HTTPException(
                        status_code=400,
                        detail=f"{nombre}, ya habías registrado tu salida el día de hoy."
                    )

                fila[4] = hora_actual
                try:
                    t_ent = datetime.strptime(fila[3], "%H:%M:%S")
                    t_sal = datetime.strptime(hora_actual, "%H:%M:%S")
                    dif_seg = (t_sal - t_ent).total_seconds()
                    horas = round(max(0, dif_seg / 3600), 2)
                    fila[5] = str(horas)
                except Exception:
                    fila[5] = "0.0"

                encontrado = True
                mensaje = f"¡Salida registrada a las {hora_actual}! Total: {fila[5]} horas."
                break

        if not encontrado:
            raise HTTPException(
                status_code=400,
                detail=f"No se encontró registro de entrada para {nombre} hoy."
            )
    else:
        raise HTTPException(status_code=400, detail="Tipo de marcación no reconocido")

    with open(ASISTENCIAS_FILE, mode="w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(registros)

    return {
        "status": "ok",
        "mensaje": mensaje,
        "hora": hora_actual,
        "nombre": nombre,
    }


# ==========================================
# DESCARGA DE REPORTE EXCEL (CSV CON BOM)
# ==========================================

@app.get("/descargar-reporte")
def descargar_reporte():
    if not os.path.exists(ASISTENCIAS_FILE):
        raise HTTPException(status_code=404, detail="No hay asistencias registradas.")

    output = StringIO()
    output.write("\ufeff")  # BOM UTF-8 para apertura directa en Excel en español
    writer = csv.writer(output, delimiter=";", quoting=csv.QUOTE_MINIMAL)

    writer.writerow([
        "Nombre y Apellido",
        "Cédula",
        "Fecha",
        "Hora Entrada",
        "Hora Salida",
        "Horas Trabajadas"
    ])

    with open(ASISTENCIAS_FILE, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        primera_fila = next(reader, None)
        if primera_fila and "nombre" not in primera_fila[0].lower():
            writer.writerow(primera_fila)
        for fila in reader:
            if fila and any(c.strip() for c in fila):
                writer.writerow(fila)

    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=reporte_asistencias.csv"}
    )