import os
import sys
import json
import urllib.request
import tempfile
import threading
from tkinter import messagebox
from version import VERSION as APP_VERSION

REPO_OWNER = "Themehakcodes"
REPO_NAME = "HazariTrackerBio"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"


def parse_version(v_str):
    """Parse a version string like '1.0.2' or 'v1.0.2' into a list of ints."""
    try:
        return [int(x) for x in v_str.lstrip('v').split('.')]
    except Exception:
        return [0, 0, 0]


def get_latest_release_info():
    """Fetch latest release info from GitHub API.
    Returns (latest_version_str, download_url, release_notes) or (None, None, None)
    """
    req = urllib.request.Request(
        LATEST_RELEASE_URL,
        headers={"User-Agent": "HazariTrackerBio-Updater"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))
            tag_name = data.get("tag_name", "")
            body = data.get("body", "")
            
            # Find the setup exe asset
            download_url = None
            assets = data.get("assets", [])
            for asset in assets:
                name = asset.get("name", "")
                # We want the setup executable (e.g. HazariTrackerBio-vX.Y.Z-Setup.exe)
                if name.endswith("-Setup.exe") and "HazariTrackerBio" in name:
                    download_url = asset.get("browser_download_url")
                    break
            
            # If not found, try any .exe asset
            if not download_url:
                for asset in assets:
                    name = asset.get("name", "")
                    if name.endswith(".exe"):
                        download_url = asset.get("browser_download_url")
                        break
                        
            return tag_name, download_url, body
    except Exception as e:
        print(f"[Updater] Failed to check updates: {e}")
        return None, None, None


def get_update_dest_path(version_str):
    temp_dir = tempfile.gettempdir()
    clean_version = version_str.lstrip('v')
    return os.path.join(temp_dir, f"HazariTrackerBio-v{clean_version}-Setup.exe")


def is_update_downloaded(version_str):
    path = get_update_dest_path(version_str)
    # Check if file exists and has size > 1MB (to avoid partial/corrupted files)
    return os.path.isfile(path) and os.path.getsize(path) > 1024 * 1024


def run_installer(path):
    """Launches the installer using Windows startfile and terminates the app."""
    try:
        print(f"[Updater] Launching installer: {path}")
        os.startfile(path)
        # Force exit this application
        os._exit(0)
    except Exception as e:
        print(f"[Updater] Failed to run installer: {e}")
        # Fallback to subprocess if startfile fails
        try:
            import subprocess
            subprocess.Popen([path], shell=True)
            os._exit(0)
        except Exception as e2:
            print(f"[Updater] Fallback launching installer failed: {e2}")


class AutoUpdater:
    def __init__(self, app):
        self.app = app
        self.checking = False
        self.downloading = False

    def start_check(self):
        """Starts the check in a background thread if running as frozen executable."""
        if not hasattr(sys, "frozen"):
            print("[Updater] Development mode detected (not frozen). Skipping update checks.")
            return
        if self.checking:
            return
        self.checking = True
        threading.Thread(target=self._check_thread_func, daemon=True).start()

    def _check_thread_func(self):
        try:
            latest_tag, download_url, notes = get_latest_release_info()
            if not latest_tag or not download_url:
                self.checking = False
                return

            v_latest = parse_version(latest_tag)
            v_current = parse_version(APP_VERSION)

            if v_latest > v_current:
                print(f"[Updater] New version available: {latest_tag} (Current: {APP_VERSION})")
                self.app.after(0, lambda: self._handle_new_version(latest_tag, download_url))
            else:
                print(f"[Updater] App is up to date (v{APP_VERSION})")
        except Exception as e:
            print(f"[Updater] Error in check thread: {e}")
        finally:
            self.checking = False

    def _handle_new_version(self, latest_tag, download_url):
        # Check if already downloaded
        if is_update_downloaded(latest_tag):
            dest_path = get_update_dest_path(latest_tag)
            self._prompt_install(latest_tag, dest_path)
        else:
            # Start downloading in background
            if not self.downloading:
                self.downloading = True
                threading.Thread(target=self._download_thread_func, args=(latest_tag, download_url), daemon=True).start()

    def _download_thread_func(self, latest_tag, download_url):
        dest_path = get_update_dest_path(latest_tag)
        print(f"[Updater] Downloading update to {dest_path}...")
        try:
            req = urllib.request.Request(
                download_url,
                headers={"User-Agent": "HazariTrackerBio-Updater"}
            )
            with urllib.request.urlopen(req) as response:
                with open(dest_path, 'wb') as f:
                    f.write(response.read())
            print("[Updater] Update downloaded successfully.")
            self.app.after(0, lambda: self._prompt_install(latest_tag, dest_path))
        except Exception as e:
            print(f"[Updater] Download failed: {e}")
            if os.path.exists(dest_path):
                try:
                    os.remove(dest_path)
                except Exception:
                    pass
        finally:
            self.downloading = False

    def _prompt_install(self, latest_tag, dest_path):
        res = messagebox.askyesno(
            "Update Available",
            f"A new version ({latest_tag}) of HazariTracker Bio is available.\n\n"
            f"Would you like to install it and restart the application now?",
            parent=self.app
        )
        if res:
            # Stop scanner, close device
            if hasattr(self.app, "_scanner_page") and self.app._scanner_page:
                try:
                    self.app._scanner_page.stop()
                except Exception:
                    pass
            try:
                self.app.sdk.close_device()
            except Exception:
                pass
            run_installer(dest_path)
