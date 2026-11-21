"""Names for a model's motions, from what the game's code does with them.

Only meanings the decompilation shows are used (dw3_decomp, MIT, https://github.com/ReGame-Labs/dw3_decomp):
- src/battle/normal_battle/techs.c WFIGHTMN_setIdleMotion and battle_mode/model_mesh.c: the idle motion is
  control->idleMotion + 1, idleMotion 0 normally and 1 when the fighter is left with a quarter of its HP or less
  -> motion 1 idle, motion 2 weak idle.
- src/battle/normal_battle/menu.c (battle won): "the partner's motion 0xD" -> motion 13 victory.
- A target's reaction script is hit + 1 (battle_mode/battle_script.c FIGHTSTG_runScriptHits, hit_effect.c);
  include/battle/battle_mode/effect.h: hits "0 a hit, 3 a miss", the last one "1 a hit, 2 a knockout"
  -> script 1 hit (not the last), 2 hit, 3 knockout, 4 miss (the target evades).
- TechData.script (include/engine/game_state.h) is the script a technique plays in its user's archive.
  normal_battle/techs.c choosePartnerScript: for script 5 the partner plays 8 with the triple hit and 6 with an
  action effect or a weapon of the enemy's family -> scripts 5, 6, 8 are one attack's variants; 12 adds a model
  (battle_script.c, model command 6) and shows message 0x3A (tech_action.c).
- battle_mode/item.c: items play scripts 10, 14, 15 and 17.
A motion no script plays keeps its neutral name "Motion N"; which technique uses which script depends on the
technique data and is not named here.
"""

SCRIPT_NAMES = {
    1: ('Treffer (Zwischentreffer)', 'Hit (not the last)'),
    2: ('Treffer', 'Hit'),
    3: ('K. o.', 'Knockout'),
    4: ('Ausweichen (verfehlt)', 'Evade (missed)'),
    5: ('Technik-Skript 5', 'Technique script 5'),
    6: ('Technik-Skript 6 (Aktionseffekt/Waffe)', 'Technique script 6 (action effect/weapon)'),
    7: ('Technik-Skript 7', 'Technique script 7'),
    8: ('Technik-Skript 8 (Dreifachtreffer)', 'Technique script 8 (triple hit)'),
    9: ('Technik-Skript 9', 'Technique script 9'),
    10: ('Item (Skript 10)', 'Item (script 10)'),
    11: ('Technik-Skript 11', 'Technique script 11'),
    12: ('Technik-Skript 12 (ruft ein Modell)', 'Technique script 12 (calls a model)'),
    14: ('Item (Skript 14)', 'Item (script 14)'),
    15: ('Item (Skript 15)', 'Item (script 15)'),
    17: ('Item (Skript 17)', 'Item (script 17)'),
}
SOURCES = {1: 'battle_script.c / effect.h hits', 2: 'effect.h HitEffect.result', 3: 'effect.h HitEffect.result',
           4: 'effect.h hits (3 = miss)', 6: 'techs.c choosePartnerScript', 8: 'techs.c choosePartnerScript',
           12: 'battle_script.c model command 6', 10: 'item.c', 14: 'item.c', 15: 'item.c', 17: 'item.c'}
FIXED = {1: ('Idle / Standby', 'Idle / standby', 'techs.c WFIGHTMN_setIdleMotion'),
         2: ('Idle geschwächt (≤ ¼ KP)', 'Idle, weak (≤ ¼ HP)', 'techs.c WFIGHTMN_setIdleMotion'),
         13: ('Sieg', 'Victory', 'menu.c: battle won, the partner\'s motion 0xD')}


def label(motion, scripts):
    """{'de', 'en', 'scripts': [index...], 'source'} for motion number MOTION (1-based)."""
    used = [s['index'] for s in scripts or [] if motion in s.get('motions', [])]
    if motion in FIXED:
        de, en, src = FIXED[motion]
    elif used:
        named = [i for i in used if i in SCRIPT_NAMES]
        rest = [i for i in used if i not in SCRIPT_NAMES]
        de = ' / '.join([SCRIPT_NAMES[i][0] for i in named] + [f'Skript {i}' for i in rest])
        en = ' / '.join([SCRIPT_NAMES[i][1] for i in named] + [f'Script {i}' for i in rest])
        src = '; '.join(sorted({SOURCES.get(i, 'Aktionsskript des Kämpfers') for i in used}))
    else:
        de, en, src = f'Motion {motion}', f'Motion {motion}', ''
    return {'de': de, 'en': en, 'scripts': used, 'source': src}
