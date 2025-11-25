# controllers/app_controller.py
import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
from typing import Any, Dict, List, Optional

from state.app_state import AppState
from services.security_service import SecurityService
from services.server_resolver import ServerResolver
from controllers.frame_router import FrameRouter

from utils.ui_actions import seleccionar_archivo as _seleccionar_archivo_helper
from utils.ui_actions import mostrar_boton_seleccionar_archivo_unifilares as _mostrar_btn_unif_helper
from utils.ui_actions import seleccionar_archivo_simple as _seleccionar_archivo_simple 
from utils.task_runner import TaskRunner

from interfaces.marco_buscar_key import crear_marco_buscar_key
from interfaces.marco_jobs import crear_marco_jobs
from interfaces.marco_unifilares import crear_marco_unifilares
from interfaces.marco_hsh import crear_marco_hsh
from interfaces.marco_bienvenida import crear_marco_bienvenida
from interfaces.marco_pruebas_pyp import crear_marco_pruebas_pyp
from interfaces.marco_consultar import crear_marco_consultar
from handlers.actualizar_datos import ejecutar_actualizar_datos_default

from ui.theme import PRIMARY, SPACING_M, BACKGROUND
from ui.components.navbar import build_navbar
from ui.components.statusbar import StatusBar
from utils.paths import ensure_workdirs, asset_path, project_root, bundle_root

class AppController:

    def __init__(
        self,
        root: tk.Tk,
        base_dir: str,
        usuario: Optional[str] = None,
        rol: Optional[str] = None,
        vault: Optional[Dict[str, Any]] = None,
    ):
        self.ventana = root
        self.marco_actual: Optional[tk.Widget] = None
        self._tasks_running = False
        self.tasks = TaskRunner(self.ventana)
        self.tasks.add_state_listener(self._on_task_runner_state)

        self.base_dir = ensure_workdirs()
        # self.resource_root = project_root()
        self.resource_root = bundle_root()

        self.root = root
        self.state = AppState(usuario=usuario, rol=rol)
        self.security = SecurityService()
        self.server_resolver = ServerResolver(os.path.join(self.resource_root, "config"))
        self.router = FrameRouter(root)

        self.vault: Dict[str, Any] = vault or {}
        self._last_secure_env_keys: List[str] = []
        self.secure_env(trace=True)

        self.styles = set()
        try:
            style = ttk.Style(self.ventana)  # requiere que Tk esté inicializado
            if style.layout("App.Small.TLabel"):
                self.styles.add("App.Small.TLabel")
        except tk.TclError:
            pass


        self.empresa_claves = self.server_resolver.empresa_claves_view()
        self.opciones_dominio = self.server_resolver.opciones_dominio_view()

        self.archivo_excel_buscar_keys = None
        self.archivo_crear_senales = None
        self.archivo_eliminar_senales = None
        self.archivos_unifilares = None
        self.archivo_cambiar_nombre = None
        self.hsh_crear_tag_file = None
        self.hsh_cambiar_key_file = None
        self.hsh_eliminar_tag_file = None

        self.boton_buscar_key = None
        self.boton_ejecutar_unifilares = None
        self.boton_seleccionar_archivo_unifilares = None
        self.boton_crear_tag_hsh = None
        self.boton_seleccionar_archivo_hsh_crear = None
        self.lbl_archivo_hsh_crear = None
        self.boton_seleccionar_archivo_hsh_cambiar = None
        self.boton_validar_cambiar_key_hsh = None
        self.boton_cambiar_key_hsh = None
        self.lbl_archivo_hsh_cambiar = None
        self.boton_seleccionar_archivo_hsh_eliminar = None
        self.boton_validar_tag_hsh_eliminar = None
        self.boton_eliminar_tag_hsh = None
        self.lbl_archivo_hsh_eliminar = None
        self.sidebar_nav = None
        self._status_manual = False
        self._auto_status_active = False

        self.opcion_empresa_pyp = tk.StringVar(value="Empresa...")
        self.opcion_dominio_pyp = tk.StringVar(value="Dominio...")
        self.pyp_inicio = tk.StringVar(value="YYYY-MM-DD HH:MM")
        self.pyp_fin = tk.StringVar(value="YYYY-MM-DD HH:MM")
        self.opciones_empresa_pyp = self.security.empresas_para_jobs(self.state.ubicacion)

        self.pyp_checklist_file = None
        self.pyp_eventosdiario_file = None
        self.pyp_varexp_file = None
        self.pyp_tmwgateway_file = None

        self.btn_pyp_checklist = None
        self.btn_pyp_eventosdiario = None
        self.btn_pyp_varexp = None
        self.btn_pyp_tmwgateway = None

        self.lbl_pyp_checklist = None
        self.lbl_pyp_eventosdiario = None
        self.lbl_pyp_varexp = None
        self.lbl_pyp_tmwgateway = None

        self.opcion_empresa_unifilares = tk.StringVar(value="Empresa...")
        self.opcion_dominio_unifilares = tk.StringVar(value="Dominio...")
        self.checkbox_var_unifilares = tk.BooleanVar(value=False)

        self._setup_window()
        self._setup_menu()
        self._guard_location()
        self._register_frames()
        self.mostrar_marco(self.router.build("bienvenida"))

    def _register_frames(self):
        self.router.register("bienvenida", lambda: crear_marco_bienvenida(self))

    def abrir_actualizacion_buscar_keys(self) -> None:
        """Ejecuta la actualización de datos usando el perfil default."""
        ejecutar_actualizar_datos_default(self)


    def set_vault(self, vault: Dict[str, Any]) -> None:
        self.vault = vault or {}
        self.secure_env(trace=True)

    def secure_env(self, trace: bool = False) -> Dict[str, str]:
        env = os.environ.copy()
        loaded_from_vault: List[str] = []

        # --- Mongo ---
        if "mongo_user" in self.vault:
            env["MONGO_USER"] = str(self.vault["mongo_user"])
            loaded_from_vault.append("MONGO_USER")
        if "mongo_pass" in self.vault:
            env["MONGO_PASS"] = str(self.vault["mongo_pass"])
            loaded_from_vault.append("MONGO_PASS")
        if "mongo_port" in self.vault:
            env["MONGO_PORT"] = str(self.vault["mongo_port"])
            loaded_from_vault.append("MONGO_PORT")
        if "replica_set" in self.vault:
            env["REPLICA_SET"] = str(self.vault["replica_set"])
            loaded_from_vault.append("REPLICA_SET")

        # --- SSH / túneles --- 
        if "ssh_user" in self.vault:
            env["SSH_USER"] = str(self.vault["ssh_user"])
            loaded_from_vault.append("SSH_USER")
        if "ssh_key_pem" in self.vault:
            env["SSH_KEY_PEM"] = str(self.vault["ssh_key_pem"])
            loaded_from_vault.append("SSH_KEY_PEM")
        if "ssh_key_passphrase" in self.vault:
            env["SSH_KEY_PASSPHRASE"] = str(self.vault["ssh_key_passphrase"])
            loaded_from_vault.append("SSH_KEY_PASSPHRASE")
        if "ssh_port" in self.vault:
            env["SSH_PORT"] = str(self.vault["ssh_port"])
            loaded_from_vault.append("SSH_PORT")

        # --- Hosts (SCADA / HIS) ---
        if "sca_hosts" in self.vault:
            sca = self.vault["sca_hosts"]
            env["SCA_HOSTS"] = ",".join(sca) if isinstance(sca, (list, tuple)) else str(sca)
            loaded_from_vault.append("SCA_HOSTS")

        if "his_hosts" in self.vault:
            his = self.vault["his_hosts"]
            # Cadena completa (para compatibilidad)
            env["HIS_HOSTS"] = ",".join(his) if isinstance(his, (list, tuple)) else str(his)
            loaded_from_vault.append("HIS_HOSTS")
            # Derivados convenientes
            if isinstance(his, (list, tuple)) and his:
                env["HIS_PRIMARY"] = str(his[0])
                loaded_from_vault.append("HIS_PRIMARY")
                if len(his) > 1:
                    env["HIS_SECONDARY"] = str(his[1])
                    loaded_from_vault.append("HIS_SECONDARY")

        # --- TLS (Mongo) ---
        if "tls_cert_key_pem" in self.vault:
            env["TLS_CERT_KEY_PEM"] = str(self.vault["tls_cert_key_pem"])
            loaded_from_vault.append("TLS_CERT_KEY_PEM")
        if "tls_ca_cert" in self.vault:
            env["TLS_CA_CERT"] = str(self.vault["tls_ca_cert"])
            loaded_from_vault.append("TLS_CA_CERT")

        def _read(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception:
                return None

        if "TLS_CERT_KEY_PEM" not in env or not env["TLS_CERT_KEY_PEM"]:
            bundle_root = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
            pem_path = os.path.join(bundle_root, "_runners", "cifrar", "mongo_client.pem")
            alt_dev  = os.path.join(os.path.dirname(__file__), os.pardir, "scripts", "cifrar", "mongo_client.pem")
            pem = _read(pem_path) or _read(os.path.abspath(alt_dev))
            if pem:
                env["TLS_CERT_KEY_PEM"] = pem

        if "TLS_CA_CERT" not in env or not env["TLS_CA_CERT"]:
            bundle_root = getattr(sys, "_MEIPASS", os.path.dirname(__file__))
            ca_path = os.path.join(bundle_root, "_runners", "cifrar", "mongo_ca.pem")
            alt_dev = os.path.join(os.path.dirname(__file__), os.pardir, "scripts", "cifrar", "mongo_ca.pem")
            ca = _read(ca_path) or _read(os.path.abspath(alt_dev))
            if ca:
                env["TLS_CA_CERT"] = ca

        # --- ODBC / HIS (PostgreSQL) ---
        # Estas vienen del vault como: odbc_driver, odbc_db, odbc_user, odbc_pass
        if "odbc_driver" in self.vault:
            env["ODBC_DRIVER"] = str(self.vault["odbc_driver"])
            loaded_from_vault.append("ODBC_DRIVER")
        if "odbc_db" in self.vault:
            env["ODBC_DB"] = str(self.vault["odbc_db"])
            loaded_from_vault.append("ODBC_DB")
        if "odbc_user" in self.vault:
            env["ODBC_USER"] = str(self.vault["odbc_user"])
            loaded_from_vault.append("ODBC_USER")
        if "odbc_pass" in self.vault:
            env["ODBC_PASS"] = str(self.vault["odbc_pass"])
            loaded_from_vault.append("ODBC_PASS")

        # Opcionales útiles
        if "odbc_port" in self.vault:
            env["ODBC_PORT"] = str(self.vault["odbc_port"])
            loaded_from_vault.append("ODBC_PORT")
        else:
            # default PostgreSQL
            env.setdefault("ODBC_PORT", "5432")

        # --- PI ---
        if "user_pi" in self.vault:
            env["USER_PI"] = str(self.vault["user_pi"])
            loaded_from_vault.append("USER_PI")
        if "pass_pi" in self.vault:
            env["PASS_PI"] = str(self.vault["pass_pi"])
            loaded_from_vault.append("PASS_PI")
 
        # Convenios app/runtime
        env["ADA_BASE_DIR"] = self.base_dir
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["FORCE_COLOR"] = "1"

        unique_keys = sorted(dict.fromkeys(loaded_from_vault))
        self._last_secure_env_keys = unique_keys
        if trace:
            if unique_keys:
                print(f"[ADA] Variables de entorno cargadas desde el vault ({len(unique_keys)}): {', '.join(unique_keys)}")
            else:
                print("[ADA] No se cargaron variables de entorno desde el vault.")
            print("[ADA] Variables adicionales aplicadas por la aplicación: ADA_BASE_DIR, PYTHONUNBUFFERED, PYTHONIOENCODING, FORCE_COLOR")

        return env

    # ------------------------------------------------------------------
    # Tareas asíncronas
    # ------------------------------------------------------------------
    def _on_task_runner_state(self, running: bool) -> None:
        self._tasks_running = running
        console = getattr(self, "console", None)
        if console and hasattr(console, "has_stop_handler") and console.has_stop_handler():
            console.set_stop_enabled(running)
        if not hasattr(self, "statusbar"):
            return
        if running:
            if not getattr(self, "_status_manual", False) and not getattr(self, "_auto_status_active", False):
                self.statusbar.start("Procesando tareas...", indeterminate=True)
                self._auto_status_active = True
        else:
            if getattr(self, "_auto_status_active", False) and not getattr(self, "_status_manual", False):
                self.statusbar.success("Listo")
                self._auto_status_active = False

    def stop_running_tasks(self) -> None:
        if self.tasks.stop_all():
            if getattr(self, "console", None):
                try:
                    self.console.write(">> Solicitud de detención enviada.", "warn")
                except Exception:
                    pass
        else:
            if getattr(self, "console", None):
                try:
                    self.console.write(">> No hay procesos en ejecución para detener.", "warn")
                except Exception:
                    pass

    # ------------------ Setup UI ------------------

    def _setup_window(self):
        # Título y fondo
        self.ventana.title("ADA - DOT INTERCOLOMBIA")
        self.ventana.configure(bg=BACKGROUND)
        self.ventana.columnconfigure(0, weight=1)
        self.ventana.rowconfigure(0, weight=1)

        shell = ttk.Frame(self.ventana, style="App.TFrame")
        shell.grid(row=0, column=0, sticky="nsew")
        shell.columnconfigure(0, weight=0)
        shell.columnconfigure(1, weight=1)
        shell.rowconfigure(0, weight=1)

        # Sidebar (left)
        self.sidebar_container = ttk.Frame(shell, style="App.Sidebar.TFrame")
        self.sidebar_container.grid(row=0, column=0, sticky="nsw")
        self.sidebar_container.configure(width=240)
        self.sidebar_container.grid_propagate(False)
        self.sidebar_container.rowconfigure(0, weight=1)
        self.sidebar_container.columnconfigure(0, weight=1)

        # Área derecha (header + contenido + status)
        right = ttk.Frame(shell, style="App.TFrame")
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        header = ttk.Frame(right, style="App.TFrame")
        header.grid(row=0, column=0, sticky="ew", padx=SPACING_M, pady=(SPACING_M, 0))
        header.columnconfigure(0, weight=1)

        logo_path = asset_path("ISAlogotipo.png") 
        if os.path.exists(logo_path):
            try:
                logo_img = Image.open(logo_path)
                max_width = 250
                if logo_img.width > max_width:
                    ratio = max_width / logo_img.width if logo_img.width else 1
                    logo_img = logo_img.resize((max_width, int(logo_img.height * ratio)), Image.LANCZOS)
                logo_photo = ImageTk.PhotoImage(logo_img)
                lbl_logo = tk.Label(header, image=logo_photo, borderwidth=0, bg=BACKGROUND)
                lbl_logo.image = logo_photo  # keep ref
                lbl_logo.grid(row=0, column=0, sticky="e")
            except Exception:
                pass

        self.content = ttk.Frame(right, style="App.TFrame")
        self.content.grid(row=1, column=0, sticky="nsew", padx=SPACING_M, pady=(SPACING_M, SPACING_M))
        self.content.columnconfigure(0, weight=1)
        self.content.rowconfigure(0, weight=1)

        self.statusbar = StatusBar(right, style_frame="App.TFrame", style_label="App.Muted.TLabel")
        self.statusbar.grid(row=2, column=0, sticky="ew", padx=SPACING_M, pady=(0, SPACING_M))

        self.ventana.update_idletasks()
        try:
            self.ventana.state('zoomed')
        except Exception:
            try:
                self.ventana.attributes('-zoomed', True)
            except Exception:
                self.ventana.attributes('-fullscreen', True)


        # ------------------ Status helpers ------------------
    
    def set_status(self, msg: str):
        if hasattr(self, "statusbar"):
            self.statusbar.set(msg)

    def start_status(self, msg: str, indeterminate: bool = True):
        if hasattr(self, "statusbar"):
            self.statusbar.start(msg, indeterminate=indeterminate)
            self._status_manual = True
            self._auto_status_active = False

    def success_status(self, msg: str = "Listo"):
        if hasattr(self, "statusbar"):
            self.statusbar.success(msg)
            self._status_manual = False
            self._auto_status_active = False

    def error_status(self, msg: str):
        if hasattr(self, "statusbar"):
            self.statusbar.error(msg)
            self._status_manual = False
            self._auto_status_active = False

    def stop_status(self):
        if hasattr(self, "statusbar"):
            self.statusbar.stop()
            self._status_manual = False
            self._auto_status_active = False


    def _setup_menu(self):
        # Definición de menús
        groups = {
            "Buscar":    {"Key": 1, "Keys": 2},
            "HSH":       {"Crear Tag": 1, "Cambiar Scada Key": 2, "Cambiar Tag": 3, "Eliminar Tag": 4, "Validar": 5},
            "Jobs":      {"Crear Señales": 1, "Eliminar Señales": 2, "Cambiar nombre": 3},
            "Unifilares": {"Validar": 1},
            "Pruebas PyP": {"itcosasv1": 1, "itcosasv2": 2},
            "Consultar": {"Consultar RTU": 1}
        }
        self.sidebar_nav = build_navbar(
            self.sidebar_container,
            groups,
            self._on_menu_select,
            on_home=self._show_home,
        )
        self.sidebar_nav.grid(row=0, column=0, sticky="nsew")


    def _on_menu_select(self, grupo: str, nombre: str, valor: int):
        key = (grupo, nombre, valor)
        skey = str(key)
        if grupo == "Buscar":
            self.router.register(skey, lambda: crear_marco_buscar_key(self, valor))
        elif grupo == "HSH":
            self.router.register(skey, lambda: crear_marco_hsh(self, valor))
        elif grupo == "Jobs":
            self.router.register(skey, lambda: crear_marco_jobs(self, valor))
        elif grupo == "Unifilares":
            self.router.register(skey, lambda: crear_marco_unifilares(self, valor))
        # NUEVO:
        elif grupo == "Pruebas PyP":
            self.router.register(skey, lambda: crear_marco_pruebas_pyp(self, valor))
        elif grupo == "Consultar":
            self.router.register(skey, lambda: crear_marco_consultar(self, valor))
        self.mostrar_marco(self.router.build(skey))
        if self.sidebar_nav:
            self.sidebar_nav.set_active(skey)

    def _show_home(self):
        if self.sidebar_nav:
            self.sidebar_nav.set_active(None)
        self.mostrar_marco(self.router.build("bienvenida"))


    def _guard_location(self):
        ubi = self.security.detectar_ubicacion()
        self.state.ubicacion = ubi
        if ubi == "Desconocido":
            messagebox.showerror("Acceso denegado", "No se puede usar esta aplicación en este PC.")
            self.ventana.destroy()

    def mostrar_marco(self, marco: tk.Widget):
        # Desmontar marco anterior si existe

        if getattr(self, "marco_actual", None):
            try:
                self.marco_actual.grid_forget()
            except Exception:
                try:
                    self.marco_actual.pack_forget()
                except Exception:
                    pass

        # Montar el nuevo marco en el área de contenido, expandiendo
        try:
            marco.grid(in_=self.content, row=0, column=0, sticky="nsew")
        except Exception:
            # fallback a pack si el marco usa pack internamente
            marco.pack(in_=self.content, fill="both", expand=True)

        self.marco_actual = marco
        self.ventana.update_idletasks()

    def generar_server(self, empresa: str, dominio: str):
        return self.server_resolver.generar_server(empresa, dominio)

    def obtener_empresas_permitidas(self):
        return self.security.empresas_permitidas(self.state.ubicacion)

    def obtener_empresas_jobs(self):
        return self.security.empresas_para_jobs(self.state.ubicacion)

    def ejecutar_en_hilo(self, funcion, *args, boton_finalizar=None, texto_final=" ¡Realizado! "):
        def _proceso():
            try:
                funcion(*args)
            except Exception as e:
                messagebox.showerror("Error", str(e))
            finally:
                if boton_finalizar is not None:
                    try:
                        boton_finalizar.config(text=texto_final, state="normal")
                    except Exception:
                        pass
        t = threading.Thread(target=_proceso, daemon=True)
        t.start()
        return t

    def seleccionar_archivo(self, *args, **kwargs):
        """
        Modo compatibilidad:
        - Si vienen kwargs tipo title/extensions/multiple -> usa el selector simple nuevo.
        - Si no -> delega al helper legacy (que espera botones, vars, etc.).
        """
        # Soporta nuevo flujo (kwargs)
        if any(k in kwargs for k in ("title", "extensions", "multiple", "initialdir")):
            title = kwargs.get("title", "Seleccionar archivo")
            extensions = kwargs.get("extensions")
            multiple = kwargs.get("multiple", False)
            initialdir = kwargs.get("initialdir")
            return _seleccionar_archivo_simple(
                title=title,
                extensions=extensions,
                multiple=multiple,
                initialdir=initialdir,
            )

        # Flujo legacy (interfaz antigua)
        return _seleccionar_archivo_helper(self, *args, **kwargs)

    def mostrar_boton_seleccionar_archivo_unifilares(self):
        return _mostrar_btn_unif_helper(self)

