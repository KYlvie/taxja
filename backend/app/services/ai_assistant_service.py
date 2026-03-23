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
        "zh": "\n\n⚠️ **免责声明**：本回答仅供一般性参考，不构成税务咨询或正式建议。请以FinanzOnline最终结果为准。复杂情况请咨询Steuerberater。",
        "fr": "\n\n⚠️ **Avertissement** : Cette réponse est fournie à titre d'information générale uniquement et ne constitue pas un conseil fiscal ni une recommandation formelle. Veuillez utiliser FinanzOnline pour la déclaration fiscale définitive. Pour les situations complexes, veuillez consulter un Steuerberater.",
        "ru": "\n\n⚠️ **Отказ от ответственности**: Этот ответ предоставлен исключительно в информационных целях и не является налоговой консультацией или официальной рекомендацией. Пожалуйста, используйте FinanzOnline для окончательной подачи налоговой декларации. В сложных ситуациях обратитесь к Steuerberater.",
        "hu": "\n\n⚠️ **Jogi nyilatkozat**: Ez a válasz kizárólag általános tájékoztatási célokat szolgál, és nem minősül adótanácsadásnak vagy hivatalos ajánlásnak. Kérjük, használja a FinanzOnline-t a végleges adóbevalláshoz. Összetett esetekben forduljon Steuerberater-hez.",
        "pl": "\n\n⚠️ **Zastrzeżenie**: Ta odpowiedź służy wyłącznie celom informacyjnym i nie stanowi porady podatkowej ani formalnej rekomendacji. Proszę korzystać z FinanzOnline do ostatecznego rozliczenia podatkowego. W złożonych sytuacjach proszę skonsultować się ze Steuerberater.",
        "tr": "\n\n⚠️ **Sorumluluk reddi**: Bu yanit yalnizca genel bilgi amaciyla verilmistir ve vergi danismanligi veya resmi tavsiye niteligi tasimaz. Lutfen nihai vergi beyannamesi icin FinanzOnline'i kullanin. Karmasik durumlarda lutfen bir Steuerberater'e danisin.",
        "bs": "\n\n⚠️ **Izjava o odricanju odgovornosti**: Ovaj odgovor sluzi samo u opce informativne svrhe i ne predstavlja porezno savjetovanje niti formalnu preporuku. Molimo koristite FinanzOnline za konacnu poreznu prijavu. U slozenim situacijama molimo konsultujte Steuerberater.",
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

您不得提供Steuerberatungsgesetz意义上的税务咨询。""",

            "fr": """Vous etes un assistant IA utile pour les questions fiscales autrichiennes.
Vous aidez les utilisateurs a comprendre leur situation fiscale et a repondre aux questions sur le systeme fiscal autrichien.

REGLES IMPORTANTES :
1. Utilisez TOUJOURS les lois et baremes fiscaux fournis comme base de vos reponses
2. Integrez les donnees fiscales actuelles de l'utilisateur dans vos reponses lorsque c'est pertinent
3. Ne donnez JAMAIS de montants fiscaux specifiques comme garantie (ex. : 'Vous obtiendrez certainement un remboursement de X EUR')
4. Expliquez les concepts fiscaux complexes en langage simple
5. En cas de doute, recommandez la consultation d'un Steuerberater
6. Repondez dans la langue de l'utilisateur
7. Soyez precis et utilisez la terminologie fiscale autrichienne officielle

Vous ne pouvez PAS fournir de conseil fiscal au sens du Steuerberatungsgesetz.""",

            "ru": """Вы полезный ИИ-ассистент по вопросам австрийского налогообложения.
Вы помогаете пользователям понять их налоговую ситуацию и отвечаете на вопросы об австрийской налоговой системе.

ВАЖНЫЕ ПРАВИЛА:
1. ВСЕГДА используйте предоставленные налоговые законы и таблицы как основу для ответов
2. Включайте текущие налоговые данные пользователя в ответы, когда это уместно
3. НИКОГДА не давайте конкретные налоговые суммы как гарантию (напр. 'Вы гарантированно получите возврат X EUR')
4. Объясняйте сложные налоговые концепции простым языком
5. Если не уверены, рекомендуйте обратиться к Steuerberater
6. Отвечайте на языке пользователя
7. Будьте точны и используйте официальную австрийскую налоговую терминологию

Вы НЕ можете предоставлять налоговые консультации в смысле Steuerberatungsgesetz.""",

            "hu": """On egy hasznos MI-asszisztens az osztrak adougyi kerdesekhez.
Segit a felhasznaloknak megerteni az adougyi helyzetuket es valaszol az osztrak adorendszerrel kapcsolatos kerdesekre.

FONTOS SZABALYOK:
1. MINDIG a megadott adotorvenyeket es tablazatokat hasznalja valaszai alapjakent
2. A felhasznalo aktualis adoadatait vonatkozo valaszaiba beleerje, ha relevans
3. SOHA ne adjon meg konkret adoosszegeket garantciakent (pl. 'Garantaltan X EUR visszaterit kap')
4. Magyarazza el az osszetett adougyi fogalmakat egyszeru nyelven
5. Ha bizonytalan, javasolja Steuerberater felkereset
6. A felhasznalo nyelven valaszoljon
7. Legyen pontos es hasznalja a hivatalos osztrak adougyi terminologiat

NEM nyujthat adotanacsadast a Steuerberatungsgesetz ertelmeben.""",

            "pl": """Jestes pomocnym asystentem AI do pytan dotyczacych austriackiego systemu podatkowego.
Pomagasz uzytkownikom zrozumiec ich sytuacje podatkowa i odpowiadasz na pytania dotyczace austriackiego systemu podatkowego.

WAZNE ZASADY:
1. ZAWSZE wykorzystuj dostarczone ustawy podatkowe i tabele jako podstawe swoich odpowiedzi
2. Uwzgledniaj aktualne dane podatkowe uzytkownika w odpowiedziach, gdy jest to istotne
3. NIGDY nie podawaj konkretnych kwot podatkowych jako gwarancji (np. 'Na pewno otrzymasz zwrot X EUR')
4. Wyjasniaj zlozone koncepcje podatkowe prostym jezykiem
5. Jesli nie jestes pewien, zalec konsultacje ze Steuerberater
6. Odpowiadaj w jezyku uzytkownika
7. Badz precyzyjny i uzywaj oficjalnej austriackiej terminologii podatkowej

NIE mozesz swiadczyc doradztwa podatkowego w rozumieniu Steuerberatungsgesetz.""",

            "tr": """Avusturya vergi sorulari icin yardimci bir yapay zeka asistanisiniz.
Kullanicilarin vergi durumlarini anlamalarina yardimci olur ve Avusturya vergi sistemi hakkindaki sorulari yanitlarsiniz.

ONEMLI KURALLAR:
1. Yanitlariniz icin HER ZAMAN saglanan vergi yasalarini ve tablolarini temel alin
2. Kullanicinin guncel vergi verilerini yanitlariniza dahil edin
3. ASLA belirli vergi tutarlarini garanti olarak vermeyin (orn. 'Kesinlikle X EUR iade alacaksiniz')
4. Karmasik vergi kavramlarini basit bir dille aciklayin
5. Emin degilseniz, bir Steuerberater'e danisilmasini onerin
6. Kullanicinin dilinde yanilayin
7. Kesin olun ve resmi Avusturya vergi terminolojisini kullanin

Steuerberatungsgesetz anlaiminda vergi danismanligi SAĞLAYAMAZSINIZ.""",

            "bs": """Vi ste koristan AI asistent za pitanja o austrijskom poreznom sistemu.
Pomazete korisnicima da razumiju svoju poreznu situaciju i odgovarate na pitanja o austrijskom poreznom sistemu.

VAZNA PRAVILA:
1. UVIJEK koristite dostavljene porezne zakone i tablice kao osnovu za vase odgovore
2. Ukljucite trenutne porezne podatke korisnika u vase odgovore kada je to relevantno
3. NIKADA ne navodite konkretne porezne iznose kao garanciju (npr. 'Garantirano cete dobiti povrat od X EUR')
4. Objasnite slozene porezne koncepte jednostavnim jezikom
5. Ako niste sigurni, preporucite konsultaciju sa Steuerberater-om
6. Odgovarajte na jeziku korisnika
7. Budite precizni i koristite sluzbenu austrijsku poreznu terminologiju

NE smijete pruzati porezno savjetovanje u smislu Steuerberatungsgesetz."""
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

请根据提供的上下文回答问题。""",

            "fr": f"""Contexte de la base de connaissances et des donnees utilisateur :
{context}

Question de l'utilisateur : {user_message}

Veuillez repondre a la question en vous basant sur le contexte fourni.""",

            "ru": f"""Контекст из базы знаний и данных пользователя:
{context}

Вопрос пользователя: {user_message}

Пожалуйста, ответьте на вопрос на основе предоставленного контекста.""",

            "hu": f"""Kontextus a tudasbazisbol es a felhasznaloi adatokbol:
{context}

Felhasznaloi kerdes: {user_message}

Kerem, valaszolja meg a kerdest a megadott kontextus alapjan.""",

            "pl": f"""Kontekst z bazy wiedzy i danych uzytkownika:
{context}

Pytanie uzytkownika: {user_message}

Prosze odpowiedziec na pytanie na podstawie dostarczonego kontekstu.""",

            "tr": f"""Bilgi tabanindan ve kullanici verilerinden baglam:
{context}

Kullanici sorusu: {user_message}

Lutfen saglanan baglama dayanarak soruyu yanitlayin.""",

            "bs": f"""Kontekst iz baze znanja i korisnickih podataka:
{context}

Pitanje korisnika: {user_message}

Molimo odgovorite na pitanje na osnovu pruzenog konteksta."""
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
            "zh": f"解释一下这个文档中识别出了什么，哪些项目可以抵税。",
            "fr": f"Expliquez ce qui a ete reconnu dans ce document et quels postes sont deductibles fiscalement.",
            "ru": f"Объясните, что было распознано в этом документе и какие позиции подлежат налоговому вычету.",
            "hu": f"Magyarazza el, mit ismertek fel ebben a dokumentumban, es mely tetelek vonhatok le adobol.",
            "pl": f"Wyjasnij, co zostalo rozpoznane w tym dokumencie i ktore pozycje mozna odliczyc od podatku.",
            "tr": f"Bu belgede nelerin tanindigini ve hangi kalemlerin vergiden dusulebilegini aciklayin.",
            "bs": f"Objasnite sta je prepoznato u ovom dokumentu i koje stavke su porezno odbitne.",
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
            "zh": "分析我目前的税务情况并给我税务优化建议。",
            "fr": "Analysez ma situation fiscale actuelle et donnez-moi des suggestions d'optimisation fiscale.",
            "ru": "Проанализируйте мою текущую налоговую ситуацию и дайте предложения по оптимизации налогов.",
            "hu": "Elemezze a jelenlegi adougyi helyzetemet, es adjon javaslatokat az adooptimalizalashoz.",
            "pl": "Przeanalizuj moja aktualna sytuacje podatkowa i podaj sugestie dotyczace optymalizacji podatkowej.",
            "tr": "Mevcut vergi durumumu analiz edin ve vergi optimizasyonu icin oneriler verin.",
            "bs": "Analizirajte moju trenutnu poreznu situaciju i dajte mi prijedloge za poreznu optimizaciju.",
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
