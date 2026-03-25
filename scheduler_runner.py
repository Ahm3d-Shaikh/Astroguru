import asyncio
import logging
from app.services.notification_service import start_scheduler

logging.basicConfig(level=logging.INFO)

async def main():
    logging.info("Starting scheduler process...")
    start_scheduler()  
    while True:
        await asyncio.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())