"""Sirve esta carpeta por http://localhost (puerto libre) y abre el mapa en el navegador."""
import http.server, threading, webbrowser, os
os.chdir(os.path.dirname(os.path.abspath(__file__)))
class Q(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Q)   # puerto 0 = el sistema asigna uno libre
url = f"http://localhost:{srv.server_address[1]}/mapa_directorio.html"
print("Mapa en:", url, "\nCierra esta ventana (o Ctrl+C) para detener el servidor.", flush=True)
threading.Timer(1.0, lambda: webbrowser.open(url)).start()
srv.serve_forever()
