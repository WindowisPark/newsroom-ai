"""SSE(Server-Sent Events) 실시간 업데이트 엔드포인트"""

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

router = APIRouter(prefix="/sse", tags=["sse"])

# 이벤트 큐 (간단한 in-memory pub/sub)
_event_queues: list[asyncio.Queue] = []


def broadcast_event(event_type: str, data: dict):
    """모든 연결된 클라이언트에게 이벤트 브로드캐스트"""
    for queue in _event_queues:
        queue.put_nowait({"event": event_type, "data": data})


@router.get("/stream")
async def event_stream():
    """SSE 이벤트 스트림"""
    queue: asyncio.Queue = asyncio.Queue()
    _event_queues.append(queue)

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield {
                        "event": event["event"],
                        "data": json.dumps(event["data"], default=str),
                    }
                except asyncio.TimeoutError:
                    # 30초마다 keepalive
                    yield {
                        "event": "keepalive",
                        "data": json.dumps({"time": datetime.now(timezone.utc).isoformat()}),
                    }
        finally:
            _event_queues.remove(queue)

    return EventSourceResponse(event_generator())
