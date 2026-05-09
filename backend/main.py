import os
import json
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局变量缓存 access_token（生产环境需加过期处理）
ACCESS_TOKEN = None

async def get_access_token():
    global ACCESS_TOKEN
    if ACCESS_TOKEN:
        return ACCESS_TOKEN
    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {
        "grant_type": "client_credentials",
        "client_id": os.getenv("ERNIE_API_KEY"),
        "client_secret": os.getenv("ERNIE_SECRET_KEY")
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, params=params)
        data = resp.json()
        ACCESS_TOKEN = data.get("access_token")
        return ACCESS_TOKEN

class ChatRequest(BaseModel):
    question: str
    subject: str = "通用"
    history: list = []   # 历史消息，格式 [{"role":"user","content":"..."}, ...]

SYSTEM_PROMPT = """你是一名全科辅导老师，请用启发、鼓励的语气回答。
当前学科：{subject}
严格按以下格式输出：
【考点总结】: <一句话>
【思路分析】: <引导式分析>
【详细解答】: <分步解答>
【易错提醒】: <常见错误>
"""

@app.post("/api/chat")
async def chat(req: ChatRequest):
    try:
        token = await get_access_token()
        url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions?access_token={token}"
        
        # 构建消息
        messages = [{"role": "system", "content": SYSTEM_PROMPT.format(subject=req.subject)}]
        # 补充历史对话（只取最近几轮，控制长度）
        messages.extend(req.history[-6:])
        messages.append({"role": "user", "content": req.question})
        
        payload = {
            "messages": messages,
            "temperature": 0.5,
            "top_p": 0.8,
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            result = response.json()
            
        if "result" in result:
            return {"code": 200, "data": {"answer": result["result"]}}
        else:
            return {"code": 500, "data": {"answer": "老师暂时无法解答，请稍后再试～"}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
