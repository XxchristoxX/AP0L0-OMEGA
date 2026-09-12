import cv2
import json
def run(params):
    if 'image_path' not in params:
        return json.dumps({"error": "El parámetro 'image_path' es requerido."})
    image_path = params['image_path']
    # Cargar la imagen
    image = cv2.imread(image_path)
    if image is None:
        return json.dumps({"error": "No se pudo abrir la imagen."})
    # Inicializar el detector de códigos QR y de barras
    detector = cv2.QRCodeDetector()
    bar_detector = cv2.barcode.BarcodeDetector()
    # Detectar códigos QR
    data, bbox, _ = detector(image)
    if data:
        return json.dumps({"type": "QR", "data": data})
    # Detectar códigos de barras
    retval, decoded_info, points, straight_qrcode = bar_detector(image)
    if retval:
        return json.dumps({"type": "Barcode", "data": decoded_info})
    return json.dumps({"error": "No se detectó ningún código."})