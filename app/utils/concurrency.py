import asyncio

async def generate_with_retry(fn, retries=4):
    delay = 0.5

    for _ in range(retries):
        try:
            return await fn()
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                await asyncio.sleep(delay)
                delay *= 2
            else:
                raise

    raise Exception("Max retries exceeded")