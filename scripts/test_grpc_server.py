#!/usr/bin/env python3
"""
Test that the gRPC server on port 50051 is running and ListVirtualAgents works.

Usage (from project root):
  python scripts/test_grpc_server.py
  python scripts/test_grpc_server.py --port 50051 --host 127.0.0.1

Port 50051 is gRPC, not HTTP - a browser cannot talk to it. This script
calls the ListVirtualAgents RPC to verify the server is up and the endpoint
is accessible.
"""
import argparse
import sys
from pathlib import Path

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

def main():
    parser = argparse.ArgumentParser(description="Test gRPC server on port 50051")
    parser.add_argument("--host", default="127.0.0.1", help="Gateway host")
    parser.add_argument("--port", type=int, default=50051, help="Gateway gRPC port")
    args = parser.parse_args()

    try:
        import grpc
        from src.generated.byova_common_pb2 import ListVARequest, ListVAResponse
        from src.generated.voicevirtualagent_pb2_grpc import VoiceVirtualAgentStub
    except ImportError as e:
        print(f"ERROR: Import failed: {e}")
        print("Run from project root: python scripts/test_grpc_server.py")
        sys.exit(1)

    address = f"{args.host}:{args.port}"
    print(f"Testing gRPC server at {address} ...")
    print("(Port 50051 is gRPC, not HTTP - browsers cannot connect to it.)")
    print()

    try:
        channel = grpc.insecure_channel(address)
        stub = VoiceVirtualAgentStub(channel)
        request = ListVARequest(customer_org_id="test-org", is_default_virtual_agent_enabled=True)
        response = stub.ListVirtualAgents(request, timeout=5.0)
    except grpc.RpcError as e:
        print(f"FAILED: gRPC error: {e.code()} - {e.details()}")
        if e.code() == grpc.StatusCode.UNAVAILABLE:
            print(f"  -> Server not running or not reachable at {address}")
            print("  -> Start the gateway with: python main.py")
        sys.exit(1)
    except Exception as e:
        print(f"FAILED: {e}")
        sys.exit(1)

    agents = list(response.virtual_agents) if response.virtual_agents else []
    print(f"OK: Server is running and ListVirtualAgents responded.")
    print(f"    Agents returned: {len(agents)}")
    for a in agents:
        print(f"      - {a.virtual_agent_name} (id: {a.virtual_agent_id})")
    print()
    print("gRPC endpoint is accessible. You can use the gateway from Webex.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
