"""
AI Tax Assistant service with LLM integration.
Supports OpenAI GPT-4, Anthropic Claude, and configurable LLM providers.
"""
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import openai
import anthropic

from app.services.rag_retrieval_service import get_rag_retrieval_service
from app.core.config import settings


class AIAssistantService:
    """Service for AI Tax Assistant with RAG"""
    
    # Disclaimer text in multiple languages
    DISCLAIMERS = {
        "de": "\n\n⚠️ **Haftungsausschluss**: Diese Antwort dient nur zu allgemeinen Informationszwecken und stellt keine Steuerberatung oder formelle Empfehlung dar. Bitte verwenden Sie FinanzOnline für die endgültige Steuererklärung. Bei komplexen Situationen konsultieren Sie bitte einen Steuerberater.",
        "en": "\n\n⚠️ **Disclaimer**: This response is for general information purposes only and does not constitute tax advice or formal recommendation. Please use FinanzOnline for final tax filing. For complex situations, please consult a Steuerberater.",
        "zh": "\n\n⚠️ **免责声明**：本回答仅供一般性参考，不构成税务咨询或正式建议。请以FinanzOnline最终结果为准。复杂情况请咨询Steuerberater。"
    }
    
    def __init__(self):
        self.rag_service = get_rag_retrieval_service()
        self.llm_provider = os.getenv("LLM_PROVIDER", "openai")  # openai, anthropic, or local
        
        # Initialize LLM clients
        if self.llm_provider == "openai":
            openai.api_key = os.getenv("OPENAI_API_KEY")
            self.model = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
        elif self.llm_provider == "anthropic":
            self.anthropic_client = anthropic.Anthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY")
            )
            self.model = os.getenv("ANTHROPIC_MODEL", "claude-3-opus-20240229")
    
    def generate_response(
        self,
        user_message: str,
        user_context: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        language: str = "de"
    ) -> str:
        """
        Generate AI response using RAG and LLM.
        
        Args:
            user_message: User's question
            user_context: User's tax data and context
            conversation_history: Previous messages in conversation
            language: User's language (de, en, zh)
        
        Returns:
            AI-generated response with disclaimer
        """
        # Retrieve relevant context
        context = self.rag_service.retrieve_context_with_user_data(
            query=user_message,
            user_context=user_context,
            language=language,
            top_k=5
        )
        
        # Format context for prompt
        context_str = self.rag_service.format_context_for_prompt(context)
        
        # Build system prompt
        system_prompt = self._build_system_prompt(language)
        
        # Build user prompt with context
        user_prompt = self._build_user_prompt(user_message, context_str, language)
        
        # Generate response using LLM
        if self.llm_provider == "openai":
            response = self._generate_openai_response(
                system_prompt,
                user_prompt,
                conversation_history
            )
        elif self.llm_provider == "anthropic":
            response = self._generate_anthropic_response(
                system_prompt,
                user_prompt,
                conversation_history
            )
        else:
            response = "LLM provider not configured. Please set OPENAI_API_KEY or ANTHROPIC_API_KEY."
        
        # Append disclaimer
        disclaimer = self.DISCLAIMERS.get(language, self.DISCLAIMERS["de"])
        response_with_disclaimer = response + disclaimer
        
        return response_with_disclaimer
    
    def _build_system_prompt(self, language: str) -> str:
        """Build system prompt for LLM"""
        prompts = {
            "de": """Du bist ein hilfreicher AI-Assistent für österreichische Steuerfragen. 
Du hilfst Benutzern, ihre Steuersituation zu verstehen und Fragen zum österreichischen Steuersystem zu beantworten.

WICHTIGE REGELN:
1. Verwende IMMER die bereitgestellten Steuergesetze und Tabellen als Grundlage für deine Antworten
2. Beziehe die aktuellen Steuerdaten des Benutzers in deine Antworten ein, wenn relevant
3. Gib NIEMALS spezifische Steuerbeträge als Garantie an (z.B. "Sie erhalten garantiert €X zurück")
4. Erkläre komplexe Steuerkonzepte in einfacher Sprache
5. Wenn du dir nicht sicher bist, empfehle die Konsultation eines Steuerberaters
6. Antworte in der Sprache des Benutzers (Deutsch, Englisch oder Chinesisch)
7. Sei präzise und verwende offizielle österreichische Steuerbegriffe

Du darfst KEINE Steuerberatung im Sinne des Steuerberatungsgesetzes anbieten.""",
            
            "en": """You are a helpful AI assistant for Austrian tax questions.
You help users understand their tax situation and answer questions about the Austrian tax system.

IMPORTANT RULES:
1. ALWAYS use the provided tax laws and tables as the basis for your answers
2. Include the user's current tax data in your responses when relevant
3. NEVER give specific tax amounts as guarantees (e.g., "You will definitely get €X back")
4. Explain complex tax concepts in simple language
5. If you're unsure, recommend consulting a Steuerberater
6. Respond in the user's language (German, English, or Chinese)
7. Be precise and use official Austrian tax terminology

You may NOT provide tax advice in the sense of the Steuerberatungsgesetz.""",
            
            "zh": """你是一个有用的奥地利税务问题AI助手。
你帮助用户理解他们的税务情况并回答有关奥地利税收制度的问题。

重要规则：
1. 始终使用提供的税法和税表作为答案的基础
2. 在相关时将用户当前的税务数据纳入您的回答
3. 永远不要给出具体的税额保证（例如"您肯定会退税€X"）
4. 用简单的语言解释复杂的税务概念
5. 如果不确定，建议咨询Steuerberater
6. 用用户的语言回答（德语、英语或中文）
7. 准确并使用官方奥地利税务术语

您不得提供Steuerberatungsgesetz意义上的税务咨询。"""
        }
        
        return prompts.get(language, prompts["de"])
    
    def _build_user_prompt(
        self,
        user_message: str,
        context: str,
        language: str
    ) -> str:
        """Build user prompt with context"""
        prompt_templates = {
            "de": f"""Kontext aus der Wissensdatenbank und Benutzerdaten:
{context}

Benutzerfrage: {user_message}

Bitte beantworte die Frage basierend auf dem bereitgestellten Kontext.""",
            
            "en": f"""Context from knowledge base and user data:
{context}

User question: {user_message}

Please answer the question based on the provided context.""",
            
            "zh": f"""来自知识库和用户数据的上下文：
{context}

用户问题：{user_message}

请根据提供的上下文回答问题。"""
        }
        
        return prompt_templates.get(language, prompt_templates["de"])
    
    def _generate_openai_response(
        self,
        system_prompt: str,
        user_prompt: str,
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """Generate response using OpenAI API"""
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add conversation history (limit to last 10 messages)
        for msg in conversation_history[-10:]:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        
        # Add current user message
        messages.append({"role": "user", "content": user_prompt})
        
        try:
            response = openai.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    def _generate_anthropic_response(
        self,
        system_prompt: str,
        user_prompt: str,
        conversation_history: List[Dict[str, str]]
    ) -> str:
        """Generate response using Anthropic Claude API"""
        messages = []
        
        # Add conversation history (limit to last 10 messages)
        for msg in conversation_history[-10:]:
            if msg["role"] != "system":
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
        
        # Add current user message
        messages.append({"role": "user", "content": user_prompt})
        
        try:
            response = self.anthropic_client.messages.create(
                model=self.model,
                max_tokens=1000,
                system=system_prompt,
                messages=messages
            )
            
            return response.content[0].text
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    def explain_ocr_result(
        self,
        ocr_data: Dict[str, Any],
        language: str = "de"
    ) -> str:
        """
        Generate natural language explanation of OCR results.
        
        Args:
            ocr_data: OCR extracted data
            language: User's language
        
        Returns:
            Natural language explanation
        """
        # Build context about OCR result
        context = {
            "document_type": ocr_data.get("document_type"),
            "extracted_fields": ocr_data.get("extracted_data", {}),
            "confidence_score": ocr_data.get("confidence_score", 0)
        }
        
        # Build question
        questions = {
            "de": f"Erkläre mir, was in diesem Dokument erkannt wurde und welche Posten steuerlich absetzbar sind.",
            "en": f"Explain what was recognized in this document and which items are tax deductible.",
            "zh": f"解释一下这个文档中识别出了什么，哪些项目可以抵税。"
        }
        
        question = questions.get(language, questions["de"])
        
        # Generate explanation
        return self.generate_response(
            user_message=question,
            user_context={"ocr_result": context},
            conversation_history=[],
            language=language
        )
    
    def suggest_tax_optimization(
        self,
        user_tax_data: Dict[str, Any],
        language: str = "de"
    ) -> str:
        """
        Analyze user's tax situation and suggest optimizations.
        
        Args:
            user_tax_data: User's current tax data
            language: User's language
        
        Returns:
            Optimization suggestions
        """
        questions = {
            "de": "Analysiere meine aktuelle Steuersituation und gib mir Vorschläge zur Steueroptimierung.",
            "en": "Analyze my current tax situation and give me suggestions for tax optimization.",
            "zh": "分析我目前的税务情况并给我税务优化建议。"
        }
        
        question = questions.get(language, questions["de"])
        
        return self.generate_response(
            user_message=question,
            user_context=user_tax_data,
            conversation_history=[],
            language=language
        )


# Singleton instance
_ai_assistant_service = None


def get_ai_assistant_service() -> AIAssistantService:
    """Get singleton instance of AIAssistantService"""
    global _ai_assistant_service
    if _ai_assistant_service is None:
        _ai_assistant_service = AIAssistantService()
    return _ai_assistant_service
