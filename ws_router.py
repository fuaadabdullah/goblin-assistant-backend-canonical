from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/ws", tags=["ws"])


@router.websocket("")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back with info and keep a heartbeat
            await websocket.send_text(f"echo: {data}")
    except WebSocketDisconnect:
        return
