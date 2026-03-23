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
        },
        'fr': {
            'title': 'Avis important',
            'content': '''
**Taxja est un système de référence et ne constitue pas un conseil fiscal officiel**

Veuillez noter les points importants suivants :

1. **Pas de conseil fiscal** : Taxja ne fournit pas de conseil fiscal professionnel au sens de la loi autrichienne sur le conseil fiscal (Steuerberatungsgesetz). Tous les calculs et recommandations servent uniquement de guide.

2. **Aucune responsabilité** : Les développeurs et opérateurs de Taxja n'assument aucune responsabilité quant à l'exactitude des calculs ou pour tout dommage résultant de l'utilisation du système.

3. **FinanzOnline fait foi** : La déclaration fiscale définitive doit être soumise via FinanzOnline. Les valeurs qui y sont calculées sont contraignantes.

4. **Cas complexes** : Pour les situations fiscales complexes, nous recommandons vivement de consulter un conseiller fiscal agréé (Steuerberater).

5. **Actualité** : Bien que nous nous efforcions de maintenir les taux d'imposition et les réglementations à jour, les lois peuvent changer. Veuillez vérifier les informations importantes.

6. **Responsabilité personnelle** : Vous êtes responsable de l'exactitude de votre déclaration fiscale.

7. **Protection des données** : Vos données sont stockées de manière chiffrée conformément au RGPD. Vous avez le droit d'accès, de rectification et de suppression à tout moment.

**En utilisant Taxja, vous confirmez avoir lu et accepté ces avis.**
            ''',
            'version': '1.0',
            'effective_date': '2026-01-01'
        },
        'ru': {
            'title': 'Важное уведомление',
            'content': '''
**Taxja является справочной системой и не является официальной налоговой консультацией**

Пожалуйста, обратите внимание на следующие важные моменты:

1. **Не является налоговой консультацией**: Taxja не предоставляет профессиональных налоговых консультаций в соответствии с австрийским законом о налоговом консультировании (Steuerberatungsgesetz). Все расчёты и рекомендации носят исключительно справочный характер.

2. **Отказ от ответственности**: Разработчики и операторы Taxja не несут ответственности за точность расчётов или за любой ущерб, возникший в результате использования системы.

3. **FinanzOnline является определяющим**: Окончательная налоговая декларация должна быть подана через FinanzOnline. Рассчитанные там значения являются обязательными.

4. **Сложные случаи**: В сложных налоговых ситуациях мы настоятельно рекомендуем обратиться к лицензированному налоговому консультанту (Steuerberater).

5. **Актуальность**: Хотя мы стремимся поддерживать налоговые ставки и правила в актуальном состоянии, законодательство может измениться. Пожалуйста, проверяйте важную информацию.

6. **Личная ответственность**: Вы несёте ответственность за правильность Вашей налоговой декларации.

7. **Защита данных**: Ваши данные хранятся в зашифрованном виде в соответствии с GDPR. Вы имеете право на доступ, исправление и удаление данных в любое время.

**Используя Taxja, Вы подтверждаете, что прочитали и приняли эти уведомления.**
            ''',
            'version': '1.0',
            'effective_date': '2026-01-01'
        },
        'hu': {
            'title': 'Fontos figyelmeztetEs',
            'content': '''
**A Taxja egy referenciarendszer, es nem hivatalos adotanacsadas**

Kerem, vegye figyelembe a kovetkezo fontos pontokat:

1. **Nem adotanacsadas**: A Taxja nem nyujt professzionalis adotanacsadast az osztrak adotanacsadasi torveny (Steuerberatungsgesetz) ertelmeben. Minden szamitas es ajanlasok kizarolag tajekoztatasi celokat szolgalnak.

2. **Felelosseg kizarasa**: A Taxja fejlesztoi es uzemeltetoi nem vallalnak feleloseget a szamitasok pontossagaert vagy a rendszer hasznalatabol eredo karokert.

3. **A FinanzOnline az iranyadO**: A vegleges adobevallast a FinanzOnline-on keresztul kell benyujtani. Az ott szamitott ertekek kotoek.

4. **Osszetett esetek**: Osszetett adougyi helyzetekben nyomatekosan javasoljuk egy engedellyel rendelkezo adotanacsado (Steuerberater) felkereseset.

5. **Aktualitas**: Bar torekszunk az adokulcsok es szabalyozasok naprakezsen tartasara, a jogszabalyok valtozhatnak. Kerem, ellenorizze a fontos informaciokat.

6. **Szemelyes felelosseg**: On felelos az adobevallasa helyessegerert.

7. **Adatvedelem**: Adatait a GDPR-nek megfeleloen titkositva taroljuk. Onnek barmikor joga van a hozzafereshez, helyesbiteshez es torleshez.

**A Taxja hasznalataval megerositi, hogy elolvasta es elfogadta ezeket a figyelmezteteseket.**
            ''',
            'version': '1.0',
            'effective_date': '2026-01-01'
        },
        'pl': {
            'title': 'Wazna informacja',
            'content': '''
**Taxja jest systemem referencyjnym i nie stanowi oficjalnego doradztwa podatkowego**

Prosze zwrocic uwage na nastepujace wazne punkty:

1. **Brak doradztwa podatkowego**: Taxja nie swiadczy profesjonalnego doradztwa podatkowego w rozumieniu austriackiej ustawy o doradztwie podatkowym (Steuerberatungsgesetz). Wszystkie obliczenia i zalecenia sluza wylacznie jako orientacja.

2. **Wylaczenie odpowiedzialnosci**: Twórcy i operatorzy Taxja nie ponoszą odpowiedzialnosci za dokladnosc obliczen ani za ewentualne szkody wynikajace z korzystania z systemu.

3. **FinanzOnline jest wiazacy**: Ostateczne zeznanie podatkowe musi zostac zlozone za posrednictwem FinanzOnline. Obliczone tam wartosci sa wiazace.

4. **Zlozone przypadki**: W zlozonych sytuacjach podatkowych zdecydowanie zalecamy konsultacje z licencjonowanym doradca podatkowym (Steuerberater).

5. **Aktualnosc**: Choc staramy sie utrzymywac stawki podatkowe i przepisy na biezaco, prawo moze sie zmieniac. Prosze weryfikowac wazne informacje.

6. **Odpowiedzialnosc osobista**: Uzytkownik jest odpowiedzialny za prawidlowosc swojego zeznania podatkowego.

7. **Ochrona danych**: Dane sa przechowywane w formie zaszyfrowanej zgodnie z RODO. W kazdej chwili przysluguje prawo dostepu, sprostowania i usuniecia danych.

**Korzystajac z Taxja, potwierdzasz, ze zapoznales sie z tymi informacjami i je akceptujesz.**
            ''',
            'version': '1.0',
            'effective_date': '2026-01-01'
        },
        'tr': {
            'title': 'Onemli uyari',
            'content': '''
**Taxja bir referans sistemidir ve resmi vergi danismanligi degildir**

Lutfen asagidaki onemli noktalara dikkat edin:

1. **Vergi danismanligi degildir**: Taxja, Avusturya vergi danismanligi yasasi (Steuerberatungsgesetz) anlaminda profesyonel vergi danismanligi sunmaz. Tum hesaplamalar ve oneriler yalnizca yol gosterici niteliktedir.

2. **Sorumluluk reddi**: Taxja'nin gelistiricileri ve isletmecileri, hesaplamalarin dogrulugu veya sistemin kullanimindan kaynaklanan zararlar icin herhangi bir sorumluluk kabul etmez.

3. **FinanzOnline belirleyicidir**: Nihai vergi beyannamesi FinanzOnline uzerinden sunulmalidir. Orada hesaplanan degerler baglayicidir.

4. **Karmasik durumlar**: Karmasik vergi durumlarinda, lisansli bir vergi danismanina (Steuerberater) basvurmanizi siddetle oneririz.

5. **Guncellik**: Vergi oranlarini ve duzenlememeleri guncel tutmaya calissak da, yasalar degisebilir. Lutfen onemli bilgileri dogrulayin.

6. **Kisisel sorumluluk**: Vergi beyannamenizin dogrolugondan siz sorumlusunuz.

7. **Veri korumasi**: Verileriniz GDPR'ye uygun olarak sifrelenerek saklanir. Istediginiz zaman erisim, dustzeltme ve silme hakkiniz vardir.

**Taxja'yi kullanarak, bu uyarilari okudogunuzu ve kabul ettiginizi onaylarsiniz.**
            ''',
            'version': '1.0',
            'effective_date': '2026-01-01'
        },
        'bs': {
            'title': 'Vazna napomena',
            'content': '''
**Taxja je referentni sistem i ne predstavlja zvanicno porezno savjetovanje**

Molimo obratite paznju na sljedece vazne tacke:

1. **Nije porezno savjetovanje**: Taxja ne pruza profesionalno porezno savjetovanje u smislu austrijskog zakona o poreznom savjetovanju (Steuerberatungsgesetz). Svi proracuni i preporuke sluze iskljucivo kao orijentacija.

2. **Iskljucenje odgovornosti**: Programeri i operateri Taxja ne preuzimaju odgovornost za tacnost proracuna niti za eventualnu stetu nastalu koriscenjem sistema.

3. **FinanzOnline je mjerodavan**: Konacna porezna prijava mora biti podnesena putem FinanzOnline. Tamo izracunate vrijednosti su obavezujuce.

4. **Slozeni slucajevi**: U slozenim poreznim situacijama snazno preporucujemo konsultaciju s licenciranim poreznim savjetnikom (Steuerberater).

5. **Aktuelnost**: Iako se trudimo odrzavati porezne stope i propise azurnim, zakoni se mogu promijeniti. Molimo provjerite vazne informacije.

6. **Licna odgovornost**: Vi ste odgovorni za tacnost vase porezne prijave.

7. **Zastita podataka**: Vasi podaci se cuvaju sifrirano u skladu s GDPR-om. U svakom trenutku imate pravo na pristup, ispravku i brisanje podataka.

**Koristenjem Taxja potvrdjujete da ste procitali i prihvatili ove napomene.**
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
                  '最终税务申报通过 FinanzOnline。复杂情况请咨询税务顾问。',
            'fr': '⚠️ Taxja est un système de référence et ne constitue pas un conseil fiscal officiel. '
                  'Déclaration fiscale définitive via FinanzOnline. Consultez un conseiller fiscal pour les cas complexes.',
            'ru': '⚠️ Taxja является справочной системой и не является официальной налоговой консультацией. '
                  'Окончательная налоговая декларация через FinanzOnline. В сложных случаях обращайтесь к налоговому консультанту.',
            'hu': '⚠️ A Taxja egy referenciarendszer, nem hivatalos adotanacsadas. '
                  'A vegleges adobevallas a FinanzOnline-on keresztul. Osszetett esetekben forduljon adotanacsadohoz.',
            'pl': '⚠️ Taxja jest systemem referencyjnym, nie stanowi oficjalnego doradztwa podatkowego. '
                  'Ostateczne zeznanie podatkowe przez FinanzOnline. W zlozonych przypadkach skonsultuj sie z doradca podatkowym.',
            'tr': '⚠️ Taxja bir referans sistemidir, resmi vergi danismanligi degildir. '
                  'Nihai vergi beyannamesi FinanzOnline uzerinden. Karmasik durumlarda vergi danismanina basvurun.',
            'bs': '⚠️ Taxja je referentni sistem i ne predstavlja zvanicno porezno savjetovanje. '
                  'Konacna porezna prijava putem FinanzOnline. U slozenim slucajevima konsultujte poreznog savjetnika.',
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
                  '请使用 FinanzOnline 进行最终计算。复杂情况请咨询税务顾问。',
            'fr': '⚠️ **Avertissement** : Cette réponse est fournie à titre indicatif uniquement et ne constitue pas '
                  'un conseil fiscal ni une recommandation formelle. Veuillez utiliser FinanzOnline pour les calculs '
                  'définitifs. Pour les cas complexes, veuillez consulter un conseiller fiscal.',
            'ru': '⚠️ **Уведомление**: Этот ответ предоставлен исключительно для общего ориентирования и не является '
                  'налоговой консультацией или официальной рекомендацией. Пожалуйста, используйте FinanzOnline для '
                  'окончательных расчётов. В сложных случаях обратитесь к налоговому консультанту.',
            'hu': '⚠️ **Megjegyzes**: Ez a valasz kizarolag altalanos tajekoztatasi celokat szolgal, es nem minosul '
                  'adotanacsadasnak vagy hivatalos ajanlasnak. Kerem, hasznalja a FinanzOnline-t a vegleges szamitasokhoz. '
                  'Osszetett esetekben kerem, forduljon adotanacsadohoz.',
            'pl': '⚠️ **Uwaga**: Ta odpowiedz sluzy wylacznie jako ogolna orientacja i nie stanowi '
                  'porady podatkowej ani formalnej rekomendacji. Prosze uzyc FinanzOnline do ostatecznych obliczen. '
                  'W zlozonych przypadkach prosze skonsultowac sie z doradca podatkowym.',
            'tr': '⚠️ **Uyari**: Bu yanit yalnizca genel bilgilendirme amaciyla verilmistir ve vergi '
                  'danismanligi veya resmi tavsiye niteligi tasimaz. Lutfen nihai hesaplamalar icin FinanzOnline kullanin. '
                  'Karmasik durumlarda lutfen bir vergi danismanina basvurun.',
            'bs': '⚠️ **Napomena**: Ovaj odgovor sluzi iskljucivo kao opca orijentacija i ne predstavlja '
                  'porezno savjetovanje niti formalnu preporuku. Molimo koristite FinanzOnline za konacne proracune. '
                  'U slozenim slucajevima molimo konsultujte poreznog savjetnika.',
        }
        
        return ai_disclaimers.get(language, ai_disclaimers['de'])
