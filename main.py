import csv
import os
from datetime import datetime
from threading import Lock
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

app = FastAPI(title="Sistema de Asistencia QR - CSV")

templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Archivos de datos y token estático del cartel
CSV_ASISTENCIAS = "asistencias.csv"
CSV_EMPLEADOS = "empleados.csv"
TOKEN_VALIDO = "c4a8b7e2-89f1-4d33-bc12-9901ef234567"

# Candado para evitar conflictos si dos personas marcan al mismo segundo
archivo_lock = Lock()

# --- MODELOS PYDANTIC ---
class MarcajeCreate(BaseModel):
    token: str
    tipo_marca: str  # "ENTRADA" o "SALIDA"
    nombre_completo: str
    cedula: Optional[str] = ""
    es_nuevo: bool = False

# --- RUTAS WEB ---
@app.get("/marcar", response_class=HTMLResponse)
def pagina_marcar(request: Request, t: str = ""):
    return templates.TemplateResponse(
        request=request,
        name="checkin.html",
        context={"token": t}
    )

@app.get("/api/scan/{token}")
def obtener_empleados(token: str):
    if token != TOKEN_VALIDO:
        raise HTTPException(status_code=404, detail="Cartel QR no válido o vencido.")

    empleados = []
    if os.path.exists(CSV_EMPLEADOS):
        with open(CSV_EMPLEADOS, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                empleados.append({
                    "id": row["id"],
                    "nombre": row["nombre"],
                    "cedula": row.get("cedula", "")
                })
    return empleados

@app.post("/api/asistencia")
def registrar_asistencia(payload: MarcajeCreate):
    if payload.token != TOKEN_VALIDO:
        raise HTTPException(status_code=400, detail="Cartel QR no válido.")

    nombre = payload.nombre_completo.strip()
    if not nombre:
        raise HTTPException(status_code=422, detail="El nombre es obligatorio.")

    cedula = (payload.cedula or "").strip() or "S/N"
    ahora = datetime.now()
    hoy_str = ahora.strftime("%Y-%m-%d")
    hora_actual_str = ahora.strftime("%H:%M")

    with archivo_lock:
        # 1. Si es nuevo personal, guardarlo en la lista para futuras ocasiones
        if payload.es_nuevo:
            empleados_existentes = []
            if os.path.exists(CSV_EMPLEADOS):
                with open(CSV_EMPLEADOS, mode="r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    empleados_existentes = list(reader)

            nombres_registrados = [e["nombre"].strip().lower() for e in empleados_existentes]
            if nombre.lower() not in nombres_registrados:
                nuevo_id = str(len(empleados_existentes) + 1)
                with open(CSV_EMPLEADOS, mode="a", encoding="utf-8", newline="") as f:
                    writer = csv.writer(f)
                    writer.writerow([nuevo_id, nombre, cedula])

        # 2. Leer registros de asistencia existentes
        registros = []
        if os.path.exists(CSV_ASISTENCIAS):
            with open(CSV_ASISTENCIAS, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                registros = list(reader)

        # 3. Buscar si el empleado ya tiene un registro hoy
        indice_hoy = None
        for i, reg in enumerate(registros):
            if reg["Nombre"].strip().lower() == nombre.lower() and reg["Fecha"] == hoy_str:
                indice_hoy = i
                break

        # 4. Procesar marcación
        if payload.tipo_marca == "ENTRADA":
            if indice_hoy is not None:
                hora_reg = registros[indice_hoy]["Hora Entrada"]
                raise HTTPException(
                    status_code=400,
                    detail=f"Ya tienes entrada registrada hoy a las {hora_reg}."
                )

            nueva_fila = {
                "Nombre": nombre,
                "Cedula": cedula,
                "Fecha": hoy_str,
                "Hora Entrada": hora_actual_str,
                "Hora Salida": "Pendiente",
                "Horas Trabajadas": "0.00"
            }
            registros.append(nueva_fila)
            mensaje_retorno = f"Entrada registrada a las {hora_actual_str}"

        elif payload.tipo_marca == "SALIDA":
            if indice_hoy is None:
                raise HTTPException(
                    status_code=400,
                    detail="No tienes registro de entrada el día de hoy."
                )

            if registros[indice_hoy]["Hora Salida"] != "Pendiente":
                hora_sal = registros[indice_hoy]["Hora Salida"]
                raise HTTPException(
                    status_code=400,
                    detail=f"Ya registraste tu salida hoy a las {hora_sal}."
                )

            # Calcular diferencia de horas
            hora_ent_str = registros[indice_hoy]["Hora Entrada"]
            t_entrada = datetime.strptime(f"{hoy_str} {hora_ent_str}", "%Y-%m-%d %H:%M")
            t_salida = datetime.strptime(f"{hoy_str} {hora_actual_str}", "%Y-%m-%d %H:%M")
            
            diferencia_horas = round((t_salida - t_entrada).total_seconds() / 3600.0, 2)
            if diferencia_horas < 0:
                diferencia_horas = 0.00

            registros[indice_hoy]["Hora Salida"] = hora_actual_str
            registros[indice_hoy]["Horas Trabajadas"] = f"{diferencia_horas:.2f}"
            mensaje_retorno = f"Salida registrada a las {hora_actual_str}. Total: {diferencia_horas:.2f} hrs."

        else:
            raise HTTPException(status_code=400, detail="Acción no válida.")

        # 5. Reescribir el archivo CSV con los datos actualizados
        encabezados = ["Nombre", "Cedula", "Fecha", "Hora Entrada", "Hora Salida", "Horas Trabajadas"]
        with open(CSV_ASISTENCIAS, mode="w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=encabezados)
            writer.writeheader()
            writer.writerows(registros)

    return {
        "estado": "exito",
        "mensaje": mensaje_retorno,
        "empleado": nombre
    }

# Endpoint directo para descargar el archivo desde el navegador o celular
@app.get("/descargar-reporte")
def descargar_reporte():
    if not os.path.exists(CSV_ASISTENCIAS):
        raise HTTPException(status_code=404, detail="Aún no hay asistencias registradas.")
    return FileResponse(
        path=CSV_ASISTENCIAS,
        filename="reporte_asistencias.csv",
        media_type="text/csv"
    )