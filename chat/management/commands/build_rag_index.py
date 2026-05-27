"""Django command used to ingest local CSV data into Qdrant."""

from django.core.management.base import BaseCommand

from rag_engine.core.config import settings
from rag_engine.ingestion.build_index import build_index
from rag_engine.rag.vector_store import count_vectors


class Command(BaseCommand):
    """CLI command to build the Qdrant collection from CSV product data."""

    help = "Build or rebuild the Qdrant collection from local product CSV data."

    def add_arguments(self, parser):
        """Declare command-line arguments for source data."""
        parser.add_argument("--data-dir", default=str(settings.data_dir))

    def handle(self, *args, **options):
        """Run ingestion and print the number of stored vectors."""
        db = build_index(
            data_dir=options["data_dir"],
        )
        # print information into console
        self.stdout.write(
            self.style.SUCCESS(
                f"Built Qdrant collection '{settings.qdrant_collection}' "
                f"with {count_vectors(db)} vectors."
            )
        )
