from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/menu", response_class=HTMLResponse)
def menu_page(request: Request):
    return templates.TemplateResponse("menu.html", {"request": request})
