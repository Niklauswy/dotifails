#!/usr/bin/env python3

import http.server
import socketserver
import socket
import sys
import os 

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

handler = http.server.SimpleHTTPRequestHandler

def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # IP externa, no se hace conexión real
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"

local_ip = get_local_ip()

try:
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        print(f"✅ Servidor iniciado en: http://{local_ip}:{PORT}")
        print("📁 Carpeta servida:", os.getcwd())
        print("🛑 Presiona Ctrl+C para detenerlo.")
        httpd.serve_forever()
except OSError as e:
    print(f"❌ Error al iniciar el servidor en el puerto {PORT}: {e}")
