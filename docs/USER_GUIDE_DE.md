# Taxja Benutzerhandbuch (Deutsch)

## Willkommen bei Taxja

Taxja ist Ihre automatisierte Steuerverwaltungsplattform für Österreich. Dieses Handbuch hilft Ihnen, das System optimal zu nutzen.

## Inhaltsverzeichnis

1. [Erste Schritte](#erste-schritte)
2. [Transaktionen verwalten](#transaktionen-verwalten)
3. [Immobilienverwaltung (für Vermieter)](#immobilienverwaltung-für-vermieter)
4. [Dokumente hochladen und OCR](#dokumente-hochladen-und-ocr)
5. [Steuerberechnungen](#steuerberechnungen)
6. [Berichte erstellen](#berichte-erstellen)
7. [AI Steuerassistent](#ai-steuerassistent)
8. [Häufig gestellte Fragen (FAQ)](#faq)

## Erste Schritte

### Registrierung

1. Besuchen Sie https://taxja.at
2. Klicken Sie auf "Registrieren"
3. Geben Sie Ihre E-Mail-Adresse und ein sicheres Passwort ein
4. Wählen Sie Ihren Benutzertyp:
   - **Arbeitnehmer**: Angestellte mit Lohnzettel
   - **Vermieter**: Personen mit Mieteinnahmen
   - **Selbständige**: EPU, Freiberufler
   - **Kombination**: Mehrere Einkommensarten

### Profil einrichten

Nach der Registrierung vervollständigen Sie Ihr Profil:

1. **Persönliche Daten**
   - Name, Adresse
   - Steuernummer
   - UID-Nummer (falls selbständig)

2. **Familieninformationen**
   - Anzahl der Kinder (für Kinderabsetzbetrag)
   - Alleinerziehend (für zusätzliche Absetzbeträge)

3. **Pendlerinformationen**
   - Entfernung zur Arbeit (für Pendlerpauschale)
   - Öffentliche Verkehrsmittel verfügbar?

### Zwei-Faktor-Authentifizierung (2FA)

Für zusätzliche Sicherheit aktivieren Sie 2FA:

1. Gehen Sie zu Einstellungen → Sicherheit
2. Klicken Sie auf "2FA aktivieren"
3. Scannen Sie den QR-Code mit einer Authenticator-App (z.B. Google Authenticator)
4. Geben Sie den 6-stelligen Code ein

## Transaktionen verwalten

### Transaktion manuell erstellen

1. Klicken Sie auf "Transaktionen" → "Neue Transaktion"
2. Wählen Sie den Typ:
   - **Einnahme**: Gehalt, Mieteinnahmen, Honorare
   - **Ausgabe**: Betriebsausgaben, abzugsfähige Kosten
3. Geben Sie ein:
   - Betrag (€)
   - Datum
   - Beschreibung
   - Kategorie (wird automatisch vorgeschlagen)
4. Klicken Sie auf "Speichern"

### Transaktionen importieren

#### CSV-Import von Bankkonto

1. Exportieren Sie Ihre Kontobewegungen als CSV
2. Klicken Sie auf "Transaktionen" → "Importieren"
3. Wählen Sie Ihre Bank aus der Liste
4. Laden Sie die CSV-Datei hoch
5. Überprüfen Sie die Vorschau
6. Bestätigen Sie den Import

**Unterstützte Banken:**
- Raiffeisen
- Erste Bank
- Sparkasse
- Bank Austria
- BAWAG P.S.K.

### Automatische Kategorisierung

Taxja kategorisiert Transaktionen automatisch:

- **Regelbasiert**: Bekannte Händler (BILLA, SPAR, etc.)
- **KI-gestützt**: Lernt aus Ihren Korrekturen

**Kategorien korrigieren:**
1. Klicken Sie auf die Transaktion
2. Wählen Sie die richtige Kategorie
3. Taxja lernt aus Ihrer Korrektur

### Abzugsfähigkeit prüfen

Taxja zeigt automatisch, ob eine Ausgabe steuerlich absetzbar ist:

- ✅ **Abzugsfähig**: Wird bei Steuerberechnung berücksichtigt
- ❌ **Nicht abzugsfähig**: Privater Aufwand

**Beispiele für abzugsfähige Ausgaben:**

**Selbständige:**
- Büromaterial
- Arbeitsmittel
- Fachliteratur
- Fortbildungen
- Geschäftsreisen

**Vermieter:**
- Instandhaltung
- Hausverwaltung
- Versicherungen
- Grundsteuer
- Kreditzinsen

## Immobilienverwaltung (für Vermieter)

Wenn Sie Vermieter mit Mietimmobilien sind, hilft Ihnen Taxja bei der Verwaltung Ihrer Immobilien, der Berechnung der Absetzung für Abnutzung (AfA) und der Verwaltung immobilienbezogener Einnahmen und Ausgaben.

### Immobilie registrieren

#### Schritt 1: Zu Immobilien navigieren

1. Klicken Sie auf "Immobilien" im Hauptmenü
2. Klicken Sie auf "Neue Immobilie hinzufügen"

#### Schritt 2: Immobiliendetails eingeben

**Adressinformationen:**
- Straße (z.B. "Hauptstraße 123")
- Postleitzahl (z.B. "1010")
- Stadt (z.B. "Wien")

**Kaufinformationen:**
- Kaufdatum (wann Sie die Immobilie gekauft haben)
- Kaufpreis (Gesamtbetrag inkl. Grundstück)
- Gebäudewert (abschreibbarer Anteil, ohne Grundstück)

**Tipp:** Wenn Sie den genauen Gebäudewert nicht kennen, berechnet Taxja ihn automatisch als 80% des Kaufpreises (österreichische Steuerkonvention).

**Gebäudedetails:**
- Baujahr (bestimmt den AfA-Satz)
- Immobilientyp:
  - **Vermietung**: Ausschließlich vermietete Immobilie
  - **Eigennutzung**: Ihr Hauptwohnsitz (keine AfA)
  - **Gemischt**: Teilweise vermietet, teilweise selbst genutzt

**Für gemischt genutzte Immobilien:**
- Vermietungsanteil (z.B. 50%, wenn Sie die Hälfte vermieten)

#### Schritt 3: Automatische Berechnungen

Taxja berechnet automatisch:

- **Grundstückswert**: Kaufpreis minus Gebäudewert
- **AfA-Satz**: 
  - 1,5% pro Jahr für Gebäude vor 1915
  - 2,0% pro Jahr für Gebäude ab 1915
- **Jährliche AfA**: Gebäudewert × AfA-Satz

#### Schritt 4: Immobilie speichern

Klicken Sie auf "Immobilie speichern", um die Registrierung abzuschließen.

### AfA (Absetzung für Abnutzung) verstehen

**Was ist AfA?**

AfA (Absetzung für Abnutzung) ist die jährliche Abschreibung des Gebäudewerts Ihrer Mietimmobilie. Sie ist eine steuerlich absetzbare Ausgabe, die die allmähliche Abnutzung des Gebäudes widerspiegelt.

**Wichtige Punkte:**
- Nur das Gebäude ist abschreibbar (nicht das Grundstück)
- Die AfA wird jährlich berechnet
- Sie reduziert Ihre steuerpflichtigen Mieteinnahmen
- Die AfA endet, wenn das Gebäude vollständig abgeschrieben ist

**Beispiel:**

Sie haben eine Mietimmobilie für €350.000 gekauft:
- Kaufpreis: €350.000
- Gebäudewert (80%): €280.000
- Grundstückswert (20%): €70.000
- Baujahr: 1985 (→ 2% AfA-Satz)
- Jährliche AfA: €280.000 × 2% = €5.600

Diese €5.600 werden automatisch jedes Jahr von Ihren Mieteinnahmen abgezogen!

### Transaktionen mit Immobilien verknüpfen

Sobald Sie eine Immobilie registriert haben, können Sie Mieteinnahmen und Ausgaben damit verknüpfen.

#### Mieteinnahmen verknüpfen

1. Gehen Sie zu "Transaktionen"
2. Finden Sie Ihre Mieteinnahmen-Transaktion
3. Klicken Sie auf "Bearbeiten"
4. Wählen Sie die Immobilie aus dem Dropdown-Menü
5. Klicken Sie auf "Speichern"

**Tipp:** Beim Import von E1-Formularen oder Bescheiden schlägt Taxja automatisch vor, Mieteinnahmen mit Ihren registrierten Immobilien zu verknüpfen.

#### Immobilienausgaben verknüpfen

Verknüpfen Sie diese Ausgabenkategorien mit Ihrer Immobilie:

- **Instandhaltung & Reparaturen**: Sanitär, Malerarbeiten, Reparaturen
- **Hausverwaltungsgebühren**: Falls Sie eine Hausverwaltung nutzen
- **Immobilienversicherung**: Gebäudeversicherung
- **Grundsteuer**: Kommunalsteuer
- **Kreditzinsen**: Hypothekenzinsen (absetzbar!)
- **Betriebskosten**: Falls Sie Betriebskosten für Mieter zahlen
- **AfA**: Wird automatisch von Taxja generiert

**Um eine Ausgabe zu verknüpfen:**

1. Gehen Sie zu "Transaktionen"
2. Finden Sie die Ausgaben-Transaktion
3. Klicken Sie auf "Bearbeiten"
4. Wählen Sie die Immobilie aus dem Dropdown-Menü
5. Klicken Sie auf "Speichern"

### Historische AfA nacherfassen

Wenn Sie eine Immobilie in einem früheren Jahr gekauft und jetzt erst registrieren, müssen Sie die historische AfA nacherfassen, um genaue Steuerberechnungen zu gewährleisten.

#### Wann nacherfassen?

Sie sollten nacherfassen, wenn:
- Sie die Immobilie vor dem aktuellen Steuerjahr gekauft haben
- Sie in früheren Jahren keine AfA geltend gemacht haben
- Sie genaue kumulierte AfA-Summen wünschen

#### Schritt 1: Historische AfA in der Vorschau anzeigen

1. Gehen Sie zu "Immobilien"
2. Wählen Sie Ihre Immobilie
3. Klicken Sie auf "Historische AfA"
4. Klicken Sie auf "Nacherfassung in Vorschau anzeigen"

Taxja zeigt Ihnen:
- AfA-Beträge Jahr für Jahr
- Gesamtbetrag der Nacherfassung
- Transaktionsdaten (31. Dezember jedes Jahres)

**Beispiel:**

Immobilie gekauft am 15. Juni 2020, registriert 2026:

| Jahr | AfA | Hinweise |
|------|-----|----------|
| 2020 | €2.800 | Anteilig (7 Monate) |
| 2021 | €5.600 | Volles Jahr |
| 2022 | €5.600 | Volles Jahr |
| 2023 | €5.600 | Volles Jahr |
| 2024 | €5.600 | Volles Jahr |
| 2025 | €5.600 | Volles Jahr |
| **Gesamt** | **€30.800** | |

#### Schritt 2: Nacherfassung bestätigen

1. Überprüfen Sie die Vorschau
2. Klicken Sie auf "Nacherfassung bestätigen"
3. Taxja erstellt AfA-Transaktionen für alle Jahre

**Wichtige Hinweise:**
- Nacherfasste Transaktionen sind als "systemgeneriert" markiert
- Sie sind auf den 31. Dezember jedes Jahres datiert
- Taxja verhindert doppelte Nacherfassungen
- Die AfA endet, wenn der Gebäudewert vollständig abgeschrieben ist

#### Schritt 3: Transaktionen überprüfen

1. Gehen Sie zu "Transaktionen"
2. Filtern Sie nach Immobilie
3. Überprüfen Sie, ob alle AfA-Transaktionen erstellt wurden

### Immobiliendetails anzeigen

#### Immobilienübersicht

1. Gehen Sie zu "Immobilien"
2. Klicken Sie auf eine Immobilie, um Details anzuzeigen

Sie sehen:

**Immobilieninformationen:**
- Adresse
- Kaufdatum und -preis
- Gebäudewert und Grundstückswert
- Baujahr
- AfA-Satz
- Immobilienstatus (Aktiv, Verkauft, Archiviert)

**Finanzkennzahlen:**
- Kumulierte AfA (gesamt bis heute)
- Verbleibender abschreibbarer Wert
- Verbleibende Jahre bis zur vollständigen Abschreibung
- Jährliche Mieteinnahmen (laufendes Jahr)
- Jährliche Ausgaben (laufendes Jahr)
- Netto-Mieteinnahmen (Einnahmen minus Ausgaben)

**Verknüpfte Transaktionen:**
- Alle mit dieser Immobilie verknüpften Einnahmen und Ausgaben
- Gruppiert nach Kategorie
- Filterbar nach Jahr

### Immobilienberichte erstellen

Taxja kann detaillierte Berichte für jede Immobilie erstellen.

#### Gewinn- und Verlustrechnung

Zeigt Mieteinnahmen und -ausgaben für einen bestimmten Zeitraum.

1. Gehen Sie zu "Immobilien"
2. Wählen Sie Ihre Immobilie
3. Klicken Sie auf "Berichte" → "Gewinn- und Verlustrechnung"
4. Wählen Sie den Zeitraum (z.B. "2025")
5. Klicken Sie auf "Generieren"

**Bericht enthält:**
- Mieteinnahmen nach Monat
- Ausgaben nach Kategorie:
  - Instandhaltung & Reparaturen
  - Hausverwaltung
  - Versicherung
  - Grundsteuer
  - Kreditzinsen
  - Betriebskosten
  - AfA
- Netto-Mieteinnahmen (Gewinn/Verlust)

#### AfA-Plan

Zeigt die AfA im Zeitverlauf.

1. Gehen Sie zu "Immobilien"
2. Wählen Sie Ihre Immobilie
3. Klicken Sie auf "Berichte" → "AfA-Plan"
4. Klicken Sie auf "Generieren"

**Bericht enthält:**
- Jährliche AfA nach Jahr
- Kumulierte AfA bis heute
- Verbleibender abschreibbarer Wert
- Prognostizierte zukünftige AfA
- Jahr der vollständigen Abschreibung

#### Berichte exportieren

Beide Berichte können exportiert werden als:
- **PDF**: Zum Drucken oder Teilen mit Steuerberater
- **CSV**: Für Excel-Analysen

### Mehrere Immobilien verwalten

Wenn Sie mehrere Mietimmobilien besitzen, bietet Taxja Portfolio-Einblicke.

#### Portfolio-Dashboard

1. Gehen Sie zu "Immobilien" → "Portfolio-Übersicht"

Sie sehen:
- Gesamtzahl der Immobilien
- Gesamter Gebäudewert aller Immobilien
- Gesamte jährliche AfA
- Gesamte Mieteinnahmen (alle Immobilien)
- Gesamte Ausgaben (alle Immobilien)
- Netto-Mieteinnahmen (Portfolio-weit)

#### Immobilien vergleichen

1. Gehen Sie zu "Immobilien" → "Vergleichen"
2. Wählen Sie Immobilien zum Vergleichen
3. Sehen Sie den Vergleich nebeneinander:
   - Mieteinnahmen
   - Ausgaben
   - Nettoeinkommen
   - Mietrendite (Einnahmen / Gebäudewert)

So identifizieren Sie Ihre besten und schlechtesten Immobilien!

### Immobilien archivieren oder löschen

#### Verkaufte Immobilie archivieren

Wenn Sie eine Immobilie verkaufen:

1. Gehen Sie zu "Immobilien"
2. Wählen Sie die Immobilie
3. Klicken Sie auf "Archivieren"
4. Geben Sie das Verkaufsdatum ein
5. Klicken Sie auf "Bestätigen"

**Was passiert:**
- Immobilienstatus ändert sich zu "Verkauft"
- AfA endet nach dem Verkaufsdatum
- Immobilie wird aus der aktiven Liste ausgeblendet
- Alle historischen Daten bleiben erhalten
- Sie können archivierte Immobilien weiterhin anzeigen

#### Immobilie löschen

Sie können eine Immobilie nur löschen, wenn sie keine verknüpften Transaktionen hat.

1. Gehen Sie zu "Immobilien"
2. Wählen Sie die Immobilie
3. Klicken Sie auf "Löschen"
4. Bestätigen Sie die Löschung

**Warnung:** Dies löscht die Immobilie dauerhaft. Wenn Sie verknüpfte Transaktionen haben, müssen Sie diese zuerst trennen oder die Immobilie stattdessen archivieren.

### Tipps für die Immobilienverwaltung

**1. Registrieren Sie Immobilien so früh wie möglich**
- Warten Sie nicht bis zur Steuererklärung
- Nacherfassung ist möglich, aber Echtzeit-Tracking ist einfacher

**2. Verknüpfen Sie alle immobilienbezogenen Transaktionen**
- Hilft Ihnen, die Rentabilität pro Immobilie zu verfolgen
- Gewährleistet genaue Steuerberechnungen
- Erleichtert die Berichtserstellung

**3. Bewahren Sie Kaufverträge auf**
- Laden Sie sie in Taxja zur Referenz hoch
- OCR kann Immobiliendetails automatisch extrahieren
- Nützlich für Steuerprüfungen

**4. Verfolgen Sie gemischt genutzte Immobilien sorgfältig**
- Setzen Sie den korrekten Vermietungsanteil
- Nur der Vermietungsanteil ist abschreibbar
- Ausgaben müssen anteilig zugeordnet werden

**5. Überprüfen Sie die AfA jährlich**
- Prüfen Sie, ob die jährliche AfA generiert wurde
- Überprüfen Sie die Beträge auf Richtigkeit
- Stellen Sie sicher, dass keine Duplikate vorhanden sind

**6. Nutzen Sie Immobilienberichte für die Steuererklärung**
- Erstellen Sie Gewinn- und Verlustrechnung für E1-Formular
- Fügen Sie AfA in die Ausgabensummen ein
- Exportieren Sie als PDF für Steuerberater

### Häufige Fragen

**F: Kann ich den Kaufpreis meiner Mietimmobilie absetzen?**
A: Nein, Sie können den vollen Kaufpreis nicht in einem Jahr absetzen. Stattdessen schreiben Sie den Gebäudewert über viele Jahre ab (AfA). Der Grundstückswert ist nicht abschreibbar.

**F: Was, wenn ich das Baujahr nicht kenne?**
A: Taxja verwendet den Standard-AfA-Satz von 2%. Sie können das Baujahr im Grundbuch oder Kaufvertrag nachsehen.

**F: Kann ich mein eigenes Haus (Eigennutzung) abschreiben?**
A: Nein. Nur Mietimmobilien sind abschreibbar. Eigengenutzte Immobilien qualifizieren nicht für AfA.

**F: Was ist mit gemischt genutzten Immobilien?**
A: Wenn Sie einen Teil Ihrer Immobilie vermieten (z.B. eine Wohnung in einem Zweifamilienhaus), können Sie den Vermietungsanteil abschreiben. Setzen Sie den Vermietungsanteil bei der Registrierung.

**F: Wie lange dauert die AfA?**
A: Mit einem 2%-Satz dauert es 50 Jahre bis zur vollständigen Abschreibung. Mit 1,5% etwa 67 Jahre. Die AfA endet, wenn die kumulierte AfA dem Gebäudewert entspricht.

**F: Kann ich den AfA-Satz ändern?**
A: Der Satz wird durch das Baujahr gemäß österreichischem Steuerrecht bestimmt. Sie können ihn manuell überschreiben, aber dies sollte nur mit Steuerberater-Beratung erfolgen.

**F: Was passiert, wenn ich eine Immobilie mitten im Jahr verkaufe?**
A: Die AfA wird anteilig für die Monate berechnet, in denen Sie die Immobilie besessen haben. Geben Sie das Verkaufsdatum beim Archivieren ein, und Taxja berechnet die anteilige AfA.

**F: Sind Immobilienkaufkosten absetzbar?**
A: Kaufkosten (Grunderwerbsteuer, Notargebühren, Grundbuchgebühren) werden in den Kaufpreis kapitalisiert, nicht sofort absetzbar. Sie erhöhen Ihre Kostenbasis für zukünftige Veräußerungsgewinnberechnungen.

## Dokumente hochladen und OCR

### Dokument hochladen

1. Klicken Sie auf "Dokumente" → "Hochladen"
2. Wählen Sie Dateien:
   - Foto mit Smartphone aufnehmen
   - Dateien vom Computer auswählen
   - Drag & Drop
3. Unterstützte Formate: JPG, PNG, PDF
4. Maximale Größe: 10 MB pro Datei

### OCR-Erkennung

Taxja erkennt automatisch:

**Lohnzettel:**
- Bruttogehalt
- Nettogehalt
- Lohnsteuer
- Sozialversicherung

**Kassenbons:**
- Datum
- Betrag
- Händler
- Einzelposten
- USt-Beträge

**Rechnungen:**
- Rechnungsnummer
- Datum
- Betrag
- Lieferant
- USt-Betrag

### OCR-Ergebnisse überprüfen

1. Nach dem Upload sehen Sie die erkannten Daten
2. Felder mit niedriger Konfidenz sind markiert
3. Korrigieren Sie bei Bedarf die Werte
4. Klicken Sie auf "Bestätigen"
5. Taxja erstellt automatisch eine Transaktion

**Tipps für bessere Erkennung:**
- Gute Beleuchtung
- Flach auflegen (nicht geknickt)
- Gesamtes Dokument im Bild
- Ausreichende Auflösung

### Kassenbon-Analyse für Selbständige

Bei Supermarkt-Kassenbons fragt Taxja:

> "Ist dies ein geschäftlicher Einkauf?"

Taxja analysiert die Einzelposten:
- ✅ Bürobedarf, Reinigungsmittel → absetzbar
- ❌ Lebensmittel, Privatartikel → nicht absetzbar

Sie können die Auswahl anpassen.

## Steuerberechnungen

### Steuerübersicht

Das Dashboard zeigt:

- **Jahreseinkommen**: Summe aller Einnahmen
- **Abzugsfähige Ausgaben**: Summe aller Betriebsausgaben
- **Geschätzte Steuer**: Voraussichtliche Steuerlast
- **Bereits bezahlt**: Lohnsteuer, Vorauszahlungen
- **Noch zu zahlen**: Restbetrag

### Einkommensteuer

Taxja berechnet nach den **offiziellen USP 2026 Tarifen**:

| Einkommen | Steuersatz |
|-----------|------------|
| €0 – €13.539 | 0% |
| €13.539 – €21.992 | 20% |
| €21.992 – €36.458 | 30% |
| €36.458 – €70.365 | 40% |
| €70.365 – €104.859 | 48% |
| €104.859 – €1.000.000 | 50% |
| über €1.000.000 | 55% |

### Umsatzsteuer (USt)

**Kleinunternehmerregelung:**
- Umsatz ≤ €55.000: USt-befreit
- Umsatz €55.000 – €60.500: Toleranzregel (noch befreit, aber nächstes Jahr automatisch pflichtig)
- Umsatz > €60.500: USt-pflichtig

**USt-Sätze:**
- Standard: 20%
- Wohnraumvermietung: 10% (oder Befreiung wählbar)

### SVS-Beiträge

Für Selbständige berechnet Taxja automatisch:

- Pensionsversicherung: 18,5%
- Krankenversicherung: 6,8%
- Unfallversicherung: €12,95/Monat
- Zusatzpension: 1,53%

**Mindestbeitragsgrundlage:** €551,10/Monat
**Höchstbeitragsgrundlage:** €8.085/Monat

SVS-Beiträge sind als Sonderausgaben absetzbar!

### Absetzbeträge

**Pendlerpauschale:**
- 20-40 km: €58-€306/Monat
- Plus Pendlereuro: €6/km/Jahr

**Homeoffice-Pauschale:**
- €300/Jahr (automatisch)

**Kinderabsetzbetrag:**
- €58,40/Monat pro Kind

**Alleinerzieher-Absetzbetrag:**
- €494/Jahr

### Was-wäre-wenn Simulator

Testen Sie Steuerszenarien:

1. Gehen Sie zu "Steuern" → "Simulator"
2. Fügen Sie hypothetische Ausgaben hinzu
3. Sehen Sie sofort die Steuerersparnis
4. Beispiel: "Was spare ich, wenn ich ein neues Notebook kaufe?"

### Pauschalierung vs. Einnahmen-Ausgaben-Rechnung

Für Kleinunternehmer zeigt Taxja beide Varianten:

**Pauschalierung:**
- 6% oder 12% Betriebsausgabenpauschale
- Einfacher, weniger Aufwand
- Keine Belegpflicht

**Einnahmen-Ausgaben-Rechnung:**
- Tatsächliche Ausgaben absetzbar
- Mehr Aufwand, Belegpflicht
- Oft höhere Steuerersparnis

Taxja empfiehlt die günstigere Variante!

## Berichte erstellen

### Steuererklärung generieren

1. Gehen Sie zu "Berichte" → "Neu erstellen"
2. Wählen Sie das Steuerjahr
3. Wählen Sie das Format:
   - **PDF**: Übersichtlicher Bericht
   - **XML**: Für FinanzOnline
   - **CSV**: Für Excel/Steuerberater
4. Wählen Sie die Sprache (Deutsch, Englisch, Chinesisch)
5. Klicken Sie auf "Generieren"

### PDF-Bericht

Der PDF-Bericht enthält:

- Persönliche Daten
- Einnahmen-Übersicht
- Ausgaben-Übersicht
- Steuerberechnung (detailliert)
- Absetzbeträge
- Zusammenfassung

### FinanzOnline XML

1. Generieren Sie den XML-Bericht
2. Laden Sie die Datei herunter
3. Loggen Sie sich bei FinanzOnline ein
4. Laden Sie die XML-Datei hoch

**Wichtig:** Taxja validiert die XML gegen das offizielle FinanzOnline-Schema!

### Prüfungs-Checkliste

Vor der Abgabe prüfen:

1. Gehen Sie zu "Berichte" → "Prüfungs-Checkliste"
2. Taxja zeigt:
   - ✅ Alle Transaktionen belegt
   - ⚠️ 2 Belege fehlen
   - ✅ Alle Absetzbeträge dokumentiert
3. Beheben Sie Warnungen vor der Abgabe

## AI Steuerassistent

### Chat starten

1. Klicken Sie auf das Chat-Symbol (unten rechts)
2. Stellen Sie Ihre Frage auf Deutsch, Englisch oder Chinesisch
3. Der AI-Assistent antwortet sofort

### Beispielfragen

**Allgemeine Fragen:**
- "Kann ich mein Homeoffice absetzen?"
- "Wie hoch ist die Pendlerpauschale?"
- "Was ist die Kleinunternehmerregelung?"

**Dokumenten-Analyse:**
- "Welche Posten auf diesem Kassenbon sind absetzbar?"
- "Ist diese Rechnung korrekt?"

**Optimierung:**
- "Wie kann ich Steuern sparen?"
- "Soll ich die Pauschalierung wählen?"

### Wichtiger Hinweis

Jede AI-Antwort endet mit:

> ⚠️ **Disclaimer:** Diese Antwort dient nur als allgemeine Information und stellt keine Steuerberatung dar. Bei komplexen Fällen konsultieren Sie bitte einen Steuerberater.

## FAQ

### Allgemein

**Q: Ist Taxja ein Ersatz für einen Steuerberater?**
A: Nein. Taxja ist ein Hilfswerkzeug zur Steuerverwaltung. Bei komplexen Fällen empfehlen wir die Konsultation eines Steuerberaters.

**Q: Sind meine Daten sicher?**
A: Ja. Taxja verwendet AES-256 Verschlüsselung für gespeicherte Daten und TLS 1.3 für die Übertragung. Wir sind DSGVO-konform.

**Q: Kann ich Taxja auf dem Smartphone nutzen?**
A: Ja! Taxja ist als Progressive Web App (PWA) verfügbar und funktioniert auf allen Geräten.

### Transaktionen

**Q: Wie importiere ich Transaktionen von meiner Bank?**
A: Exportieren Sie Ihre Kontobewegungen als CSV und importieren Sie sie unter "Transaktionen" → "Importieren".

**Q: Was passiert, wenn ich eine Transaktion falsch kategorisiere?**
A: Kein Problem! Korrigieren Sie einfach die Kategorie. Taxja lernt aus Ihren Korrekturen.

**Q: Werden Duplikate automatisch erkannt?**
A: Ja. Beim Import prüft Taxja auf Duplikate (gleicher Betrag, Datum, ähnliche Beschreibung).

### OCR

**Q: Welche Dokumente kann Taxja erkennen?**
A: Lohnzettel, Kassenbons, Rechnungen, Mietverträge, SVS-Bescheide, Bankbelege.

**Q: Was mache ich, wenn die OCR-Erkennung fehlschlägt?**
A: Sie können die Daten manuell eingeben. Tipps für bessere Erkennung: gute Beleuchtung, flaches Dokument, ausreichende Auflösung.

**Q: Werden die Original-Dokumente gespeichert?**
A: Ja. Alle hochgeladenen Dokumente werden verschlüsselt gespeichert und sind jederzeit abrufbar.

### Steuern

**Q: Wie genau sind die Steuerberechnungen?**
A: Taxja verwendet die offiziellen USP 2026 Tarife. Die Berechnungen wurden gegen den offiziellen USP-Rechner validiert (Abweichung < €0,01).

**Q: Kann ich Steuern aus Vorjahren berechnen?**
A: Ja. Taxja unterstützt mehrere Steuerjahre und Verlustvorträge.

**Q: Was ist der Unterschied zwischen Lohnsteuer und Einkommensteuer?**
A: Lohnsteuer wird vom Arbeitgeber einbehalten. Einkommensteuer ist die Gesamtsteuer auf alle Einkünfte. Mit der Arbeitnehmerveranlagung können Sie zu viel bezahlte Lohnsteuer zurückfordern.

### Berichte

**Q: Kann ich den Bericht direkt an FinanzOnline senden?**
A: Nein. Sie müssen die XML-Datei herunterladen und manuell bei FinanzOnline hochladen. (FinanzOnline hat keine öffentliche API.)

**Q: In welchen Sprachen kann ich Berichte erstellen?**
A: Deutsch, Englisch und Chinesisch.

**Q: Kann ich den Bericht an meinen Steuerberater senden?**
A: Ja. Exportieren Sie als PDF oder CSV und senden Sie die Datei per E-Mail.

### Datenschutz

**Q: Kann ich meine Daten exportieren?**
A: Ja. Unter "Einstellungen" → "Daten exportieren" können Sie alle Ihre Daten als ZIP-Archiv herunterladen (DSGVO-Recht).

**Q: Kann ich mein Konto löschen?**
A: Ja. Unter "Einstellungen" → "Konto löschen" werden alle Ihre Daten permanent gelöscht.

**Q: Wer hat Zugriff auf meine Daten?**
A: Nur Sie. Taxja-Mitarbeiter haben keinen Zugriff auf Ihre Steuerdaten.

## Support

Bei Fragen oder Problemen:

- **E-Mail**: support@taxja.at
- **Telefon**: +43 1 234 5678 (Mo-Fr, 9-17 Uhr)
- **Chat**: Im System verfügbar
- **Dokumentation**: https://docs.taxja.at

## Rechtlicher Hinweis

Taxja ist ein Steuerverwaltungstool und bietet keine Steuerberatung im Sinne des Steuerberatungsgesetzes. Die Berechnungen dienen als Orientierung. Die endgültige Steuerfestsetzung erfolgt durch das Finanzamt. Bei komplexen Steuerfällen empfehlen wir die Konsultation eines zugelassenen Steuerberaters.

---

**Version:** 1.0  
**Stand:** März 2026  
**© 2026 Taxja GmbH**
