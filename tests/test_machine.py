import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from gilty import machine


class FakeAPI(BaseHTTPRequestHandler):
    """A Kubernetes API with one node, and an IMDSv2 with one value."""

    def do_GET(self):
        if self.path == "/api/v1/nodes/node-a" and self.headers.get("Authorization") == "Bearer t0ken":
            body = {"metadata": {"labels": {"node.kubernetes.io/instance-type": "c8a.large"}}}
        elif self.path == "/latest/meta-data/instance-type" and self.headers.get("X-aws-ec2-metadata-token") == "imds":
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"r5a.large")
            return
        else:
            self.send_response(403)
            self.end_headers()
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())

    def do_PUT(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"imds")

    def log_message(self, *args):
        pass


def serve():
    srv = HTTPServer(("127.0.0.1", 0), FakeAPI)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_port}"


def test_kubernetes_label(tmp_path):
    srv, url = serve()
    token = tmp_path / "token"
    token.write_text("t0ken\n")
    try:
        assert machine.from_kubernetes("node-a", api=url, token_file=str(token)) == "c8a.large"
        assert machine.from_kubernetes("node-b", api=url, token_file=str(token)) is None  # 403
        assert machine.from_kubernetes("node-a", api=url, token_file=str(tmp_path / "missing")) is None
    finally:
        srv.shutdown()


def test_imds():
    srv, url = serve()
    try:
        assert machine.from_aws_imds(base=url) == "r5a.large"
    finally:
        srv.shutdown()
    assert machine.from_aws_imds(base="http://127.0.0.1:9", timeout=0.2) is None


def test_override_wins(monkeypatch):
    monkeypatch.setenv("GILTY_INSTANCE_TYPE", "m8a.large")
    assert machine.instance_type() == "m8a.large"
