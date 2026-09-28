"""Publish traceable opening and wall inputs for the section-1 review."""
import json,csv
from pathlib import Path
H=Path(__file__).resolve().parent;ROOT=H.parent.parent
D=json.loads((H/'geometry.json').read_text())
CAL=json.loads((ROOT/'verification/stage-1/calibration.json').read_text())['1']
with (ROOT/'verification/stage-1/measurements.csv').open(encoding='utf-8-sig') as f:M={r['id']:r for r in csv.DictReader(f) if r['section']=='1'}
rows=[]
for oid,o in D['openings'].items():
    wall=next(w for w in D['walls']+D['upper_context']['walls'] if oid in w.get('openings',[]))
    width=float(M[oid]['raw_mm']) if oid in M else (o['range_png'][1]-o['range_png'][0])*CAL['mm_per_png_pixel_y']
    rows.append({'id':oid,'description':M[oid]['description'] if oid in M else o['description'],'wall':wall['id'],'width_mm':width,'base_m':o['base'],'height_m':o['height'],'kind':o['kind'],'leaf_count':o['leaf_count'],'hinge':o.get('hinge'),'swing':o.get('swing'),'open_angle_degrees':o.get('open_angle_degrees'),'source_pages':o['source_pages'],'status':o['status']})
(H/'source-register.json').write_text(json.dumps({'section':1,'source_pdf':'sources/ep-petropavlovsk.pdf','plan_priority':'Approved PNG for first-floor XY; EP for levels and upper-floor context','openings':rows,'walls':D['walls'],'upper_walls':D['upper_context']['walls'],'levels':D['levels_m'],'alignment':D['upper_context']['alignment']},ensure_ascii=False,indent=2)+'\n')
lines=['# Ведомость геометрии секции 1','', 'Положение и ширина исходных проёмов сохранены по утверждённому PNG. Неподписанные высоты остаются условными. Идентификаторы S1-14…S1-33 сохранены; S1-U2-W01 обозначает дополнительный верхний фрагмент.','', '| ID | Назначение | Стена | Проём, мм | Порог, м | Высота, м | Полотен | Петля / сторона | Открывание | ЭП, стр. | Статус |','|---|---|---|---:|---:|---:|---:|---|---|---|---|']
for r in rows:
    lines.append(f"| {r['id']} | {r['description']} | {r['wall']} | {r['width_mm']:.1f} | {r['base_m']:+.3f} | {r['height_m']:.3f} | {r['leaf_count']} | {r['hinge'] or '—'} / {r['swing'] or '—'} | {str(r['open_angle_degrees'])+'°' if r['open_angle_degrees'] else '—'} | {', '.join(map(str,r['source_pages']))} | {r['status']} |")
lines+=['','Петли start/end относятся к порядку концов проёма в исходных координатах; double — две створки, sliding — раздвижное заполнение лифта. Сторона открывания соответствует дугам PNG. Число полотен окна равно 0: детализация оконных створок не назначалась.','', 'Все прямоугольники стен и параметры уровней доступны в [машиночитаемой ведомости](source-register.json). Верхний фрагмент совмещён по наружной границе лестницы и граням шахты; координаты страниц PDF между собой не смешиваются.']
(H/'source-register.md').write_text('\n'.join(lines)+'\n')
