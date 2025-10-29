import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Dict, Any

from scripts.vault_manager import load_vault_from_credentials, resolve_named_vault_path
from services.security_service import SecurityService
from ui.theme import SPACING_M, PRIMARY


class LoginWindow(ttk.Frame):
    def __init__(
        self,
        master: tk.Tk,
        on_success: Callable[[Dict[str, Any], str, str], None],
        require_authorized: bool = False,
        title: str = "Acceso seguro - Vault",
        width: int = 520,
        height: int = 300,
    ) -> None:
        super().__init__(master, style="App.TFrame")

        self.master = master
        self.on_success = on_success
        self.require_authorized = require_authorized
        self.security = SecurityService()

        self.master.title(title)
        self.master.configure(bg=PRIMARY)
        self._center_root(width, height)

        self.pack(fill="both", expand=True)

        self._return_binding = None
        self._escape_binding = None

        root_frame = ttk.Frame(self, style="App.TFrame")
        root_frame.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        content = ttk.Frame(root_frame, style="App.TFrame")
        content.grid(row=0, column=0, sticky="nsew", padx=SPACING_M, pady=SPACING_M)
        root_frame.columnconfigure(0, weight=1)
        root_frame.rowconfigure(0, weight=1)

        for c in (0, 2):
            content.columnconfigure(c, weight=1, uniform="u")
        for r in (0, 2):
            content.rowconfigure(r, weight=1, uniform="u")

        form = ttk.Frame(content, style="App.TFrame")
        form.grid(row=1, column=1, sticky="n")
        form.columnconfigure(0, weight=1)

        ttk.Label(form, text="Acceso al Vault", style="App.Subtitle.TLabel").grid(
            row=0, column=0, pady=(0, SPACING_M), sticky="n"
        )

        entry_width = 32
        entry_justify = "center"
        label_width = 8

        fields_frame = ttk.Frame(form, style="App.TFrame")
        fields_frame.grid(row=1, column=0, pady=(0, SPACING_M), sticky="")

        fields_frame.columnconfigure(0, weight=0, minsize=80)
        fields_frame.columnconfigure(1, weight=1)

        self.user_var = tk.StringVar()
        ttk.Label(fields_frame, text="Usuario:", style="App.TLabel", width=label_width).grid(
            row=0, column=0, padx=(0, 8), pady=(0, SPACING_M), sticky="e"
        )
        self.user_entry = ttk.Entry(
            fields_frame,
            textvariable=self.user_var,
            width=entry_width,
            justify=entry_justify,
            style="App.TEntry",
            takefocus=True,
        )
        self.user_entry.grid(row=0, column=1, pady=(0, SPACING_M), sticky="w")

        self.pass_var = tk.StringVar()
        ttk.Label(fields_frame, text="Clave:", style="App.TLabel", width=label_width).grid(
            row=1, column=0, padx=(0, 8), sticky="e"
        )

        pass_container = ttk.Frame(fields_frame, style="App.TFrame")
        pass_container.grid(row=1, column=1, sticky="w")

        self.pass_entry = ttk.Entry(
            pass_container,
            textvariable=self.pass_var,
            width=entry_width - 3,
            justify=entry_justify,
            style="App.TEntry",
            show="*",
        )
        self.pass_entry.grid(row=0, column=0, sticky="w")

        self.show_pass_var = tk.BooleanVar()
        self.toggle_btn = ttk.Button(
            pass_container,
            text="👁",
            width=3,
            command=self._toggle_password_visibility,
        )
        self.toggle_btn.grid(row=0, column=1, padx=(2, 0), sticky="w")

        self.btn = ttk.Button(form, text="Desbloquear", style="App.TButton", command=self._try_open_vault)
        self.btn.grid(row=2, column=0, pady=SPACING_M, sticky="")

        self._return_binding = self.master.bind("<Return>", lambda _e: self._try_open_vault())
        self._escape_binding = self.master.bind("<Escape>", lambda _e: self._cancel())
        self.master.protocol("WM_DELETE_WINDOW", self._cancel)

        self.after(0, self._bring_front_and_focus)

    def _center_root(self, width: int, height: int) -> None:
        try:
            self.master.update_idletasks()
            sw, sh = self.master.winfo_screenwidth(), self.master.winfo_screenheight()
            x = max(0, (sw - width) // 2)
            y = max(0, (sh - height) // 2)
            self.master.geometry(f"{width}x{height}+{x}+{y}")
        except Exception:
            pass

    def _toggle_password_visibility(self) -> None:
        if self.show_pass_var.get():
            self.pass_entry.config(show="*")
            self.toggle_btn.config(text="👁")
            self.show_pass_var.set(False)
        else:
            self.pass_entry.config(show="")
            self.toggle_btn.config(text="🙈")
            self.show_pass_var.set(True)

    def _bring_front_and_focus(self) -> None:
        try:
            self.master.lift()
            self.master.focus_force()
        except Exception:
            pass
        try:
            self.user_entry.focus_set()
            self.user_entry.selection_range(0, tk.END)
        except Exception:
            pass

    def _cleanup_bindings(self) -> None:
        try:
            if self._return_binding:
                self.master.unbind("<Return>", self._return_binding)
        except Exception:
            pass
        finally:
            self._return_binding = None
        try:
            if self._escape_binding:
                self.master.unbind("<Escape>", self._escape_binding)
        except Exception:
            pass
        finally:
            self._escape_binding = None
        try:
            self.master.protocol("WM_DELETE_WINDOW", self.master.destroy)
        except Exception:
            pass

    def _cancel(self) -> None:
        self._cleanup_bindings()
        try:
            self.destroy()
        finally:
            self.master.destroy()

    def _finish_success(self) -> None:
        self._cleanup_bindings()
        try:
            self.destroy()
        except Exception:
            pass

    def _try_open_vault(self) -> None:
        usuario = self.user_var.get().strip()
        pwd = self.pass_var.get().strip()

        if not usuario:
            messagebox.showerror("Error", "Por favor ingresa el nombre de usuario.")
            try:
                self.user_entry.focus_set()
            except Exception:
                pass
            return

        if not pwd:
            messagebox.showerror("Error", "Por favor ingresa la clave del vault.")
            return

        self.btn.config(text="Verificando...", state="disabled")
        self.update_idletasks()

        try:
            ubicacion = self.security.detectar_ubicacion()
            vault_filename = self.security.resolve_vault_filename(ubicacion)
            vault_path = None
            if vault_filename:
                try:
                    vault_path = resolve_named_vault_path(vault_filename)
                except FileNotFoundError:
                    vault_path = None

            vault = load_vault_from_credentials(
                usuario,
                pwd,
                vault_path=vault_path,
                require_authorized=self.require_authorized,
            )
        except Exception as exc:
            messagebox.showerror("Acceso denegado", str(exc))
            self.btn.config(text="Desbloquear", state="normal")
            return

        rol = "admin"
        self._finish_success()
        self.on_success(vault, usuario, rol)

    # ---------- Demo ----------
if __name__ == "__main__":
    def _fake_on_success(vault, usuario, rol):
        messagebox.showinfo("Login ok", f"Bienvenido {usuario} ({rol})")
        ttk.Label(root, text="Contenido principal...").pack(padx=20, pady=20)

    root = tk.Tk()
    style = ttk.Style(root)
    style.configure("App.TFrame")
    style.configure("App.TLabel")
    style.configure("App.Subtitle.TLabel", font=("Segoe UI", 12, "bold"))
    style.configure("App.TEntry")
    style.configure("App.TButton")

    LoginWindow(root, on_success=_fake_on_success, require_authorized=True)
    root.mainloop()
