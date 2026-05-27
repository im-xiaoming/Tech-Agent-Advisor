from rag_engine.core.config import settings

def retrieve(db, query, k=10):
    """
    Find the k most similar documents to the query using similarity search.
    
    Args:
        db: A vector store with a similarity_search method.
        query: The input query string to search for.
        k: The number of top similar documents to return.
        
    Returns:
        A list of the k most similar documents to the query.
    """
    return db.similarity_search(query, k=k, score_threshold=settings.score_threshold)
