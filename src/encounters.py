ENCOUNTER_SCRIPT = [
    {
        'trigger_dist': 8000,        # how close player gets to activate
        'origin': (0, 0, 8000),      # world position of the encounter
        'formation': 'wedge',
        'enemies': [
            ('drone', (-200, 0, 0)),
            ('drone', (200, 0, 0)),
            ('drone', (0, 100, -200)),
            ('fighter', (0, 0, -400)),
        ],
        'filler': False,             # suppress random spawns during this
    },
    {
        'trigger_dist': 6000,
        'origin': (2000, -500, 16000),
        'formation': 'pincer',
        'enemies': [
            ('fighter', (-800, 0, 0)),
            ('fighter', (800, 0, 0)),
            ('drone', (-200, 200, 200)),
            ('drone', (200, 200, 200)),
            ('drone', (0, -200, 200)),
        ],
        'filler': True,
    },
]
