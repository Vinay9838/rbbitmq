from __future__ import annotations
import os 
import ssl
from dataclasses import dataclass
from typing import Optional, Any
import errno

import pika

@dataclass
class RabbitMQConfig:
    host: str = os.getenv("RABBITMQ_HOST", "localhost")
    port: int = int(os.getenv("RABBITMQ_PORT", 5672))
    username: str = os.getenv("RABBITMQ_USERNAME", "guest")
    password: str = os.getenv("RABBITMQ_PASSWORD", "guest")
    virtual_host: str = os.getenv("RABBITMQ_VHOST", "/")
    queue_name: str = os.getenv("RABBITMQ_QUEUE", "rabbitmq_poc")
    heartbeat: int = int(os.getenv("RABBITMQ_HEARTBEAT", 60))
    blocked_connection_timeout: int = int(os.getenv("RABBITMQ_BLOCKED_CONNECTION_TIMEOUT", 300))
    use_tls: bool = os.getenv("RABBITMQ_USE_TLS", "false").lower() == "true"
    ca_cert: str | None = os.getenv("RABBITMQ_CA_CERT")
    client_cert: str | None = os.getenv("RABBITMQ_CLIENT_CERT")
    client_key: str | None = os.getenv("RABBITMQ_CLIENT_KEY")
    verify_peer: bool = os.getenv("RABBITMQ_VERIFY_PEER", "true").lower() == "true"
    server_hostname: str | None = os.getenv("RABBITMQ_SERVER_HOSTNAME")
    print("RABBITMQ_USE_TLS:", use_tls)


class RabbitMQClient:
    def __init__(self, config: Optional[RabbitMQConfig] = None) -> None:
        self.config = config or RabbitMQConfig()
        self._connection: Optional[pika.BlockingConnection] = None
        self._channel: Optional[pika.channel.Channel] = None

    def establish_connection(self) -> None:
        if self._connection and self._connection.is_open and self._channel and self._channel.is_open:
            return # Connection already established
        
        use_external = (
            self.config.use_tls
            and bool(self.config.client_cert)
            and bool(self.config.client_key)
            and self.config.verify_peer
        )
        if use_external:
            print("Using EXTERNAL authentication with client certificates.")
            credentials = pika.credentials.ExternalCredentials()
        else:
            credentials = pika.PlainCredentials(
                username=self.config.username,
                password=self.config.password
            )
        ssl_options = None
        if self.config.use_tls:
            def _check(path: Optional[str], label:str) -> None:
                if not path:
                    raise ValueError(f"{label} path not provided")
                if not os.path.isfile(path):
                    raise FileNotFoundError(errno.ENOENT, os.strerror(errno.ENOENT), path)
                if not os.access(path, os.R_OK):
                    raise PermissionError(errno.EACCES, os.strerror(errno.EACCES), path)
                
        
            _check(self.config.ca_cert, "CA certificate")
            context = ssl.create_default_context(cafile=self.config.ca_cert)
            if not self.config.verify_peer:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            if self.config.client_cert and self.config.client_key:
                _check(self.config.client_cert, "Client certificate")
                _check(self.config.client_key, "Client key")
                context.load_cert_chain(certfile=self.config.client_cert, keyfile=self.config.client_key)
            
            server_hostname = self.config.server_hostname or self.config.host
            ssl_options = pika.SSLOptions(context, server_hostname)

        params = pika.ConnectionParameters(
            host=self.config.host,
            port=self.config.port,
            virtual_host=self.config.virtual_host,
            credentials=credentials,
            heartbeat=self.config.heartbeat,
            blocked_connection_timeout=self.config.blocked_connection_timeout,
            ssl_options=ssl_options
        )
        self._connection = pika.BlockingConnection(params)
        self._channel = self._connection.channel()
        self._channel.queue_declare(queue=self.config.queue_name, durable=True)

    def publish_message(self, body:str | bytes, persistent:bool = True) -> None:
        if not self._channel or not self._channel.is_open:
            raise RuntimeError("Connection not established. Call establish_connection() first.")
        
        properties = pika.BasicProperties(
            delivery_mode=2 if persistent else 1
        )
        self._channel.basic_publish(
            exchange='',
            routing_key=self.config.queue_name,
            body=body,
            properties=properties
        )

    def get_message_count(self) -> int:
        if not self._channel or self._channel.is_closed:
            self.establish_connection()
        declare_ok = self._channel.queue_declare(
            queue=self.config.queue_name,
            passive=True
        )
        return declare_ok.method.message_count
    
    def close_connections(self) -> None:
        if self._channel and self._channel.is_open:
            try:
                self._channel.close()
            except Exception:
                pass
        if self._connection and self._connection.is_open:
            try:
                self._connection.close()
            except Exception:
                pass
        self._channel = None
        self._connection = None

    def health_check(self) -> bool:
        try:
            if not self._connection or self._connection.is_closed:
                self.establish_connection()
            self._channel.queue_declare(queue=self.config.queue_name, passive=True)
            return True
        except Exception:
            return False
        

    def tls_details(self) -> dict[str, Any]:
        if not self._connection or self._connection.is_closed:
            return {"tls": False}
        details: dict[str, Any] = {"tls": self.config.use_tls}

        try:
            transport = getattr(self._connection._impl, "transport", None)
            socket = getattr(transport, "_socket", None)
            if isinstance(socket, ssl.SSLSocket):
                details["tls"] = True
                details["cipher"] = socket.cipher()
                peercert = socket.getpeercert()
                if peercert:
                    details["peercert_subject"] = dict(x[0] for x in peercert.get("subject", ()))
                    details["peercert_issuer"] = peercert.get("subjectAltName")
                details["version"] = socket.version()
        except Exception:
            pass
        return details
    

if __name__ == "__main__":
    client = RabbitMQClient()
    client.establish_connection()
    client.publish_message("Hello, RabbitMQ!")
    count = client.get_message_count()
    print(f"Message count in queue '{client.config.queue_name}': {count}")
    tls_info = client.tls_details()
    print(f"TLS Details: {tls_info}")
    client.close_connections()
        

