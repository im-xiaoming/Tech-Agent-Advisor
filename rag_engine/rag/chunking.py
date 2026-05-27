from langchain_text_splitters import RecursiveCharacterTextSplitter
from rag_engine.core.config import settings

def split_docs(docs):
    """
    Split a list of Document objects into smaller chunks with a fixed overlap.
    
    Args:
        docs (List[Document]): A list of Document objects to split.
    
    Returns:
        List[Document]: A list of chunked Document objects.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size, # 800 chars
        chunk_overlap=settings.chunk_overlap, # 100 chars
        length_function=len,
        add_start_index=True,
    )
    return splitter.split_documents(docs)