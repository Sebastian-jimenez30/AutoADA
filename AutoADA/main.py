import sys, os, runpy
from utils.paths import asset_path

def _bundle_root():
    if getattr(sys, "frozen", False):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.abspath(__file__))

def _cli_dispatcher():

    if len(sys.argv) >= 3 and sys.argv[1] == "--run":
        mod = sys.argv[2]
        args = sys.argv[3:]

        if mod.startswith("scripts."):
            rel = mod.split(".", 1)[1].replace(".", os.sep) + ".py"
            candidate = os.path.join(_bundle_root(), "_runners", rel)
            if os.path.exists(candidate):
                script_dir = os.path.dirname(candidate)
                if script_dir not in sys.path:
                    sys.path.insert(0, script_dir)
                sys.argv = [candidate] + args
                runpy.run_path(candidate, run_name="__main__")
                raise SystemExit(0)

        if mod.startswith("scripts."):
            dev_scripts_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")
            if os.path.isdir(dev_scripts_dir) and dev_scripts_dir not in sys.path:
                sys.path.insert(0, dev_scripts_dir)

        sys.argv = [mod] + args
        runpy.run_module(mod, run_name="__main__")
        raise SystemExit(0)


_cli_dispatcher()

from controllers.app_controller import AppController
from login import LoginWindow

def main():
    import tkinter as tk
    from ui.theme import apply_theme 

    base_dir = os.path.dirname(__file__)
    root = tk.Tk()
    root.title("ADA - DOT INTERCOLOMBIA")
    icon_path = asset_path("Logodot.ico")
    if os.path.exists(icon_path):
        try:
            root.iconbitmap(icon_path)  # Windows
        except Exception:
            try:
                root.iconbitmap(default=icon_path)
            except Exception:
                pass

    apply_theme(root)

    login_view = None

    def on_login_success(vault, usuario, rol):
        nonlocal login_view
        if login_view is not None:
            try:
                login_view.destroy()
            except Exception:
                pass
            login_view = None
        AppController(root, base_dir, usuario=usuario, rol=rol, vault=vault)

    login_view = LoginWindow(root, on_success=on_login_success, require_authorized=False)
    root.mainloop()

if __name__ == "__main__":
    main()
