# RabbitMQ Two-Way SSL Authentication Guide

This project provides a step-by-step guide to install RabbitMQ on an Ubuntu machine, generate SSL certificates, configure RabbitMQ for two-way (mutual) SSL authentication, and verify the setup using a Python client script without using a username and password.

## Table of Contents
- [Prerequisites](#prerequisites)
- [1. Install RabbitMQ on Ubuntu](#1-install-rabbitmq-on-ubuntu)
- [2. Generate SSL Certificates](#2-generate-ssl-certificates)
- [3. Configure RabbitMQ for SSL](#3-configure-rabbitmq-for-ssl)
- [4. Place Certificates](#4-place-certificates)
- [5. Verify Two-Way Authentication](#5-verify-two-way-authentication)
- [References](#references)

---

## Prerequisites
- Ubuntu machine (tested on 20.04/22.04)
- sudo privileges
- Python 3.x

---

echo "deb https://packages.erlang-solutions.com/ubuntu $(lsb_release -cs) contrib" | sudo tee /etc/apt/sources.list.d/erlang.list
echo "deb https://packagecloud.io/rabbitmq/rabbitmq-server/ubuntu/ $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/rabbitmq.list

## 1. Install RabbitMQ on Ubuntu 24.04

Follow the official RabbitMQ guide for Ubuntu 24.04:

```bash
# Install dependencies
sudo apt-get install -y curl gnupg apt-transport-https

# Add RabbitMQ signing key
curl -1sLf "https://keys.openpgp.org/vks/v1/by-fingerprint/0A9AF2115F4687BD29803A206B73A36E6026DFCA" \
   | sudo gpg --dearmor \
   | sudo tee /usr/share/keyrings/com.rabbitmq.team.gpg > /dev/null

# Add the correct apt sources for Ubuntu 24.04
sudo tee /etc/apt/sources.list.d/rabbitmq.list <<'EOF'
## Modern Erlang/OTP releases
##
deb [arch=amd64 signed-by=/usr/share/keyrings/com.rabbitmq.team.gpg] https://deb1.rabbitmq.com/rabbitmq-erlang/ubuntu/noble noble main
deb [arch=amd64 signed-by=/usr/share/keyrings/com.rabbitmq.team.gpg] https://deb2.rabbitmq.com/rabbitmq-erlang/ubuntu/noble noble main

## Latest RabbitMQ releases
##
deb [arch=amd64 signed-by=/usr/share/keyrings/com.rabbitmq.team.gpg] https://deb1.rabbitmq.com/rabbitmq-server/ubuntu/noble noble main
deb [arch=amd64 signed-by=/usr/share/keyrings/com.rabbitmq.team.gpg] https://deb2.rabbitmq.com/rabbitmq-server/ubuntu/noble noble main
EOF

# Update and install Erlang + RabbitMQ
sudo apt-get update -y

# Install Erlang
sudo apt-get install -y erlang-base \
   erlang-asn1 erlang-crypto erlang-eldap erlang-ftp erlang-inets \
   erlang-mnesia erlang-os-mon erlang-parsetools erlang-public-key \
   erlang-runtime-tools erlang-snmp erlang-ssl \
   erlang-syntax-tools erlang-tftp erlang-tools erlang-xmerl

# Install RabbitMQ
sudo apt-get install -y rabbitmq-server --fix-missing
```

RabbitMQ will start automatically.

### 2. Verify and enable management UI

Check status:

```bash
sudo systemctl status rabbitmq-server
```

Enable the management plugin:

```bash
sudo rabbitmq-plugins enable rabbitmq_management
sudo systemctl restart rabbitmq-server
```

Open in browser:

http://localhost:15672

---

---

## 2. Generate SSL Certificates

Use the provided script to generate the required certificates:

```bash
bash generate_certs.sh
```

This will generate the CA, server, and client certificates and keys.

---

## 3. Configure RabbitMQ for SSL

1. **Create SSL directory:**
   ```bash
   sudo mkdir -p /etc/rabbitmq/ssl
   ```
2. **Copy certificates:**
   ```bash
   sudo cp certs/ca_certificate.pem certs/server_certificate.pem certs/server_key.pem /etc/rabbitmq/ssl/
   sudo chown rabbitmq:rabbitmq /etc/rabbitmq/ssl/*
   sudo chmod 600 /etc/rabbitmq/ssl/server_key.pem
   ```
3. **Edit RabbitMQ config:**
   Edit `/etc/rabbitmq/rabbitmq.conf` and add:
   ```
   listeners.ssl.default = 5671
   ssl_options.cacertfile = /etc/rabbitmq/ssl/ca_certificate.pem
   ssl_options.certfile   = /etc/rabbitmq/ssl/server_certificate.pem
   ssl_options.keyfile    = /etc/rabbitmq/ssl/server_key.pem
   ssl_options.verify     = verify_peer
   ssl_options.fail_if_no_peer_cert = true
   ```
4. **Restart RabbitMQ:**
   ```bash
   sudo systemctl restart rabbitmq-server
   ```

---

## 4. Place Certificates

- The server certificates should be in `/etc/rabbitmq/ssl/` as shown above.
- The client certificates (`client_certificate.pem`, `client_key.pem`, and `ca_certificate.pem`) will be used by the Python script.

---

## 5. Verify Two-Way Authentication

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
2. **Run the client script:**
   ```bash
   python3 rabbitmq_client.py
   ```
   The script will connect to RabbitMQ using the client certificate for authentication (no username/password required).

---

## References
- [RabbitMQ SSL Guide](https://www.rabbitmq.com/ssl.html)
- [pika Python client](https://pika.readthedocs.io/en/stable/)

---

**Note:**
- Ensure firewall allows port 5671.
- For troubleshooting, check RabbitMQ logs in `/var/log/rabbitmq/`.
