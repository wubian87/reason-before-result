"""从账本里冻一份脱敏证据快照进 递送/证据.json。

只抄白名单字段。账户号、密钥、参与者资料一律不经过这里。
"""
import json, glob, re, sys

编号 = "J-2026-08-31-007"
账 = []
for f in sorted(glob.glob("账/*.jsonl")):
    for line in open(f):
        line = line.strip()
        if line:
            账.append(json.loads(line))

def 取(类, 编=None, 幂等=None):
    for d in 账:
        if d["类"] != 类:
            continue
        if 编 and d.get("编号") != 编:
            continue
        if 幂等 and (d["正文"] or {}).get("幂等键") != 幂等:
            continue
        return d
    return None

判断 = 取("判断", 编号)
闸 = 取("闸", 编号)
回执 = 取("回执", 幂等=编号)
assert 判断 and 闸 and 回执, (bool(判断), bool(闸), bool(回执))

摘 = 回执["正文"]["摘要"]
腿白名单 = ("symbol", "side", "position_intent", "qty", "status", "asset_class")

证据 = {
    "冻结于": "2026-09-02",
    "说明": "从只增不改的本地账本里冻出的一笔真实模拟盘期权单。"
            "账户号、密钥不在此文件——评委在官方表单里单独拿到账户号，自己去 Alpaca 拉。",
    "这一笔": {
        "编号": 编号,
        "落纸判断时刻": 判断["时刻"],
        "过闸时刻": 闸["时刻"],
        "回执时刻": 回执["时刻"],
        "判断书": 判断["正文"],
        "闸": {
            "放行": 闸["正文"]["放行"],
            "一句话": 闸["正文"]["结果"]["一句话"],
            "逐条": 闸["正文"]["结果"]["逐条"],
            "提案": 闸["正文"]["提案"],
        },
        "券商回执": {
            "order_id": 摘["id"],
            "client_order_id": 摘["client_order_id"],
            "submitted_at": 摘["submitted_at"],
            "status": 摘["status"],
            "order_class": 摘["order_class"],
            "order_type": 摘["order_type"],
            "limit_price": 摘["limit_price"],
            "qty": 摘["qty"],
            "time_in_force": 摘["time_in_force"],
            "legs": [{k: 腿.get(k) for k in 腿白名单} for 腿 in (摘.get("legs") or [])],
        },
    },
    "账上留过的拦": [],
}

拦过的 = {}
for d in 账:
    if d["类"] != "闸" or d["正文"].get("放行") is True:
        continue
    正 = d["正文"]
    句 = (正.get("结果") or {}).get("一句话") or 正.get("一句话")
    拦过的.setdefault(句, d["编号"])          # 同一条理由只留头一次
证据["账上留过的拦"] = [{"编号": 编, "一句话": 句} for 句, 编 in 拦过的.items()]

文本 = json.dumps(证据, ensure_ascii=False, indent=2)

# 脱敏兜底：账户号、密钥形状一律不许出现
坏 = []
for 模式, 名 in [(r"PK[A-Z0-9]{16,}", "Alpaca key id"),
                (r"[A-Za-z0-9/+]{40,}", "疑似密钥"),
                (r"\b\d{3}-?\d{2}-?\d{4}\b", "疑似身份号")]:
    for m in re.findall(模式, 文本):
        坏.append((名, m))
# 已知的 uuid 是 order id / asset id，白名单放行
坏 = [b for b in 坏 if not re.fullmatch(r"[0-9a-f-]{36}", b[1])]
if 坏:
    print("⛔ 脱敏没过，停：", 坏, file=sys.stderr)
    sys.exit(1)

open("递送/证据.json", "w").write(文本 + "\n")
print(f"写好 递送/证据.json，{len(文本)} 字符")
print("拦的条数：", len(证据["账上留过的拦"]))
print("order id：", 证据["这一笔"]["券商回执"]["order_id"])
