# Emergency Safety Helper — AI + Rule-Based Guidance

A calm, simple tool that provides **non-medical, step-by-step safety guidance** when users describe stressful situations (e.g., *“I smell gas”*, *“Basement flooding”*).

It uses a **hybrid approach**:

* **Rule-based hazard detection** → instant & deterministic
* **Gemini AI classification** → when rules are unsure
* **Optional PDF “Book Guidance”** via Gemini Files API
* **Fallback guidance** when no PDF or match is available

Built as a full-stack + AI portfolio project by **Nikhar Bhavsar**.

---

## Live Demo

Frontend (Netlify):
https://emergencyai.netlify.app

Backend (Render):
https://emergency-ai-backend.onrender.com
---

## Tech Stack

### **Frontend**

* React (CRA)
* Custom dark theme UI
* Markdown rendering with `marked`
* Google Analytics 4
* Ko-fi donation card

### **Backend**

* Python + Flask
* Rule-based classification
* Gemini 2.0 Flash for hazard classification
* Gemini Files API for PDF-based guidance
* CORS enabled

### **DevOps**

* GitHub Actions CI/CD (backend + frontend)
* Scheduled workflow to refresh PDF uploads every 48 hours
* Deployments:

  * **Backend:** Render
  * **Frontend:** Netlify

---

## How It Works

1. User enters a short situation description.
2. Backend checks for obvious medical emergencies.
3. Rule-based classifier tries to map the situation.
4. If unknown → Gemini AI classifies the hazard.
5. Hazard maps to official guides.
6. Normal mode → short, calm steps.
7. “Book Guidance” (PDF Mode) → Gemini reads emergency PDFs using Files API for more detailed advice.
8. If no match is found → graceful fallback with general guidance.

---

## Book-Based Guidance (Files API Mode)

The backend uploads real emergency PDFs (flood, wildfire, earthquake guides) to Gemini’s **Files API**.

When a user selects “Book Guidance”:

* The relevant PDF is attached to the request.
* Gemini reads the PDF and produces more detailed, context-based steps.

If PDF is missing:

> “No relevant guide found — using general safety steps.”

---

## Why This Will Evolve Into a RAG System (Future Improvement)

The Files API is good for small projects, but has limitations:

### 1. Token usage is unpredictable

Large PDFs → expensive and inconsistent output.

### 2. Not guaranteed to reference the right part of the PDF

It’s powerful, but not fully controllable.

### 3. Hard to scale

Each upload returns a new file ID → syncing required.

### **RAG Upgrade Planned**

To make it production-level, I plan to replace Files API with a **RAG pipeline**:

* Extract PDF text
* Chunk it
* Create vector embeddings
* Store in vector DB
* Retrieve relevant chunks
* Pass chunks to Gemini for final reasoning

RAG gives:

* Full control
* Lower cost
* Better accuracy
* Scales cleanly with many guides

---

## Project Structure

```
backend/
  app.py
  gemini_client.py
  guides_map.json
  situations_seed.json
  upload_guides.py
  requirements.txt

frontend/
  src/
    App.js
    ga4.js
    index.css
  package.json

.github/workflows/
  ci.yml
  upload-pdfs.yml
```

---

## API Endpoints

### Health Check
Simple uptime probe.

```
GET /health
Response: { "status": "ok" }
```

### Normal Guidance (`/api/help`)
Classifies a user-provided situation using rule-based detection; falls back to Gemini if unknown.

Request:
```
POST /api/help
Content-Type: application/json
```
Body:
```json
{ "situationText": "My basement is flooding" }
```
Sample Response:
```json
{
  "hazard": "flood",
  "hazardSource": "rules",
  "guidesUsed": ["flood_preparedness", "fema_are_you_ready"],
  "canDeepDive": true,
  "guidance": "Stay calm. If water is rising, move to higher ground...",
  "mode": "normal"
}
```
Medical trigger case returns a special response with `hazard` = `medical_emergency` and a prompt to call emergency services (no AI invoked).

### Deep Guidance (`/api/help/deep`)
Enhanced version. Uses rule-based first, then Gemini if unknown, and attempts PDF-backed guidance when guides exist.

Request:
```
POST /api/help/deep
Content-Type: application/json
```
Body:
```json
{ "situationText": "Wildfire smoke is getting thicker" }
```
Sample Response:
```json
{
  "hazard": "wildfire",
  "hazardSource": "rules",
  "guidesUsed": ["wildfire_preparedness", "wildfire_toolkit"],
  "canDeepDive": true,
  "guidance": "Close windows, shut off HVAC bringing outside air...",
  "mode": "deep"
}
```
If no guide PDFs match, it gracefully falls back to normal AI guidance.

### Direct Deep PDF Guidance (`/api/deep-guidance`)
Explicit endpoint when the client already knows the hazard + guide key and wants a PDF-informed answer.

Request:
```
POST /api/deep-guidance
Content-Type: application/json
```
Body:
```json
{
  "situationText": "River water entering ground floor",
  "hazard": "flood",
  "guideKey": "flood_preparedness"
}
```
Sample Response:
```json
{
  "hazard": "flood",
  "guideKey": "flood_preparedness",
  "deepGuidance": "Move valuables above potential water line. Disconnect power if safe..."
}
```
Notes:
- `hazardSource` is not returned here (client is asserting context).
- Fails with `400` if `situationText` or `guideKey` missing.
- Falls back to general guidance if PDF unavailable internally.

---

## Running Locally

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export GEMINI_API_KEY="your-key"
python app.py
```

### Frontend

```bash
cd frontend
npm install
npm start
```

---

## Support

Ko-fi link:
[https://ko-fi.com/nikbhavsar](https://ko-fi.com/nikbhavsar)

> Completely optional — your support helps reduce 503 errors, speed up slow-thinking AI, and increase happiness by at least 14%.

---

## Future Improvements

* Replace Files API with a proper **RAG** system
* Multi-language support
* Offline PWA mode
* Voice input + text-to-speech
* More hazard categories
* Geolocation-based emergency numbers

---

## Summary

This project demonstrates:

* Full-stack engineering
* AI integration using Gemini
* Hybrid rule-based + AI reasoning
* PDF-based contextual AI
* CI/CD automation
* Cloud deployment

