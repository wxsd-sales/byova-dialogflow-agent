# TLS certificate files (optional)

When `gateway.tls.enabled` is `true` in `config/config.yaml`, place PEM files here (or set paths in config).

- **server-chain.pem** — server certificate + intermediate CAs (leaf first)
- **server-key.pem** — private key

Do not commit real keys; `*.pem` is ignored by `.gitignore`.

For production, terminating TLS at a load balancer and using plaintext gRPC to this process is common.
