from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from controllers import importar_controller

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _base_context(request: Request, empresa: str | None = None, result: str | None = None):
    return {
        "request": request,
        "active_page": None,
        "active_section": "buscar",
        "page_title": "Importar datos",
        "page_subtitle": "Sincroniza los datasets SCADA, HSH y ODS desde los servidores remotos autorizados.",
        "empresa": empresa,
        "result": result,
    }


@router.get("/importar", response_class=HTMLResponse)
def importar_page(request: Request):
    return templates.TemplateResponse("importar.html", _base_context(request))


@router.post("/importar", response_class=HTMLResponse)
def ejecutar_importacion(request: Request, empresa: str = Form(...)):
    result = importar_controller.ejecutar_importar(empresa)
    return templates.TemplateResponse("importar.html", _base_context(request, empresa, result))
