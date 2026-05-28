from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_text_splitters import SentenceTransformersTokenTextSplitter
from rag_engine.core.config import settings


def _get_splitter():
    if settings.splitter_method == "tiktoken":
        print("Using tiktoken-based splitter for chunking.")
        return RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            model_name="gpt-4",
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
    elif settings.splitter_method == "sentence_transformer":
        print("Using sentence-transformer-based splitter for chunking.")
        return SentenceTransformersTokenTextSplitter(
            model_name="BAAI/bge-m3",
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
    else:
        print("Using default recursive character splitter for chunking.")
        return RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            length_function=len,
            add_start_index=True,
        )
        


def split_docs(docs):
    """
    Split a list of Document objects into smaller chunks with a fixed overlap.
    
    Args:
        docs (List[Document]): A list of Document objects to split.
    
    Returns:
        List[Document]: A list of chunked Document objects.
    """
    splitter = _get_splitter()
    return splitter.split_documents(docs)