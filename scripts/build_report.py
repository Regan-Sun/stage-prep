"""Validate manually reasoned plans/reviews and render portable Markdown + HTML."""
import argparse
import hashlib
import html
import json
import math
import shutil
from pathlib import Path


def require(test, message):
    if not test:
        raise ValueError(message)


def interval(pair):
    require(isinstance(pair, list) and len(pair) == 2, 'Need [start,end] interval')
    require(all(isinstance(x, (int, float)) and math.isfinite(x) for x in pair), 'Invalid interval numbers')
    require(0 <= pair[0] <= pair[1], 'Invalid interval ordering')


def validate(data, root):
    require(data.get('schema_version') == '1.0', 'Unsupported schema_version')
    require(data.get('mode') in ('plan', 'review'), 'mode must be plan or review')
    for field in ('title', 'practice'):
        require(data.get(field), 'Missing ' + field)
    for field in ('focus', 'steps', 'criterion'):
        require(data['practice'].get(field), 'Missing practice.' + field)
    if data['mode'] == 'plan':
        for field in ('source_text', 'script_version', 'intent', 'assumptions', 'paragraphs', 'stage'):
            require(field in data, 'Missing ' + field)
        ids = [p['id'] for p in data['paragraphs']]
        require(len(ids) == len(set(ids)), 'Duplicate paragraph ids')
        require(''.join(p['text'] for p in data['paragraphs']) == data['source_text'], 'Paragraphs must preserve exact source text including whitespace')
        positions = data['stage']['positions']
        pos_ids = {p['id'] for p in positions}
        require(len(pos_ids) == len(positions), 'Duplicate stage position ids')
        require(data['stage'].get('orientation'), 'Stage orientation required')
        for action in data.get('actions', []):
            require(action['paragraph_id'] in ids, 'Unknown paragraph')
            for f in ('quote', 'task', 'prepare', 'land', 'hold', 'reset', 'reason', 'alternative'):
                require(action.get(f), 'Missing action.' + f)
            para = next(p for p in data['paragraphs'] if p['id'] == action['paragraph_id'])
            require(action['quote'] in para['text'], 'Action quote must exist in original paragraph')
        for move in data['stage'].get('moves', []):
            require(move['from'] in pos_ids and move['to'] in pos_ids, 'Unknown stage position')
            for f in ('reason', 'connector', 'key_sentence'):
                require(move.get(f), 'Missing move.' + f)
            require(move['connector'] in data['source_text'] and move['key_sentence'] in data['source_text'], 'Move quotes must exist in source')
    else:
        require(data.get('scope'), 'Missing review scope')
        for f in ('viewing_method', 'audio_status', 'limitations', 'intervals'):
            require(f in data['scope'], 'Missing scope.' + f)
        for pair in data['scope']['intervals']:
            interval(pair)
        require(data.get('findings'), 'At least one evidence observation required')
        require(len([f for f in data['findings'] if f.get('priority') == 'adjust']) <= 1, 'Only one priority adjustment')
        for finding in data['findings']:
            interval(finding['interval'])
            require(any(a <= finding['interval'][0] <= finding['interval'][1] <= b for a,b in data['scope']['intervals']), 'Finding outside reviewed intervals')
            require(finding.get('status') in ('verified','partial','needs_context','unjudgeable'), 'Invalid evidence status')
            for f in ('fact', 'interpretation', 'advice', 'frames'):
                require(finding.get(f), 'Missing finding.' + f)
            if finding.get('dynamic'):
                require(finding.get('sequence_basis'), 'Dynamic claim requires sequence basis and viewing description')
            for frame in finding['frames']:
                require(finding['interval'][0] <= frame['seconds'] <= finding['interval'][1], 'Frame outside finding interval')
                require((root / frame['file']).is_file(), 'Evidence image does not exist: ' + frame['file'])
                ctx = frame['context']
                require(ctx.get('state') in ('speech','silence','unknown'), 'Invalid speech state')
                require(ctx.get('source'), 'Context provenance required')
                for side in ('before', 'after'):
                    require(isinstance(ctx.get(side), list) and len(ctx[side]) <= 2, 'Context needs at most two sentences per side')
                if ctx['state'] == 'speech':
                    require(ctx.get('current'), 'Current spoken/subtitle sentence required')
                    interval(ctx['interval'])
                    require(ctx['interval'][0] <= frame['seconds'] <= ctx['interval'][1], 'Frame not inside current sentence interval')
                if ctx['state'] == 'silence':
                    require(ctx.get('verified_silence') is True, 'Silence requires explicit verification; otherwise use unknown')
    return data


def render(data, root, out):
    validate(data, root)
    require(not out.exists(), 'Output exists; use a new run directory')
    out.mkdir(parents=True)
    md, web = [], []
    def line(text='', level=0, bold=False):
        prefix = '#' * level + ' ' if level else ''
        md.append(prefix + ('**' + text + '**' if bold else text))
        tag = 'h' + str(level) if level else 'p'
        safe = html.escape(text)
        web.append(f'<{tag}>' + ('<strong>' + safe + '</strong>' if bold else safe) + f'</{tag}>')
    line(data['title'], 1)
    if data['mode'] == 'plan':
        line('稿件版本：' + data['script_version'])
        line('表达意图：' + data['intent'])
        line('场景与假设：' + json.dumps(data['assumptions'], ensure_ascii=False))
        line('动作标注稿', 2)
        for paragraph in data['paragraphs']:
            line(paragraph['id'], 3); line(paragraph['text'])
            for action in data.get('actions', []):
                if action['paragraph_id'] == paragraph['id']:
                    line('排练提示：' + action['task'] + '｜' + action['quote'])
                    for k, label in [('prepare','准备'),('land','成形'),('hold','停留'),('reset','复位'),('reason','表达理由'),('alternative','替代')]:
                        line(label + '：' + action[k])
        line('舞台走位', 2); line(data['stage']['orientation'])
        for position in data['stage']['positions']:
            line(position['id'] + '：' + position['meaning'])
        for move in data['stage'].get('moves', []):
            line(f"{move['from']} → {move['to']}｜{move['connector']}｜{move['reason']}｜重点前站稳：{move['key_sentence']}")
        if not data['stage'].get('moves'):
            line('本轮采用单定点；无需为了动而动。')
        # Simple stage map: positions use x=0..1, y=0..1, audience at bottom.
        svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="800" height="420" viewBox="0 0 800 420">', '<rect width="800" height="420" fill="#f2f6fa"/>', '<text x="400" y="400" text-anchor="middle" font-size="22">观众方向（图左=演讲者右）</text>']
        coords = {p['id']: (80 + 640 * max(0,min(1,p.get('x',.5))), 55 + 240 * max(0,min(1,p.get('y',.5)))) for p in data['stage']['positions']}
        svg.append('<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#527797"/></marker></defs>')
        for move in data['stage'].get('moves', []):
            a,b=coords[move['from']],coords[move['to']]
            svg.append(f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" stroke="#527797" stroke-width="3" marker-end="url(#arrow)"/>')
        for p in data['stage']['positions']:
            x,y=coords[p['id']]
            svg.append(f'<circle cx="{x}" cy="{y}" r="18" fill="#244665"/><text x="{x}" y="{y+45}" text-anchor="middle" font-size="18">{html.escape(p["id"]+": "+p["meaning"])}</text>')
        svg.append('</svg>'); (out / 'stage.svg').write_text(''.join(svg),encoding='utf-8')
        md.append('![舞台图](stage.svg)'); web.append('<img src="stage.svg" alt="舞台图">')
        (out / '原稿.txt').write_text(data['source_text'],encoding='utf-8')
    else:
        line('实际观察范围', 2)
        line(json.dumps(data['scope'], ensure_ascii=False))
        for index, finding in enumerate(data['findings']):
            line(f"{index+1}. {finding.get('title','观察')}｜{finding['interval']}｜{finding['status']}", 2)
            for k,label in [('fact','可见事实'),('interpretation','解释'),('advice','建议'),('sequence_basis','连续证据')]:
                if finding.get(k): line(label + '：' + finding[k])
            for j, frame in enumerate(finding['frames']):
                source = (root / frame['file']).resolve()
                target = Path('evidence') / f'{index+1:02d}_{j+1:02d}{source.suffix.lower()}'
                (out / target).parent.mkdir(exist_ok=True)
                shutil.copyfile(source, out / target)
                frame['file'] = target.as_posix()
                md.append(f"![{frame['seconds']:.3f}s]({target.as_posix()})")
                web.append(f'<img src="{target.as_posix()}" alt="evidence">')
                line(f"截图时间：{frame['seconds']:.3f} 秒")
                ctx = frame['context']
                line('语境来源：' + ctx['source'])
                for s in ctx['before']: line('前文：' + s)
                if len(ctx['before']) < 2: line('前文不足两句或未取得，不补写。')
                if ctx['state'] == 'speech': line(ctx['current'], bold=True)
                elif ctx['state'] == 'silence': line('此帧无口播（已核验）')
                else: line('此帧台词尚未核验，不能判定静默。')
                for s in ctx['after']: line('后文：' + s)
                if len(ctx['after']) < 2: line('后文不足两句或未取得，不补写。')
    line('本轮练习卡', 2)
    line('只练：' + data['practice']['focus'])
    for step in data['practice']['steps']: line(step)
    line('可观察标准：' + data['practice']['criterion'])
    (out / '报告.md').write_text('\n\n'.join(md), encoding='utf-8')
    doc = '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>' + html.escape(data['title']) + '</title><style>body{max-width:960px;margin:40px auto;padding:0 24px;font:18px/1.7 system-ui;color:#243447}img{max-width:100%;height:auto}p{white-space:pre-wrap}h2{border-bottom:1px solid #cbd5df;padding-top:20px}@media print{img{max-height:60vh}h2{break-after:avoid}}</style><body>' + '\n'.join(web) + '</body></html>'
    (out / '报告.html').write_text(doc, encoding='utf-8')
    (out / (data['mode'] + '.json')).write_text(json.dumps(data, ensure_ascii=False, indent=2),encoding='utf-8')
    return out


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input'); parser.add_argument('--out', required=True)
    args = parser.parse_args()
    try:
        source = Path(args.input).resolve()
        data = json.loads(source.read_text(encoding='utf-8-sig'))
        render(data, source.parent, Path(args.out).resolve())
        print('Report generated')
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, str(exc) + '\n')
