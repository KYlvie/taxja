"""
Vector database service for AI Tax Assistant knowledge base.
Uses ChromaDB for storing and retrieving document embeddings.
"""
import os
from typing import List, Dict, Any, Optional
import chromadb
from sentence_transformers import SentenceTransformer
from pathlib import Path


class VectorDBService:
    """Service for managing vector database operations"""
    
    def __init__(self, persist_directory: str = "./data/chroma"):
        """
        Initialize vector database service.
        
        Args:
            persist_directory: Directory to persist ChromaDB data
        """
        self.persist_directory = persist_directory
        Path(persist_directory).mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client (v1.5+ PersistentClient)
        self.client = chromadb.PersistentClient(path=persist_directory)
        
        # Initialize embedding model (multilingual support)
        self.embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        
        # Get or create collections
        self.tax_law_collection = self._get_or_create_collection("austrian_tax_law")
        self.tax_tables_collection = self._get_or_create_collection("usp_2026_tax_tables")
        self.faq_collection = self._get_or_create_collection("tax_faq")
        self.scraped_collection = self._get_or_create_collection("scraped_tax_law")
    
    def _get_or_create_collection(self, name: str):
        """Get or create a ChromaDB collection"""
        return self.client.get_or_create_collection(
            name=name,
            metadata={"hnsw:space": "cosine"}
        )
    
    def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: Optional[List[str]] = None
    ):
        """
        Add documents to a collection.
        
        Args:
            collection_name: Name of the collection
            documents: List of document texts
            metadatas: List of metadata dicts for each document
            ids: Optional list of document IDs
        """
        collection = self._get_collection(collection_name)
        
        # Generate embeddings
        embeddings = self.embedding_model.encode(documents).tolist()
        
        # Generate IDs if not provided
        if ids is None:
            ids = [f"doc_{i}" for i in range(len(documents))]
        
        # Add to collection (v1.5+ auto-persists)
        collection.add(
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
    
    def query_documents(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Query documents from a collection.
        
        Args:
            collection_name: Name of the collection
            query_text: Query text
            n_results: Number of results to return
            where: Optional metadata filter
        
        Returns:
            Dict containing documents, metadatas, distances, and ids
        """
        collection = self._get_collection(collection_name)
        
        # Generate query embedding
        query_embedding = self.embedding_model.encode([query_text]).tolist()
        
        # Query collection
        results = collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            where=where
        )
        
        return results
    
    def _get_collection(self, name: str):
        """Get a collection by name"""
        if name == "austrian_tax_law":
            return self.tax_law_collection
        elif name == "usp_2026_tax_tables":
            return self.tax_tables_collection
        elif name == "tax_faq":
            return self.faq_collection
        elif name == "scraped_tax_law":
            return self.scraped_collection
        else:
            return self.client.get_collection(name=name)
    
    def delete_collection(self, name: str):
        """Delete a collection"""
        self.client.delete_collection(name=name)
    
    def reset_collection(self, name: str):
        """Reset a collection (delete and recreate), updating cached references."""
        try:
            self.client.delete_collection(name=name)
        except Exception:
            pass
        new_coll = self._get_or_create_collection(name)
        # Update cached reference so _get_collection returns the new object
        if name == "austrian_tax_law":
            self.tax_law_collection = new_coll
        elif name == "usp_2026_tax_tables":
            self.tax_tables_collection = new_coll
        elif name == "tax_faq":
            self.faq_collection = new_coll
        elif name == "scraped_tax_law":
            self.scraped_collection = new_coll
        return new_coll



# Singleton instance
_vector_db_service = None


def get_vector_db_service() -> VectorDBService:
    """Get singleton instance of VectorDBService"""
    global _vector_db_service
    if _vector_db_service is None:
        _vector_db_service = VectorDBService()
    return _vector_db_service
