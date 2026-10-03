from pathlib import Path

import jwt
from cryptography import x509

from gateway.devkeys import write_signing_keys, write_tls_certs


def test_signing_keys_roundtrip(tmp_path: Path):
    write_signing_keys(tmp_path)
    private = (tmp_path / "gateway_jwt_private.pem").read_bytes()
    public = (tmp_path / "gateway_jwt_public.pem").read_bytes()

    token = jwt.encode({"x": 1}, private, algorithm="RS256")
    assert jwt.decode(token, public, algorithms=["RS256"]) == {"x": 1}


def test_tls_cert_issued_by_ca_for_localhost(tmp_path: Path):
    write_tls_certs(tmp_path)
    ca = x509.load_pem_x509_certificate((tmp_path / "ca.pem").read_bytes())
    server = x509.load_pem_x509_certificate((tmp_path / "server.pem").read_bytes())

    server.verify_directly_issued_by(ca)
    san = server.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert "localhost" in san.get_values_for_type(x509.DNSName)
    assert (tmp_path / "server-key.pem").exists()
