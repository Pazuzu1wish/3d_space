ENCOUNTER_SCRIPT = [
    # ── ENCOUNTER 1: THE SNIPER GAUNTLET ─────────────────────────────────────
    # A wall of snipers protected by a screen of drones.
    {
        'trigger_dist': 8000,
        'origin': (0, 0, 10000),
        'formation': 'gauntlet',
        'enemies': [
            # The Snipers (Rear Guard)
            ('drone', (-1200, -1200, -500)),
            ('drone', ( 1200, -1200, -500)),
            ('drone', (-1200,  1200, -500)),
            ('drone', ( 1200,  1200, -500)),
            # The Drone Screen (Vanguard)
            ('drone',  (-400,  200, 800)),
            ('drone',  ( 400,  200, 800)),
            ('drone',  (-800, -200, 1200)),
            ('drone',  ( 800, -200, 1200)),
            ('drone',  (   0,  600, 1000)),
            ('drone',  (   0, -600, 1000)),
            ('drone',  (-1200, 0,   1500)),
            ('drone',  ( 1200, 0,   1500)),
        ],
        'filler': False,
    },

    # ── ENCOUNTER 2: CARRIER STRIKE GROUP ────────────────────────────────────
    # A massive set-piece featuring the capital ship and its escorts.
    {
        'trigger_dist': 7000,
        'origin': (2000, -500, 25000),
        'formation': 'strike_group',
        'enemies': [
            ('carrier',  (0, 0, 0)),
            # Escorts
            ('corvette', (-1800, -300, 600)),
            ('corvette', ( 1800, -300, 600)),
            # High Cover
            ('fighter',  (-1000, 800, 300)),
            ('fighter',  ( 1000, 800, 300)),
            ('fighter',  (-500, 1200, 600)),
            ('fighter',  ( 500, 1200, 600)),
            # Close defense
            ('drone',    (-300, -400, 400)),
            ('drone',    ( 300, -400, 400)),
            ('drone',    (   0, -800, 200)),
        ],
        'filler': False,
    },

    # ── ENCOUNTER 3: THE STEALTH MINEFIELD ───────────────────────────────────
    # Hazard-based area with invisible threats.
    {
        'trigger_dist': 7000,
        'origin': (-1500, 1000, 40000),
        'formation': 'minefield',
        'enemies': [
            # The Minelayers
            ('minelayer', (-2500, 0, 0)),
            ('minelayer', (    0, 0, 0)),
            ('minelayer', ( 2500, 0, 0)),
            # The Ambushers
            ('stealth',   (-1800,  600, 600)),
            ('stealth',   ( 1800,  600, 600)),
            ('stealth',   (-1200, -600, 900)),
            ('stealth',   ( 1200, -600, 900)),
        ],
        'filler': False,
    },

    # ── ENCOUNTER 4: THE SWARM ───────────────────────────────────────────────
    # Pure volume of weak enemies rushing the player.
    {
        'trigger_dist': 6000,
        'origin': (0, -1200, 55000),
        'formation': 'swarm',
        'enemies': [
            ('drone', (x, y, z)) for x, y, z in [
                (-300, -300, 0), (300, -300, 0), (-300, 300, 0), (300, 300, 0),
                (-600, 0, 300), (600, 0, 300), (0, -600, 300), (0, 600, 300),
                (-200, -200, 600), (200, -200, 600), (-200, 200, 600), (200, 200, 600),
                (0, 0, 900), (-400, 0, 900), (400, 0, 900), (0, 400, 1200)
            ]
        ],
        'filler': False,
    },

    # ── ENCOUNTER 5: FINAL STAND (ELITE SQUADRON) ────────────────────────────
    # The ultimate test of the player's combat skills.
    {
        'trigger_dist': 12000,
        'origin': (0, 0, 75000),
        'formation': 'final_stand',
        'enemies': [
            # Command Centers
            ('carrier',  (-2500, 200, -1000)),
            ('carrier',  ( 2500, 200, -1000)),
            # Vanguard
            ('corvette', (-1200, -500, 500)),
            ('corvette', ( 1200, -500, 500)),
            ('corvette', (-3500, -500, 500)),
            ('corvette', ( 3500, -500, 500)),
            # Hunters
            ('stealth',  (-2000, 1000, 800)),
            ('stealth',  ( 2000, 1000, 800)),
            ('stealth',  (    0, 1500, 1200)),
            ('stealth',  (-1000, -1000, 1500)),
            ('stealth',  ( 1000, -1000, 1500)),
            ('stealth',  (    0, -1500, 1800)),
        ],
        'filler': False,
    },
]