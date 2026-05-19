# pyrefly: ignore [missing-import]
import os
import wave
import time
import pygame

class SoundHandler:
    def __init__(self, sample_rate=44100, bit_depth=-16, channels=2, buffer_size=2048):
        self.sample_rate = sample_rate
        self.bit_depth = bit_depth
        self.channels = channels
        self.buffer_size = buffer_size
        
        self.sounds = {}
        self.cooldowns = {}
        
        # Audio voice limit rules: max simultaneous playbacks of the same sound
        self.voice_limits = {
            "laser": 4,
            "missile": 2,
            "explosion": 3,
            "shield_hit": 2,
            "armor_hit": 2,
        }
        
        # Cooldown between triggers of the same sound (in seconds)
        self.trigger_cooldowns = {
            "laser": 0.08,
            "missile": 0.15,
            "shield_hit": 0.10,
            "armor_hit": 0.10,
        }
        
        self.music_volume = .7
        self.sfx_volume = .7
        
        self.engine_hum_channels = {}
        
        self._init_mixer()

    def _init_mixer(self):
        """Initializes Pygame mixer with custom optimal settings for 2011 i5 CPU."""
        if pygame.mixer.get_init():
            pygame.mixer.quit()
            
        try:
            # size=-16 means signed 16-bit depth
            pygame.mixer.init(
                frequency=self.sample_rate,
                size=self.bit_depth,
                channels=self.channels,
                buffer=self.buffer_size
            )
            print(f"Pygame mixer initialized: {self.sample_rate}Hz, 16-bit, {self.channels} channels, buffer={self.buffer_size}")
        except pygame.error as e:
            print(f"Failed to initialize Pygame mixer: {e}")
            return
        
        # Pre-allocate static mixing channels to avoid runtime allocation overhead
        pygame.mixer.set_num_channels(32)

    def validate_wav_header(self, filepath):
        """
        Parses WAV header using standard 'wave' module to verify it matches
        the exact initialization parameters of the Pygame mixer.
        Raises ValueError if there is any mismatch (avoiding on-the-fly resampling).
        """
        try:
            with wave.open(filepath, 'rb') as w:
                n_channels = w.getnchannels()
                samp_width = w.getsampwidth()
                framerate = w.getframerate()
                
                # Check sample rate (frequency)
                if framerate != self.sample_rate:
                    raise ValueError(
                        f"Sample rate mismatch for {filepath}. "
                        f"Expected {self.sample_rate} Hz, found {framerate} Hz. "
                        f"Dynamic resampling will degrade CPU performance on low-end hardware."
                    )
                
                # Check bit depth (sample width)
                # 2 bytes = 16-bit, size = -16
                expected_width = abs(self.bit_depth) // 8
                if samp_width != expected_width:
                    raise ValueError(
                        f"Bit depth mismatch for {filepath}. "
                        f"Expected {abs(self.bit_depth)}-bit (width {expected_width} bytes), found {samp_width * 8}-bit."
                        f"Dynamic resampling will degrade CPU performance."
                    )
                
                # Check channels (mono vs stereo)
                if n_channels != self.channels:
                    raise ValueError(
                        f"Channel mismatch for {filepath}. "
                        f"Expected {self.channels} channels, found {n_channels} channels. "
                        f"Dynamic resampling will degrade CPU performance."
                    )
                    
        except wave.Error as e:
            raise ValueError(f"Invalid or corrupted WAV file: {filepath}. Error: {e}")

    def load_sfx(self, name, filepath):
        """Loads and caches sound effect, validating WAV headers to prevent resampling overhead."""
        if not pygame.mixer.get_init():
            return
            
        if not os.path.exists(filepath):
            print(f"Warning: SFX file not found: {filepath}")
            return
            
        # Verify the format before loading to protect our 2011 i5 CPU!
        try:
            self.validate_wav_header(filepath)
        except ValueError as err:
            print(f"\n[AUDIO PERFORMANCE ERROR] Resampling Detected!")
            print(f"Reason: {err}")
            print(f"To solve this, re-encode the WAV using:")
            print(f"ffmpeg -i {filepath} -ar {self.sample_rate} -ac {self.channels} -c:a pcm_s16le cleaned_{name}.wav\n")
            raise err

        try:
            sound = pygame.mixer.Sound(filepath)
            sound.set_volume(self.sfx_volume)
            self.sounds[name] = sound
            self.cooldowns[name] = 0.0
            print(f"Successfully loaded and validated SFX '{name}' from {filepath}")
        except pygame.error as e:
            print(f"Failed to load Pygame Sound '{name}' from {filepath}: {e}")
    def play_sfx(self, name):
        """Plays sound effect with voice limiting and trigger cooldowns to minimize CPU cycles.
        Returns True if triggered, False if skipped."""
        if not pygame.mixer.get_init() or name not in self.sounds:
            return False
            
        now = time.time()
        
        # 1. Cooldown Check (Prevents high frequency triggering)
        cooldown = self.trigger_cooldowns.get(name, 0.0)
        if cooldown > 0:
            last_played = self.cooldowns.get(name, 0.0)
            if now - last_played < cooldown:
                return False # Skip triggering, still in cooldown to save CPU cycles!
                
        # 2. Voice Limit Check (Prevents voice stack-up)
        limit = self.voice_limits.get(name, 4)
        sound = self.sounds[name]
        
        # Count how many channels are currently playing this Sound object
        active_channels = sound.get_num_channels()
        if active_channels >= limit:
            return False # Skip playing to prevent sound congestion and CPU spike!
            
        # 3. Play sound (non-blocking)
        sound.play()
        self.cooldowns[name] = now
        return True

    def play_music(self, filepath, loops=-1, volume=0.4):
        """Streams BGM from disk to conserve RAM and avoid decompression overhead."""
        if not pygame.mixer.get_init():
            return
            
        if not os.path.exists(filepath):
            print(f"Warning: Music file not found: {filepath}")
            return
            
        try:
            pygame.mixer.music.load(filepath)
            self.music_volume = volume
            pygame.mixer.music.set_volume(volume)
            pygame.mixer.music.play(loops)
            print(f"Streaming background music: {filepath}")
        except pygame.error as e:
            print(f"Failed to load/play background music '{filepath}': {e}")

    def stop_music(self):
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()

    def set_sfx_volume(self, volume):
        self.sfx_volume = max(0.0, min(1.0, volume))
        for sound in self.sounds.values():
            sound.set_volume(self.sfx_volume)

    def set_music_volume(self, volume):
        self.music_volume = max(0.0, min(1.0, volume))
        if pygame.mixer.get_init():
            pygame.mixer.music.set_volume(self.music_volume)

    def start_engine_hum(self):
        """Starts the continuous multi-layer engine hums on dedicated channels."""
        if not pygame.mixer.get_init():
            return
            
        self.engine_hum_channels = {}
        self.engine_hum_sounds = ["engine_hum_low", "engine_hum_mid", "engine_hum_high", "engine_hum_overdrive"]
        
        for name in self.engine_hum_sounds:
            if name in self.sounds:
                chan = pygame.mixer.find_channel()
                if chan:
                    self.engine_hum_channels[name] = chan
                    chan.play(self.sounds[name], loops=-1)
                    chan.set_volume(0.0) # Start silent

    def update_engine_hum(self, throttle, yaw_input, roll_input, pitch_input):
        """
        Dynamically adjusts the volume and blending of multi-layer engine hums
        based on ship movement and throttle/rotational effort.
        """
        if not hasattr(self, 'engine_hum_channels') or not self.engine_hum_channels:
            return
            
        # Verify at least one channel is active
        active = any(chan.get_busy() for chan in self.engine_hum_channels.values())
        if not active:
            return
            
        # Base engine effort: 10% volume when idle, up to 70% at max throttle
        effort = abs(throttle)
        
        # Add rotational effort (thrusters working to turn)
        rot_effort = min(1.0, (abs(yaw_input) + abs(roll_input) + abs(pitch_input)) / 2.0)
        
        total_effort = min(1.0, effort + rot_effort * 0.3)
        base_vol = 0.1 + (0.6 * total_effort)
        
        # Apply master SFX volume
        base_vol *= self.sfx_volume
        
        # Panning: If turning right, left thrusters work harder.
        pan_amount = (yaw_input + roll_input) * 0.5
        pan_amount = max(-1.0, min(1.0, pan_amount))
        
        left_vol = base_vol * (1.0 + pan_amount * 0.4)
        right_vol = base_vol * (1.0 - pan_amount * 0.4)
        
        # Calculate contribution for each of the 4 layers:
        # engine_hum_low       (center: 0.00)
        # engine_hum_mid       (center: 0.33)
        # engine_hum_high      (center: 0.66)
        # engine_hum_overdrive (center: 1.00)
        
        contribs = {
            "engine_hum_low": 0.0,
            "engine_hum_mid": 0.0,
            "engine_hum_high": 0.0,
            "engine_hum_overdrive": 0.0,
        }
        
        if total_effort <= 0.33:
            # Blend low and mid
            t = total_effort / 0.33
            contribs["engine_hum_low"] = 1.0 - t
            contribs["engine_hum_mid"] = t
        elif total_effort <= 0.66:
            # Blend mid and high
            t = (total_effort - 0.33) / 0.33
            contribs["engine_hum_mid"] = 1.0 - t
            contribs["engine_hum_high"] = t
        else:
            # Blend high and overdrive
            t = (total_effort - 0.66) / 0.34
            contribs["engine_hum_high"] = 1.0 - t
            contribs["engine_hum_overdrive"] = t
            
        # Apply scaled volume to each layer's channel
        for name, chan in self.engine_hum_channels.items():
            contrib = contribs.get(name, 0.0)
            l_vol = max(0.0, min(1.0, left_vol * contrib))
            r_vol = max(0.0, min(1.0, right_vol * contrib))
            chan.set_volume(l_vol, r_vol)
