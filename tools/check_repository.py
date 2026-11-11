"""Read-only tracked-file hygiene guard. Never prints suspected secret contents."""
from pathlib import Path
import re
import subprocess


def forbidden_path(name):
    path = Path(name)
    parts = path.as_posix().split("/")
    lower = path.name.lower()
    if any(part in (".dart_tool", ".gradle", "build", "node_modules", "__pycache__", "managed_components") for part in parts):
        return "generated cache or build output"
    if parts[0] == "artifacts" or (parts[:2] == ["docs", "evidence"] and path.suffix.lower() in (".jpg", ".jpeg", ".png")):
        return "local test media or detailed reports"
    if (parts[0] == "tests" or parts[:2] == ["tools", "acceptance"]) and path.suffix.lower() in (".png", ".jpg", ".jpeg"):
        return "test media must be generated in the ignored private directory"
    if (lower == ".env" or lower.startswith(".env.") and lower != ".env.example"
            or lower in ("local.properties", "key.properties")
            or path.suffix.lower() in (".jks", ".keystore", ".p12", ".pfx", ".pem", ".key", ".cer", ".crt", ".apk", ".aab", ".elf", ".bin", ".log")):
        return "credential, local configuration or binary artifact"
    return None


def secret_like(content):
    return bool(re.search(r"sk-(?:proj-)?[A-Za-z0-9_-]{30,}", content)
                or re.search(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", content))


def main():
    root = Path(__file__).resolve().parents[1]
    names = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).decode("utf-8").split("\0")
    failures = []
    for name in filter(None, names):
        reason = forbidden_path(name)
        if reason:
            failures.append((name, reason))
            continue
        # Inspect the actual index snapshot, including a secret staged then
        # removed from the working tree. Never interpolate a shell command.
        raw = subprocess.check_output(["git", "show", ":" + name], cwd=root)
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            continue
        if secret_like(text):
            failures.append((name, "possible secret"))
    for name, reason in failures:
        print(f"FAIL: {name}: {reason}")
    if not failures:
        print("PASS: tracked files contain no forbidden artifacts or recognized secret patterns")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
