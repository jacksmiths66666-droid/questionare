"""翻译质量复查"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import pandas as pd

q = pd.read_csv("outputs/screening_v3/tisp_v3_review_queue.csv")

probes = [
    "La medecine beneficie le plus de la science",
    "Los cientificos y bueno el ser humano ya",
    "La scienza e gli scienziati sono al servizio",
    "en osaa kertoa",
    "dsfbsdh dsgrewt fdhdsrztw eqwet er hngdh",
    "they can make solution that can prevent diseases",
    "encok insanlar faydalanıyor",
    "tous",
    "toll",
]

for p in probes:
    mask = q["BENEFIT_OPEN"].astype(str).str.contains(p[:20], na=False)
    if mask.any():
        r = q[mask].iloc[0]
        src = str(r["BENEFIT_OPEN"])[:80]
        tgt = str(r["BENEFIT_OPEN_ZH"])[:80]
        print(f"原文: {src}")
        print(f"翻译: {tgt}")
        print()
    else:
        # try TRUST_OPEN
        mask2 = q["TRUST_OPEN"].astype(str).str.contains(p[:20], na=False)
        if mask2.any():
            r = q[mask2].iloc[0]
            src = str(r["TRUST_OPEN"])[:80]
            tgt = str(r["TRUST_OPEN_ZH"])[:80]
            print(f"原文: {src}")
            print(f"翻译: {tgt}")
            print()
