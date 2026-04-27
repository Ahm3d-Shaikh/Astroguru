import asyncio

async def generate_with_retry(fn, retries=5):
    delay = 1  

    for i in range(retries):
        try:
            return await fn()
        except Exception as e:
            if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                if i == retries - 1:
                    break
                await asyncio.sleep(delay)
                delay *= 2.5  
            else:
                raise

    raise Exception("Max retries exceeded")