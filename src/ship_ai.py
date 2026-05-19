import math
import os
import random
import pygame

class ShipAI:
    def __init__(self, sound_handler, voice_folder="assets/sounds/voice"):
        self.sound_handler = sound_handler
        self.voice_folder = voice_folder
        
        self.ai_channel = None
        if pygame.mixer.get_init():
            self.ai_channel = pygame.mixer.Channel(30)
            self.ai_channel.set_volume(0.85)  # Ship AI should be very clear

        # Priority definitions
        self.PRIORITY_LOW = 1
        self.PRIORITY_INFO = 2
        self.PRIORITY_WARNING = 3
        self.PRIORITY_CRITICAL = 4

        # Map sound relative paths to priorities
        self.sound_priorities = {
            "combat/missile_incoming": self.PRIORITY_CRITICAL,
            "combat/missile_incoming_2": self.PRIORITY_CRITICAL,
            "combat/missile_incoming_3": self.PRIORITY_CRITICAL,
            "combat/target_acquired": self.PRIORITY_INFO,
            "combat/target_lost": self.PRIORITY_INFO,
            "combat/target_destroyed": self.PRIORITY_INFO,
            
            "damage/shields_low": self.PRIORITY_WARNING,
            "damage/shields_critical": self.PRIORITY_CRITICAL,
            "damage/shields_down": self.PRIORITY_CRITICAL,
            "damage/shields_restored": self.PRIORITY_INFO,
            "damage/hull_damage_moderate": self.PRIORITY_WARNING,
            "damage/hull_damage_critical": self.PRIORITY_CRITICAL,
            
            "encounter/wave_incoming": self.PRIORITY_INFO,
            "encounter/wave_cleared": self.PRIORITY_INFO,
            "encounter/boss_detected": self.PRIORITY_WARNING,
            "encounter/carrier_detected": self.PRIORITY_WARNING,
            "encounter/minelayer_detected": self.PRIORITY_INFO,
            "encounter/stealth_contact": self.PRIORITY_INFO,
            "encounter/sniper_contact": self.PRIORITY_INFO,
            "encounter/player_destroyed": self.PRIORITY_CRITICAL,
            
            "system/power_nominal": self.PRIORITY_LOW
        }

        # Cache of loaded Sound objects
        self.sounds = {}
        self.current_priority = 0
        self.current_sound_name = None

        # State tracking variables
        self.last_shield_pct = 1.0
        self.last_hp_pct = 1.0
        self.last_target = None
        
        self.last_pending_waves = None
        self.last_filler_suppressed = False

        self.announced_enemy_types = set()  # Reset when wave cleared or new wave incoming
        self.seen_enemies = set()  # Set of enemy instances currently in world

        # Cooldowns
        self.missile_warning_cooldown = 0.0
        
        # Load sounds
        self._load_sounds()

    def _load_sounds(self):
        """Preload the voice SFX assets into Pygame, validating headers."""
        if not pygame.mixer.get_init():
            return
            
        for name in self.sound_priorities.keys():
            path = os.path.join(self.voice_folder, f"{name}.wav")
            if os.path.exists(path):
                try:
                    # Validate WAV header first to avoid dynamic resampling frame stutters!
                    self.sound_handler.validate_wav_header(path)
                    sound = pygame.mixer.Sound(path)
                    self.sounds[name] = sound
                except ValueError as ve:
                    print(f"[ShipAI WARNING] Resampling or header validation warning for {name}: {ve}")
                    # Load it anyway as fallback so the sound still plays
                    try:
                        sound = pygame.mixer.Sound(path)
                        self.sounds[name] = sound
                    except Exception as e:
                        print(f"[ShipAI] Failed to load voice clip {name}: {e}")
                except Exception as e:
                    print(f"[ShipAI] Failed to load voice clip {name}: {e}")
            else:
                print(f"[ShipAI] Warning: Voice file not found: {path}")

    def announce(self, sound_name, force=False):
        """Triggers a voice announcement if priority conditions are met."""
        if not pygame.mixer.get_init() or self.ai_channel is None:
            return False

        # Reset current priority if channel is done playing
        if not self.ai_channel.get_busy():
            self.current_priority = 0
            self.current_sound_name = None

        priority = self.sound_priorities.get(sound_name, self.PRIORITY_LOW)
        
        # We can interrupt if it's strictly higher priority, or if forced, or if channel is free
        if force or priority > self.current_priority or not self.ai_channel.get_busy():
            sound = self.sounds.get(sound_name)
            if sound:
                self.ai_channel.play(sound)
                self.current_priority = priority
                self.current_sound_name = sound_name
                return True
        return False

    def update(self, player, enemies, projectiles, wave_director, dt):
        """Update loop to monitor gameplay state changes and trigger voice warnings."""
        if player.hp <= 0:
            # Player is destroyed, state is dead
            if self.last_hp_pct > 0:
                self.announce("encounter/player_destroyed")
                self.last_hp_pct = 0.0
            return

        # ── 1. SHIELD STATE MACHINE ──
        shield_pct = player.shield / 100.0  # SHIELD_MAX is 100
        
        if shield_pct == 0 and self.last_shield_pct > 0:
            self.announce("damage/shields_down")
        elif shield_pct < 0.10 and self.last_shield_pct >= 0.10 and shield_pct > 0:
            self.announce("damage/shields_critical")
        elif shield_pct < 0.30 and self.last_shield_pct >= 0.30 and shield_pct >= 0.10:
            self.announce("damage/shields_low")
        elif self.last_shield_pct == 0 and shield_pct > 0:
            self.announce("damage/shields_restored")
            
        self.last_shield_pct = shield_pct

        # ── 2. HULL HP STATE MACHINE ──
        from src.constants import PLAYER_MAX_HP
        hp_pct = player.hp / PLAYER_MAX_HP

        if hp_pct < 0.30 and self.last_hp_pct >= 0.30:
            self.announce("damage/hull_damage_critical")
        elif hp_pct < 0.60 and self.last_hp_pct >= 0.60 and hp_pct >= 0.30:
            self.announce("damage/hull_damage_moderate")

        self.last_hp_pct = hp_pct

        # ── 3. TARGETING STATE MACHINE ──
        target = player.active_target
        if target is not None and self.last_target is None:
            self.announce("combat/target_acquired")
        elif target is None and self.last_target is not None:
            # Check if last target was destroyed (not in enemies or hp <= 0)
            if self.last_target not in enemies or getattr(self.last_target, 'hp', 0) <= 0:
                self.announce("combat/target_destroyed")
            else:
                self.announce("combat/target_lost")

        self.last_target = target

        # ── 4. MISSILE WARNING STATE MACHINE ──
        incoming_missile = False
        for proj in projectiles:
            if getattr(proj, 'homing', False) and proj.life > 0:
                dist = math.dist((proj.x, proj.y, proj.z), player.pos)
                if dist < 5000.0:  # Within 5000 meters
                    incoming_missile = True
                    break

        if incoming_missile:
            if self.missile_warning_cooldown <= 0:
                # Cycle through warning lines
                warning = random.choice([
                    "combat/missile_incoming",
                    "combat/missile_incoming_2",
                    "combat/missile_incoming_3"
                ])
                self.announce(warning)
                self.missile_warning_cooldown = 5.0  # Cooldown between missile warnings
        else:
            self.missile_warning_cooldown = max(0.0, self.missile_warning_cooldown - dt)

        # ── 5. WAVE & ENCOUNTER STATE MACHINE ──
        pending_waves = len(wave_director.pending)
        if self.last_pending_waves is None:
            self.last_pending_waves = pending_waves

        if pending_waves < self.last_pending_waves:
            # Scripted encounter triggered!
            self.announce("encounter/wave_incoming")
            self.announced_enemy_types.clear()  # Reset for new wave

        self.last_pending_waves = pending_waves

        if wave_director.filler_suppressed != self.last_filler_suppressed:
            if not wave_director.filler_suppressed:
                # Scripted encounter cleared!
                self.announce("encounter/wave_cleared")
                self.announced_enemy_types.clear()

        self.last_filler_suppressed = wave_director.filler_suppressed

        # ── 6. SPECIAL ENEMY DETECTION ──
        from src.enemy import Carrier, StealthInterceptor, Minelayer, Sniper, Corvette
        for enemy in enemies:
            if enemy not in self.seen_enemies:
                self.seen_enemies.add(enemy)
                etype = type(enemy)
                
                # Check distance so AI only announces them when they are relatively close/detectable on sensor
                dist = math.dist((enemy.x, enemy.y, enemy.z), player.pos)
                if dist < 8000.0:
                    if etype is Carrier and "carrier" not in self.announced_enemy_types:
                        self.announce("encounter/carrier_detected")
                        self.announced_enemy_types.add("carrier")
                    elif etype is StealthInterceptor and "stealth" not in self.announced_enemy_types:
                        self.announce("encounter/stealth_contact")
                        self.announced_enemy_types.add("stealth")
                    elif etype is Minelayer and "minelayer" not in self.announced_enemy_types:
                        self.announce("encounter/minelayer_detected")
                        self.announced_enemy_types.add("minelayer")
                    elif etype is Sniper and "sniper" not in self.announced_enemy_types:
                        self.announce("encounter/sniper_contact")
                        self.announced_enemy_types.add("sniper")
                    elif etype is Corvette and "corvette" not in self.announced_enemy_types:
                        self.announce("encounter/boss_detected")
                        self.announced_enemy_types.add("corvette")

        # Clean up seen_enemies to prevent memory leaks as enemies are destroyed/removed
        self.seen_enemies = {e for e in self.seen_enemies if e in enemies}
