ENCOUNTER_SCRIPT = [
    # ── ENCOUNTER 1 ──────────────────────────────────────────────────────────
    # Opening skirmish: a wedge of drones with a dogfighter anchor.
    # Filler is suppressed so this set-piece has room to breathe.
    {
        'trigger_dist': 8000,
        'origin': (0, 0, 8000),
        'formation': 'wedge',
        'enemies': [
            ('carrier', (100 , 0, 0)),
            ('fighter',   (-200,   0,    0)),
            ('minelayer',   (   0,   0,    0)),
            ('corvette',    (   100, 200, 100))
            ],
        'filler': False,
    },

    # ── ENCOUNTER 2 ──────────────────────────────────────────────────────────
    # Pincer: fighters come from both flanks while drones rush the nose.
    {
        'trigger_dist': 6000,
        'origin': (2000, -500, 16000),
        'formation': 'pincer',
        'enemies': [
            ('fighter', (-800,   0,    0)),
            ('fighter', ( 800,   0,    0)),
            ('drone',   (-200, 200,  200)),
            ('drone',   ( 200, 200,  200)),
            ('drone',   (   0, -200, 200)),
        ],
        'filler': False,
    },

    # ── ENCOUNTER 3 ──────────────────────────────────────────────────────────
    # Sniper nest: two snipers hang back while a minelayer cuts across
    # the player's path to complicate approach.
    {
        'trigger_dist': 7000,
        'origin': (-1000, 800, 28000),
        'formation': 'sniper_nest',
        'enemies': [
            ('sniper',    (-600,  400, -200)),
            ('sniper',    ( 600,  400, -200)),
            ('minelayer', (   0, -200,  300)),
        ],
        'filler': False,
    },

    # ── ENCOUNTER 4 ──────────────────────────────────────────────────────────
    # Stealth ambush: interceptors decloak close in while a corvette
    # lumbers in from the front to eat fire.
    {
        'trigger_dist': 6000,
        'origin': (3000, -1200, 40000),
        'formation': 'ambush',
        'enemies': [
            ('corvette', (   0,    0,  -600)),
            ('stealth',  ( 500,  200,   400)),
            ('stealth',  (   0, -300,   500)),
            ('drone',    (-200, -100,   200)),
            ('drone',    ( 200, -100,   200)),
        ],
        'filler': False,
    },

    # ── ENCOUNTER 5 ──────────────────────────────────────────────────────────
    # Boss wave: a flanked by dogfighters.
    # Filler suppressed — this is the climax.
    {
        'trigger_dist': 10000,
        'origin': (0, 0, 55000),
        'formation': 'boss',
        'enemies': [
            ('carrier', (   0,   0,    0)),
            ('fighter', (-600, 200, -800)),
            ('fighter', ( 600, 200, -800)),
            ('sniper',  (-1200, 400, -1200)),
            ('sniper',  ( 1200, 400, -1200)),
        ],
        'filler': False,
    },
]