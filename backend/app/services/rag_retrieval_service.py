"""
RAG (Retrieval-Augmented Generation) retrieval service.
Retrieves relevant context from knowledge base for AI assistant.
"""
from typing import List, Dict, Any, Optional
from app.services.vector_db_service import get_vector_db_service


class RAGRetrievalService:
    """Service for retrieving relevant context using RAG"""
    
    def __init__(self):
        self.vector_db = get_vector_db_service()
    
    def retrieve_context(
        self,
        query: str,
        language: str = "de",
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant context for a user query.
        
        Args:
            query: User's question
            language: User's language (de, en, zh)
            top_k: Number of results to retrieve from each collection
        
        Returns:
            List of relevant context documents with metadata
        """
        all_results = []
        
        # Query tax law collection (hand-written)
        tax_law_results = self.vector_db.query_documents(
            collection_name="austrian_tax_law",
            query_text=query,
            n_results=top_k,
            where={"language": language}
        )
        
        # Query scraped tax law collection (auto-fetched from official sources)
        try:
            scraped_results = self.vector_db.query_documents(
                collection_name="scraped_tax_law",
                query_text=query,
                n_results=top_k,
                where={"language": language}
            )
        except Exception:
            scraped_results = {}
        
        # Query tax tables collection
        tax_tables_results = self.vector_db.query_documents(
            collection_name="usp_2026_tax_tables",
            query_text=query,
            n_results=top_k,
            where={"language": language}
        )
        
        # Query FAQ collection
        faq_results = self.vector_db.query_documents(
            collection_name="tax_faq",
            query_text=query,
            n_results=top_k,
            where={"language": language}
        )
        
        # Combine and rank results — scraped (official) gets priority
        all_results.extend(self._format_results(scraped_results, "scraped_official"))
        all_results.extend(self._format_results(tax_law_results, "tax_law"))
        all_results.extend(self._format_results(tax_tables_results, "tax_tables"))
        all_results.extend(self._format_results(faq_results, "faq"))
        
        # Sort by relevance (distance/similarity score)
        all_results.sort(key=lambda x: x["distance"])
        
        # Return top results
        return all_results[:top_k]
    
    def _format_results(
        self,
        results: Dict[str, Any],
        collection_type: str
    ) -> List[Dict[str, Any]]:
        """Format query results into structured format"""
        formatted = []
        
        if not results or not results.get("documents"):
            return formatted
        
        documents = results["documents"][0] if results["documents"] else []
        metadatas = results["metadatas"][0] if results["metadatas"] else []
        distances = results["distances"][0] if results["distances"] else []
        ids = results["ids"][0] if results["ids"] else []
        
        for i in range(len(documents)):
            formatted.append({
                "document": documents[i],
                "metadata": metadatas[i] if i < len(metadatas) else {},
                "distance": distances[i] if i < len(distances) else 1.0,
                "id": ids[i] if i < len(ids) else f"unknown_{i}",
                "collection": collection_type
            })
        
        return formatted
    
    def retrieve_context_with_user_data(
        self,
        query: str,
        user_context: Dict[str, Any],
        language: str = "de",
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Retrieve context including user's transaction data.
        
        Args:
            query: User's question
            user_context: User's current tax data (transactions, income, etc.)
            language: User's language
            top_k: Number of knowledge base results
        
        Returns:
            Dict containing knowledge base context and user data
        """
        # Get knowledge base context
        kb_context = self.retrieve_context(query, language, top_k)
        
        # Combine with user data
        return {
            "knowledge_base": kb_context,
            "user_data": user_context,
            "query": query,
            "language": language
        }
    
    def format_context_for_prompt(
        self,
        context: Dict[str, Any]
    ) -> str:
        """
        Format retrieved context into a prompt string for LLM.
        
        Args:
            context: Retrieved context from retrieve_context_with_user_data
        
        Returns:
            Formatted context string
        """
        prompt_parts = []
        
        # Add knowledge base context
        if context.get("knowledge_base"):
            prompt_parts.append("=== Relevant Tax Law Information ===")
            for i, doc in enumerate(context["knowledge_base"], 1):
                prompt_parts.append(f"\n[Source {i}]: {doc['document']}")
        
        # Add user data context
        if context.get("user_data"):
            user_data = context["user_data"]
            prompt_parts.append("\n\n=== User's Current Tax Situation ===")
            
            if user_data.get("year_to_date_income"):
                prompt_parts.append(f"Year-to-date income: €{user_data['year_to_date_income']:,.2f}")
            
            if user_data.get("year_to_date_expenses"):
                prompt_parts.append(f"Year-to-date expenses: €{user_data['year_to_date_expenses']:,.2f}")
            
            if user_data.get("estimated_tax"):
                prompt_parts.append(f"Estimated tax liability: €{user_data['estimated_tax']:,.2f}")
            
            if user_data.get("user_type"):
                prompt_parts.append(f"User type: {user_data['user_type']}")
            
            if user_data.get("vat_liable"):
                prompt_parts.append(f"VAT liable: {user_data['vat_liable']}")
        
        return "\n".join(prompt_parts)


# Singleton instance
_rag_retrieval_service = None


def get_rag_retrieval_service() -> RAGRetrievalService:
    """Get singleton instance of RAGRetrievalService"""
    global _rag_retrieval_service
    if _rag_retrieval_service is None:
        _rag_retrieval_service = RAGRetrievalService()
    return _rag_retrieval_service
