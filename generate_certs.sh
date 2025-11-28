#!/usr/bin/env sh

DIR=tls-certs
mkdir -p "$DIR"

# Detect hostname and allow IP override via env SERVER_IP
HOSTNAME="$(hostname -f 2>/dev/null || hostname)"
SERVER_IP="${SERVER_IP:-127.0.0.1}"

# OpenSSL config for CSR with CN=hostname and SANs (server)
cat > "$DIR/openssl-server.cnf" <<EOF
[ req ]
default_bits        = 2048
prompt              = no
distinguished_name = req_distinguished_name
req_extensions     = v3_req

[ req_distinguished_name ]
CN = $HOSTNAME

[ v3_req ]
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names


[ alt_names ]
DNS.1 = localhost
DNS.2 = $HOSTNAME
IP.1  = $SERVER_IP
EOF

# OpenSSL config for client CSR with CN=rabbit-client and SANs
cat > "$DIR/openssl-client.cnf" <<EOF
[ req ]
default_bits        = 2048
prompt              = no
distinguished_name = req_distinguished_name
req_extensions     = v3_req

[ req_distinguished_name ]
CN = rabbit-client

[ v3_client ]
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = clientAuth
subjectAltName = @alt_names


[ alt_names ]
DNS.1 = localhost
DNS.2 = $HOSTNAME
IP.1  = $SERVER_IP
EOF

# 1. Create CA key and cert(proper CA extensions)
openssl genrsa -out "$DIR/ca.key.pem" 4096
openssl req -x509 -new -nodes -key "$DIR/ca.key.pem" -sha256 -days 365 \
    -out "$DIR/ca.cert.pem" -subj "/CN=LocalRabbitMQCA" \
    -addext "basicConstraints=critical,CA:true,pathlen:0" \
    -addext "keyUsage=critical,cRLSign,keyCertSign"

# 2. Server key and CSR with SANs (CN=$HOSTNAME)
openssl genrsa -out "$DIR/server.key.pem" 2048
openssl req -new -key "$DIR/server.key.pem" -out "$DIR/server.csr.pem" \
    -config "$DIR/openssl-server.cnf"


# 3. Sign server cert with SANs
openssl x509 -req -in "$DIR/server.csr.pem" -CA "$DIR/ca.cert.pem" -CAkey "$DIR/ca.key.pem" \
    -CAcreateserial -out "$DIR/server.cert.pem" -days 365 -sha256 \
    -extensions v3_req -extfile "$DIR/openssl-server.cnf"
# Also write a .crt filename for server
cp "$DIR/server.cert.pem" "$DIR/server.crt.pem"

# 4. Client  key and CSR (CN=rabbit-client) with SANs
openssl genrsa -out "$DIR/client.key.pem" 2048
openssl req -new -key "$DIR/client.key.pem" -out "$DIR/client.csr.pem" \
    -config "$DIR/openssl-client.cnf"

# 5. Sign client cert (clientAuth) with SANs
openssl x509 -req -in "$DIR/client.csr.pem" -CA "$DIR/ca.cert.pem" -CAkey "$DIR/ca.key.pem" \
    -CAcreateserial -out "$DIR/client.cert.pem" -days 365 -sha256 \
    -extensions v3_client -extfile "$DIR/openssl-client.cnf"
# Also write a .crt filename for client
cp "$DIR/client.cert.pem" "$DIR/client.crt.pem"

# Tighen key permissions
chmod 600 "$DIR/"*.key.pem

printf "\nGenerated TLS certificates in ./%s/\n" "$DIR"
ls -l "$DIR"

printf "\n RabbitMQ config snippet (rabbitmq.conf):\n"
cat <<'EOF'
listeners.ssl.default = 5671
ssl_options.cacertfile = $DIR/ca.cert.pem
ssl_options.certfile   = $DIR/server.cert.pem
ssl_options.keyfile    = $DIR/server.key.pem
ssl_options.verify     = verify_peer
ssl_options.fail_if_no_peer_cert = true
auth_mechanisms.1 = EXTERNAL
EOF

printf "\n client environment variables example:\n"
cat <<EOF
export RABBITMQ_USE_TLS=true
export RABBITMQ_PORT=5671
export RABBITMQ_CA_CERT=$(pwd)/tls-certs/ca.cert.pem
export RABBITMQ_CLIENT_CERT=$(pwd)/tls-certs/client.cert.pem
export RABBITMQ_CLIENT_KEY=$(pwd)/tls-certs/client.key.pem
export RABBITMQ_SERVER_HOSTNAME="$HOSTNAME"
EOF

printf "\n Tip: set SERVER_IP to include your  VM IP in SANs, then regenerate certs.\n\n"
printf " export SERVER_IP=%s && sh ./generate_certs.sh\n\n" "$SERVER_IP"


# Sanity checks
[ -s "$DIR/client.cert.pem"] || { echo "Client cert missing"; exit 1; }
[ -s "$DIR/server.cert.pem"] || { echo "Server cert missing"; exit 1; }
