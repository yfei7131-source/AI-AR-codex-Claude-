"""Generate a task-local development CA without changing any trust store."""
from datetime import datetime, timedelta, timezone
import ipaddress
import json
from pathlib import Path


def private_ipv4(value):
    address = ipaddress.ip_address(value)
    if address.version != 4 or not (address.is_private or address.is_loopback) or address.is_unspecified or address.is_multicast or address.is_reserved:
        raise ValueError("choose a specific private LAN IPv4 address or 127.0.0.1")
    return address


def ensure_tls(directory, host):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
    address = private_ipv4(host)
    directory = Path(directory)
    names = {"ca": directory / "ca.pem", "ca_der": directory / "ca.cer", "ca_key": directory / "ca-key.pem",
             "cert": directory / "server.pem", "key": directory / "server-key.pem"}
    now = datetime.now(timezone.utc)
    if any(path.exists() for path in names.values()):
        if not all(path.is_file() for path in names.values()):
            raise ValueError("partial TLS files exist; use a new private TLS directory")
        cert = x509.load_pem_x509_certificate(names["cert"].read_bytes())
        ca = x509.load_pem_x509_certificate(names["ca"].read_bytes())
        sans = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
        if address not in sans.get_values_for_type(x509.IPAddress) or cert.not_valid_after_utc <= now:
            raise ValueError("TLS host changed or certificate expired; use a new TLS directory and re-pair")
    else:
        directory.mkdir(parents=True, exist_ok=True)
        ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "AI Glasses local development CA")])
        ca = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(ca_key.public_key())
              .serial_number(x509.random_serial_number()).not_valid_before(now - timedelta(minutes=5))
              .not_valid_after(now + timedelta(days=365))
              .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
              .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False,
                  data_encipherment=False, key_agreement=False, key_cert_sign=True, crl_sign=True, encipher_only=False, decipher_only=False), critical=True)
              .add_extension(x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()), critical=False)
              .sign(ca_key, hashes.SHA256()))
        cert = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, str(address))]))
                .issuer_name(subject).public_key(leaf_key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=30))
                .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
                .add_extension(x509.SubjectAlternativeName([x509.IPAddress(address), x509.IPAddress(ipaddress.ip_address("127.0.0.1")), x509.DNSName("localhost")]), critical=False)
                .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
                .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=True,
                    data_encipherment=False, key_agreement=False, key_cert_sign=False, crl_sign=False, encipher_only=False, decipher_only=False), critical=True)
                .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False)
                .sign(ca_key, hashes.SHA256()))
        for key, path in ((ca_key, names["ca_key"]), (leaf_key, names["key"])):
            with path.open("xb") as output:
                output.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        names["ca"].write_bytes(ca.public_bytes(serialization.Encoding.PEM))
        names["ca_der"].write_bytes(ca.public_bytes(serialization.Encoding.DER))
        names["cert"].write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    result = {key: str(path.resolve()) for key, path in names.items()}
    result.update({"host": str(address), "ca_sha256": ca.fingerprint(hashes.SHA256()).hex(),
                   "expires_utc": cert.not_valid_after_utc.isoformat(), "trust_store_modified": False})
    (directory / "public-info.json").write_text(json.dumps({key: result[key] for key in ("host", "ca_sha256", "expires_utc", "trust_store_modified")}, indent=2), encoding="utf-8")
    return result
