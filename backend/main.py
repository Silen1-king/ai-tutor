import os
import json
import httpx
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局变量缓存 access_token 和过期时间
ACCESS_TOKEN = None
TOKEN_EXPIRE_TIME = 0  # 记录token的过期时间戳

async def get_access_token():
    """获取有效的access_token，自动处理过期"""
    global ACCESS_TOKEN, TOKEN_EXPIRE_TIME
    current_time = time.time()
    
    # 如果token存在且未过期（提前1小时刷新，避免临界过期问题）
    if ACCESS_TOKEN and current_time < TOKEN_EXPIRE_TIME - 3600:
        return ACCESS_TOKEN
    
    # 从环境变量获取密钥
    api_key = os.getenv("ERNIE_API_KEY")
    secret_key = os.getenv("ERNIE_SECRET_KEY")
    if not api_key or not secret_key:
        raise HTTPException(status_code=500, detail="API_KEY或SECRET_KEY未配置，请检查.env文件")
    
    url = "https://aip.baidubce.com/oauth/2.0/token"
    params = {
        "grant_type": "client_credentials",
        "client_id": api_key,
        "client_secret": secret_key
    }
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, params=params, timeout=10.0)
            resp.raise_for_status()  # 抛出HTTP错误（如4xx/5xx）
            data = resp.json()
            
            if "access_token" not in data:
                raise HTTPException(status_code=500, detail=f"获取token失败：{data}")
            
            ACCESS_TOKEN = data["access_token"]
            # 记录过期时间（expires_in单位是秒，通常为2592000=30天）
            TOKEN_EXPIRE_TIME = current_time + data.get("expires_in", 2592000)
            print(f"获取到新的access_token，有效期至：{time.ctime(TOKEN_EXPIRE_TIME)}")
            return ACCESS_TOKEN
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"请求token接口失败：{str(e)}")

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
        # 1. 获取有效的access_token
        token = await get_access_token()
        url = f"https://aip.baidubce.com/rpc/2.0/ai_custom/v1/wenxinworkshop/chat/completions?access_token={token}"
        
        # 2. 构建消息，过滤无效的历史消息
        messages = [{"role": "system", "content": SYSTEM_PROMPT.format(subject=req.subject)}]
        # 只保留格式正确的历史消息，最多6轮
        valid_history = []
        for msg in req.history[-6:]:
            if isinstance(msg, dict) and "role" in msg and "content" in msg:
                valid_history.append({"role": msg["role"], "content": str(msg["content"])})
        messages.extend(valid_history)
        messages.append({"role": "user", "content": req.question})
        
        payload = {
            "messages": messages,
            "temperature": 0.5,
            "top_p": 0.8,
        }
        print("请求参数：", json.dumps(payload, ensure_ascii=False, indent=2))
        
        # 3. 调用文心接口
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload)
            print(f"文心接口状态码：{response.status_code}")
            result = response.json()
            print("文心返回结果：", json.dumps(result, ensure_ascii=False, indent=2))
        
        # 4. 处理接口返回
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail=f"上游接口错误，状态码：{response.status_code}，错误信息：{result}")
        
        if "error_code" in result:
            # 处理文心接口返回的错误码
            error_code = result["error_code"]
            error_msg = result.get("error_msg", "未知错误")
            if error_code == 6:
                raise HTTPException(status_code=401, detail=f"权限不足：{error_msg}，请检查API_KEY和权限配置")
            else:
                raise HTTPException(status_code=500, detail=f"文心接口错误，错误码：{error_code}，错误信息：{error_msg}")
        
        if "result" in result:
            return {"code": 200, "data": {"answer": result["result"]}}
        else:
            raise HTTPException(status_code=500, detail="文心接口返回格式异常，无result字段")
    
    except HTTPException as e:
        # 直接抛出已知的HTTP异常
        raise e
    except Exception as e:
        # 捕获所有其他异常，返回友好提示并打印错误栈
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"服务器内部错误：{str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)