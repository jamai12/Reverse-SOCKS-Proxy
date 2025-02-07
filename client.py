import threading
import struct
import sys
import socket
import time

# Server (proxy) details
SERVER_IP = "192.168.213.138"  # Remote proxy server IP
SERVER_PORT = int(sys.argv[1])  # Remote proxy server port from command-line argument

def forward_traffic(proxy_socket, destination_socket, initial_data, dest_address, dest_port):
    """
    Forwards data from the proxy to the destination and vice versa.
    When a reconnection signal (b"\x05\x01\x00") is received from the proxy,
    this function returns so that a new target connection can be established.
    """
    data = initial_data
    while True:
        if not data:
            print("[-] No data received from proxy. Closing destination connection.")
            break

        # Forward data from proxy to target (destination)
        try:
            destination_socket.sendall(data)
            print("[+] Data forwarded to destination.")
        except Exception as e:
            print(f"[-] Error while sending data to destination: {e}")
            break

        # Receive response from destination
        try:
            response = destination_socket.recv(4096)
            if not response:
                print("[-] No response from destination. Closing connection.")
                break
            print(f"[+] Received response from destination: {response}")
        except socket.timeout:
            print("[-] Timeout while receiving from destination. Closing connection.")
            break
        except Exception as e:
            print(f"[-] Error while receiving from destination: {e}")
            break

        # Send the destination's response back to the proxy
        try:
            proxy_socket.sendall(response)
            print("[+] Response forwarded to proxy.")
        except Exception as e:
            print(f"[-] Error while sending response to proxy: {e}")
            break

        # Wait for further data from proxy (with timeout)
        try:
            proxy_socket.settimeout(5)
            data = proxy_socket.recv(4096)
        except socket.timeout:
            print("[-] Timeout while receiving from proxy. Closing connection.")
            break
        except Exception as e:
            print(f"[-] Error while receiving data from proxy: {e}")
            break

        # If the proxy sends a reconnection signal, end this forwarding session
        if data == b"\x05\x01\x00":
            print("[*] Reconnection signal received from proxy. Preparing to reconnect to target.")
            try:
                destination_socket.close()
            except Exception:
                pass
            return proxy_socket, data

    print("[*] Traffic forwarding ended.")
    try:
        destination_socket.close()
    except Exception:
        pass
    return proxy_socket, None


def extract_address_port(proxy_socket, dummy_data):
    """
    Performs the SOCKS5 handshake over the persistent proxy connection.
    Returns the target (destination) address, port, and the same proxy_socket.
    This function does not close the proxy connection.
    """
    try:
        # Wait indefinitely for the greeting from the proxy
        proxy_socket.settimeout(None)
        # Receive exactly 3 bytes (greeting)
        greeting = proxy_socket.recv(3)
    except Exception as e:
        print(f"[-] Error receiving greeting from proxy: {e}")
        return proxy_socket, None, None

    print(f"[+] Received SOCKS5 greeting from proxy: {greeting}")

    if greeting != b"\x05\x01\x00":
        print("[-] Unexpected SOCKS5 greeting. Expected b'\\x05\\x01\\x00'.")
        return proxy_socket, None, None

    # Send method selection (no authentication)
    try:
        proxy_socket.sendall(b"\x05\x00")
    except Exception as e:
        print(f"[-] Error sending method selection: {e}")
        return proxy_socket, None, None

    # Get the connection request (first 4 bytes)
    try:
        conn_request = proxy_socket.recv(4)
    except Exception as e:
        print(f"[-] Error receiving connection request: {e}")
        return proxy_socket, None, None

    if len(conn_request) < 4 or conn_request[0] != 0x05 or conn_request[1] != 0x01:
        print(f"[-] Unsupported or malformed SOCKS5 command: {conn_request}")
        return proxy_socket, None, None

    try:
        address_type = conn_request[3]
    except Exception as e:
        print(f"[-] Exception reading address type: {e}")
        return proxy_socket, None, None

    if address_type == 0x01:  # IPv4
        try:
            addr_bytes = proxy_socket.recv(4)
            dest_address = socket.inet_ntoa(addr_bytes)
        except Exception as e:
            print(f"[-] Error receiving IPv4 address: {e}")
            return proxy_socket, None, None
    elif address_type == 0x03:  # Domain name
        try:
            domain_length = proxy_socket.recv(1)[0]
            dest_address = proxy_socket.recv(domain_length).decode('utf-8')
        except Exception as e:
            print(f"[-] Error receiving domain name: {e}")
            return proxy_socket, None, None
    else:
        print("[-] Unsupported address type received.")
        return proxy_socket, None, None

    try:
        port_bytes = proxy_socket.recv(2)
        dest_port = struct.unpack('!H', port_bytes)[0]
    except Exception as e:
        print(f"[-] Error receiving port: {e}")
        return proxy_socket, None, None

    print(f"[+] Extracted destination: {dest_address}:{dest_port}")
    return proxy_socket, dest_address, dest_port


def handle_persistent_tunnel(proxy_socket):
    """
    Runs in a dedicated thread.
    Continuously intercepts SOCKS5 connection requests arriving over the persistent
    proxy connection, establishes a target connection, and then forwards traffic.
    The proxy connection remains open across successive sessions.
    """
    while True:
        # Perform SOCKS5 handshake to extract destination address/port.
        proxy_socket, dest_address, dest_port = extract_address_port(proxy_socket, None)
        if dest_address is None or dest_port is None:
            print("[-] Failed to extract destination. Waiting before retrying handshake...")
            time.sleep(2)
            continue

        # Connect to the target (destination) machine.
        print(f"[*] Connecting to destination {dest_address}:{dest_port}")
        destination_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        destination_socket.settimeout(5)
        try:
            destination_socket.connect((dest_address, dest_port))
            print(f"[+] Connected to destination {dest_address}:{dest_port}")
        except (socket.timeout, ConnectionRefusedError, Exception) as e:
            print(f"[-] Failed to connect to destination {dest_address}:{dest_port}: {e}")
            try:
                proxy_socket.sendall(b"\x05\x01")  # Send SOCKS5 failure response.
            except Exception:
                pass
            continue  # Do not close the persistent proxy connection; try next handshake.

        # Send a success response back to the proxy.
        try:
            success_response = b"\x05\x00\x00\x01" + socket.inet_aton("127.0.0.1") + struct.pack("!H", 1080)
            proxy_socket.sendall(success_response)
            print("[+] Sent SOCKS5 success response to proxy.")
        except Exception as e:
            print(f"[-] Error sending success response: {e}")
            destination_socket.close()
            continue

        # Get initial data from the proxy for forwarding.
        try:
            data = proxy_socket.recv(4096)
            print(f"[+] Received initial data from proxy: {data}")
        except Exception as e:
            print(f"[-] Error receiving initial data: {e}")
            destination_socket.close()
            continue

        # Spawn a thread for forwarding traffic between proxy and destination.
        # (You can remove the extra thread if you want the forwarding to happen in this same thread.)
        forward_thread = threading.Thread(
            target=forward_traffic,
            args=(proxy_socket, destination_socket, data, dest_address, dest_port)
        )
        forward_thread.start()
        forward_thread.join()  # Wait until the forwarding session ends.
        print("[*] Forwarding session ended; waiting for new SOCKS5 connection request on persistent tunnel.")
        # The persistent proxy connection remains open. Loop back to wait for the next handshake.

def start_client():
    """
    Establishes a single persistent connection to the proxy server and spawns a thread
    to handle all incoming SOCKS5 requests over that tunnel.
    """
    # Establish connection with the proxy server
    while True:
        try:
            proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            proxy_socket.connect((SERVER_IP, SERVER_PORT))
            print(f"[+] Connected to proxy server at {SERVER_IP}:{SERVER_PORT}")
            break
        except Exception as e:
            print(f"[-] Error connecting to proxy server: {e}. Retrying in 5 seconds...")
            time.sleep(5)

    # Spawn the persistent tunnel handler thread.
    tunnel_thread = threading.Thread(target=handle_persistent_tunnel, args=(proxy_socket,))
    tunnel_thread.daemon = True
    tunnel_thread.start()

    # Keep the main thread alive.
    while True:
        time.sleep(10)

if __name__ == "__main__":
    start_client()
