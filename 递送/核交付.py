#!/usr/bin/env python3
"""黑客松递送的本地核验器。

默认为「准备」模式：公开链接、正式成片和园主问 4 可以显示为待办。
交付前跑 ``python 递送/核交付.py --final``，待办也会按失败处理。
它不读 .env、账户号、账本内容或密钥。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import struct
import subprocess
import sys
import time
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


@dataclass
class Result:
    state: str
    name: str
    detail: str


RESULTS: list[Result] = []


def add(state: str, name: str, detail: str) -> None:
    RESULTS.append(Result(state, name, detail))


def run(*args: str, timeout: int = 90) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
    )


def check_command(name: str, args: list[str], proof: str | None = None) -> None:
    proc = run(*args)
    if proc.returncode == 0 and (proof is None or proof in proc.stdout):
        add("PASS", name, proof or "退出码 0")
    else:
        tail = " | ".join(proc.stdout.strip().splitlines()[-3:])
        add("FAIL", name, f"退出码 {proc.returncode}；{tail or '无输出'}")


def png_size(path: Path) -> tuple[int, int]:
    with path.open("rb") as fh:
        header = fh.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("不是 PNG")
    return struct.unpack(">II", header[16:24])


def pdf_pages(path: Path) -> int:
    proc = run("pdfinfo", str(path))
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout.strip())
    match = re.search(r"^Pages:\s+(\d+)$", proc.stdout, re.MULTILINE)
    if not match:
        raise RuntimeError("pdfinfo 没有 Pages")
    return int(match.group(1))


def pptx_slides(path: Path) -> int:
    with zipfile.ZipFile(path) as archive:
        return len([
            name for name in archive.namelist()
            if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)
        ])


def media_probe(path: Path) -> dict:
    proc = run(
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration:stream=codec_type,codec_name",
        "-of", "json", str(path),
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stdout.strip())
    return json.loads(proc.stdout)


def check_streamlit() -> None:
    port = "18501"
    env = os.environ.copy()
    env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
    proc = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run", "app.py",
            "--server.headless=true", f"--server.port={port}",
            "--server.address=127.0.0.1",
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        detail = ""
        for _ in range(30):
            if proc.poll() is not None:
                detail = f"进程提前退出 {proc.returncode}"
                break
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/_stcore/health", timeout=0.5
                ) as response:
                    body = response.read().decode("utf-8", errors="replace").strip()
                    if response.status == 200 and body == "ok":
                        add("PASS", "托管 Demo", "Streamlit 健康端点返回 ok")
                        return
                    detail = f"HTTP {response.status}: {body[:80]}"
            except Exception as exc:
                detail = str(exc)
            time.sleep(0.25)
        add("FAIL", "托管 Demo", detail or "健康端点超时")
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)


def check_files() -> None:
    required = [
        "README.md", "LICENSE", "requirements.txt", "app.py",
        "递送/one-pager.md", "递送/one-pager.pdf",
        "递送/cover.png", "递送/slides/reason-before-result.pptx",
        "递送/slides/reason-before-result.pdf", "递送/submission.md",
        "递送/social-drafts.md", "递送/video-script.md",
    ]
    missing = [rel for rel in required if not (ROOT / rel).is_file()]
    add("FAIL" if missing else "PASS", "必需文件", ", ".join(missing) if missing else f"{len(required)} 件齐")


def check_repository_hygiene() -> None:
    tracked = set(run("git", "ls-files").stdout.splitlines())
    forbidden = [
        name for name in tracked
        if name == ".env" or name.startswith("账/") or name.startswith("日志/")
        or name.endswith(".wav") or name.endswith(".mp4")
    ]
    add("FAIL" if forbidden else "PASS", "公开仓边界", ", ".join(forbidden) if forbidden else "无密钥、账/日志、旁白或视频")

    ignored = []
    for rel in (".env", "账", "日志"):
        if run("git", "check-ignore", "-q", rel).returncode == 0:
            ignored.append(rel)
    add("PASS" if len(ignored) == 3 else "FAIL", "运行时隔离", f"已忽略：{', '.join(ignored) or '无'}")


def check_copy(final: bool) -> None:
    text = (ROOT / "递送/submission.md").read_text(encoding="utf-8")
    match = re.search(r"## Long description\s+(.*?)(?=\n## )", text, re.S)
    words = re.findall(r"\b[\w'-]+\b", match.group(1) if match else "")
    add("PASS" if len(words) >= 100 else "FAIL", "长描述", f"{len(words)} 词（要求 >= 100）")

    pending = text.count("[PENDING]")
    if pending == 0:
        add("PASS", "公开链接", "GitHub、Demo、视频已填")
    else:
        add("FAIL" if final else "PENDING", "公开链接", f"还有 {pending} 个 [PENDING]")


def check_artifacts(final: bool) -> None:
    try:
        size = png_size(ROOT / "递送/cover.png")
        is_16_9 = size[0] * 9 == size[1] * 16
        is_large_enough = size[0] >= 1280 and size[1] >= 720
        add("PASS" if is_16_9 and is_large_enough else "FAIL", "封面图", f"{size[0]}x{size[1]}；16:9")
    except Exception as exc:
        add("FAIL", "封面图", str(exc))

    for rel, expected, name in (
        ("递送/one-pager.pdf", 1, "一页纸 PDF"),
        ("递送/slides/reason-before-result.pdf", 5, "幻灯片 PDF"),
    ):
        try:
            count = pdf_pages(ROOT / rel)
            add("PASS" if count == expected else "FAIL", name, f"{count} 页（预期 {expected}）")
        except Exception as exc:
            add("FAIL", name, str(exc))

    try:
        count = pptx_slides(ROOT / "递送/slides/reason-before-result.pptx")
        add("PASS" if count == 5 else "FAIL", "PPTX", f"{count} 张（预期 5）")
    except Exception as exc:
        add("FAIL", "PPTX", str(exc))

    video = ROOT / "递送/video/reason-before-result.mp4"
    if not video.is_file():
        add("FAIL" if final else "PENDING", "正式成片", "等待开盘后真实 paper 证据")
        return
    try:
        data = media_probe(video)
        duration = float(data["format"]["duration"])
        codecs = {item.get("codec_name") for item in data.get("streams", [])}
        ok = duration <= 300 and {"h264", "aac"}.issubset(codecs)
        add("PASS" if ok else "FAIL", "正式成片", f"{duration:.1f}s；编码 {', '.join(sorted(codecs))}")
    except Exception as exc:
        add("FAIL", "正式成片", str(exc))


def check_question4(final: bool) -> None:
    evidence = ROOT / "递送/question4-result.md"
    if not evidence.is_file():
        add(
            "FAIL" if final else "PENDING",
            "问 4",
            "园主让不懂的人看成片前 15 秒；结果尚未回来，AI 不代做",
        )
        return
    text = evidence.read_text(encoding="utf-8")
    required = (
        "Paper/simulated: yes",
        "Options: yes",
        "Stops after loss: yes",
        "Observer quote:",
    )
    missing = [item for item in required if item not in text]
    quote = re.search(r"Observer quote:\s*(\S.{8,})", text)
    ok = not missing and quote is not None
    add(
        "PASS" if ok else "FAIL",
        "问 4",
        "三格复述与原话已落纸" if ok else f"缺：{', '.join(missing) or '完整原话'}",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--final", action="store_true", help="公开提交前严格模式")
    args = parser.parse_args()

    check_files()
    tracked_python = [
        name for name in run("git", "-c", "core.quotepath=false", "ls-files", "*.py").stdout.splitlines()
        if name
    ]
    check_command("代码编译", [sys.executable, "-m", "py_compile", *tracked_python])
    check_command("七条风控自检", [sys.executable, "闸自检.py"], "10 个相符，0 个不符")
    check_command("账本/MCP 手自检", [sys.executable, "手自检.py"], "✅ 写 6 条、读回 6 条")
    check_command("录制链脚本", ["bash", "-n", "录制/录一条.sh", "录制/合成.sh"])
    check_streamlit()
    check_repository_hygiene()
    check_copy(args.final)
    check_artifacts(args.final)
    check_question4(args.final)

    labels = {"PASS": "✅", "PENDING": "⏳", "FAIL": "❌"}
    for result in RESULTS:
        print(f"{labels[result.state]} {result.state:<7} {result.name}：{result.detail}")
    counts = {state: sum(item.state == state for item in RESULTS) for state in labels}
    print(f"\n总账：{counts['PASS']} 过｜{counts['PENDING']} 待｜{counts['FAIL']} 败")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
