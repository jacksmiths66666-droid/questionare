# -*- coding: utf-8 -*-
import csv, math, sys
import numpy as np
from numpy.linalg import inv, LinAlgError
from collections import Counter

csv_path = r'C:\Users\34611\Desktop\问卷数据清洗\D087_政治社会学_西班牙抗议参与_2019_完整交付\02_官方原始数据\02_PROTEiCA_survey_EN.csv'

rows = []
with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for r in reader:
        rows.append(r)

n = len(rows)
print(f'原始样本: {n}')

# ==================== STEP 1: 跳题违规直接剔除 ====================
skip_bad = set()
for i, r in enumerate(rows):
    if r.get('P12','') == 'No' and r.get('P12Btx','').strip():
        skip_bad.add(i)
    if r.get('P27','') not in ('Yes','') and r.get('P27C','').strip() in ('Man','Woman'):
        skip_bad.add(i)
print(f'跳题违规: {len(skip_bad)}人')
rows_clean = [r for i, r in enumerate(rows) if i not in skip_bad]
print(f'跳题清理后: {len(rows_clean)}人')
print()

# ==================== 映射表 ====================
likert_map = {'Strongly disagree':1, 'Disagree':2, 'Neither agree nor disagree':3, 'Agree':4, 'Strongly agree':5}
freq_map = {'Never':1, 'Less (almost never)':2, '1 or 2 days/weekends':3, '3 or 4 days (quite a lot)':4, 'Everyday or almost everyday (5-7)':5}
DKNA_SET = {'DK','NA'}

def is_dkna(v):
    if not v or not v.strip(): return True
    t = v.strip()
    return t in DKNA_SET or t in ('Can\'t say','No memories','NC')

# ==================== 编码 P11 (翻转P11A) ====================
p11_encoded = []
for r in rows_clean:
    vals = []
    for vi, v in enumerate(['P11A','P11B','P11C','P11D','P11E']):
        raw = r.get(v,'')
        if raw in likert_map:
            val = likert_map[raw]
            if vi == 0: val = 6 - val  # P11A 翻转
            vals.append(val)
        else:
            vals.append(None)
    p11_encoded.append(vals)

# 完整样本
p11_idx_map = {}
p11_data = []
for i, p in enumerate(p11_encoded):
    if all(v is not None for v in p):
        p11_idx_map[len(p11_data)] = i
        p11_data.append(p)

X = np.array(p11_data, dtype=float)
mu = X.mean(axis=0)
cov = np.cov(X, rowvar=False)
cov_reg = cov + np.eye(5) * 1e-8
print(f'P11完整样本: {X.shape[0]}')

# ==================== 马氏距离 ====================
try:
    inv_cov = inv(cov_reg)
    d2 = np.array([(x - mu) @ inv_cov @ (x - mu) for x in X])
except LinAlgError:
    d2 = np.zeros(len(X))

sorted_d2 = sorted(d2)
print('=== 马氏距离(D2) 分位数 ===')
for pct in [50, 75, 90, 95, 97, 99]:
    idx = int(len(sorted_d2) * pct / 100)
    cap = sorted_d2[min(idx, len(sorted_d2)-1)]
    print(f'  P{pct}: D2={cap:.2f}')

print('=== 马氏距离 阈值扫描 ===')
for th in [6, 7, 8, 9, 10, 11, 12, 14, 16, 18, 20, 25]:
    cnt = int((d2 > th).sum())
    print(f'  D2>{th}: {cnt}/{len(d2)} ({cnt/len(d2)*100:.1f}%)')

mah_cut = {}
for th in [8, 9, 10, 11, 12]:
    mah_cut[th] = int((d2 > th).sum())

print()

# ==================== Longstring (P11+P02 共10题) ====================
longstrings = []
long_valid = []
for ri, r in enumerate(rows_clean):
    vals = []
    for vi, v in enumerate(['P11A','P11B','P11C','P11D','P11E']):
        raw = r.get(v,'')
        if raw in likert_map:
            val = likert_map[raw]
            if vi == 0: val = 6 - val
            vals.append(val)
    for v in ['P02A','P02B','P02C','P02D','P02E']:
        raw = r.get(v,'')
        if raw in freq_map:
            vals.append(freq_map[raw])
    if len(vals) < 10: continue
    max_len = 1; cur = 1
    for j in range(1, len(vals)):
        if vals[j] == vals[j-1]: cur += 1
        else: cur = 1
        if cur > max_len: max_len = cur
    longstrings.append(max_len)
    long_valid.append(ri)

print('=== Longstring (10题) 分布 ===')
for k, v in sorted(Counter(longstrings).items()):
    print(f'  {k}: {v}人 ({v/len(longstrings)*100:.1f}%)')

print('=== Longstring 阈值扫描 ===')
ls_cut = {}
for th in [4, 5, 6, 7, 8, 9, 10]:
    cnt = sum(1 for l in longstrings if l >= th)
    ls_cut[th] = cnt
    print(f'  LS>={th}: {cnt}人 ({cnt/len(longstrings)*100:.1f}%)')
print()

# ==================== DK/NA ====================
core_vars = ['P01','P02A','P02B','P02C','P02D','P02E','P03','P04','P05','P06','P07','P07B','P07D1','P07D2','P07D3','P07D4','P07D5','P07D6','P08','P09','P09B','P10B','P11A','P11B','P11C','P11D','P11E','P12','P13','P13B','P13C','P14','P15','P16','P17','P17B','P17C','P18','P19','P19B','P20','P20B','P21A','P21B','P21C','P21D','P22','P23','P24','P25','P27','P27B','P27C','P28','P28B']
dkna_counts = []
for r in rows_clean:
    cnt = 0
    for v in core_vars:
        if is_dkna(r.get(v,'')): cnt += 1
    dkna_counts.append(cnt)

print('=== DK/NA 阈值扫描 ===')
dk_cut = {}
for th in range(4, 16):
    cnt = sum(1 for d in dkna_counts if d >= th)
    dk_cut[th] = cnt
    print(f'  DK/NA>={th}: {cnt}人 ({cnt/len(rows_clean)*100:.1f}%)')
print()

# ==================== 其他辅助指标 ====================
# P11E > P11D
tmp_data = [(p11_idx_map[i], p[4] > p[3]) for i, p in enumerate(p11_data)]
p11_contra = set()
for idx, flag in tmp_data:
    if flag: p11_contra.add(idx)
print(f'P11E>P11D矛盾: {len(p11_contra)}')

# IRV = 0
irv0 = set()
for i, p in enumerate(p11_data):
    if np.std(p) == 0: irv0.add(p11_idx_map[i])
print(f'IRV=0: {len(irv0)}')

# P08+P09
p8p9 = set()
for i, r in enumerate(rows_clean):
    if r.get('P08','') == 'Very necessary' and r.get('P09','') == 'Rather negative':
        p8p9.add(i)
print(f'P08+P09矛盾: {len(p8p9)}')

# P01高+DK高
p1dk = set()
for i, (r, dk) in enumerate(zip(rows_clean, dkna_counts)):
    if r.get('P01','') in ('Very','Quite') and dk >= 8:
        p1dk.add(i)
print(f'高兴趣+DK>=8: {len(p1dk)}')

# P02全一样
p2same = set()
for i, r in enumerate(rows_clean):
    vals = [r.get(v,'') for v in ['P02A','P02B','P02C','P02D','P02E']]
    if all(v in freq_map for v in vals) and len(set(vals)) == 1:
        p2same.add(i)
print(f'P02全一样: {len(p2same)}')

# 抗议忘主题
pf = set()
for i, r in enumerate(rows_clean):
    p = r.get('P16','')
    b = r.get('P16B_1','')
    if p in ('Yes, in two or more','Yes, once') and (b == 'DK' or not b.strip()):
        pf.add(i)
print(f'抗议忘主题: {len(pf)}')

# 大学+无能力
uni = set()
for i, r in enumerate(rows_clean):
    if 'University' in r.get('P25','') and r.get('P10B','') == 'No capable':
        uni.add(i)
print(f'大学+无能力: {len(uni)}')

# P01=Very + P02全<=2
vp2 = set()
for i, r in enumerate(rows_clean):
    if r.get('P01','') != 'Very': continue
    max_freq = 0
    for v in ['P02A','P02B','P02C','P02D','P02E']:
        val = freq_map.get(r.get(v,''), 0)
        if val > max_freq: max_freq = val
    if max_freq <= 2:
        vp2.add(i)
print(f'Very+P02全<=2: {len(vp2)}')

print()
print('=' * 60)
print('指标汇总 (可调阈值:)')
print(f'  - 马氏距离: 测试临界值 {list(mah_cut.keys())} -> 筛选人数 {list(mah_cut.values())}')
print(f'  - Longstring: 测试临界值 {list(ls_cut.keys())} -> 筛选人数 {list(ls_cut.values())}')
print(f'  - DK/NA: 测试临界值 {list(dk_cut.keys())[:5]}... -> 筛选人数 {list(dk_cut.values())[:5]}...')
