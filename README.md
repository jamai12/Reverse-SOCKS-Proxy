# How reverse Socks proxy work
I often encountered situations where i needed a proxy for pivoting but the biggest challenge was that most proxies were easily detected even after obfuscating and modifying their signatures, they remained difficult to evade advanced EDR solutions and enterprise security measures.

So, i thought why not create my own proxy and fully understand how it works? for that i started by researching and then jumped straight into developing a simple reverse proxy using Python, i initially used Python because it’s easy to prototype and test ideas and once i had a working version, i applied the same logic and structure to develop a more advanced version in C#, using HTTPS protocol....

I've tried to explain each line of code as clearly as possible and for a deeper understanding visit my blog [link](https://blog.hack-notes.pro/posts/Build-your-own-Socks-Proxy/)
