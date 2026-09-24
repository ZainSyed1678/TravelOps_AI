"""Database seeding script."""

import asyncio
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.database import AsyncSessionLocal, engine
from app.core.init_db import init_db, seed_initial_data
from app.core.logging import logger


async def main():
    logger.info("Initializing database tables...")
    await init_db(engine)
    logger.info("Seeding baseline travel data...")
    async with AsyncSessionLocal() as session:
        await seed_initial_data(session)
    logger.info("Database successfully seeded.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
