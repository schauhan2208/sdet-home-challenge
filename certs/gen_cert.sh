#!/usr/bin/env sh
# Self-signed cert for local TLS testing
openssl req -x509 -newkey rsa:2048 -nodes -days 365 -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" \
  -keyout "$(dirname "$0")/key.pem" -out "$(dirname "$0")/cert.pem"
