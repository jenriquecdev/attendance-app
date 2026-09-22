import qrcode

url = "https://asistencia.raptordevecu.com/marcar?t=c4a8b7e2-89f1-4d33-bc12-9901ef234567"

qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_H,
    box_size=15,
    border=4,
)
qr.add_data(url)
qr.make(fit=True)

img = qr.make_image(fill_color="#0f172a", back_color="white")
img.save("QR_Asistencia_Obra.png")
print("QR generado con éxito: QR_Asistencia_Obra.png")
