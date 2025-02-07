# How reverse Socks proxy work
I often encountered situations where i needed a proxy for pivoting but the biggest challenge was that most proxies were easily detected even after obfuscating and modifying their signatures, they remained difficult to evade advanced EDR solutions and enterprise security measures.

So, i thought why not create my own proxy and fully understand how it works? for that i started by researching and then jumped straight into developing a simple reverse proxy using Python, i initially used Python because it’s easy to prototype and test ideas and once i had a working version, i applied the same logic and structure to develop a more advanced version in C#, using HTTPS protocol.

The result was a proxy that successfully bypassed multiple security solutions, including Kaspersky Endpoint and Windows Defender Endpoint etc.

Let’s dive in, i w'll start by explaining how a proxy server works.

A proxy server is responsible for handling connections from a client, establishing a persistent socket tunnel and maintaining the connection similar to a reverse shell. The client initiates a connection with the server on a specified port, while the server simultaneously listens for connections from ProxyChains. We can define where ProxyChains should initiate connections in its configuration file located in the `/etc` directory.

Once the server receives a connection from ProxyChains, it forwards it to the previously established tunnel with the client so the client then determines the connection type based on ProxyChains’ request and extracts the target IP address and port from the incoming packet. After extraction, the client creates a socket and initiates a direct connection with the target machine on the specified port, effectively establishing another tunnel within the internal network.

Once the client receives a response from the target machine, it forwards the data back to the proxy server via the persistent socket tunnel. To avoid socket pipe errors, the client closes its direct connection with the target machine but it maintains a connection with the proxy server. The server then forwards the received traffic to ProxyChains without modification, acting as a gateway. Since only the server communicates directly with ProxyChains, it continuously listens for new connections. If no data is received from ProxyChains for a certain period, the server closes the connection and returns to listening mode.
