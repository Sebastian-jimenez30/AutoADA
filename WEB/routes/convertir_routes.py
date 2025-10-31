from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from controllers import convertir_controller

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _base_context(
    request: Request,
    empresa: str | None = None,
    modo: str = "Buscar_keys",
    result: str | None = None,
):
    return {
        "request": request,
        "active_page": "convertir",
        "page_title": "Convertir datos",
        "page_subtitle": "Genera reportes operativos a partir de la información importada.",
        "empresa": empresa,
        "modo": modo,
        "result": result,
    }


@router.get("/convertir", response_class=HTMLResponse)
def convertir_page(request: Request):
    return templates.TemplateResponse("convertir.html", _base_context(request))


@router.post("/convertir", response_class=HTMLResponse)
def ejecutar_convertir(
    request: Request,
    empresa: str = Form(...),
    modo: str = Form("Buscar_keys"),
):
    result = convertir_controller.ejecutar_convertir(empresa, modo)
    return templates.TemplateResponse("convertir.html", _base_context(request, empresa, modo, result))
