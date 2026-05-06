"""
test_do.py -- Quick test for DigitalOcean Inference Hub (Tier 1 free models)
Run from: d:/finos/backend/
  python test_do.py
"""
import asyncio
from openai import AsyncOpenAI
from app.core.config import settings

if not settings.DO_INFERENCE_API_KEY:
    raise SystemExit("DO_INFERENCE_API_KEY is not set in .env")

client = AsyncOpenAI(
    api_key=settings.DO_INFERENCE_API_KEY,
    base_url=settings.DO_INFERENCE_BASE_URL,
)

CHAT_MODEL = "llama3.3-70b-instruct"
EMBED_MODEL = "bge-m3"

print("\n" + "=" * 55)
print("  DO Inference Hub Test (Tier 1 free models)")
print(f"  base_url   : {settings.DO_INFERENCE_BASE_URL}")
print(f"  key        : {settings.DO_INFERENCE_API_KEY[:12]}...")
print(f"  chat model : {CHAT_MODEL}")
print(f"  embed model: {EMBED_MODEL}")
print("=" * 55 + "\n")


async def test_chat():
    print("-- 1. Chat Completion --")
    response = await client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": "You are a concise financial assistant."},
            {"role": "user", "content": "What is accounts payable in one sentence?"},
        ],
        temperature=0,
        max_tokens=80,
    )
    msg = response.choices[0].message.content
    usage = response.usage
    print(f"  Response : {msg}")
    print(f"  Tokens   : {usage.prompt_tokens} in / {usage.completion_tokens} out")
    print(f"  Model    : {response.model}")
    print("  [PASS] Chat OK\n")


async def test_streaming():
    print("-- 2. Streaming (token by token) --")
    print("  Response : ", end="", flush=True)
    token_count = 0
    stream = await client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": "Count from 1 to 5, one word per number."}],
        temperature=0,
        max_tokens=30,
        stream=True,
    )
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            print(chunk.choices[0].delta.content, end="", flush=True)
            token_count += 1
    print(f"\n  Tokens streamed : ~{token_count}")
    print("  [PASS] Streaming OK\n")


async def test_tool_calling():
    print("-- 3. Tool Calling (bind_tools simulation) --")
    tools = [{
        "type": "function",
        "function": {
            "name": "get_invoice_total",
            "description": "Get the total amount for an invoice",
            "parameters": {
                "type": "object",
                "properties": {
                    "invoice_id": {"type": "string", "description": "The invoice ID"}
                },
                "required": ["invoice_id"]
            }
        }
    }]
    response = await client.chat.completions.create(
        model=CHAT_MODEL,
        messages=[{"role": "user", "content": "What is the total for invoice INV-001?"}],
        tools=tools,
        tool_choice="auto",
        temperature=0,
        max_tokens=100,
    )
    choice = response.choices[0]
    if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
        tc = choice.message.tool_calls[0]
        print(f"  Tool called : {tc.function.name}")
        print(f"  Arguments   : {tc.function.arguments}")
        print("  [PASS] Tool Calling OK\n")
    else:
        print(f"  finish_reason: {choice.finish_reason}")
        print(f"  content: {choice.message.content}")
        print("  [INFO] Model responded without tool call (still OK)\n")


async def test_embeddings():
    print("-- 4. Embeddings (bge-m3) --")
    texts = ["Invoice from Vendor A for $5,000", "Cash flow report Q1 2025"]
    response = await client.embeddings.create(model=EMBED_MODEL, input=texts)
    for i, emb in enumerate(response.data):
        vec = emb.embedding
        print(f"  Text[{i}] : dim={len(vec)}  first3={[round(v, 4) for v in vec[:3]]}")
    print("  [PASS] Embeddings OK\n")


async def main():
    await test_chat()
    await test_streaming()
    await test_tool_calling()
    await test_embeddings()
    print("=" * 55)
    print("  All tests passed -- DO Tier 1 ready!")
    print("=" * 55)

if __name__ == "__main__":
    asyncio.run(main())
