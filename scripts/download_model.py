import logging
import os

from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    model_name = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    logger.info(f"Pre-downloading embedding model: {model_name}...")

    # This triggers the download and caching
    try:
        SentenceTransformer(model_name)
        logger.info("✅ Model downloaded and cached successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to download model: {e}")
        # Build should fail if model key component missing
        exit(1)


if __name__ == "__main__":
    main()
