#!/usr/bin/env bash
# FusedMathAgent Web 驱动 · 巡检快照（另可改用 runtime/periodic_check.py）
cd "C:/Users/Cyl/Downloads/new math agent" && date "+%H:%M:%S"; curl -s --max-time 8 http://127.0.0.1:8901/api/state > "C:/Users/Cyl/AppData/Local/Temp/s.json" 2>/dev/null; PYTHONIOENCODING=utf-8 python -c "
import json
d=json.load(open('C:/Users/Cyl/AppData/Local/Temp/s.json',encoding='utf-8'))
print('running:',d['running'],'| cur:',d['cur'])
print('stages:',{k:v for k,v in d['stages'].items() if v not in ('idle',)})
print('log最近2:')
[print(' ',l) for l in d['log'][-2:]]
logtxt='\n'.join(d['log'])
hits=[w for w in ['孕妇','染色体','BMI','删失','烟幕','无人机','导弹'] if w in logtxt]
print('跨题残留词:', hits if hits else '无')
"; ls -la reports/VERIFY_REPORT.md 2>/dev/null | awk '{print "verify:",$5,"B",$6,$7,$8}' || echo "(未出)"
