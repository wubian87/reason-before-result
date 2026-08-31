"""Generate English narration WAV files with Gemini TTS on existing Vertex ADC."""

import base64
import json
import os
import subprocess
import urllib.request
import wave


os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "gen-lang-client-0451202674")
项目 = os.environ["GOOGLE_CLOUD_PROJECT"]
区域 = "global"
令牌 = subprocess.check_output(
    ["/home/xin/google-cloud-sdk/bin/gcloud", "auth", "application-default", "print-access-token"],
    text=True,
).strip()

段 = {
    "01-open": (
        "This is a paper account. These are options. Every order has a maximum loss before it exists. "
        "When the agent cannot prove that number, it stops."
    ),
    "02-what": (
        "Reason Before Result is an autonomous Alpaca paper-options agent. The unusual part is not the strategy. "
        "The explanation is written before the gate and before the order, so a later outcome cannot invent its reason."
    ),
    "03-mcp": (
        "One uncut run. Clock, account, positions, price, and option chain all arrive through MCP. "
        "Only tool names and timing appear in the recording; credentials, parameters, and response bodies never do."
    ),
    "04-judgment": (
        "The judgment is appended here, before the gate runs: every leg, maximum gain and loss, break-evens, "
        "what would prove it wrong, and the intended exit."
    ),
    "05-gate": (
        "Every rule leaves a receipt. A naked option, a missing quote, an unknown structure, or an unreadable value "
        "resolves to stop, never approval. A stop is a normal ledger event."
    ),
    "06-order": (
        "Only after release may the MCP tool place option order appear. The Alpaca receipt is appended to the same ledger. "
        "There is no direct H T T P execution bypass."
    ),
    "07-verify": (
        "The repository contains the complete MCP path, deterministic tests, and a read-only public demo. "
        "Judges receive the dedicated paper account I D privately, so Alpaca can verify activity and P and L directly."
    ),
    "08-close": (
        "A winning trade can still have a bad reason. A stopped trade can prove the agent worked. "
        "Reason Before Result makes both visible. Paper trading only. No real capital."
    ),
}

网址 = (
    f"https://aiplatform.googleapis.com/v1/projects/{项目}/locations/{区域}/publishers/google/"
    "models/gemini-2.5-flash-preview-tts:generateContent"
)

成功 = 0
for 名, 文 in 段.items():
    载荷 = {
        "contents": [{"role": "user", "parts": [{"text": 文}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Charon"}}},
        },
    }
    请求 = urllib.request.Request(
        网址,
        data=json.dumps(载荷).encode(),
        headers={"Authorization": f"Bearer {令牌}", "Content-Type": "application/json"},
    )
    try:
        返回 = json.load(urllib.request.urlopen(请求, timeout=180))
        音频 = base64.b64decode(返回["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
        with wave.open(f"旁白-{名}.wav", "wb") as 文件:
            文件.setnchannels(1)
            文件.setsampwidth(2)
            文件.setframerate(24000)
            文件.writeframes(音频)
        print(f"✅ {名}  {len(音频) / 48000:.1f}s")
        成功 += 1
    except Exception as 错:
        原文 = 错.read().decode()[:240] if hasattr(错, "read") else str(错)[:240]
        print(f"❌ {名}: {原文}")

print(f"成功 {成功}/{len(段)}")
