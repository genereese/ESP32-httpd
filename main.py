import errno
import gc
import json
import network
import os
import socket
import sys


def readConfig():
    config = {}
    config_file = "config.json"
    try:
        with open(config_file, 'r') as file:
            config = json.load(file)
            if (config['wifi_name'] == "") or (config['wifi_password'] == ""):
                print(f"WiFi configuration is incomplete. Please update '{config_file}' with your credentials.")
                print(config)
                sys.exit()
            return config
    except OSError:
        # File does not exist; create a blank wifi.json file
        data = {"wifi_name": "", "wifi_password": ""}
        with open(config_file, 'w') as file:
            json.dump(data, file)
        print("ERROR: 'config.json' not found; created a blank config.json file. Please update it with your Wi-Fi credentials, etc.")
        sys.exit()
        
    except Exception as e:
        print(f"Error reading '{config_file}':", e)
        sys.exit()

# Helper functions to replace os.path methods
def exists(path):
    try:
        os.stat(path)
        return True
    except OSError:
        return False

def isDir(path):
    try:
        mode = os.stat(path)[0]
        return (mode & 0x4000) == 0x4000
    except OSError:
        return False

def isFile(path):
    try:
        mode = os.stat(path)[0]
        return (mode & 0x8000) == 0x8000
    except OSError:
        return False

def sanitizePath(path):
    # Remove any '..' or absolute path components
    return '/' + '/'.join(segment for segment in path.strip('/').split('/') if segment not in ('', '..'))

def dirname(path):
    # Custom implementation of os.path.dirname
    if path == '':
        return '/'
    parts = path.rstrip('/').split('/')
    if len(parts) > 1:
        return '/' + '/'.join(parts[:-1])
    else:
        return '/'

def basename(path):
    # Custom implementation of os.path.basename
    return path.rstrip('/').split('/')[-1]

def urlEncode(s):
    res = ''
    for c in s:
        ascii_code = ord(c)
        # Check if character is alphanumeric (digits 0-9, letters A-Z, a-z)
        if (48 <= ascii_code <= 57) or (65 <= ascii_code <= 90) or (97 <= ascii_code <= 122) or c in '-_.~/':
            res += c
        else:
            res += '%' + '{:02X}'.format(ascii_code)
    return res

def urlDecode(s):
    res = ''
    i = 0
    while i < len(s):
        if s[i] == '%':
            if i + 2 < len(s):
                try:
                    res += chr(int(s[i+1:i+3], 16))
                    i += 3
                except ValueError:
                    res += '%'
                    i += 1
            else:
                res += '%'
                i += 1
        else:
            res += s[i]
            i += 1
    return res

class WiFiConnection:

    def __init__(self, ssid, password):
        self.ssid = ssid
        self.password = password
        self.station = network.WLAN(network.STA_IF)
        self.connect()

    def connect(self):
        self.station.active(True)
        self.station.connect(self.ssid, self.password)
        print('Connecting to WiFi...')
        while not self.station.isconnected():
            pass
        print('Connection successful')
        print('Network config:', self.station.ifconfig())


class TemplateRenderer:

    def __init__(self, template_dir='./files/'):
        self.template_dir = template_dir

    def render(self, template_path, context={}):
        full_path = self.template_dir + template_path
        if not isFile(full_path):
            return None
        try:
            with open(full_path, 'r') as file:
                content = file.read()
            for key, value in context.items():
                placeholder = '{{ ' + key + ' }}'
                content = content.replace(placeholder, str(value))
                placeholder_nospace = '{{' + key + '}}'
                content = content.replace(placeholder_nospace, str(value))
            return content
        except Exception as e:
            print('Error rendering template:', e)
            return None


class FileManager:

    def __init__(self, base_dir='./files'):
        self.base_dir = base_dir.rstrip('/')
        base_dir = base_dir.lstrip('.').lstrip('/')
        # Check for files directory and create if required
        if (not 'files' in os.listdir()):
            os.mkdir('/files')
            print('Created /files directory')
        # Check for index.html and create if required
        file_path = '/files/index.html'
        if not 'index.html' in os.listdir('/files'):
            html_content = '<html><head><title>Home Page</title></head><body><h1>Home Page</h1>Data: {{ title }}<br><br><a href="/files">Edit Files</a></body></html>'
            with open(file_path, 'w') as f:
                f.write(html_content)
            print('Created /files/index.html')

    def listItems(self, path='/'):
        target_dir = self.base_dir + sanitizePath(path)
        if not isDir(target_dir):
            return []
        try:
            return os.listdir(target_dir)
        except Exception as e:
            print('Error listing items in', target_dir, ':', e)
            return []

    def listDirectories(self, path='/'):
        items = self.listItems(path)
        directories = []
        for item in items:
            item_path = path + '/' + item if path != '/' else '/' + item
            full_path = self.base_dir + sanitizePath(item_path)
            if isDir(full_path):
                directories.append(item)
        return directories

    def getAllDirectories(self, path='/', exclude=[]):
        directories = []
        items = self.listItems(path)
        for item in items:
            item_path = path + '/' + item if path != '/' else '/' + item
            full_path = self.base_dir + sanitizePath(item_path)
            if isDir(full_path) and item_path not in exclude:
                directories.append(item_path)
                # Recursively add subdirectories
                directories.extend(self.getAllDirectories(item_path, exclude))
        return directories

    def readFile(self, file_path):
        full_path = self.base_dir + sanitizePath(file_path)
        if not isFile(full_path):
            return None
        try:
            with open(full_path, 'rb') as file:
                return file.read()
        except Exception as e:
            print('Error reading file', full_path, ':', e)
            return None

    def saveFile(self, file_path, data):
        full_path = self.base_dir + sanitizePath(file_path)
        try:
            with open(full_path, 'wb') as file:
                file.write(data)
            print('File saved to:', full_path)
        except Exception as e:
            print('Error saving file', full_path, ':', e)

    def deleteItem(self, item_path):
        full_path = self.base_dir + sanitizePath(item_path)
        try:
            if isFile(full_path):
                os.remove(full_path)
                print('File deleted:', full_path)
            elif isDir(full_path):
                os.rmdir(full_path)
                print('Directory deleted:', full_path)
        except OSError as e:
            print('Error deleting item', full_path, ':', e)
            return "Directory not empty."
        except Exception as e:
            print('Unexpected error deleting item', full_path, ':', e)

    def renameItem(self, old_path, new_name):
        full_old_path = self.base_dir + sanitizePath(old_path)
        new_name = new_name.strip('/').replace('/', '_')  # Prevent directory traversal
        new_dir = dirname(full_old_path)
        full_new_path = new_dir + '/' + new_name
        try:
            if exists(full_old_path):
                os.rename(full_old_path, full_new_path)
                print('Renamed', full_old_path, 'to', full_new_path)
        except Exception as e:
            print('Error renaming item:', e)

    def createDirectory(self, dir_path):
        full_path = self.base_dir + sanitizePath(dir_path)
        try:
            if not exists(full_path):
                os.mkdir(full_path)
                print('Directory created:', full_path)
        except Exception as e:
            print('Error creating directory', full_path, ':', e)

    def moveItem(self, src_path, dest_dir):
        full_src_path = self.base_dir + sanitizePath(src_path)
        dest_dir_path = self.base_dir + sanitizePath(dest_dir)
        if exists(full_src_path) and exists(dest_dir_path):
            item_name = basename(src_path)
            full_dest_path = dest_dir_path + '/' + item_name
            print('Attempting to move:')
            print('Source:', full_src_path)
            print('Destination:', full_dest_path)
            try:
                os.rename(full_src_path, full_dest_path)
                print('Move successful.')
            except Exception as e:
                print('Error moving item:', e)
        else:
            print('Source or destination does not exist.')
            print('Source exists:', exists(full_src_path))
            print('Destination exists:', exists(dest_dir_path))


class HTTPServer:

    def __init__(self, port=80):
        self.address = ('', port)
        self.template_renderer = TemplateRenderer()
        self.file_manager = FileManager()
        self.socket = socket.socket()
        self.socket.bind(self.address)
        self.socket.listen(5)  # Increased backlog for better handling
        print('Server listening on port', port)
    
    def getContentType(self, file_path):
        if file_path.endswith('.html'):
            return 'text/html'
        elif file_path.endswith('.jpg') or file_path.endswith('.jpeg'):
            return 'image/jpeg'
        elif file_path.endswith('.png'):
            return 'image/png'
        elif file_path.endswith('.gif'):
            return 'image/gif'
        elif file_path.endswith('.css'):
            return 'text/css'
        elif file_path.endswith('.js'):
            return 'application/javascript'
        else:
            return 'application/octet-stream'


    def serveForever(self):
        while True:
            try:
                client_sock, client_addr = self.socket.accept()
                print('Client connected from', client_addr)
                self.handleClient(client_sock)
                gc.collect()
            except Exception as e:
                print('Error accepting client:', e)

    def handleClient(self, client_sock):
        try:
            # Read request line and headers
            header_data = b''
            while True:
                chunk = client_sock.recv(1024)
                if not chunk:
                    break
                header_data += chunk
                if b'\r\n\r\n' in header_data:
                    headers_end = header_data.find(b'\r\n\r\n') + 4
                    break

            if not header_data:
                print('No data received from client.')
                return

            header_text = header_data[:headers_end].decode('utf-8', 'ignore')
            lines = header_text.split('\r\n')
            request_line = lines[0]
            headers = {}
            for line in lines[1:]:
                if line == '':
                    continue
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip().lower()] = value.strip()

            method, path, params = self.parseRequestLine(request_line)
            print(f"Method: {method}, Path: {path}, Params: {params}")

            content_length = int(headers.get('content-length', 0))
            content_type = headers.get('content-type', '')
            print(f"Content-Length: {content_length}")

            # Now, for methods that have body (e.g., POST), need to handle body
            if method == 'POST':
                remaining_data = header_data[headers_end:]
                if path.startswith('/files/upload'):
                    # For file upload, pass socket and remaining data to handler
                    self.handleFileRequest(client_sock, method, path, params, headers, remaining_data)
                else:
                    # For other POST requests, read body into memory
                    body_data = remaining_data
                    bytes_to_read = content_length - len(remaining_data)
                    while bytes_to_read > 0:
                        chunk = client_sock.recv(1024)
                        if not chunk:
                            break
                        body_data += chunk
                        bytes_to_read -= len(chunk)
                    # Now pass body_data to handler
                    self.handleFileRequest(client_sock, method, path, params, headers, body_data)
            else:
                # For GET or other methods
                self.handleFileRequest(client_sock, method, path, params, headers, None)
        except Exception as e:
            print('Unhandled exception in handleClient:', e)
            self.sendResponse(client_sock, '<h1>Internal Server Error</h1>', content_type='text/html', status='500 Internal Server Error')
        finally:
            client_sock.close()
            print('Client socket closed')

    def parseRequestLine(self, request_line):
        parts = request_line.split(' ')
        if len(parts) >= 2:
            method = parts[0]
            full_path = parts[1]
            try:
                params = '?' + full_path.split('?')[1]
            except IndexError:
                params = ''
            # Remove query parameters from path
            path = full_path.split('?')[0]
            return method, path, params
        return 'GET', '/', ''  # Default values

    def sendResponse(self, client_sock, content, content_type='text/html', status='200 OK'):
        if isinstance(content, str):
            content = content.encode('utf-8')
        content_length = len(content)
        response_header = f'HTTP/1.1 {status}\r\nContent-Type: {content_type}\r\nContent-Length: {content_length}\r\nConnection: close\r\n\r\n'
        try:
            client_sock.send(response_header.encode('utf-8'))
            client_sock.send(content)
            print(f"Sent response with status {status}")
        except Exception as e:
            print('Error sending response:', e)
    
    def sendResponseStream(self, client_sock, content_generator, content_type='application/octet-stream', status='200 OK', content_length=None):
        headers = f'HTTP/1.1 {status}\r\nContent-Type: {content_type}\r\n'
        if content_length is not None:
            headers += f'Content-Length: {content_length}\r\n'
        headers += 'Connection: close\r\n\r\n'
        try:
            client_sock.send(headers.encode('utf-8'))
            for chunk in content_generator:
                client_sock.send(chunk)
            print(f"Sent streamed response with status {status}")
        except Exception as e:
            print('Error sending streamed response:', e)

    def streamFile(self, file_path, chunk_size=1024):
        try:
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        except Exception as e:
            print('Error streaming file:', e)

    def send404(self, client_sock):
        content = '<h1>404 - Page Not Found</h1>'
        self.sendResponse(client_sock, content, content_type='text/html', status='404 Not Found')

    def sendRedirect(self, client_sock, location):
        response_header = f'HTTP/1.1 303 See Other\r\nLocation: {location}\r\nContent-Length: 0\r\n\r\n'
        try:
            client_sock.send(response_header.encode('utf-8'))
            print(f"Redirected to {location}")
        except Exception as e:
            print('Error sending redirect:', e)

    def handleFileRequest(self, client_sock, method, path, params, headers, body):

        sub_path = sanitizePath(urlDecode(path[len('/files'):]))
        if (urlDecode(path).startswith("/files")):
            if method == 'GET':
                if path == '/':
                    context = {'title': 'Home Page'}
                    response = self.template_renderer.render('index.html', context)
                    if response:
                        self.sendResponse(client_sock, response)
                    else:
                        self.send404(client_sock)
                elif path.startswith('/files/delete/'):
                    item_path = sub_path[len('/delete'):]
                    item_path = urlDecode(item_path.split('?')[0])
                    print('Delete request for:', item_path)
                    self.file_manager.deleteItem(item_path.split('?')[0])
                    parent_dir = dirname(item_path)
                    self.sendRedirect(client_sock, '/files' + parent_dir)
                elif path.startswith('/files/rename/'):
                    item_path = sub_path[len('/rename'):]
                    item_path = urlDecode(item_path.split('?')[0])
                    print('Rename request for:', item_path)
                    self.showRenameForm(client_sock, item_path.split('?')[0])
                elif path.startswith('/files/create_dir/'):
                    dir_path = sub_path[len('/create_dir'):]
                    print('Create directory request for:', dir_path)
                    self.showCreateDirForm(client_sock, dir_path)
                elif path.startswith('/files/move/'):
                    item_path = sub_path[len('/move'):]
                    item_path = urlDecode(item_path.split('?')[0])
                    print('Move request for:', item_path)
                    self.showMoveSelection(client_sock, item_path.split('?')[0])
                elif path.startswith('/files/move_confirm'):
                    print("Move confirm request received.")
                    item_path = sub_path[len('/move_confirm'):]
                    item_path = urlDecode(item_path.split('?')[0])
                    if (params):
                        params_dict = self.parseQueryString(params.lstrip("?/"))
                        print("Params:", params_dict)
                        dest_dir = params_dict.get('dest_dir', '/')
                    else:
                        dest_dir = '/'
                    self.handleMoveConfirm(client_sock, item_path, dest_dir)
                elif isDir(self.file_manager.base_dir + sub_path):
                    print("Show file manager request received.")
                    self.showFileManager(client_sock, sub_path)

            elif method == 'POST':
                if path.startswith('/files/upload'):
                    current_dir = sub_path[len('/upload'):]
                    current_dir = sanitizePath(current_dir)
                    print('File upload to directory:', current_dir)
                    content_length = int(headers.get('content-length', 0))
                    self.handleFileUpload(client_sock, headers, current_dir, content_length, body)
                elif path.startswith('/files/rename/'):
                    item_path = sub_path[len('/rename'):]
                    print('Processing rename for:', item_path)
                    form_data = self.parseFormData(body)
                    if 'new_name' in form_data:
                        new_name = form_data['new_name']
                        self.file_manager.renameItem(item_path, new_name)
                        parent_dir = dirname(item_path)
                        self.sendRedirect(client_sock, '/files' + parent_dir)
                    else:
                        self.sendResponse(client_sock, '<h1>Rename failed</h1>', status='400 Bad Request')
                elif path.startswith('/files/create_dir/'):
                    dir_path = sub_path[len('/create_dir'):]
                    print('Processing create directory in:', dir_path)
                    form_data = self.parseFormData(body)
                    if 'dir_name' in form_data:
                        new_dir = dir_path + '/' + form_data['dir_name']
                        self.file_manager.createDirectory(new_dir)
                        self.sendRedirect(client_sock, '/files' + dir_path)
                    else:
                        self.sendResponse(client_sock, '<h1>Create directory failed</h1>', status='400 Bad Request')
                else:
                    self.send404(client_sock)
            else:
                self.send404(client_sock)
        else:
            print("Handle custom file received.")
            self.handleCustomPaths(client_sock, method, path)
    
    def handleCustomPaths(self, client_sock, method, path):
        if method != 'GET':
            self.send404(client_sock)
            return
    
        decoded_path = urlDecode(path)
        sanitized_path = sanitizePath(decoded_path)
        sanitized_path = sanitized_path.lstrip('/')
        if (len(sanitized_path) < 1):
            sanitized_path = "index"

        if (sanitized_path.find(".") < 0):
            sanitized_path = sanitized_path + '.html'

        full_file_path = self.file_manager.base_dir + '/' + sanitized_path
        full_file_path = sanitizePath(full_file_path)

        if isFile(full_file_path):
            content_type = self.getContentType(full_file_path)
            file_size = os.stat(full_file_path)[6]
            self.sendResponseStream(
                client_sock,
                self.streamFile(full_file_path),
                content_type=content_type,
                content_length=file_size
            )
        else:
            self.send404(client_sock)

    def handleFileUpload(self, client_sock, headers, current_dir, content_length, initial_data):
        try:
            print('Handling file upload...')
            print('Attempting to save to:', current_dir)
            gc.collect()
            print('Memory before upload:', gc.mem_free())

            if current_dir == '/':
                current_dir = '/files'

            content_type_header = headers.get('content-type', '')
            if 'multipart/form-data' not in content_type_header:
                print('Invalid Content-Type for upload:', content_type_header)
                self.sendResponse(client_sock, '<h1>Invalid form submission</h1>', status='400 Bad Request')
                return

            # Correct boundary parsing
            boundary = content_type_header.split('boundary=')[1].strip()
            boundary_bytes = boundary.encode('utf-8')
            print('Boundary:', boundary)

            # Define the boundary markers
            start_boundary = b'--' + boundary_bytes
            end_boundary = b'--' + boundary_bytes + b'--'

            bytes_read = len(initial_data)
            buffer = initial_data
            state = 'searching_start_boundary'
            filename = None
            f = None

            while True:
                while True:
                    if state == 'searching_start_boundary':
                        index = buffer.find(start_boundary)
                        if index != -1:
                            buffer = buffer[index + len(start_boundary):]
                            state = 'parsing_headers'
                        else:
                            if len(buffer) > len(start_boundary):
                                buffer = buffer[-len(start_boundary):]
                            break
                    elif state == 'parsing_headers':
                        headers_end = buffer.find(b'\r\n\r\n')
                        if headers_end != -1:
                            part_headers = buffer[:headers_end].decode('utf-8', 'ignore')
                            buffer = buffer[headers_end + 4:]
                            filename = self.parsePartHeaders(part_headers)
                            if filename:
                                if current_dir != '/files':
                                    current_dir = '/files' + current_dir

                                if not current_dir.endswith('/'):
                                    current_dir += '/'

                                save_path = current_dir + filename
                                print("Saving to:", save_path)
                                try:
                                    f = open(save_path, 'wb')
                                except Exception as e:
                                    print('Error opening file for writing:', e)
                                    self.sendResponse(client_sock, '<h1>File write error</h1>', status='500 Internal Server Error')
                                    return
                                state = 'writing_file'
                            else:
                                state = 'skipping_part'
                        else:
                            break
                    elif state == 'writing_file':
                        next_boundary_index = buffer.find(b'\r\n' + start_boundary)
                        end_boundary_index = buffer.find(b'\r\n' + end_boundary)
                        print(".", end="")
                        if next_boundary_index != -1:
                            f.write(buffer[:next_boundary_index])
                            f.close()
                            print()
                            print('File saved to:', save_path)
                            buffer = buffer[next_boundary_index + 2:]
                            state = 'parsing_headers'
                            filename = None
                            f = None
                        elif end_boundary_index != -1:
                            f.write(buffer[:end_boundary_index])
                            f.close()
                            print()
                            print('File saved to:', save_path)
                            buffer = buffer[end_boundary_index + 2:]
                            state = 'done'
                            break
                        else:
                            f.write(buffer)
                            buffer = b''
                            break
                    elif state == 'skipping_part':
                        next_boundary_index = buffer.find(b'\r\n' + start_boundary)
                        end_boundary_index = buffer.find(b'\r\n' + end_boundary)
                        if next_boundary_index != -1:
                            buffer = buffer[next_boundary_index + 2:]
                            state = 'parsing_headers'
                        elif end_boundary_index != -1:
                            buffer = buffer[end_boundary_index + 2:]
                            state = 'done'
                            break
                        else:
                            buffer = b''
                            break
                    elif state == 'done':
                        break
                    else:
                        print('Unknown state:', state)
                        self.sendResponse(client_sock, '<h1>Internal Server Error</h1>', status='500 Internal Server Error')
                        return
                if state == 'done':
                    break
                if bytes_read >= content_length:
                    # No more data to read
                    break
                else:
                    # Need to read more data from socket
                    try:
                        chunk = client_sock.recv(4096)
                    except OSError as e:
                        print('Socket error:', e)
                        if e.args[0] == errno.ETIMEDOUT:
                            print('Socket timed out while receiving data')
                            break
                        else:
                            raise
                    if not chunk:
                        break
                    bytes_read += len(chunk)
                    buffer += chunk

            # After the loop, handle any remaining data
            if f:
                if not f.closed:
                    # Write any remaining data in the buffer
                    f.write(buffer)
                    f.close()
                    print('File saved to:', save_path)
                state = 'done'

            print('Memory after upload:', gc.mem_free())
        except Exception as e:
            print('Error handling file upload:', e)
            self.sendResponse(client_sock, '<h1>File upload failed</h1>', status='500 Internal Server Error')
        finally:
            # Ensure file is closed
            if f and f is not None and not f.closed:
                f.close()
            self.sendRedirect(client_sock, current_dir)


    def parsePartHeaders(self, part_headers_text):
        lines = part_headers_text.split('\r\n')
        disposition = ''
        for line in lines:
            if line.lower().startswith('content-disposition:'):
                disposition = line
                break
        if 'filename="' in disposition:
            filename = disposition.split('filename="')[1].split('"')[0]
            filename = filename.replace('/', '').replace('\\', '')
            print('Filename:', filename)
            return filename
        else:
            return None

    def showFileManager(self, client_sock, current_dir):
        items = self.file_manager.listItems(current_dir)
        content = '<html><body>'
        content += f'<h1>Index of /files{current_dir}</h1>'

        # Back link
        if current_dir != '/':
            parent_dir = dirname(current_dir)
            content += f'<b><a href="/files{urlEncode(parent_dir)}">../ (Parent Directory)</a></b><br><br>'

        # File/dir list
        if len(items) > 0:

            directories = []
            files = []

            # Sort directories first
            for item in items:
                item_path = current_dir + '/' + item if current_dir != '/' else '/' + item
                if (isDir(self.file_manager.base_dir + item_path)):
                    directories.append(item)
                else:
                    files.append(item)
            items = directories + files

            content += '<ul>'
            for item in items:
                item_path = current_dir + '/' + item if current_dir != '/' else '/' + item
                item_path_encoded = urlEncode(item_path)
                # Actions: Delete, Rename, Move
                content += '<li style="padding: 2px">'
                # Delete button
                content += f'<form action="/files/delete{item_path_encoded}" method="get" style="display:inline;">'
                content += '<button type="submit">DELETE</button></form> '
                # Rename button
                content += f'<form action="/files/rename{item_path_encoded}" method="get" style="display:inline;">'
                content += '<button type="submit">RENAME</button></form> '
                # Move button
                content += f'<form action="/files/move{item_path_encoded}" method="get" style="display:inline;">'
                content += '<button type="submit">MOVE</button></form> - '

                if isDir(self.file_manager.base_dir + item_path):
                    content += f'<b>[DIR]</b> <a href="/files{item_path_encoded}">{item}</a>'
                else:
                    content += f'<a href="{item_path_encoded}">{item}</a>'
                content += '</li>'
            content += '</ul>'
        else:
            content += "<ul><li><i>Directory Empty</i></li></ul>"

        content += '<br>'

        # Upload form
        action_url = '/files/upload' + current_dir
        action_url_encoded = urlEncode(action_url)
        content += (
            f'<form action="{action_url_encoded}" method="post" enctype="multipart/form-data">'
            'Select file: <input type="file" name="file">'
            '<input type="submit" value="Upload">'
            '</form>'
        )

        # Create directory form
        action_url = '/files/create_dir' + current_dir
        action_url_encoded = urlEncode(action_url)
        content += (
            f'<form action="{action_url_encoded}" method="post">'
            'New Directory Name: <input type="text" name="dir_name">&nbsp&nbsp'
            '<input type="submit" value="Create Directory">'
            '</form>'
        )

        content += '<br><a href="/">Go Home</a>'
        content += '</body></html>'
        self.sendResponse(client_sock, content)


    def showRenameForm(self, client_sock, item_path):
        action_url = '/files/rename' + item_path
        content = '<html><body><h1>Rename Item</h1>'
        content += f'<form action="{urlEncode(action_url)}" method="post">'
        content += 'New name: <input type="text" name="new_name">&nbsp'
        content += '<input type="submit" value="Rename">'
        content += f'<br><a href="/files{dirname(item_path)}">Cancel</a>'
        content += '</form>'
        content += '</body></html>'
        self.sendResponse(client_sock, content)

    def showCreateDirForm(self, client_sock, dir_path):
        action_url = '/files/create_dir' + dir_path
        content = '<html><body><h1>Create Directory</h1>'
        content += f'<form action="{urlEncode(action_url)}" method="post">'
        content += 'Directory name: <input type="text" name="dir_name">'
        content += '<input type="submit" value="Create">'
        content += f'<br><a href="/files{dir_path}">Cancel</a>'
        content += '</form>'
        content += '</body></html>'
        self.sendResponse(client_sock, content)

    def showMoveSelection(self, client_sock, item_path):
        current_dir = dirname(item_path)
        directories = self.getAllDirectories('/', exclude=[current_dir, item_path])
        directories.insert(0, "/")
        content = '<html><body><h1>Move Item</h1>'
        content += '<p>Select a destination directory:</p>'
        content += '<ul>'
        for dir_path in directories:
            if dir_path != current_dir:
                dir_path_encoded = urlEncode(dir_path)
                item_path_encoded = urlEncode(item_path)
                content += f'<li><a href="/files/move_confirm{item_path_encoded}?dest_dir={dir_path_encoded}">{dir_path}</a></li>'
        content += '</ul>'
        content += f'<br><a href="/files{current_dir}">Cancel</a>'
        content += '</body></html>'
        self.sendResponse(client_sock, content)

    def handleMoveConfirm(self, client_sock, item_path, dest_dir):
        item_path = urlDecode(item_path)
        print(dest_dir)
        dest_dir = urlDecode(dest_dir)
        print('handleMoveConfirm called with:')
        print('item_path:', item_path)
        print('dest_dir:', dest_dir)
        self.file_manager.moveItem(item_path, dest_dir)
        self.sendRedirect(client_sock, '/files' + dest_dir)

    def parseFormData(self, body):
        form_data = {}
        try:
            request_str = body.decode('utf-8', 'ignore')
            pairs = request_str.split('&')
            for pair in pairs:
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    key = key.replace('+', ' ')
                    value = value.replace('+', ' ')
                    key = urlDecode(key)
                    value = urlDecode(value)
                    form_data[key] = value
        except Exception as e:
            print('Error parsing form data:', e)
        return form_data

    def parseQueryString(self, query_string):
        params = {}
        pairs = query_string.split('&')
        for pair in pairs:
            if '=' in pair:
                key, value = pair.split('=', 1)
                key = key.replace('+', ' ')
                value = value.replace('+', ' ')
                key = urlDecode(key)
                value = urlDecode(value)
                params[key] = value
        return params

    def getAllDirectories(self, path='/', exclude=[]):
        return self.file_manager.getAllDirectories(path, exclude)

def main():
    config = readConfig()
    wifi = WiFiConnection(config['wifi_name'],  config['wifi_password'])  # Replace with your WiFi credentials
    server = HTTPServer()
    server.serveForever()

if __name__ == '__main__':
    main()