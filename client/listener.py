import socketserver
import re

PORT = 31337


class TCPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request.recv(512*1024).strip()
        client_ip = self.client_address[0]
        match_num = re.findall(b'\/team(\d+)', data)
        if match_num:
            match_num = match_num[0].decode()
            actual_addr = f'10.0.0.{match_num}'
        else:
            actual_addr = '0.0.0.0'
        print(f'SPLOIT_TEAM_{actual_addr}')
        print(data, flush=True)


if __name__ == '__main__':
    with socketserver.TCPServer(('0.0.0.0', PORT), TCPHandler) as server:
        server.serve_forever()
