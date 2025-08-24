# Automated Mailer Desktop App
# Tech: Python 3.10+, Tkinter, customtkinter, pandas, requests, smtplib
# Features (v1):
# - Login screen
# - Dashboard with 3 flows:
#     1) Group Send – Constant Data (same subject/body for all)
#     2) Group Send – Dynamic Data (template placeholders from Excel columns)
#     3) Group Send – API-assisted (fetch extra data via API per row before sending)
# - Light/Dark theme toggle
# - SMTP settings dialog (Gmail-friendly)
# - Async send (thread) with progress & log area
#
# Notes:
# - Install deps: pip install customtkinter pandas requests
# - For Gmail: enable 2FA and generate an App Password, then configure SMTP settings.
# - This is a starter you can extend (attachments, richer validation, better auth, etc.)

import threading
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any

import tkinter as tk
from tkinter import filedialog, messagebox
import os
import customtkinter as ctk
import pandas as pd
import requests

from valid_email import is_email_valid
from save_cred import save_credentials, load_credentials
import webbrowser

# ---------------------------
# App Config
# ---------------------------
APP_TITLE = "Automated Mailer"
DEFAULT_THEME = "Dark"  # "Light" or "Dark"

# Dummy login (replace with real auth or remove for open app)
VALID_USER = "admin"
VALID_PASS = "password"
check= False
# ---------------------------
# Helpers
# ---------------------------

def safe_show_error(msg: str):
    messagebox.showerror("Error", msg)


def send_email_smtp(settings: Dict[str, Any], to_addr: str, subject: str, body_html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["From"] = settings.get("sender_email", "")
    msg["To"] = to_addr
    msg["Subject"] = subject

    # Plain text fallback (strip HTML tags minimally)
    plain = body_html.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(body_html, "html"))

    server = None
    try:
        server = smtplib.SMTP(settings.get("smtp_host", "smtp.gmail.com"), int(settings.get("smtp_port", 587)))
        if settings.get("use_tls", True):
            server.starttls()
        server.login(settings.get("sender_email", ""), settings.get("app_password", ""))
        server.sendmail(settings.get("sender_email", ""), [to_addr], msg.as_string())
    finally:
        if server:
            server.quit()


def fill_template(template: str, row: Dict[str, Any]) -> str:
    """Replace {placeholders} in template with row values. Missing keys become empty strings."""
    class SafeDict(dict):
        def __missing__(self, key):
            return ""
    return template.format_map(SafeDict({k: ("" if pd.isna(v) else str(v)) for k, v in row.items()}))


# ---------------------------
# Frames
# ---------------------------

class Sidebar(ctk.CTkFrame):
    def __init__(self, master, on_nav, on_theme_toggle, on_settings):
        super().__init__(master, width=220, corner_radius=0)
        self.on_nav = on_nav

        logo = ctk.CTkLabel(self, text=APP_TITLE, font=("Segoe UI", 18, "bold"))
        logo.pack(padx=16, pady=(20, 10))

        ctk.CTkButton(self, text="Dashboard", command=lambda: on_nav("dashboard"), height=36).pack(fill="x", padx=16, pady=6)
        ctk.CTkButton(self, text="Constant Send", command=lambda: on_nav("constant"), height=36).pack(fill="x", padx=16, pady=6)
        ctk.CTkButton(self, text="Dynamic Send", command=lambda: on_nav("dynamic"), height=36).pack(fill="x", padx=16, pady=6)
        ctk.CTkButton(self, text="API Send", command=lambda: on_nav("api"), height=36).pack(fill="x", padx=16, pady=6)

        ctk.CTkButton(self, text="SMTP Settings", command=on_settings, height=36).pack(fill="x", padx=16, pady=(20, 6))

        self.theme_switch = ctk.CTkSwitch(self, text="Dark Mode", command=on_theme_toggle)
        self.theme_switch.select()  # default Dark
        self.theme_switch.pack(padx=16, pady=(10, 16))
        def verify_mail():
            global check
            check = self.verify_switch.get() == 1
        self.verify_switch = ctk.CTkSwitch(self, text="Verify Mail Address",command=verify_mail)
        self.verify_switch.pack(padx=16, pady=(10, 16))


class Dashboard(ctk.CTkFrame):
    def __init__(self, master, on_nav):
        super().__init__(master)
        self.on_nav = on_nav

        title = ctk.CTkLabel(self, text="Welcome 👋", font=("Segoe UI", 26, "bold"))
        title.pack(padx=20, pady=(20, 8), anchor="w")
        subtitle = ctk.CTkLabel(self, text="Choose a flow to begin or configure SMTP settings.")
        subtitle.pack(padx=20, pady=(0, 20), anchor="w")

        def open_user_guide():
            webbrowser.open(f"user_guide.html")     # open in default browser

        # Example button inside your app
        help_btn = ctk.CTkButton(self, text="📘 User Guide", command=open_user_guide)
        help_btn.place(x=700, y=20)

        row = ctk.CTkFrame(self)
        row.pack(fill="both", expand=True, padx=20, pady=20)
        for i in range(3):
            row.grid_columnconfigure(i, weight=1)

        ConstantCard(row, lambda: on_nav("constant")).grid(row=0, column=0, padx=8, pady=8, sticky="nsew")
        DynamicCard(row, lambda: on_nav("dynamic")).grid(row=0, column=1, padx=8, pady=8, sticky="nsew")
        ApiCard(row, lambda: on_nav("api")).grid(row=0, column=2, padx=8, pady=8, sticky="nsew")


class ConstantCard(ctk.CTkFrame):
    def __init__(self, master, on_open):
        super().__init__(master, corner_radius=16)
        ctk.CTkLabel(self, text="Group Send – Constant", font=("Segoe UI", 18, "bold")).pack(pady=(16, 6))
        ctk.CTkLabel(self, text="Same subject/body for all recipients\nEmails read from Excel (email column)").pack(pady=(0, 12))
        ctk.CTkButton(self, text="Open", command=on_open).pack(pady=(4, 16))


class DynamicCard(ctk.CTkFrame):
    def __init__(self, master, on_open):
        super().__init__(master, corner_radius=16)
        ctk.CTkLabel(self, text="Group Send – Dynamic", font=("Segoe UI", 18, "bold")).pack(pady=(16, 6))
        ctk.CTkLabel(self, text="Use {placeholders} from Excel columns\n(e.g., {name}, {due_date})").pack(pady=(0, 12))
        ctk.CTkButton(self, text="Open", command=on_open).pack(pady=(4, 16))


class ApiCard(ctk.CTkFrame):
    def __init__(self, master, on_open):
        super().__init__(master, corner_radius=16)
        ctk.CTkLabel(self, text="Group Send – API", font=("Segoe UI", 18, "bold")).pack(pady=(16, 6))
        ctk.CTkLabel(self, text="Fetch extra data via API per row\nthen send emails accordingly").pack(pady=(0, 12))
        ctk.CTkButton(self, text="Open", command=on_open).pack(pady=(4, 16))


class LogArea(ctk.CTkTextbox):
    def __init__(self, master):
        super().__init__(master, height=160)
        self.configure(state="disabled")

    def write(self, text: str):
        self.configure(state="normal")
        self.insert("end", text + "\n")
        self.see("end")
        self.configure(state="disabled")

    def clear_log(self):
            self.configure(state="normal")
            self.delete("1.0", "end")  # clears Text widget
            self.insert("end", "🔄 Log cleared, ready for new session...\n")
            self.configure(state="disabled")    
class BaseSendPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.df: pd.DataFrame | None = None

        # Header
        hdr = ctk.CTkFrame(self)
        hdr.pack(fill="x", padx=20, pady=(16, 8))
        self.title_lbl = ctk.CTkLabel(hdr, text="", font=("Segoe UI", 22, "bold"))
        self.title_lbl.pack(side="left")
        ctk.CTkButton(hdr, text="Back", command=lambda: app.navigate("dashboard"), width=100).pack(side="right")

        # Content left/right
        body = ctk.CTkFrame(self)
        body.pack(fill="both", expand=True, padx=20, pady=10)
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(1, weight=1)

        # Left: inputs
        left = ctk.CTkFrame(body)
        left.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 10), pady=0)
        left.grid_columnconfigure(0, weight=1)

        self.file_path_var = tk.StringVar()
        file_row = ctk.CTkFrame(left)
        file_row.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 6))
        ctk.CTkButton(file_row, text="Choose Excel", command=self.pick_file, width=140).pack(side="left")
        ctk.CTkLabel(file_row, textvariable=self.file_path_var, wraplength=260, anchor="w", justify="left").pack(side="left", padx=8)

        self.email_col_var = tk.StringVar(value="email")
        email_row = ctk.CTkFrame(left)
        email_row.grid(row=1, column=0, sticky="ew", padx=10, pady=6)
        ctk.CTkLabel(email_row, text="Email column name:").pack(side="left")
        ctk.CTkEntry(email_row, textvariable=self.email_col_var, width=160).pack(side="left", padx=8)

        # Subject & body (overridden in subclasses as needed)
        self.subject_var = tk.StringVar(value="")
        sub_row = ctk.CTkFrame(left)
        sub_row.grid(row=2, column=0, sticky="ew", padx=10, pady=6)
        ctk.CTkLabel(sub_row, text="Subject:").pack(side="left")
        ctk.CTkEntry(sub_row, textvariable=self.subject_var).pack(side="left", padx=8, fill="x", expand=True)

        self.body_txt = ctk.CTkTextbox(left, height=180)
        self.body_txt.grid(row=3, column=0, sticky="nsew", padx=10, pady=6)
        hint = ctk.CTkLabel(left, text=self.body_hint(), justify="left")
        hint.grid(row=4, column=0, sticky="w", padx=10, pady=(0, 10))

        btns = ctk.CTkFrame(left)
        btns.grid(row=5, column=0, sticky="ew", padx=10, pady=(6, 10))
        ctk.CTkButton(btns, text="Preview First 5", command=self.preview).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btns, text="Send All", command=self.send_all).pack(side="right")
        

        # Right: preview & log
        right = ctk.CTkFrame(body)
        right.grid(row=0, column=1, sticky="nsew", padx=(10, 0), pady=0)
        right.grid_rowconfigure(1, weight=1)
        right.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(right, text="Preview", font=("Segoe UI", 16, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 4))
        self.preview_box = ctk.CTkTextbox(right, height=220)
        self.preview_box.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        ctk.CTkLabel(right, text="Log", font=("Segoe UI", 16, "bold")).grid(row=2, column=0, sticky="w", padx=10, pady=(0, 4))
        self.log = LogArea(right)
        self.log.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
   
        ctk.CTkButton(right, text="Clear Log", command=self.log.clear_log).grid(row=4, column=0, sticky="e", padx=10, pady=(0, 10))
    
    
    
    def body_hint(self) -> str:
        return ""

    def pick_file(self):
        path = filedialog.askopenfilename(title="Choose Excel file", filetypes=[("Excel files", "*.xlsx;*.xls;*.csv")])
        if not path:
            return
        self.file_path_var.set(path)
        try:
            if path.lower().endswith(".csv"):
                self.df = pd.read_csv(path)
            else:
                self.df = pd.read_excel(path)
            messagebox.showinfo("Loaded", f"Rows loaded: {len(self.df)}\nColumns: {', '.join(self.df.columns.astype(str).tolist())}")
        except Exception as e:
            self.df = None
            safe_show_error(f"Failed to load file:\n{e}")

    def _collect_settings(self) -> Dict[str, Any]:
        return self.app.smtp_settings

    def _compose(self, row: Dict[str, Any]) -> tuple[str, str]:
        raise NotImplementedError

    def preview(self):
        if self.df is None:
            safe_show_error("Please choose an Excel/CSV file first.")
            return
        email_col = self.email_col_var.get().strip()
        if email_col not in self.df.columns:
            safe_show_error(f"Email column '{email_col}' not found. Available: {list(self.df.columns)}")
            return
        self.preview_box.delete("1.0", "end")
        sample = self.df.head(5)
        for _, row in sample.iterrows():
            to = str(row[email_col])
            subject, body = self._compose(row.to_dict())
            self.preview_box.insert("end", f"To: {to}\nSubject: {subject}\nBody:\n{body}\n{'-'*48}\n")

    
    def send_all(self):
        if self.df is None:
            safe_show_error("Please choose an Excel/CSV file first.")
            return
        email_col = self.email_col_var.get().strip()
        if email_col not in self.df.columns:
            safe_show_error(f"Email column '{email_col}' not found.")
            return
        settings = self._collect_settings()
        missing = [k for k in ("sender_email", "app_password", "smtp_host", "smtp_port") if not settings.get(k)]
        if missing:
            safe_show_error(f"Configure SMTP settings first. Missing: {missing}")
            return

        def _worker():
            success = 0
            total = len(self.df)
            for idx, row in self.df.iterrows():
                to = str(row[email_col])
                try:
                    subject, body = self._compose(row.to_dict())
                    if check==True:
                        ok= is_email_valid(to)
                        if not ok:
                            self.log.write(f"✖ Invalid address {to}")
                            continue
                    send_email_smtp(settings, to, subject, body)
                    self.log.write(f"✔ Sent to {to}")
                    success += 1
                except Exception as e:
                    self.log.write(f"✖ Failed to {to}: {e}")
            self.log.write(f"Done. {success}/{total} sent.")

        threading.Thread(target=_worker, daemon=True).start()

    def clear_log(self):
            self.log.delete("1.0", "end")  # clears Text widget
            self.log.insert("end", "🔄 Log cleared, ready for new session...\n")
    

class ConstantSendPage(BaseSendPage):
    def __init__(self, master, app):
        super().__init__(master, app)
        self.title_lbl.configure(text="Group Send – Constant Data")
        self.subject_var.set("Your update")
        self.body_txt.insert("1.0", "<p>Hello,</p><p>This is an automated update.</p>")

    def body_hint(self) -> str:
        return "All recipients receive the same Subject & HTML Body. Provide an 'email' column in Excel."

    def _compose(self, row: Dict[str, Any]) -> tuple[str, str]:
        return self.subject_var.get().strip(), self.body_txt.get("1.0", "end").strip()


class DynamicSendPage(BaseSendPage):
    def __init__(self, master, app):
        super().__init__(master, app)
        self.title_lbl.configure(text="Group Send – Dynamic (Mail Merge)")
        self.subject_var.set("Reminder for {name}")
        self.body_txt.insert("1.0", "<p>Hi {name},</p><p>Your due date is {due_date} and balance is Rs {balance}.</p>")

    def body_hint(self) -> str:
        return (
            "Use placeholders from Excel column names in {curly_braces}.\n"
            "Example columns: name, due_date, balance."
        )

    def _compose(self, row: Dict[str, Any]) -> tuple[str, str]:
        subject_tpl = self.subject_var.get().strip()
        body_tpl = self.body_txt.get("1.0", "end").strip()
        return fill_template(subject_tpl, row), fill_template(body_tpl, row)


class ApiSendPage(BaseSendPage):
    def __init__(self, master, app):
        super().__init__(master, app)
        self.title_lbl.configure(text="Group Send – API Assisted")

        # Extra inputs (top-right small panel)
        self.api_panel = ctk.CTkFrame(self)
        self.api_panel.pack(fill="x", padx=20, pady=(0, 10))

        inner = ctk.CTkFrame(self.api_panel)
        inner.pack(fill="x", padx=10, pady=10)

        self.id_col_var = tk.StringVar(value="student_id")
        self.api_url_tpl_var = tk.StringVar(value="https://api.example.com/attendance/{student_id}")
        self.simulate_var = tk.BooleanVar(value=True)

        ctk.CTkLabel(inner, text="ID column (Excel):").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        ctk.CTkEntry(inner, textvariable=self.id_col_var, width=180).grid(row=0, column=1, padx=6, pady=6, sticky="w")

        ctk.CTkLabel(inner, text="API URL template:").grid(row=0, column=2, padx=6, pady=6, sticky="w")
        ctk.CTkEntry(inner, textvariable=self.api_url_tpl_var, width=360).grid(row=0, column=3, padx=6, pady=6, sticky="ew")

        ctk.CTkCheckBox(inner, text="Simulate API (no network)", variable=self.simulate_var).grid(row=0, column=4, padx=6, pady=6)
        inner.grid_columnconfigure(3, weight=1)

        # Defaults
        self.subject_var.set("Absence Alert for {name}")
        self.body_txt.insert("1.0", "<p>Hi {name},</p><p>You were marked absent on {date}. Please contact admin.</p>")

    def body_hint(self) -> str:
        return (
            "Provide Excel with 'email' and an ID column (e.g., student_id).\n"
            "API URL template should contain {student_id}. Only rows flagged by API will be mailed."
        )

    def _fetch_attendance(self, student_id: str) -> Dict[str, Any]:
        if self.simulate_var.get():
            # Simulate: odd IDs absent, even present
            try:
                n = int(str(student_id)[-1])
            except Exception:
                n = 1
            absent = (n % 2 == 1)
            return {"absent": absent, "date": "2025-08-23"}
        else:
            url = self.api_url_tpl_var.get().format(student_id=student_id)
            resp = requests.get(url, timeout=5)
            resp.raise_for_status()
            return resp.json()

    def _compose(self, row: Dict[str, Any]) -> tuple[str, str]:
        # First call API; if not absent, raise a Skip exception to not send
        sid_col = self.id_col_var.get().strip()
        if sid_col not in row:
            raise ValueError(f"ID column '{sid_col}' not found in row.")
        data = self._fetch_attendance(str(row[sid_col]))
        if not data.get("absent", False):
            return "skip"," Skip: not absent"  # special signal to skip

        # Merge API data into row for templating
        merged = {**row, **data}
        subject_tpl = self.subject_var.get().strip()
        body_tpl = self.body_txt.get("1.0", "end").strip()
        return fill_template(subject_tpl, merged), fill_template(body_tpl, merged)

    def send_all(self):
        if self.df is None:
            safe_show_error("Please choose an Excel/CSV file first.")
            return
        email_col = self.email_col_var.get().strip()
        if email_col not in self.df.columns:
            safe_show_error(f"Email column '{email_col}' not found.")
            return
        settings = self._collect_settings()
        missing = [k for k in ("sender_email", "app_password", "smtp_host", "smtp_port") if not settings.get(k)]
        if missing:
            safe_show_error(f"Configure SMTP settings first. Missing: {missing}")
            return

        def _worker():
            success = 0
            skipped = 0
            total = len(self.df)
            for idx, row in self.df.iterrows():
                to = str(row[email_col])
                try:
                    subject, body = self._compose(row.to_dict())
                    if "skip" in subject:
                        self.log.write(f"→ Skipped {to}: {body}")
                        skipped += 1
                        continue
                    send_email_smtp(settings, to, subject, body)
                    self.log.write(f"✔ Sent to {to}")
                    success += 1
                except Exception as e:
                    self.log.write(f"✖ Failed {to}: {e}")
            self.log.write(f"Done. Sent: {success} | Skipped (not absent): {skipped} | Total rows: {total}")

        threading.Thread(target=_worker, daemon=True).start()


# ---------------------------
# SMTP Settings Dialog
# ---------------------------
class SMTPSettingsDialog(ctk.CTkToplevel):
    def __init__(self, master, settings: Dict[str, Any]):
        super().__init__(master)
        self.title("SMTP Settings")
        self.geometry("520x340")
        self.resizable(False, False)
        self.grab_set()

        self.settings = settings

        grid = ctk.CTkFrame(self)
        grid.pack(fill="both", expand=True, padx=16, pady=16)

        labels = [
            ("Sender Email", "sender_email"),
            ("App Password / SMTP Password", "app_password"),
            ("SMTP Host", "smtp_host"),
            ("SMTP Port", "smtp_port"),
        ]
        self.vars: Dict[str, tk.StringVar] = {}
        for i, (lbl, key) in enumerate(labels):
            ctk.CTkLabel(grid, text=lbl).grid(row=i, column=0, sticky="w", padx=8, pady=8)
            var = tk.StringVar(value=str(settings.get(key, "")))
            entry = ctk.CTkEntry(grid, textvariable=var, width=280)
            if key == "app_password":
                entry.configure(show="*")
            entry.grid(row=i, column=1, sticky="w", padx=8, pady=8)
            self.vars[key] = var

        self.use_tls = tk.BooleanVar(value=bool(settings.get("use_tls", True)))
        ctk.CTkCheckBox(grid, text="Use STARTTLS", variable=self.use_tls).grid(row=len(labels), column=1, sticky="w", padx=8, pady=8)

        btns = ctk.CTkFrame(grid)
        btns.grid(row=len(labels)+1, column=0, columnspan=2, pady=(16,0))
        ctk.CTkButton(btns, text="Save", command=self._save).pack(side="left", padx=6)
        ctk.CTkButton(btns, text="Cancel", command=self.destroy, fg_color="#555555").pack(side="left", padx=6)

        # Helper text
        helper = (
            "Gmail tip: Host=smtp.gmail.com, Port=587, Use STARTTLS.\n"
            "Use an App Password (after enabling 2-Step Verification)."
        )
        ctk.CTkLabel(grid, text=helper, justify="left").grid(row=len(labels)+2, column=0, columnspan=2, sticky="w", padx=8, pady=(10,0))

    def _save(self):
        for k, v in self.vars.items():
            self.settings[k] = v.get().strip()
        self.settings["use_tls"] = bool(self.use_tls.get())
        save_credentials(self.settings)
        messagebox.showinfo("Saved", "SMTP settings updated.")
        self.destroy()


# ---------------------------
# Main App
# ---------------------------
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("1100x680")
        ctk.set_appearance_mode(DEFAULT_THEME)
        ctk.set_default_color_theme("blue")

        self.smtp_settings: Dict[str, Any] = {
            "sender_email": "",
            "app_password": "",
            "smtp_host": "smtp.gmail.com",
            "smtp_port": "587",
            "use_tls": True,
        }

        if os.path.exists("config.secure"):
            creds = load_credentials()
            if creds:
                self.smtp_settings=creds
        

        self.container = ctk.CTkFrame(self)
        self.container.pack(fill="both", expand=True)

        self._init_login()

    def _init_login(self):
        self._init_main()

    def _init_main(self):
        # clear login
        for w in self.container.winfo_children():
            w.destroy()

        # Shell layout: sidebar + content
        shell = ctk.CTkFrame(self.container)
        shell.pack(fill="both", expand=True)
        shell.grid_columnconfigure(1, weight=1)
        shell.grid_rowconfigure(0, weight=1)

        self.sidebar = Sidebar(shell, on_nav=self.navigate, on_theme_toggle=self._toggle_theme, on_settings=self._open_settings)
        self.sidebar.grid(row=0, column=0, sticky="ns")

        self.content = ctk.CTkFrame(shell)
        self.content.grid(row=0, column=1, sticky="nsew")

        # Pages
        self.pages: Dict[str, ctk.CTkFrame] = {
            "dashboard": Dashboard(self.content, on_nav=self.navigate),
            "constant": ConstantSendPage(self.content, self),
            "dynamic": DynamicSendPage(self.content, self),
            "api": ApiSendPage(self.content, self),
        }
        for name, frame in self.pages.items():
            frame.place(relx=0, rely=0, relwidth=1, relheight=1)

        self.navigate("dashboard")

    def navigate(self, name: str):
        frame = self.pages.get(name)
        if not frame:
            return
        frame.lift()

    def _toggle_theme(self):
        # Switch based on sidebar switch state
        is_on = self.sidebar.theme_switch.get() == 1
        mode = "Dark" if is_on else "Light"
        ctk.set_appearance_mode(mode)

    def _open_settings(self):
        SMTPSettingsDialog(self, self.smtp_settings)


if __name__ == "__main__":
    app = App()
    app.mainloop()
