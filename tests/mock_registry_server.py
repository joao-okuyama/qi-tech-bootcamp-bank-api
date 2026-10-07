"""Servidor HTTP local para verificar o contrato CSV sem Docker/MockServer."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread


def start_registry_server(port):
    server = ThreadingHTTPServer(("127.0.0.1", port), RegistryHandler)
    server.content = ""
    server.response_status = 404
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


class RegistryHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_PUT(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/mockserver/clear":
            self.server.content, self.server.response_status = "", 404
        elif self.path == "/mockserver/expectation":
            self.server.content = payload["httpResponse"]["body"]
            self.server.response_status = payload["httpResponse"]["statusCode"]
        else:
            self.send_error(404)
            return
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        if self.path != "/bets.csv":
            self.send_error(404)
            return
        content = self.server.content.encode("utf-8")
        self.send_response(self.server.response_status)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)
