"""CLI script for synchronizing the Knowledge Graph."""

import sys
from pathlib import Path

# Add project root and backend to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))
backend_dir = root_dir / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.logging import logger
from app.graph.ingestion import sync_knowledge_graph


def main():
    logger.info("Initializing Knowledge Graph Synchronization...")
    stats = sync_knowledge_graph()

    print("\n" + "=" * 60)
    print("TravelOps AI Knowledge Graph Synchronization Results")
    print("=" * 60)
    for entity, count in stats.items():
        print(f"  - {entity.capitalize():<18}: {count:>6} nodes/records merged")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
