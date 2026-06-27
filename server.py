import socket
import os
import mimetypes
import sys
from urllib.parse import unquote
import random

if len(sys.argv) < 2:
    port = 3000
else:
    if str.isdigit(sys.argv[1]):
        port = int(sys.argv[1])
    else:
        port = 3000

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(('', port))
sock.listen()

print("Listening on port", port)

while True:
    files = os.listdir('.')
    conn, addr = sock.accept()
    print("New connection from", addr)

    request = conn.recv(4096).decode()
    print(request)

    lines = request.split("\r\n")
    first_line = lines[0]
    parts = first_line.split(" ")
    path = unquote(parts[1])

    cookies = {}
    for line in lines:
        if line.startswith("Cookie:"):
            cookie_line = line.split(":", 1)[1].strip()
            for pair in cookie_line.split(";"):
                if "=" in pair:
                    k, v = pair.strip().split("=", 1)
                    cookies[k] = v
    color = cookies.get("color", "white")
    chunked = cookies.get("chunked", "0") == "1"
    max_chunk = int(cookies.get("max_chunk", "1024"))
    random_chunks = cookies.get("random", "0") == "1"
    
    if path == "/settings":
        body = """
        <html>
        <body>
            <h2>Set The  Background Color</h2>
            <form method="GET" action="/setcolor">
                Color: <input type="text" name="color"><br>
                Chunked: <input type="checkbox" name="chunked"><br>
                Max Chunk Size: <input type="text" name="max_chunk"><br>
                Random Chunk Size: <input type="checkbox" name="random"><br>
                Make settings permanent: <input type="checkbox" name="permanent"><br>
                <input type="submit" value="Submit">
            </form>
        </body>
        </html>
        """
    
        response = "HTTP/1.1 200 OK\r\n"
        response += "Content-Type: text/html\r\n"
        response += f"Content-Length: {len(body)}\r\n"
        response += "Connection: close\r\n\r\n"
        response += body
    
        conn.send(response.encode())
        conn.close()
        continue
    if path.startswith("/setcolor"):
        if "?" in path:
            query = path.split("?", 1)[1]
        else:
            query = ""
    
        params = {}
        if query:
            pairs = query.split("&")
            for p in pairs:
                if "=" in p:
                    k, v = p.split("=", 1)
                    params[k] = v
    
        color = params.get("color", "white")
        persistent = params.get("persistent") == "on"
        chunked = params.get("chunked") == "on"
        max_chunk = params.get("max_chunk", "1024")
        if max_chunk:
            max_chunk = int(max_chunk)
        else:
            max_chunk = 0
        random_chunks = params.get("random") == "on"
        permanent = params.get("permanent") == "on"
        
    
        cookies = []
        
        cookies.append(f"color={color}; Path=/")
        cookies.append(f"chunked={int(chunked)}; Path=/")
        cookies.append(f"max_chunk={max_chunk}; Path=/")
        cookies.append(f"random={int(random_chunks)}; Path=/")
        
        if permanent:                                                # if persistent:
            for i in range(len(cookies)):                            #     cookie += "; Max-Age=864000"  # 10 days                          
                cookies[i] += "; Max-Age=2592000"  # 30 days
    
        body = "<html><head><link rel=\"icon\" type=\"image/png\" href=\"https://lehman.edu/favicon.png\"/></head>"
        body += "<body><h2>Color saved!</h2><a href='/'>Go back</a></body></html>"
    
        response = "HTTP/1.1 200 OK\r\n"
        response += "Content-Type: text/html\r\n"
        response += f"Content-Length: {len(body)}\r\n"
        for cookie in cookies:
            response += f"Set-Cookie: {cookie}\r\n"
        response += "Connection: close\r\n\r\n"
        response += body
    
        conn.send(response.encode())
        conn.close()
        continue
        
    content_type = "text/html"
    filename = os.path.join(".", path.lstrip("/"))
    if os.path.isfile(filename):
        print("Requested file:", filename)
        
        with open(filename, "rb") as f:
            body = f.read()
        if '.' in filename:
            ext = '.' + filename.split('.')[-1]
        else:
            ext = "application/octet-stream"
        content_type = mimetypes.types_map.get(ext, "application/octet-stream")
        
    elif os.path.isdir(filename):
        print("Requested directory:", filename)
        items = os.listdir(filename)

        color = cookies.get("color", "white")
        body = f"<html><head><link rel=\"icon\" type=\"image/png\" href=\"https://lehman.edu/favicon.png\"/></head>"
        body += f"<body bgcolor='{color}'>"
        body += f"<h1>Directory Listing for {filename}</h1>"
        body += f"<p><b>(chunked={chunked}, max_chunk={max_chunk}, random={random_chunks})</b></p>"
        
        for f in items:
            body += f'<a href="/{filename}/{f}">{f}</a><br>'

        body += "</body></html>"
    else:
        print("File not found:", filename)
        body = '<h1>404 Not Found</h1>'
        response = "HTTP/1.1 404 Not Found\r\n"
        response += "Content-Type: text/html\r\n"
        response += f"Content-Length: {len(body)}\r\n"
        response += "Connection: close\r\n"
        response += "\r\n"
        response += body
        conn.send(response.encode())
        conn.close()
        continue
    
    response = "HTTP/1.1 200 OK\r\n"
    response += f"Content-Type: {content_type}\r\n"
    if chunked:
        response += "Transfer-Encoding: chunked\r\n"
    else:
        response += f"Content-Length: {len(body)}\r\n"
    response += "Connection: close\r\n"
    response += "\r\n"
    
    if chunked:
        conn.send(response.encode())
        if not isinstance(body, bytes):
            body = body.encode()

        i = 0
        length = len(body)

        while i < length:
            if random_chunks:
                chunk_size = random.randint(1, max_chunk)
            else:
                chunk_size = max_chunk

            chunk = body[i:i+chunk_size]
            actual_size = len(chunk)

            conn.send(f"{actual_size:x}\r\n".encode())

            conn.send(chunk + b"\r\n")

            i += actual_size

        conn.send(b"0\r\n\r\n")
    else:
        if isinstance(body, bytes):
            conn.send(response.encode() + body)
        else:
            conn.send((response + body).encode())
            
    conn.close()

    print("Requested path:", path)
