from fastapi import APIRouter, Body, Request
from .service import execute
router = APIRouter(tags=["M5-索引对账"])

@router.get("/reconcile")
def page(request: Request):
    # 预览不写批次，避免只浏览页面就产生记录。
    data = execute()
    return request.app.state.templates.TemplateResponse(request, "m5_reconcile.html", {"title": "索引对账", "data": data})

@router.post("/api/reconcile")
def api(request: Request, payload: dict = Body(default={})):
    return execute(payload or None, store=request.app.state.store)
