# Korjaa

**A hands-free voice assistant for repairs and real-world tasks.** Describe the problem, show it a photo, or start a live camera session. Korjaa finds instructions, turns them into short spoken steps, and waits for you.

Built at the Hacktoberfest Hack Day Mikkeli, hosted by Hacklab Mikkeli ry.

## What it does

- **Guided steps:** one instruction at a time, with how-to notes and example images.
- **Photos with your prompt:** attach photos, say what you need, then send.
- **Live camera:** a video-call style mode that checks a frame every few seconds.
- **Hands-free:** turn on the switch and say "Hey Buddy".
- **Did that fix it?** Stop early when an easy fix works.
- **Saved guides:** common jobs load instantly from `procedures/`, even on bad Wi-Fi.
- **Ask anything mid-task:** "where is the filter cap?" is answered from the guide without moving your step.
- **Timers and status:** say "set a timer for ten minutes" or "where are we?"
- **Ignores room chatter:** during a task, only commands, questions, buying requests and hazard words count.
- **Finding parts:** instant eBay, Verkkokauppa.com, Amazon and Google Shopping links, plus comparison results on request.

Korjaa never places an order.

## How it works

| Job | Handled by |
|---|---|
| Web and image search | Tavily (optional) |
| Reading photos and writing steps | Gemma 4 through the Gemini API |
| Spoken guidance | ElevenLabs |
| Progress, safety rules and refusals | Application code |

Korjaa uses `gemma-4-26b-a4b-it`, and falls back to `gemma-4-31b-it` if a request fails. If a full guide still fails, it gives a shorter guide from general knowledge.

Model terms: <add the official Gemma terms link here>

## Safety

- Dangerous jobs are refused in code, including microwaves, gas work, mains wiring, damaged lithium batteries, brakes and airbags.
- Phone screen and battery jobs need the phrase "I understand the risk".
- Say "stop", "smoke", "fire", "burning", "spark" or "shock", or press STOP.
- Live mode stops if it sees a likely hazard. It can miss things, so use your own judgement.

## Run it

```bash
pip install -r requirements.txt
cp .env.example .env
python check_keys.py
uvicorn main:app
```

Add your keys to `.env`. A phone needs HTTPS for the camera and microphone:

```bash
cloudflared tunnel --url http://localhost:8000
```

## Limitations

- Requests, photos and voice text go to external services.
- Free plans have usage limits, and hosted models can be slow.
- Web instructions, shop results and AI answers can be wrong.
- "Hey Buddy" needs the page open and works best in Chrome.

## License

MIT. See [LICENSE](LICENSE). Voice by ElevenLabs.
