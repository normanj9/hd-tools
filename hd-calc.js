// Shared HD2 damage engine — used by damage-calc.html and loadouts.html.
// Keep game-math here so both pages always agree.

// Key heavy enemies per faction (breakpoint summaries, faction view)
const FACTION_HEAVIES = {
  bugs:   ['bile-titan', 'charger', 'charger-behemoth', 'impaler', 'dragonroach'],
  bots:   ['factory-strider', 'war-strider', 'hulk-bruiser', 'annihilator-tank', 'gunship', 'vox-engine'],
  squids: ['harvester', 'fleshmob', 'grounded-warp-ship', 'gatekeeper', 'veracitor', 'crusher'],
};

function calcComponent(comp, part, chargeMult = 1) {
  const ap = comp.ap, av = part.av;
  let penMult;
  if      (ap > av) penMult = 1.0;
  else if (ap === av) penMult = 0.65;
  else return { damage: 0, pen: 'none', penMult: 0 };

  let exdrMult = 1.0;
  const type = (comp.type || '').toLowerCase();
  if (type === 'explosion') {
    exdrMult = (100 - (part.exdr || 0)) / 100;
    if (exdrMult <= 0) return { damage: 0, pen: 'exdr', penMult };
  }

  const dur     = (part.durable_pct || 0) / 100;
  const stdD    = comp.damage || 0;
  const durD    = comp.durable_damage != null ? comp.durable_damage : Math.floor(stdD / 2);
  const pellets = comp.pellets || 1;
  // Pellets: assumes every pellet connects (close-range/point-blank best case),
  // same "best-case" convention used elsewhere (100% hits, no misses).
  const effD    = (stdD * (1 - dur) + durD * dur) * pellets;

  return {
    damage:   effD * penMult * exdrMult * chargeMult,
    pen:      penMult === 1.0 ? 'full' : 'partial',
    penMult,
    exdrMult,
    chargeMult,
    rawEff:   effD,
  };
}

function calcHit(weapon, modeIdx, part, chargeMult = 1) {
  const mode = weapon.modes[modeIdx];
  if (!mode) return { total: 0, results: [] };
  const results = mode.components.map(c => ({ comp: c, ...calcComponent(c, part, chargeMult) }));
  const total = results.reduce((s, r) => s + r.damage, 0);
  return { total, results };
}

function stk(dmg, hp) {
  if (dmg <= 0) return Infinity;
  return Math.ceil(hp / dmg);
}

// Effective HP for shots-to-kill purposes: base health plus Constitution, a
// secondary pool some parts have on top of Health (e.g. Factory Strider's Leg
// Assembly: 1,500 health + 2,000 constitution = 3,500 total). Most decay at
// 0/s (pure extra HP); a handful decay over time once Health hits 0, which
// isn't modeled here — treated as static extra HP for all parts.
function partHP(part, mainHP) {
  const base = part.health_is_main ? mainHP : part.health;
  return base + (part.constitution || 0);
}
