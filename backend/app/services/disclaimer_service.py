"""
Disclaimer Service

Manages legal disclaimers in multiple languages.
Tracks user acceptance of disclaimers.

Requirements: 17.11
"""

from datetime import datetime
from typing import Dict, Optional
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.disclaimer_acceptance import DisclaimerAcceptance


class DisclaimerService:
    """Service for managing disclaimers"""
    
    # Disclaimer text in multiple languages
    DISCLAIMERS = {
        'de': {
            'title': 'Wichtiger Hinweis',
            'content': '''
**Taxja ist ein Referenzsystem und keine offizielle Steuerberatung**

Bitte beachten Sie folgende wichtige Punkte:

1. **Keine Steuerberatung**: Taxja bietet keine professionelle Steuerberatung im Sinne des Steuerberatungsgesetzes. Alle Berechnungen und Empfehlungen dienen nur als Orientierungshilfe.

2. **Keine Haftung**: Die Entwickler und Betreiber von Taxja übernehmen keine Haftung für die Richtigkeit der Berechnungen oder für eventuelle Schäden, die durch die Nutzung des Systems entstehen.

3. **FinanzOnline ist maßgeblich**: Die endgültige Steuererklärung muss über FinanzOnline eingereicht werden. Die dort berechneten Werte sind verbindlich.

4. **Komplexe Fälle**: Bei komplexen steuerlichen Situationen empfehlen wir dringend die Konsultation eines zugelassenen Steuerberaters.

5. **Aktualität**: Obwohl wir uns bemühen, die Steuersätze und Regelungen aktuell zu halten, können sich Gesetze ändern. Bitte überprüfen Sie wichtige Informationen.

6. **Eigenverantwortung**: Sie sind selbst für die Richtigkeit Ihrer Steuererklärung verantwortlich.

7. **Datenschutz**: Ihre Daten werden gemäß DSGVO verschlüsselt gespeichert. Sie haben jederzeit das Recht auf Auskunft, Berichtigung und Löschung.

**Mit der Nutzung von Taxja bestätigen Sie, dass Sie diese Hinweise zur Kenntnis genommen haben und akzeptieren.**
            ''',
            'version': '1.0',
            'effective_date': '2026-01-01'
        },
        'en': {
            'title': 'Important Notice',
            'content': '''
**Taxja is a reference system and not official tax advice**

Please note the following important points:

1. **Not Tax Advice**: Taxja does not provide professional tax advice as defined by Austrian tax advisory law. All calculations and recommendations serve only as guidance.

2. **No Liability**: The developers and operators of Taxja assume no liability for the accuracy of calculations or for any damages arising from the use of the system.

3. **FinanzOnline is Authoritative**: The final tax return must be submitted through FinanzOnline. The values calculated there are binding.

4. **Complex Cases**: For complex tax situations, we strongly recommend consulting a licensed tax advisor (Steuerberater).

5. **Currency**: While we strive to keep tax rates and regulations current, laws may change. Please verify important information.

6. **Personal Responsibility**: You are responsible for the accuracy of your tax return.

7. **Data Privacy**: Your data is stored encrypted in accordance with GDPR. You have the right to access, correction, and deletion at any time.

**By using Taxja, you confirm that you have read and accept these notices.**
            ''',
            'version': '1.0',
            'effective_date': '2026-01-01'
        },
        'zh': {
            'title': '重要声明',
            'content': '''
**Taxja 是参考系统，不提供正式税务咨询**

请注意以下重要事项：

1. **非税务咨询**：Taxja 不提供奥地利税务咨询法定义的专业税务咨询。所有计算和建议仅供参考。

2. **免责声明**：Taxja 的开发者和运营者对计算的准确性或因使用本系统而产生的任何损害不承担责任。

3. **FinanzOnline 为准**：最终税务申报必须通过 FinanzOnline 提交。那里计算的数值具有约束力。

4. **复杂情况**：对于复杂的税务情况，我们强烈建议咨询持牌税务顾问（Steuerberater）。

5. **时效性**：虽然我们努力保持税率和法规的最新状态，但法律可能会发生变化。请核实重要信息。

6. **个人责任**：您对税务申报的准确性负责。

7. **数据隐私**：您的数据按照 GDPR 加密存储。您随时有权访问、更正和删除数据。

**使用 Taxja 即表示您确认已阅读并接受这些声明。**
            ''',
            'version': '1.0',
            'effective_date': '2026-01-01'
        }
    }
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_disclaimer(self, language: str = 'de') -> Dict:
        """
        Get disclaimer text in specified language
        
        Args:
            language: Language code (de, en, zh)
            
        Returns:
            Disclaimer dictionary with title, content, version, effective_date
        """
        if language not in self.DISCLAIMERS:
            language = 'de'  # Default to German
        
        return self.DISCLAIMERS[language]
    
    def has_accepted_disclaimer(self, user_id: int) -> bool:
        """
        Check if user has accepted the current disclaimer
        
        Args:
            user_id: User ID
            
        Returns:
            True if user has accepted current version
        """
        current_version = self.DISCLAIMERS['de']['version']
        
        acceptance = self.db.query(DisclaimerAcceptance).filter(
            DisclaimerAcceptance.user_id == user_id,
            DisclaimerAcceptance.version == current_version
        ).first()
        
        return acceptance is not None
    
    def record_acceptance(
        self,
        user_id: int,
        language: str = 'de',
        ip_address: Optional[str] = None
    ) -> DisclaimerAcceptance:
        """
        Record user acceptance of disclaimer
        
        Args:
            user_id: User ID
            language: Language in which disclaimer was shown
            ip_address: IP address of acceptance
            
        Returns:
            DisclaimerAcceptance record
        """
        disclaimer = self.get_disclaimer(language)
        
        acceptance = DisclaimerAcceptance(
            user_id=user_id,
            version=disclaimer['version'],
            language=language,
            accepted_at=datetime.utcnow(),
            ip_address=ip_address
        )
        
        self.db.add(acceptance)
        self.db.commit()
        self.db.refresh(acceptance)
        
        return acceptance
    
    def get_acceptance_history(self, user_id: int) -> list:
        """
        Get history of disclaimer acceptances for a user
        
        Args:
            user_id: User ID
            
        Returns:
            List of acceptance records
        """
        acceptances = self.db.query(DisclaimerAcceptance).filter(
            DisclaimerAcceptance.user_id == user_id
        ).order_by(DisclaimerAcceptance.accepted_at.desc()).all()
        
        return [
            {
                'version': acc.version,
                'language': acc.language,
                'accepted_at': acc.accepted_at.isoformat(),
                'ip_address': acc.ip_address
            }
            for acc in acceptances
        ]
    
    def get_short_disclaimer(self, language: str = 'de') -> str:
        """
        Get short disclaimer text for display at bottom of pages
        
        Args:
            language: Language code
            
        Returns:
            Short disclaimer text
        """
        short_disclaimers = {
            'de': '⚠️ Taxja ist ein Referenzsystem und keine offizielle Steuerberatung. '
                  'Endgültige Steuererklärung über FinanzOnline. Bei komplexen Fällen Steuerberater konsultieren.',
            'en': '⚠️ Taxja is a reference system and not official tax advice. '
                  'Final tax return through FinanzOnline. Consult tax advisor for complex cases.',
            'zh': '⚠️ Taxja 是参考系统，不提供正式税务咨询。'
                  '最终税务申报通过 FinanzOnline。复杂情况请咨询税务顾问。'
        }
        
        return short_disclaimers.get(language, short_disclaimers['de'])
    
    def get_ai_disclaimer(self, language: str = 'de') -> str:
        """
        Get disclaimer text specifically for AI assistant responses
        
        Args:
            language: Language code
            
        Returns:
            AI disclaimer text
        """
        ai_disclaimers = {
            'de': '⚠️ **Hinweis**: Diese Antwort dient nur als allgemeine Orientierung und stellt keine '
                  'Steuerberatung oder formelle Empfehlung dar. Bitte verwenden Sie FinanzOnline für die '
                  'endgültige Berechnung. Bei komplexen Fällen konsultieren Sie bitte einen Steuerberater.',
            'en': '⚠️ **Notice**: This response is for general guidance only and does not constitute '
                  'tax advice or formal recommendation. Please use FinanzOnline for final calculations. '
                  'For complex cases, please consult a tax advisor.',
            'zh': '⚠️ **声明**：此回答仅供一般性参考，不构成税务咨询或正式建议。'
                  '请使用 FinanzOnline 进行最终计算。复杂情况请咨询税务顾问。'
        }
        
        return ai_disclaimers.get(language, ai_disclaimers['de'])
