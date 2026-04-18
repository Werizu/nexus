# NEXUS Alexa Skill — Setup-Anleitung

## Voraussetzungen
- Amazon Developer Account (kostenlos)
- AWS Account (Lambda Free Tier reicht)
- Tailscale Funnel auf dem Pi aktiviert

## Schritt 1: Tailscale Funnel auf dem Pi

```bash
# Auf dem Pi (192.168.178.202):
sudo tailscale funnel --bg 8000
```

Das gibt dir eine URL wie: `https://server2.tail12345.ts.net`
Diese URL ist deine NEXUS_API_URL.

## Schritt 2: AWS Lambda erstellen

1. Gehe zu AWS Lambda Console → **Funktion erstellen**
2. Name: `nexus-alexa-skill`
3. Runtime: **Python 3.12**
4. Architektur: **arm64**
5. Code: Kopiere `lambda_function.py` rein
6. Umgebungsvariablen:
   - `NEXUS_API_URL` = deine Tailscale Funnel URL (z.B. `https://server2.tail12345.ts.net`)
7. Timeout: **10 Sekunden** (unter Konfiguration → Allgemein)
8. Trigger hinzufügen: **Alexa Skills Kit**

## Schritt 3: Alexa Skill erstellen

1. Gehe zu https://developer.amazon.com/alexa/console/ask
2. **Skill erstellen** → Name: "NEXUS" → Sprache: **Deutsch**
3. Modell: **Custom** → Hosting: **Eigener Endpunkt**
4. Endpoint: Die **ARN** deiner Lambda-Funktion
5. Im **JSON Editor**: Inhalt von `interaction_model.json` einfügen
6. **Build Model** klicken
7. **Test** Tab → Skill aktivieren

## Schritt 4: Testen

Im Alexa Test-Simulator oder auf deinem Echo:
- "Alexa, öffne NEXUS"
- "Alexa, sag NEXUS Programmier Modus"
- "Alexa, frag NEXUS wie ist der Status"
- "Alexa, sag NEXUS alles aus"
- "Alexa, sag NEXUS PC hochfahren"

## Sprachbefehle

| Befehl | Aktion |
|--------|--------|
| "Programmier Modus" | Startet dev_mode Szene |
| "Guten Morgen" | Morgen-Routine |
| "Filmabend" | Film-Abend Szene |
| "Gute Nacht" | Schlaf-Modus |
| "PC hochfahren" | Wake-on-LAN |
| "Alles aus" | Alles ausschalten |
| "Status" | System-Status vorlesen |
| "Stromverbrauch" | Energie-Daten vorlesen |
| "[Gerät] an/aus" | Einzelnes Gerät steuern |
