from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from services.vault_service import VaultService

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@router.post("/login", response_class=HTMLResponse)
def login_action(request: Request, usuario: str = Form(...), clave: str = Form(...)):
    try:
        VaultService.load_vault(usuario, clave)
        return templates.TemplateResponse("login.html", {
            "request": request,
            "success": True
        })
    except Exception as e:
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": str(e)
        })
