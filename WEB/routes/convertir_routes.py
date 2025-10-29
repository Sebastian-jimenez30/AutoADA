from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from controllers import convertir_controller

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/convertir", response_class=HTMLResponse)
def convertir_page(request: Request):
    return templates.TemplateResponse("convertir.html", {"request": request})

@router.post("/convertir", response_class=HTMLResponse)
def ejecutar_convertir(request: Request, empresa: str = Form(...)):
    result = convertir_controller.ejecutar_convertir(empresa)
    return templates.TemplateResponse(
        "convertir.html",
        {"request": request, "empresa": empresa, "result": result},
    )
