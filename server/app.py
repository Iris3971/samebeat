"""SameBeat Server。

- POST /ingest：接收 Mac Agent 上报（Phase 2）
- GET  /state：仅供验收与排错（Phase 2）
- /mcp/<secret>：只读 MCP（Streamable HTTP，Phase 3）

环境变量：
  SAMEBEAT_TOKEN          必填，/ingest 与 /state 的 Bearer token
  SAMEBEAT_MCP_SECRET     必填，MCP 秘密路径（与 SAMEBEAT_TOKEN 必须不同）；轮换 = 改值后重启
  SAMEBEAT_USER_TIMEZONE  用户时区，「今天」和可读时间按它计算，默认 Asia/Shanghai
  SAMEBEAT_PUBLIC_HOSTS   允许的 Host 头（逗号分隔），默认仅本机；公网部署必须显式配置
  SAMEBEAT_DB             SQLite 路径，默认 /data/samebeat.db
"""

from __future__ import annotations

import contextlib
import hmac
import logging
import os
import time
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import Depends, FastAPI, HTTPException, Request
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, Field

from mcp_tools import build_mcp
from store import Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

TOKEN = os.environ.get("SAMEBEAT_TOKEN", "")
if len(TOKEN) < 32:
    raise SystemExit("SAMEBEAT_TOKEN 未设置或太短（至少 32 个字符）")
MCP_SECRET = os.environ.get("SAMEBEAT_MCP_SECRET", "")
if len(MCP_SECRET) < 32 or not MCP_SECRET.isalnum():
    raise SystemExit("SAMEBEAT_MCP_SECRET 未设置、太短（至少 32 个字符）或含非字母数字字符")
if hmac.compare_digest(MCP_SECRET, TOKEN):
    raise SystemExit("SAMEBEAT_MCP_SECRET 不能与 SAMEBEAT_TOKEN 相同")
USER_TZ = ZoneInfo(os.environ.get("SAMEBEAT_USER_TIMEZONE", "Asia/Shanghai"))
PUBLIC_HOSTS = [h.strip() for h in os.environ.get("SAMEBEAT_PUBLIC_HOSTS", "").split(",") if h.strip()]


class RedactSecret(logging.Filter):
    """任何日志里出现 MCP 秘密都替换掉（uvicorn 访问日志会记录完整路径）。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(a.replace(MCP_SECRET, "<secret>") if isinstance(a, str) else a
                                for a in record.args)
        if isinstance(record.msg, str) and MCP_SECRET in record.msg:
            record.msg = record.msg.replace(MCP_SECRET, "<secret>")
        return True


for name in ("uvicorn.access", "uvicorn.error", "uvicorn", ""):
    logging.getLogger(name).addFilter(RedactSecret())

store = Store(os.environ.get("SAMEBEAT_DB", "/data/samebeat.db"))

mcp = build_mcp(store, USER_TZ)
mcp_app = mcp.streamable_http_app(
    streamable_http_path=f"/mcp/{MCP_SECRET}",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=PUBLIC_HOSTS + ["127.0.0.1:*", "localhost:*"],
        allowed_origins=[f"https://{h}" for h in PUBLIC_HOSTS] + ["https://claude.ai", "https://chatgpt.com"],
    ),
)


@contextlib.asynccontextmanager
async def lifespan(_app):
    async with mcp.session_manager.run():
        yield


app = FastAPI(title="SameBeat", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
app.router.routes.extend(mcp_app.routes)

Text = Field(default=None, max_length=500)


class LastKnown(BaseModel):
    stale: Literal[True]
    title: str | None = Text
    artist: str | None = Text
    album: str | None = Text
    duration: float | None = Field(default=None, ge=0, le=86400)
    position: float | None = Field(default=None, ge=0, le=86400)
    playing: bool | None = None
    observed_at: float | None = None


class Ingest(BaseModel):
    """Phase 1 Agent 实际上报格式（docs/phase1-agent.md）。"""
    status: Literal["playing", "paused", "occluded", "idle"]
    title: str | None = Text
    artist: str | None = Text
    album: str | None = Text
    duration: float | None = Field(default=None, ge=0, le=86400)
    position: float | None = Field(default=None, ge=0, le=86400)
    playing: bool | None = None
    position_confirmed: bool | None = None
    observed_at: float
    reason: str | None = Field(default=None, max_length=32)
    sent_at: float | None = None
    last_known: LastKnown | None = None


def require_token(request: Request) -> None:
    auth = request.headers.get("authorization", "")
    scheme, _, given = auth.partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(given.encode(), TOKEN.encode()):
        raise HTTPException(status_code=401, detail="unauthorized")


@app.post("/ingest", dependencies=[Depends(require_token)])
def ingest(body: Ingest):
    received_at = time.time()
    p = body.model_dump()
    if p["status"] in ("playing", "paused") and not p["title"]:
        raise HTTPException(status_code=422, detail="playing/paused 需要 title")
    return store.ingest(p, received_at)


@app.get("/state", dependencies=[Depends(require_token)])
def state():
    """调试接口：当前状态 + 最近 5 段播放。不是面向 AI 的正式接口（那是 Phase 3 的 MCP）。"""
    return store.state(time.time(), recent=5)


@app.get("/healthz")
def healthz():
    return {"ok": True}
