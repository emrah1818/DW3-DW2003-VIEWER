"""Names for a model's motions, from what the game's code does with them.

Only meanings the decompilation shows are used (dw3_decomp, MIT, https://github.com/ReGame-Labs/dw3_decomp):
- src/battle/normal_battle/techs.c WFIGHTMN_setIdleMotion and src/battle/battle_mode/model_mesh.c:
  the idle motion is control->idleMotion + 1 with idleMotion 0 normally and 1 when the fighter is left
  with a quarter of its HP or less -> motion 1 idle, motion 2 weak idle.
- include/battle/battle_mode/effect.h HitEffect.result "1 a hit, 2 a knockout: the script is result + 1"
  -> script 2 hit, script 3 knockout.
- the other scripts are started by techniques (TechData.script, src/battle/normal_battle/techs.c) and
  items (src/battle/battle_mode/item.c): shown with their number only.
A motion no script plays keeps its neutral name "Motion N".
"""

SCRIPT_NAMES = {2: 'Treffer', 3: 'K. o.'}
SCRIPT_NAMES_EN = {2: 'Hit', 3: 'Knockout'}
FIXED = {1: ('Idle / Standby', 'Idle / standby'), 2: ('Idle geschwächt (≤ ¼ KP)', 'Idle, weak (≤ ¼ HP)')}


def label(motion, scripts):
    """{'de', 'en', 'scripts': [index...], 'source'} for motion number MOTION (1-based)."""
    used = [s['index'] for s in scripts or [] if motion in s.get('motions', [])]
    if motion in FIXED:
        de, en = FIXED[motion]
        src = 'techs.c WFIGHTMN_setIdleMotion'
    else:
        named = [i for i in used if i in SCRIPT_NAMES]
        if named:
            de = ' / '.join(SCRIPT_NAMES[i] for i in named)
            en = ' / '.join(SCRIPT_NAMES_EN[i] for i in named)
            src = 'effect.h HitEffect.result'
        elif used:
            de = 'Aktion (Skript ' + ', '.join(map(str, used)) + ')'
            en = 'Action (script ' + ', '.join(map(str, used)) + ')'
            src = 'Aktionsskript des Kämpfers'
        else:
            de, en, src = f'Motion {motion}', f'Motion {motion}', ''
    return {'de': de, 'en': en, 'scripts': used, 'source': src}
