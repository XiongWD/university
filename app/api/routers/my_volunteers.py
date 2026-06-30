"""我的志愿组 API（design：志愿编排工作台）。

单用户 MVP：owner_key 固定 "default"。服务端用 group.profile_snapshot 重新校验资格/档位，
不信任前端传的任何展示字段（前端只传 school_code+major_group_code）。

端点：
  GET    /my-volunteers                         获取志愿组（重算 latest_algorithm_tier + stats）
  POST   /my-volunteers/items                   添加志愿（服务端重新校验）
  PATCH  /my-volunteers/layout                  原子布局更新（跨档拖拽专用）
  PATCH  /my-volunteers/items/{id}/tier         单改规划档位
  DELETE /my-volunteers/items/{id}              删除单个
  POST   /my-volunteers/clear                   清空全部
"""
from __future__ import annotations

import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import Session

from app.db import get_session_dep
from app.models.volunteer import UserVolunteerGroup, VolunteerConflictError
from app.repositories import volunteer_repo

router = APIRouter(prefix="/my-volunteers", tags=["my-volunteers"])

DEFAULT_OWNER = "default"

# 测试隔离：当 VOLUNTEER_OWNER_ISOLATION=1 时，允许请求通过 X-Owner-Key header
# 选择独立 owner_key（每个 E2E 测试用唯一 owner，彻底隔离志愿组，杜绝测试间污染）。
# 生产环境默认关闭，保持单用户 MVP 的 "default" owner。
_OWNER_ISOLATION = os.getenv("VOLUNTEER_OWNER_ISOLATION", "") == "1"
_OWNER_HEADER = "X-Owner-Key"


def _resolve_owner(request: Request) -> str:
    """解析当前请求的 owner_key：隔离开启时读 header，否则固定 default。"""
    if not _OWNER_ISOLATION:
        return DEFAULT_OWNER
    owner = request.headers.get(_OWNER_HEADER) or DEFAULT_OWNER
    # 仅允许字母数字/下划线/连字符，避免注入或路径穿越
    if owner != DEFAULT_OWNER and not owner.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=400, detail="非法 owner_key")
    return owner


class AddItemRequest(BaseModel):
    school_code: str
    major_group_code: str
    # 考生档案（首次添加时绑定，后续重算依据）。前端从当前推荐表单传入。
    profile: dict


class LayoutItem(BaseModel):
    item_id: int
    planned_tier: str | None = None
    sort_order: int


class LayoutRequest(BaseModel):
    items: list[LayoutItem]
    version: int


class TierRequest(BaseModel):
    planned_tier: str | None = None
    version: int


class ClearRequest(BaseModel):
    confirm: bool
    version: int


def _conflict_response(exc: VolunteerConflictError) -> JSONResponse:
    """乐观锁冲突 → 409，返回最新 group 供前端加载。"""
    body: dict = {"error": "version_conflict", "message": str(exc)}
    if exc.latest_group is not None:
        body["latest_group"] = exc.latest_group.model_dump(mode="json")
    return JSONResponse(status_code=409, content=body)


@router.get("")
def get_my_volunteers(request: Request, session: Session = Depends(get_session_dep)):
    """获取志愿组（GET 重算 latest_algorithm_tier + stats）。"""
    group = volunteer_repo.get_group(session, _resolve_owner(request))
    return group.model_dump(mode="json")


@router.post("/items")
def add_item(req: AddItemRequest, request: Request, session: Session = Depends(get_session_dep)):
    """添加志愿（服务端用 profile 重新校验资格/档位，不信任前端展示字段）。"""
    try:
        group = volunteer_repo.add_item(
            session, _resolve_owner(request), req.school_code, req.major_group_code, req.profile
        )
    except VolunteerConflictError as exc:
        return _conflict_response(exc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return group.model_dump(mode="json")


@router.patch("/layout")
def apply_layout(req: LayoutRequest, request: Request, session: Session = Depends(get_session_dep)):
    """原子布局更新（跨档拖拽专用）：单事务改 planned_tier+全局sort_order+version。"""
    owner = _resolve_owner(request)
    group_row = volunteer_repo.get_or_create_group(session, owner)
    try:
        group = volunteer_repo.apply_layout(
            session, group_row,
            [li.model_dump() for li in req.items], req.version,
        )
    except VolunteerConflictError as exc:
        return _conflict_response(exc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return group.model_dump(mode="json")


@router.patch("/items/{item_id}/tier")
def update_tier(item_id: int, req: TierRequest, request: Request, session: Session = Depends(get_session_dep)):
    """菜单内单改规划档位（null=恢复用算法档位）。"""
    owner = _resolve_owner(request)
    group_row = volunteer_repo.get_or_create_group(session, owner)
    try:
        group = volunteer_repo.update_planned_tier(
            session, group_row, item_id, req.planned_tier, req.version
        )
    except VolunteerConflictError as exc:
        return _conflict_response(exc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return group.model_dump(mode="json")


@router.delete("/items/{item_id}")
def delete_item(item_id: int, request: Request, version: int, session: Session = Depends(get_session_dep)):
    """删除单个志愿 + 重排 sort_order + version+1。

    version 走 query 参数（DELETE 带 body 兼容性差）。
    """
    owner = _resolve_owner(request)
    group_row = volunteer_repo.get_or_create_group(session, owner)
    try:
        group = volunteer_repo.delete_item(session, group_row, item_id, version)
    except VolunteerConflictError as exc:
        return _conflict_response(exc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return group.model_dump(mode="json")


@router.post("/clear")
def clear_group(req: ClearRequest, request: Request, session: Session = Depends(get_session_dep)):
    """清空全部志愿（单条 SQL 删全组 items，事务化）。"""
    if not req.confirm:
        raise HTTPException(status_code=400, detail="需 confirm=true 才能清空")
    owner = _resolve_owner(request)
    group_row = volunteer_repo.get_or_create_group(session, owner)
    try:
        group = volunteer_repo.clear_group(session, group_row, req.version)
    except VolunteerConflictError as exc:
        return _conflict_response(exc)
    return group.model_dump(mode="json")
