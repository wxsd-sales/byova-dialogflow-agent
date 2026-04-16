#!/usr/bin/env python3
"""
Check if a BYOVA gateway URL is reachable from THIS machine (TCP + optional gRPC).

- https:// URLs (e.g. ngrok: https://xxx.ngrok-free.dev) use port 443 and TLS for gRPC.
- Plain hostnames or http:// use port 50051 by default (direct gRPC).

Usage:
  python scripts/check_gateway_reachable.py https://customer-gateway.company.com --grpc
  python scripts/check_gateway_reachable.py https://xxx.ngrok-free.dev --grpc
  python scripts/check_gateway_reachable.py customer-gateway.company.com --port 50051 --grpc
  python scripts/check_gateway_reachable.py customer-gateway.company.com --port 50051 --grpc --tls
"""
import argparse
import socket
import sys
from urllib.parse import urlparse

def parse_host_port(url_or_host: str, default_port: int) -> tuple:
    """Return (host, port). For https:// URLs without port use 443 (e.g. ngrok); else default_port."""
    s = url_or_host.strip()
    if "://" in s:
        parsed = urlparse(s)
        host = parsed.hostname or parsed.path.split("/")[0] or s
        if parsed.port is not None:
            return host, parsed.port
        # https://host -> 443 (ngrok, load balancers); http://host -> 80; else use default
        if parsed.scheme and parsed.scheme.lower() == "https":
            return host, 443
        if parsed.scheme and parsed.scheme.lower() == "http":
            return host, 80
        return host, default_port
    return s, default_port

def tcp_check(host: str, port: int, timeout: float = 5.0) -> bool:
    """Return True if TCP connect succeeds from this machine."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, port))
            return True
    except (socket.error, socket.timeout, OSError) as e:
        print(f"  TCP error: {e}")
        return False

def grpc_check(host: str, port: int, timeout: float = 5.0, use_tls: bool = False) -> bool:
    """Return True if gRPC ListVirtualAgents succeeds. use_tls=True for port 443 (e.g. ngrok)."""
    try:
        import grpc
        from pathlib import Path
        project_root = Path(__file__).resolve().parent.parent
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
        from src.generated.byova_common_pb2 import ListVARequest
        from src.generated.voicevirtualagent_pb2_grpc import VoiceVirtualAgentStub
    except ImportError as e:
        print(f"  gRPC check skipped (import error): {e}")
        return False

    try:
        if use_tls or port == 443:
            channel = grpc.secure_channel(
                f"{host}:{port}",
                grpc.ssl_channel_credentials(),
            )
        else:
            channel = grpc.insecure_channel(f"{host}:{port}")
        stub = VoiceVirtualAgentStub(channel)
        stub.ListVirtualAgents(ListVARequest(customer_org_id="test"), timeout=timeout)
        return True
    except grpc.RpcError as e:
        print(f"  gRPC error: {e.code()} - {e.details()}")
        return False
    except Exception as e:
        print(f"  gRPC error: {e}")
        return False

def main():
    ap = argparse.ArgumentParser(
        description="Check if a gateway host:port is reachable from this machine."
    )
    ap.add_argument(
        "url_or_host",
        help="Gateway URL or hostname (e.g. https://gateway.company.com or gateway.company.com)",
    )
    ap.add_argument("--port", type=int, default=50051, help="gRPC port (default 50051)")
    ap.add_argument("--grpc", action="store_true", help="Also call ListVirtualAgents (requires project)")
    ap.add_argument(
        "--tls",
        action="store_true",
        help="Use TLS for gRPC (e.g. grpcs on port 50051). Implied for https:// on port 443.",
    )
    ap.add_argument("--timeout", type=float, default=10.0, help="Timeout in seconds (default 10)")
    args = ap.parse_args()

    host, port = parse_host_port(args.url_or_host, args.port)
    use_tls_grpc = args.tls or port == 443
    print(f"Checking reachability from THIS MACHINE to: {host}:{port}")
    if port == 443:
        print("(Using port 443 / TLS for https:// URL; gRPC will use TLS.)")
    elif args.tls:
        print("(Using TLS for gRPC; cert must be trusted by system CA store.)")
    print("(Webex runs in the cloud; for agents to appear, the URL must be reachable from the internet.)")
    print()

    # TCP
    print("1. TCP connect ...", end=" ")
    if tcp_check(host, port, args.timeout):
        print("OK (port is open)")
    else:
        print("FAILED (port closed or blocked)")
        print()
        print("  -> From here, nothing is listening or a firewall is blocking.")
        print("  -> If this is the customer URL, Webex cannot reach it from the cloud either.")
        return 1

    if args.grpc:
        print("2. gRPC ListVirtualAgents ...", end=" ")
        if grpc_check(host, port, args.timeout, use_tls=use_tls_grpc):
            print("OK")
        else:
            print("FAILED")
            return 1

    print()
    print("Result: Reachable from this machine.")
    print("If you ran this from outside the customer network and it passed, the URL is open to the internet.")
    print("If you ran this from inside the customer network only, have someone outside run it (or use an online port checker) to confirm the URL is open from the internet.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
