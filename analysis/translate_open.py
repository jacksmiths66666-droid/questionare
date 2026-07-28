"""翻译开放题文本，断点续传 + 批量翻译"""
import json, time
from pathlib import Path
import pandas as pd
from deep_translator import GoogleTranslator

QUEUE = Path("outputs/screening_v3/tisp_v3_review_queue.csv")
CACHE = Path("outputs/screening_v3/translation_cache.json")
BATCH = 5   # 每批数量
SLEEP = 3   # 批间隔（秒）

# 加载缓存
cache: dict[str, str] = {}
if CACHE.exists():
    cache = json.loads(CACHE.read_text(encoding="utf-8"))
    print(f"已加载缓存 {len(cache)} 条")

q = pd.read_csv(QUEUE)
t = GoogleTranslator(source="auto", target="zh-CN")

for col in ["BENEFIT_OPEN", "TRUST_OPEN"]:
    out_col = col + "_ZH"
    texts = sorted(set(str(t) for t in q[col].dropna().unique() if str(t).strip()))

    # 过滤出未缓存的
    todo = [t for t in texts if t not in cache]
    print(f"[{col}] 共 {len(texts)} 唯一，待翻译 {len(todo)}")

    for i in range(0, len(todo), BATCH):
        batch = todo[i:i + BATCH]
        try:
            results = t.translate_batch(batch)
            for src, dst in zip(batch, results):
                cache[src] = dst
        except Exception as e:
            print(f"  BATCH FAIL ({i}-{i+BATCH}): {e}")
            for src in batch:
                cache[src] = f"[TRANSLATION_ERROR]"
            time.sleep(5)

        if (i // BATCH + 1) % 5 == 0:
            print(f"  进度 {min(i+BATCH, len(todo))}/{len(todo)}，缓存 {len(cache)}")
            CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

        time.sleep(SLEEP)

    # 回填
    q[out_col] = q[col].astype(str).map(lambda x: cache.get(x, "") if pd.notna(x) and str(x).strip() else "")
    print(f"[{col}] 完成")

CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
q.to_csv(QUEUE, index=False, encoding="utf-8-sig")
print("ALL DONE")
