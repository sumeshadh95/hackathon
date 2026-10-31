import asyncio
import json
import os

import httpx

RETRY_STATUSES = {429, 500, 503}


class Gemma:
    async def generate(self, prompt: str, images: str | list[str] | None = None, json_mode: bool = False,
                       max_tokens: int = 3500, timeout: int = 75) -> str:
        parts = [{"text": prompt}]
        for image in [images] if isinstance(images, str) else images or []:
            parts.append({"inline_data": {"mime_type": "image/jpeg", "data": image}})
        body = {"contents": [{"role": "user", "parts": parts}]}
        if json_mode:
            # JSON mode skips written reasoning, which is several times faster.
            body["generationConfig"] = {"responseMimeType": "application/json", "maxOutputTokens": max_tokens}
        primary = os.getenv("GEMMA_MODEL", "gemma-4-26b-a4b-it")
        fallback = os.getenv("GEMMA_FALLBACK_MODEL", "gemma-4-31b-it")
        # The hosted model sometimes stalls or returns 500, so a slow attempt moves on quickly.
        attempts = [(primary, 1), (fallback, 0)]
        async with httpx.AsyncClient(timeout=timeout) as client:
            for model, delay in attempts:
                try:
                    response = await client.post(
                        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                        headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
                        json=body,
                    )
                except httpx.TransportError as error:
                    if not delay:
                        raise
                    print(f"{model} failed with {type(error).__name__}, trying again")
                    await asyncio.sleep(delay)
                    continue
                if response.status_code not in RETRY_STATUSES or not delay:
                    break
                print(f"{model} returned {response.status_code}, trying again")
                await asyncio.sleep(delay)
        response.raise_for_status()
        content = response.json()["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in content if not p.get("thought"))


def parse_json(text: str) -> dict:
    # Gemma can write reasoning before its answer, so the last JSON object is the reply.
    decoder, position, found = json.JSONDecoder(), 0, {}
    while (start := text.find("{", position)) != -1:
        try:
            value, position = decoder.raw_decode(text, start)
            found = value if isinstance(value, dict) else found
        except json.JSONDecodeError:
            position = start + 1
    return found


async def ask_json(model, prompt: str, images: str | list[str] | None = None, **options) -> dict:
    try:
        return parse_json(await model.generate(prompt, images, json_mode=True, **options))
    except httpx.HTTPStatusError as error:
        print(f"Gemma request failed: HTTP {error.response.status_code}")
        return {}
    except (httpx.HTTPError, KeyError, IndexError) as error:
        print(f"Gemma request failed: {type(error).__name__}")
        return {}