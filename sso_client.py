import http.server
import json
import secrets
import urllib.parse
import urllib.request
import webbrowser
from threading import Thread
import db

# Port and redirect URI configured for local SSO callback
PORT = 5005
REDIRECT_URI = f"http://localhost:{PORT}/callback"
CLIENT_ID = "hazari_python_app"

# Module-level variables for thread communication
captured_code = None
captured_state = None
server_instance = None
expected_state = None
sso_thread = None


class CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Handles callback requests from the browser redirect."""
    
    def log_message(self, format, *args):
        # Suppress logging console noise
        return

    def do_GET(self):
        global captured_code, captured_state
        parsed_url = urllib.parse.urlparse(self.path)
        
        # Check if the request path matches the redirect URI callback path
        if parsed_url.path == "/callback":
            query_params = urllib.parse.parse_qs(parsed_url.query)
            captured_code = query_params.get("code", [None])[0]
            captured_state = query_params.get("state", [None])[0]

            # Return a clean authorization confirmation response page
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            
            html_content = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>HazariTracker Authentication</title>
                <style>
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        background-color: #f9fafb;
                        display: flex;
                        justify-content: center;
                        align-items: center;
                        height: 100vh;
                        margin: 0;
                    }
                    .card {
                        background-color: white;
                        padding: 2.5rem;
                        border-radius: 1.5rem;
                        box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.05);
                        text-align: center;
                        max-width: 400px;
                        border: 1px solid #f3f4f6;
                    }
                    .icon {
                        background-color: #f0fdf4;
                        color: #16a34a;
                        width: 3.5rem;
                        height: 3.5rem;
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        margin: 0 auto 1.5rem;
                    }
                    h1 { color: #111827; font-size: 1.5rem; margin-bottom: 0.5rem; }
                    p { color: #4b5563; font-size: 0.95rem; line-height: 1.5; margin-bottom: 1.5rem; }
                    .close-msg { font-size: 0.85rem; color: #9ca3af; }
                </style>
            </head>
            <body>
                <div class="card">
                    <div class="icon">
                        <svg width="24" height="24" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7"></path>
                        </svg>
                    </div>
                    <h1>Sign In Successful!</h1>
                    <p>The Python desktop app has been authorized. You can safely close this browser window and return to the application.</p>
                    <div class="close-msg">This window will close automatically soon.</div>
                </div>
                <script>
                    setTimeout(function() { window.close(); }, 5000);
                </script>
            </body>
            </html>
            """
            self.wfile.write(html_content.encode("utf-8"))
            
            # Start clean server shutdown in a separate thread to prevent lockup
            Thread(target=shutdown_server).start()
        else:
            self.send_response(404)
            self.end_headers()


def start_local_server():
    """Starts the temporary HTTP server to capture the callback."""
    global server_instance
    try:
        server_address = ("", PORT)
        server_instance = http.server.HTTPServer(server_address, CallbackHandler)
        server_instance.serve_forever()
    except Exception as e:
        print(f"[SSO] Local server error: {e}")


def shutdown_server():
    """Stops the local server."""
    global server_instance
    if server_instance:
        server_instance.shutdown()
        server_instance = None


def get_server_url():
    """Gets the configured base URL of the HazariTracker server."""
    url = db.get_setting("server_url")
    return url if url else "http://127.0.0.1:8000"


def set_server_url(url):
    """Sets the base URL of the HazariTracker server."""
    db.set_setting("server_url", url.strip().rstrip("/"))


def get_token():
    """Returns the stored Sanctum access token, or None if not authenticated."""
    return db.get_setting("sso_token")


def get_user_info():
    """Returns the stored user dictionary, or None."""
    user_str = db.get_setting("sso_user")
    if user_str:
        try:
            return json.loads(user_str)
        except Exception:
            return None
    return None


def is_authenticated():
    """Checks if the user has a stored authentication token."""
    return get_token() is not None


def sign_out():
    """Removes stored tokens and user details from the database."""
    db.delete_setting("sso_token")
    db.delete_setting("sso_user")


def start_sso_flow(on_success, on_error):
    """Starts the asynchronous SSO authentication flow in a background thread."""
    global sso_thread
    sso_thread = Thread(target=_run_sso_flow, args=(on_success, on_error), daemon=True)
    sso_thread.start()


def _run_sso_flow(on_success, on_error):
    global captured_code, captured_state, expected_state
    
    captured_code = None
    captured_state = None
    expected_state = secrets.token_hex(16)
    
    # 1. Start the local server
    server_thread = Thread(target=start_local_server, daemon=True)
    server_thread.start()
    
    # 2. Formulate authorize URL
    base_url = get_server_url()
    query_params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "state": expected_state
    }
    authorize_url = f"{base_url}/sso/authorize?{urllib.parse.urlencode(query_params)}"
    
    # 3. Open system web browser
    try:
        webbrowser.open(authorize_url)
    except Exception as e:
        on_error(f"Failed to open web browser: {e}")
        shutdown_server()
        return

    # 4. Wait for local server to capture redirect
    # Wait for the server thread to finish (which happens when server_instance is shut down)
    server_thread.join(timeout=120)  # 2 minute timeout
    
    # Clean up server just in case
    shutdown_server()
    
    if captured_state != expected_state:
        on_error("CSRF State mismatch! The authentication request was rejected for security reasons.")
        return
        
    if not captured_code:
        on_error("Authentication timed out or was cancelled.")
        return
        
    # 5. Exchange code for token
    token_url = f"{base_url}/api/sso/token"
    payload = {
        "code": captured_code,
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI
    }
    
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            token_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            
            if "access_token" in res_data:
                token = res_data["access_token"]
                user = res_data["user"]
                
                # Save to database
                db.set_setting("sso_token", token)
                db.set_setting("sso_user", json.dumps(user))
                
                on_success(user)
            else:
                on_error(res_data.get("error_description", "Failed to retrieve access token."))
                
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        try:
            res_err = json.loads(err_msg)
            on_error(res_err.get("error_description", f"HTTP Error {e.code}"))
        except Exception:
            on_error(f"Server returned error status {e.code}")
    except Exception as e:
        on_error(f"Network error connecting to server: {e}")


def send_punch_to_server(employee_id, location="Fingerprint Device"):
    """Sends a punch record to the Laravel server using the stored SSO token."""
    token = get_token()
    if not token:
        return False, "Not authenticated"
        
    base_url = get_server_url()
    punch_url = f"{base_url}/api/attendance/punch"
    
    payload = {
        "employee_id": str(employee_id),
        "location": location,
    }
    
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            punch_url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {token}"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            if res_data.get("success"):
                return True, res_data
            return False, res_data.get("message", "Unknown server error")
            
    except urllib.error.HTTPError as e:
        if e.code == 401:
            # Token invalid/expired - sign out!
            sign_out()
            return False, "Unauthorized"
        err_msg = e.read().decode("utf-8")
        try:
            res_err = json.loads(err_msg)
            return False, res_err.get("message", f"Server error: {e.code}")
        except Exception:
            return False, f"Server returned error code {e.code}"
    except Exception as e:
        return False, f"Connection failed: {e}"


def sync_employees_from_server():
    """Fetches employees and fingerprint templates from the server and updates the local DB."""
    token = get_token()
    if not token:
        return False, "Not authenticated"

    base_url = get_server_url()
    url = f"{base_url}/api/employees"

    try:
        req = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {token}"
            },
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            if not res_data.get("success"):
                return False, res_data.get("message", "Failed to fetch employees")

            employees = res_data.get("employees", [])
            import base64
            synced_count = 0
            for emp in employees:
                emp_id = emp.get("employee_id")
                name = emp.get("name")
                dept = emp.get("department", "")
                template_str = emp.get("fingerprint_template")

                if not emp_id or not name:
                    continue

                template_bytes = None
                if template_str:
                    try:
                        # Decode template string (base64 or hex)
                        try:
                            template_bytes = base64.b64decode(template_str)
                        except Exception:
                            template_bytes = bytes.fromhex(template_str)
                    except Exception as e:
                        print(f"[Sync] Failed to decode template for {emp_id}: {e}")

                existing = db.get_employee(emp_id)
                if existing:
                    db.update_employee_details(emp_id, name, dept)
                    if template_bytes:
                        db.update_template(emp_id, template_bytes)
                else:
                    db.add_employee(emp_id, name, dept, template_bytes)
                synced_count += 1

            return True, f"Successfully synced {synced_count} employee profiles"


    except urllib.error.HTTPError as e:
        if e.code == 401:
            sign_out()
            return False, "Unauthorized"
        return False, f"Server returned error code {e.code}"
    except Exception as e:
        return False, f"Sync connection failed: {e}"


def upload_fingerprint_template(employee_id, template_bytes):
    """Uploads a base64 encoded fingerprint template for an employee to the server."""
    token = get_token()
    if not token:
        return False, "Not authenticated"

    base_url = get_server_url()
    url = f"{base_url}/api/employees/fingerprint"

    import base64
    template_str = base64.b64encode(template_bytes).decode("utf-8")

    payload = {
        "employee_id": str(employee_id),
        "fingerprint_template": template_str
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {token}"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            if res_data.get("success"):
                return True, res_data.get("message", "Success")
            return False, res_data.get("message", "Server error")

    except urllib.error.HTTPError as e:
        if e.code == 401:
            sign_out()
            return False, "Unauthorized"
        err_msg = e.read().decode("utf-8")
        try:
            res_err = json.loads(err_msg)
            return False, res_err.get("message", f"Server error: {e.code}")
        except Exception:
            return False, f"Server returned error code {e.code}"
    except Exception as e:
        return False, f"Connection failed: {e}"


