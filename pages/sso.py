"""
pages/sso.py
────────────
SSO Cloud Sync Configuration Page and Login Overlay.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sso_client
from theme import *

class SSOPage(tk.Frame):
    def __init__(self, master, **kw):
        super().__init__(master, bg=BG_BASE, **kw)
        self._build()
        self.refresh()

    def _build(self):
        # Top banner/header
        hdr = tk.Frame(self, bg=BG_SURFACE, pady=PAD_MD, padx=PAD_LG)
        hdr.pack(fill="x")
        
        lbl_title = tk.Label(hdr, text="☁  Cloud Sync Settings", font=FONT_H1, bg=BG_SURFACE, fg=TEXT_PRIMARY)
        lbl_title.pack(anchor="w")
        
        lbl_desc = tk.Label(hdr, text="Configure your Laravel web portal connection and manage SSO authentication.", font=FONT_BODY, bg=BG_SURFACE, fg=TEXT_SECONDARY)
        lbl_desc.pack(anchor="w", pady=(PAD_XS, 0))
        
        tk.Frame(self, bg=ACCENT, height=2).pack(fill="x")

        # Main content split layout
        main_content = tk.Frame(self, bg=BG_BASE, padx=PAD_LG, pady=PAD_MD)
        main_content.pack(fill="both", expand=True)

        # Left Column: Connection Settings
        left_col = tk.LabelFrame(main_content, text=" Server Connection ", font=FONT_H2, bg=BG_SURFACE, fg=ACCENT, bd=1, relief="solid", padx=PAD_MD, pady=PAD_MD)
        left_col.place(relx=0.0, rely=0.0, relwidth=0.48, relheight=1.0)

        tk.Label(left_col, text="Portal Base URL:", font=FONT_H3, bg=BG_SURFACE, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0, PAD_SM))
        
        self._url_entry = ttk.Entry(left_col, width=40)
        self._url_entry.pack(fill="x", pady=(0, PAD_MD))
        
        self._btn_save_url = tk.Button(left_col, text="Save Connection URL", font=FONT_BODY, bg=BG_ELEVATED, fg=TEXT_PRIMARY, relief="flat", bd=0, padx=PAD_MD, pady=6, cursor="hand2", command=self._save_url)
        self._btn_save_url.pack(anchor="w")

        desc_text = (
            "\nNote:\n"
            "This URL is the base domain of your Laravel application.\n"
            "• Local development: http://127.0.0.1:8000\n"
            "• Production portal: https://hazaritracker.in"
        )
        tk.Label(left_col, text=desc_text, font=FONT_SMALL, bg=BG_SURFACE, fg=TEXT_SECONDARY, justify="left", anchor="w").pack(fill="x", pady=PAD_MD)

        # Right Column: Auth Status & SSO
        self._right_col = tk.LabelFrame(main_content, text=" Authentication Status ", font=FONT_H2, bg=BG_SURFACE, fg=ACCENT, bd=1, relief="solid", padx=PAD_MD, pady=PAD_MD)
        self._right_col.place(relx=0.52, rely=0.0, relwidth=0.48, relheight=1.0)

        # Create child frames for different states
        self._state_frame = tk.Frame(self._right_col, bg=BG_SURFACE)
        self._state_frame.pack(fill="both", expand=True)

    def refresh(self):
        """Update fields and state display based on current authentication."""
        # Populate URL entry
        url = sso_client.get_server_url()
        self._url_entry.delete(0, tk.END)
        self._url_entry.insert(0, url)

        # Clear state frame
        for child in self._state_frame.winfo_children():
            child.destroy()

        if sso_client.is_authenticated():
            self._build_authenticated_state()
        else:
            self._build_unauthenticated_state()

    def _build_unauthenticated_state(self):
        lbl_icon = tk.Label(self._state_frame, text="🔓", font=("Segoe UI", 48), bg=BG_SURFACE, fg=WARNING)
        lbl_icon.pack(pady=PAD_MD)

        lbl_status = tk.Label(self._state_frame, text="Not Authenticated", font=FONT_H2, bg=BG_SURFACE, fg=WARNING)
        lbl_status.pack()

        lbl_info = tk.Label(self._state_frame, text="This device is not connected to your portal. Attendance punches will only be logged locally.", font=FONT_BODY, bg=BG_SURFACE, fg=TEXT_SECONDARY, wraplength=300, justify="center")
        lbl_info.pack(pady=PAD_MD)

    def _build_authenticated_state(self):
        lbl_icon = tk.Label(self._state_frame, text="🔒", font=("Segoe UI", 48), bg=BG_SURFACE, fg=SUCCESS)
        lbl_icon.pack(pady=(0, PAD_SM))

        lbl_status = tk.Label(self._state_frame, text="Cloud Connection Active", font=FONT_H2, bg=BG_SURFACE, fg=SUCCESS)
        lbl_status.pack()

        # User Info
        user = sso_client.get_user_info()
        if user:
            info_frame = tk.Frame(self._state_frame, bg=BG_ELEVATED, padx=PAD_MD, pady=PAD_MD, bd=1, relief="solid")
            info_frame.pack(fill="x", pady=PAD_MD)

            details = [
                ("User", user.get("name")),
                ("Email", user.get("email")),
                ("Role", user.get("role", "").capitalize()),
                ("Tenant", user.get("tenant_id")),
            ]
            for i, (label, val) in enumerate(details):
                tk.Label(info_frame, text=f"{label}:", font=FONT_H3, bg=BG_ELEVATED, fg=TEXT_SECONDARY).grid(row=i, column=0, sticky="w", pady=2)
                tk.Label(info_frame, text=str(val), font=FONT_BODY, bg=BG_ELEVATED, fg=TEXT_PRIMARY).grid(row=i, column=1, sticky="w", padx=PAD_SM, pady=2)

        btn_logout = tk.Button(self._state_frame, text="Disconnect Account", font=FONT_BODY, bg=BG_ELEVATED, fg=DANGER, relief="flat", bd=0, padx=PAD_MD, pady=6, cursor="hand2", command=self._logout)
        btn_logout.pack(pady=PAD_SM)

    def _save_url(self):
        url = self._url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "URL cannot be empty.")
            return
        sso_client.set_server_url(url)
        messagebox.showinfo("Success", "Portal server URL updated successfully.")
        self.refresh()

    def _logout(self):
        if messagebox.askyesno("Confirm Disconnect", "Are you sure you want to disconnect from the cloud server?"):
            sso_client.sign_out()
            try:
                self.master.master._show_login_screen()
            except Exception:
                self.refresh()


class SSOLoginFrame(tk.Frame):
    def __init__(self, master, **kw):
        super().__init__(master, bg=BG_BASE, **kw)
        self._is_authorizing = False
        self._build()
        self.refresh()

    def _build(self):
        # Center card container with subtle modern borders
        card = tk.Frame(self, bg=BG_SURFACE, bd=1, relief="solid", highlightbackground=BORDER, highlightthickness=1)
        card.place(relx=0.5, rely=0.5, anchor="center", width=460, height=440)

        # Branding
        hdr = tk.Frame(card, bg=BG_SURFACE)
        hdr.pack(fill="x", pady=(PAD_LG, PAD_MD))

        # Brand name with Orange/White split
        brand = tk.Frame(hdr, bg=BG_SURFACE)
        brand.pack(anchor="center")
        tk.Label(brand, text="Hazari", font=("Segoe UI", 28, "bold"), bg=BG_SURFACE, fg=TEXT_PRIMARY).pack(side="left")
        tk.Label(brand, text="Tracker", font=("Segoe UI", 28, "bold"), bg=BG_SURFACE, fg=ACCENT).pack(side="left")
        
        lbl_subtitle = tk.Label(hdr, text="Biometric Client Authentication", font=FONT_H3, bg=BG_SURFACE, fg=TEXT_SECONDARY)
        lbl_subtitle.pack(anchor="center", pady=(PAD_XS, 0))

        # Divider line
        tk.Frame(card, bg=BORDER, height=1).pack(fill="x", padx=PAD_LG, pady=(0, PAD_LG))

        # URL Entry Field
        self._entry_frame = tk.Frame(card, bg=BG_SURFACE)
        self._entry_frame.pack(fill="x", padx=PAD_LG)

        tk.Label(self._entry_frame, text="Portal Base URL", font=FONT_H3, bg=BG_SURFACE, fg=TEXT_PRIMARY).pack(anchor="w", pady=(0, PAD_XS))
        
        self._url_entry = ttk.Entry(self._entry_frame)
        self._url_entry.pack(fill="x", pady=(0, PAD_MD))

        # Action area
        self._action_frame = tk.Frame(card, bg=BG_SURFACE)
        self._action_frame.pack(fill="both", expand=True, padx=PAD_LG, pady=(0, PAD_LG))

    def refresh(self):
        url = sso_client.get_server_url()
        self._url_entry.delete(0, tk.END)
        self._url_entry.insert(0, url)

        # Clear action frame
        for child in self._action_frame.winfo_children():
            child.destroy()

        if self._is_authorizing:
            self._build_authorizing()
        else:
            self._build_unauthenticated()

    def _build_unauthenticated(self):
        self._url_entry.config(state="normal")
        
        lbl_desc = tk.Label(self._action_frame, 
                            text="Connect this terminal to your HazariTracker cloud workspace. Signing in is required to log biometric attendance.",
                            font=FONT_BODY, bg=BG_SURFACE, fg=TEXT_SECONDARY, wraplength=400, justify="center")
        lbl_desc.pack(fill="x", pady=(0, PAD_LG))

        self._btn_login = tk.Button(self._action_frame, text="🔑  Sign In with HazariTracker", font=FONT_H2,
                                    bg=ACCENT, fg=TEXT_PRIMARY, activebackground=ACCENT, activeforeground=TEXT_PRIMARY,
                                    relief="flat", bd=0, padx=PAD_MD, pady=10, cursor="hand2", command=self._start_sso)
        self._btn_login.pack(fill="x")

    def _build_authorizing(self):
        self._url_entry.config(state="disabled")

        lbl_status = tk.Label(self._action_frame, text="⏳ Awaiting Browser Authentication", font=FONT_H2, bg=BG_SURFACE, fg=INFO)
        lbl_status.pack(pady=(0, PAD_SM))

        lbl_desc = tk.Label(self._action_frame, 
                            text="We opened a login tab in your browser. Please authorize this device to connect to your account.",
                            font=FONT_BODY, bg=BG_SURFACE, fg=TEXT_SECONDARY, wraplength=400, justify="center")
        lbl_desc.pack(fill="x", pady=(0, PAD_LG))

        btn_cancel = tk.Button(self._action_frame, text="Cancel & Reconfigure", font=FONT_BODY,
                               bg=BG_ELEVATED, fg=DANGER, activebackground=BG_ELEVATED, activeforeground=DANGER,
                               relief="flat", bd=0, padx=PAD_MD, pady=8, cursor="hand2", command=self._cancel_sso)
        btn_cancel.pack(fill="x")

    def _start_sso(self):
        url = self._url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "URL cannot be empty.")
            return
        sso_client.set_server_url(url)
        self._is_authorizing = True
        self.refresh()

        sso_client.start_sso_flow(
            on_success=self._on_sso_success,
            on_error=self._on_sso_error
        )

    def _cancel_sso(self):
        sso_client.shutdown_server()
        self._is_authorizing = False
        self.refresh()

    def _on_sso_success(self, user):
        self.after(0, lambda: self._handle_success(user))

    def _on_sso_error(self, err_msg):
        self.after(0, lambda: self._handle_error(err_msg))

    def _handle_success(self, user):
        self._is_authorizing = False
        messagebox.showinfo("SSO Success", f"Successfully authenticated as {user.get('name')}!")
        # Switch to the main app window!
        try:
            self.master._show_main_app()
        except Exception as exc:
            print(f"[SSO] transition failed: {exc}")

    def _handle_error(self, err_msg):
        self._is_authorizing = False
        messagebox.showerror("SSO Failed", f"Authentication failed:\n{err_msg}")
        self.refresh()
