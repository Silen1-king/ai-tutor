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

# DeepSeek无需提前获取token，直接使用API Key（替换.env中的配置）
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
# DeepSeek模型版本（根据需求选择，如deepseek-chat/deepseek-coder等）
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 移除原百度的get_access_token函数（无需再用）

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
        # 1. 校验API Key
        if not DEEPSEEK_API_KEY:
            raise HTTPException(status_code=500, detail="未配置DeepSeek API Key")
        
        # 2. 构建DeepSeek请求参数（兼容OpenAI格式）
        url = "https://api.deepseek.com/v1/chat/completions"
        
        # 构建消息（system + 历史 + 最新问题）
        messages = [{"role": "system", "content": SYSTEM_PROMPT.format(subject=req.subject)}]
        # 补充历史对话（只取最近几轮，控制长度）
        messages.extend(req.history[-6:])
        messages.append({"role": "user", "content": req.question})
        
        # 3. DeepSeek请求体（兼容OpenAI格式）
        payload = {
            "model": DEEPSEEK_MODEL,  # 指定DeepSeek模型
            "messages": messages,
            "temperature": 0.5,
            "top_p": 0.8,
            "max_tokens": 2048,  # 响应最大长度（可根据需求调整）
            "stream": False  # 非流式输出
        }
        
        # 4. 设置请求头（DeepSeek鉴权方式：Bearer Token）
        headers = {
            "Authorization": f"Bearer sk-842519c0c1294fe8b10bd3affee798c7",
            "Content-Type": "application/json"
        }
        
        # 5. 发送请求到DeepSeek
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            result = response.json()
            
        # 6. 解析DeepSeek响应（格式与百度不同）
        if "choices" in result and len(result["choices"]) > 0:
            answer = result["choices"][0]["message"]["content"].strip()
            return {"code": 200, "data": {"answer": answer}}
        else:
            error_msg = result.get("error", {}).get("message", "未知错误")
            return {"code": 500, "data": {"answer": f"老师暂时无法解答：{error_msg}"}}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
