"""Same-origin TLS + ephemeral Bearer gateway for a private iPhone test LAN.

The existing API remains loopback-only. No tunnel, cloud deployment, trust-store
change or firewall modification is performed. Never log request paths/tokens.
"""
from __future__ import annotations
import argparse
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import mimetypes
from pathlib import Path
import secrets
import socket
import ssl
from threading import Thread
import time
from urllib import error, request
from urllib.parse import unquote, urlsplit
from app.dev_tls import ensure_tls, private_ipv4

ROOT = Path(__file__).resolve().parents[1]
MAX_BODY = 3 * 1024 * 1024
MAX_REPLY = 2 * 1024 * 1024


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


class PrivateServer(ThreadingHTTPServer):
    # Windows SO_REUSEADDR can let two gateways share a listening port, leaving
    # the pairing file associated with a different live token. Fail closed.
    allow_reuse_address = False
    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


class Gateway(PrivateServer):
    daemon_threads = True
    def __init__(self, address, *, upstream, web_root, token=None, session_seconds=8 * 3600, protected_roots=()):
        parsed = urlsplit(upstream)
        if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment or parsed.username or parsed.password):
            raise ValueError("gateway upstream must be an explicit 127.0.0.1 HTTP origin")
        if not 1 <= session_seconds <= 8 * 3600:
            raise ValueError("session lifetime must be 1–28800 seconds")
        self.upstream = upstream.rstrip("/")
        self.web_root = Path(web_root).resolve()
        self.protected_roots = tuple(Path(path).resolve() for path in
                                     (ROOT / "artifacts/private", *protected_roots))
        if any(self.web_root.is_relative_to(path) or path.is_relative_to(self.web_root)
               for path in self.protected_roots):
            raise ValueError("web root must not overlap private credential directories")
        self.token = token or secrets.token_urlsafe(32)
        self.deadline = time.monotonic() + session_seconds
        self.opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
        self.allowed_hosts = {address[0], "127.0.0.1", "localhost"}
        super().__init__(address, GatewayHandler)


class GatewayHandler(BaseHTTPRequestHandler):
    server_version = "AIARPhoneGateway/0.1"
    def log_message(self, *args):
        pass

    def reply(self, status, body, content_type="application/json; charset=utf-8"):
        raw = json.dumps(body, ensure_ascii=False).encode("utf-8") if isinstance(body, dict) else body
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "camera=(self), microphone=(self), geolocation=()")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def fail(self, status, code, message):
        return self.reply(status, {"code": code, "error": message})

    def same_origin(self):
        try:
            host = urlsplit("https://" + self.headers.get("Host", ""))
            if host.hostname not in self.server.allowed_hosts or host.port != self.server.server_port:
                return False
            origin = self.headers.get("Origin")
            return (not origin or origin == "https://" + host.netloc) and self.headers.get("Sec-Fetch-Site") != "cross-site"
        except ValueError:
            return False

    def authorized(self):
        if time.monotonic() >= self.server.deadline:
            return False
        value = self.headers.get("Authorization", "")
        expected = "Bearer " + self.server.token
        return hmac.compare_digest(value.encode("utf-8"), expected.encode("utf-8"))

    def do_GET(self):
        self.route()

    def do_POST(self):
        self.route()

    def do_OPTIONS(self):
        self.fail(403, "ORIGIN_DENIED", "Only same-origin requests are allowed")

    def route(self):
        if not isinstance(self.connection, ssl.SSLSocket):
            return self.fail(426, "TLS_REQUIRED", "Use HTTPS; plaintext gateway access is disabled")
        if not self.same_origin():
            return self.fail(403, "ORIGIN_DENIED", "Use the trusted same-origin HTTPS pairing link")
        path = urlsplit(self.path).path
        if path == "/gateway/health" and self.command == "GET":
            return self.reply(200, {"ok": True, "api_gateway": "local_tls", "session_expired": time.monotonic() >= self.server.deadline})
        if path.startswith("/api/"):
            if not self.authorized():
                return self.fail(401, "PAIRING_REQUIRED", "Pairing token missing, invalid or expired; reopen the private pairing link")
            return self.proxy(path)
        if self.command != "GET":
            return self.fail(404, "NOT_FOUND", "Unknown endpoint")
        decoded = unquote(path)
        if ("\\" in decoded or "\0" in decoded or ":" in decoded
                or any(part.startswith(".") or part.endswith((" ", ".")) for part in decoded.split("/") if part)
                or Path(decoded).suffix.lower() in (".pem", ".key", ".p12", ".pfx", ".cer", ".crt")):
            return self.fail(404, "NOT_FOUND", "Unknown asset")
        asset = (self.server.web_root / (decoded.lstrip("/") or "index.html")).resolve()
        if (not asset.is_relative_to(self.server.web_root)
                or any(asset.is_relative_to(path) for path in self.server.protected_roots)
                or asset.suffix.lower() in (".pem", ".key", ".p12", ".pfx", ".cer", ".crt")
                or not asset.is_file()):
            return self.fail(404, "NOT_FOUND", "Unknown asset")
        content_type = {".js": "text/javascript; charset=utf-8", ".wasm": "application/wasm"}.get(asset.suffix, mimetypes.guess_type(str(asset))[0] or "application/octet-stream")
        return self.reply(200, asset.read_bytes(), content_type)

    def proxy(self, path):
        if self.headers.get("Transfer-Encoding"):
            return self.fail(400, "INVALID_REQUEST", "Chunked uploads are not supported")
        body = None
        if self.command == "POST":
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self.fail(400, "INVALID_REQUEST", "Invalid content length")
            if not 0 < length <= MAX_BODY:
                return self.fail(413, "BODY_TOO_LARGE", "Request must be 1 byte to 3 MiB")
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                return self.fail(415, "INVALID_CONTENT_TYPE", "JSON request required")
            self.connection.settimeout(10)
            try:
                body = self.rfile.read(length)
                if len(body) != length:
                    return self.fail(400, "INVALID_REQUEST", "Incomplete upload")
            except TimeoutError:
                return self.fail(408, "UPLOAD_TIMEOUT", "Local upload timed out")
        # No original Host, Origin, Cookie, Authorization or forwarding header
        # reaches the backend; it receives an ordinary local JSON request.
        req = request.Request(self.server.upstream + path, data=body, method=self.command,
                              headers={"Content-Type": "application/json"})
        try:
            try:
                response = self.server.opener.open(req, timeout=80)
            except error.HTTPError as exc:
                response = exc
            with response:
                if 300 <= response.code < 400:
                    return self.fail(502, "UPSTREAM_REDIRECT_DENIED", "Backend redirects are prohibited")
                raw = response.read(MAX_REPLY + 1)
                if len(raw) > MAX_REPLY:
                    return self.fail(502, "UPSTREAM_RESPONSE_TOO_LARGE", "Backend response too large")
                content_type = response.headers.get("Content-Type", "")
                if not content_type.startswith("application/json"):
                    return self.fail(502, "INVALID_BACKEND", "Backend must return JSON")
                return self.reply(response.code, raw, content_type)
        except (error.URLError, TimeoutError, OSError):
            return self.fail(502, "BACKEND_UNAVAILABLE", "Local backend unavailable or timed out")


def ca_bootstrap(address, certificate_bytes):
    class CertificateOnly(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_GET(self):
            if self.path != "/ca.cer":
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/pkix-cert")
            self.send_header("Content-Length", str(len(certificate_bytes)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(certificate_bytes)
    return PrivateServer(address, CertificateOnly)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lan-ip", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=9443)
    parser.add_argument("--tls-dir", type=Path, default=ROOT / "artifacts/private/iphone/tls")
    parser.add_argument("--private-dir", type=Path, default=ROOT / "artifacts/private/iphone")
    parser.add_argument("--web-root", type=Path, default=ROOT / "mobile/build/web")
    parser.add_argument("--backend-url", help="optional existing 127.0.0.1 backend; otherwise start current code internally")
    parser.add_argument("--serve-ca", action="store_true", help="also serve the PUBLIC CA certificate only over HTTP on port+1; manually verify fingerprint")
    args = parser.parse_args(argv)
    address = str(private_ipv4(args.lan_ip))
    if not 1 <= args.port < 65535:
        parser.error("port must be 1–65534")
    if not (args.web_root / "index.html").is_file():
        parser.error("build the existing Flutter Web app first")
    private_root = (ROOT / "artifacts/private").resolve()
    if not args.private_dir.resolve().is_relative_to(private_root) or not args.tls_dir.resolve().is_relative_to(private_root):
        parser.error("TLS and pairing credentials must stay in artifacts/private")
    paths = ensure_tls(args.tls_dir, address)
    backend = None
    if args.backend_url:
        upstream = args.backend_url
    else:
        from app.server import Handler
        backend = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        Thread(target=backend.serve_forever, daemon=True).start()
        upstream = "http://127.0.0.1:" + str(backend.server_port)
    gateway = Gateway((address, args.port), upstream=upstream, web_root=args.web_root,
                      protected_roots=(args.private_dir, args.tls_dir))
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(paths["cert"], paths["key"])
    gateway.socket = context.wrap_socket(gateway.socket, server_side=True)
    private_dir = args.private_dir.resolve()
    if not private_dir.is_relative_to((ROOT / "artifacts/private").resolve()):
        parser.error("pairing credentials must stay in artifacts/private")
    private_dir.mkdir(parents=True, exist_ok=True)
    link = f"https://{address}:{args.port}/#pair={gateway.token}"
    (private_dir / "pairing.txt").write_text(link + "\n", encoding="utf-8")
    import qrcode
    qrcode.make(link).save(private_dir / "pairing-qr.png")
    ca_server = None
    if args.serve_ca:
        ca_server = ca_bootstrap((address, args.port + 1), Path(paths["ca_der"]).read_bytes())
        Thread(target=ca_server.serve_forever, daemon=True).start()
    print("Local HTTPS gateway ready; private pairing link/QR:", private_dir, flush=True)
    print("CA SHA256 (compare before manual trust):", paths["ca_sha256"], flush=True)
    print("No trust-store/firewall changes; session expires in 8 hours; restart rotates token.", flush=True)
    try:
        gateway.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        gateway.server_close()
        if ca_server:
            ca_server.shutdown()
            ca_server.server_close()
        if backend:
            backend.shutdown()
            backend.server_close()


if __name__ == "__main__":
    main()
