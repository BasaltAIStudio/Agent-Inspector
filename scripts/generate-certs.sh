#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_DIR="${SCRIPT_DIR}/../certs"
mkdir -p "${CERT_DIR}"

echo "Generating CA key and certificate..."
openssl genrsa -out "${CERT_DIR}/ca.key" 4096
openssl req -x509 -new -nodes -key "${CERT_DIR}/ca.key" -sha256 -days 3650 \
    -out "${CERT_DIR}/ca.crt" \
    -subj "/C=US/ST=State/L=City/O=AgentInspector/OU=CA/CN=AgentInspector CA"

echo "Generating server key and CSR..."
openssl genrsa -out "${CERT_DIR}/server.key" 4096
openssl req -new -key "${CERT_DIR}/server.key" \
    -out "${CERT_DIR}/server.csr" \
    -subj "/C=US/ST=State/L=City/O=AgentInspector/OU=Server/CN=localhost"

echo "Signing server certificate with CA..."
openssl x509 -req -in "${CERT_DIR}/server.csr" -CA "${CERT_DIR}/ca.crt" -CAkey "${CERT_DIR}/ca.key" \
    -CAcreateserial -out "${CERT_DIR}/server.crt" -days 825 -sha256 \
    -extfile <(echo "subjectAltName=DNS:localhost,IP:127.0.0.1")

echo "Generating client key and CSR..."
openssl genrsa -out "${CERT_DIR}/client.key" 4096
openssl req -new -key "${CERT_DIR}/client.key" \
    -out "${CERT_DIR}/client.csr" \
    -subj "/C=US/ST=State/L=City/O=AgentInspector/OU=Client/CN=agentinspector-client"

echo "Signing client certificate with CA..."
openssl x509 -req -in "${CERT_DIR}/client.csr" -CA "${CERT_DIR}/ca.crt" -CAkey "${CERT_DIR}/ca.key" \
    -CAcreateserial -out "${CERT_DIR}/client.crt" -days 825 -sha256

chmod 600 "${CERT_DIR}"/*.key
chmod 644 "${CERT_DIR}"/*.crt

rm -f "${CERT_DIR}"/*.csr "${CERT_DIR}"/*.srl

echo "Certificates generated in ${CERT_DIR}"
echo "  ca.crt      - CA certificate (trust this on clients)"
echo "  server.crt  - Server certificate"
echo "  server.key  - Server private key"
echo "  client.crt  - Client certificate (present this to nginx)"
echo "  client.key  - Client private key"
