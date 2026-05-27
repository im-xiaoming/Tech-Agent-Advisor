from pathlib import Path
from langchain_community.document_loaders import CSVLoader, DirectoryLoader
from rag_engine.core.config import settings


def load_data(directory_path=None):
    """
    Load all CSV files in the data directory and return a list of Document objects.
    
    Args:
        directory_path (str, optional): Path to the directory containing CSV files.
            If None, defaults to settings.data_dir.
    
    Returns:
        List[Document]: A list of Document objects loaded from the CSV files.
    """
    data_path = Path(directory_path or settings.data_dir).resolve()

    loader = DirectoryLoader(
        path=str(data_path),
        glob="**/*.csv",
        loader_cls=CSVLoader,
        loader_kwargs={
            "encoding": "utf-8",
            "csv_args": {
                "delimiter": ",",
            },
        },
    )

    return loader.load()
