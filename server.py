import threading
import socket
import sys
import select
import time

TIMEOUT = 10  # seconds for select() timeout

# Global lock to ensure that only one proxychains session uses the persistent client socket at a time.
client_lock = threading.Lock()

def handle_socks5(proxychains_socket, client_socket):
    """
    This function runs in its own thread for each incoming proxychains connection.
    It waits (blocks) until the persistent client socket is available, then performs
    a bidirectional relay (using select) between proxychains and the client.
    """
    print("[*] New SOCKS5 session arrived; waiting for exclusive access to persistent client connection.")
    # Acquire the lock in blocking mode. (This means the new proxychains session will wait rather than be dropped.)
    client_lock.acquire()
    print("[*] Acquired exclusive access to persistent client connection for this session.")
    try:
        while True:
            # Monitor the proxychains socket and the persistent client socket.
            readable, _, _ = select.select([proxychains_socket, client_socket], [], [], TIMEOUT)

            if not readable:
                print("[-] Timeout: no activity for 10 seconds. Ending this proxychains session.")
                break

            # Data coming from proxychains
            if proxychains_socket in readable:
                data = proxychains_socket.recv(65536)
                if not data:
                    print("[-] Proxychains disconnected. Ending session.")
                    break
                try:
                    client_socket.sendall(data)
                    print(f"[*] Relayed to client: {data}")
                except Exception as e:
                    print(f"[!] Error sending data to client: {e}")
                    break

            # Data coming from the persistent client
            if client_socket in readable:
                data = client_socket.recv(4096)
                if not data:
                    print("[-] Persistent client disconnected. Ending session.")
                    break
                try:
                    proxychains_socket.sendall(data)
                    print(f"[*] Relayed to proxychains: {data}")
                except Exception as e:
                    print(f"[!] Error sending data to proxychains: {e}")
                    break

    except Exception as e:
        print(f"[!] Exception in session: {e}")

    finally:
        try:
            proxychains_socket.close()
        except Exception:
            pass
        print("[-] Closed proxychains connection for this session.")
        client_lock.release()
        print("[*] Released persistent client connection for waiting sessions.")

def start_server():
    # Listen for the persistent client connection.
    port = int(sys.argv[1])
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("0.0.0.0", port))
    server_socket.listen(5)
    print(f"[+] Listening on 0.0.0.0:{port} for persistent client connection...")

    client_socket, client_addr = server_socket.accept()
    print(f"[+] Accepted persistent client connection from {client_addr}")

    # Listen for incoming SOCKS5 connections from proxychains on 127.0.0.1:1080.
    server_proxy = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_proxy.bind(("127.0.0.1", 1080))
    server_proxy.listen(5)
    print("[+] SOCKS5 proxy listening on 127.0.0.1:1080 for proxychains connections")

    while True:
        try:
            proxychains_socket, proxy_addr = server_proxy.accept()
            print(f"[+] Accepted SOCKS5 connection from proxychains at {proxy_addr}")

            # Spawn a new thread to handle this SOCKS5 session.
            t = threading.Thread(target=handle_socks5, args=(proxychains_socket, client_socket))
            t.daemon = True
            t.start()

        except Exception as e:
            print(f"[!] Error in main server loop: {e}")
            time.sleep(1)

if __name__ == "__main__":
    start_server()
