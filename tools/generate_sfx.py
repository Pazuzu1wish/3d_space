#!/usr/bin/env python3
import os
import wave
import numpy as np

def save_wav(filename, data, sample_rate=44100):
    """
    Saves a numpy array as a 16-bit signed PCM stereo WAV file.
    Assumes data is in range [-1.0, 1.0] and shape (N, 2).
    """
    filepath = os.path.join("assets", "sounds", filename)
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    
    # Clip and scale to 16-bit signed PCM
    clipped = np.clip(data, -1.0, 1.0)
    pcm_data = (clipped * 32767).astype(np.int16)
    
    with wave.open(filepath, 'wb') as w:
        w.setnchannels(2)           # Force stereo
        w.setsampwidth(2)           # 2 bytes = 16-bit
        w.setframerate(sample_rate)
        w.writeframes(pcm_data.tobytes())
    print(f"Synthesized and saved: {filepath} ({len(data)} samples, Stereo, 44100Hz, 16-bit PCM)")

def make_stereo_with_haas(mono_data, delay_ms=2.0, sample_rate=44100):
    """Converts mono data to stereo using the Haas effect for premium wide soundstage."""
    delay_samples = int(sample_rate * (delay_ms / 1000.0))
    stereo = np.zeros((len(mono_data), 2), dtype=np.float32)
    
    # Left channel: original signal
    stereo[:, 0] = mono_data
    
    # Right channel: delayed signal
    if delay_samples < len(mono_data):
        stereo[delay_samples:, 1] = mono_data[:-delay_samples]
    else:
        stereo[:, 1] = mono_data
        
    return stereo

def make_centered_stereo(mono_data):
    """Converts mono data to centered stereo (duplicated left and right channels)."""
    stereo = np.zeros((len(mono_data), 2), dtype=np.float32)
    stereo[:, 0] = mono_data
    stereo[:, 1] = mono_data
    return stereo

def generate_laser(sample_rate=44100):
    """Muffled dull cockpit thump from firing inside the vacuum, centered and click-free."""
    duration = 0.14
    num_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    
    # Deep chassis vibration sweep: 150 Hz down to 35 Hz
    phase = 2 * np.pi * (150 * t + 0.5 * (35 - 150) * t**2 / duration)
    vibration = np.sin(phase)
    
    # Add a bit of low-pass filtered structural rumble
    noise = np.random.normal(0, 0.4, num_samples)
    window_size = 28  # Heavy low-pass filtering for muffled sound
    rumble = np.convolve(noise, np.ones(window_size)/window_size, mode='same')
    
    # Combine vibration and rumble
    raw_thump = vibration * 0.7 + rumble * 0.3
    
    # Heavy exponential decay envelope to make it punchy
    env = np.exp(-24 * t)
    
    # Apply a fade-out envelope to ensure it drops to exactly 0 (prevents clicking)
    fade_len = int(num_samples * 0.15)
    fade = np.ones(num_samples)
    fade[-fade_len:] = np.linspace(1.0, 0.0, fade_len)
    
    mono_laser = raw_thump * env * fade
    return make_centered_stereo(mono_laser)

def generate_missile(sample_rate=44100):
    """Muffled structural rocket combustion roar inside the vacuum, centered and click-free."""
    duration = 0.40
    num_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    
    # Muffled rocket engine hum: low-mid pitch sweep (120 Hz down to 40 Hz)
    phase = 2 * np.pi * (120 * t + 0.5 * (40 - 120) * t**2 / duration)
    hum = np.sin(phase)
    
    # Engine white noise
    noise = np.random.normal(0, 0.4, num_samples)
    # Heavy low-pass filtering (window size 32) for deep muffled thrust roar
    window_size = 32
    rumble = np.convolve(noise, np.ones(window_size)/window_size, mode='same')
    
    # Envelope: quick linear rise, then gradual decay
    attack_samples = int(sample_rate * 0.05)
    env = np.ones(num_samples)
    env[:attack_samples] = np.linspace(0, 1.0, attack_samples)
    env[attack_samples:] = np.exp(-6.5 * (t[attack_samples:] - 0.05))
    
    # Apply fade-out to prevent clicks
    fade_len = int(num_samples * 0.15)
    fade = np.ones(num_samples)
    fade[-fade_len:] = np.linspace(1.0, 0.0, fade_len)
    
    mono_missile = (hum * 0.35 + rumble * 0.65) * env * fade
    return make_centered_stereo(mono_missile)

def generate_explosion(sample_rate=44100):
    """Massive, bass-heavy structural shockwave thud through the hull, centered and click-free."""
    duration = 0.85
    num_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    
    # Deep structural rumble: heavy low-pass filtered noise (window size 64)
    noise = np.random.normal(0, 0.9, num_samples)
    window_size = 64
    rumble = np.convolve(noise, np.ones(window_size)/window_size, mode='same')
    
    # Massive physical shockwave sine sweep: 75 Hz down to 20 Hz
    phase = 2 * np.pi * (75 * t + 0.5 * (20 - 75) * t**2 / duration)
    shockwave = np.sin(phase)
    
    # Envelope: instant attack, long deep decay
    env = np.exp(-4.2 * t)
    
    # Apply fade-out to prevent any end clicks
    fade_len = int(num_samples * 0.12)
    fade = np.ones(num_samples)
    fade[-fade_len:] = np.linspace(1.0, 0.0, fade_len)
    
    mono_explosion = (shockwave * 0.45 + rumble * 0.55) * env * fade
    return make_centered_stereo(mono_explosion)

def generate_shield_hit(sample_rate=44100):
    """Satisfying electromagnetic energy absorption thump (low-pitched muffled static surge)."""
    duration = 0.15
    num_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    
    # Low electromagnetic sweep (280 Hz down to 60 Hz) ring-modulated by 35 Hz
    carrier_phase = 2 * np.pi * (280 * t + 0.5 * (60 - 280) * t**2 / duration)
    carrier = np.sin(carrier_phase)
    modulator = np.sin(2 * np.pi * 35 * t)
    surge = carrier * modulator
    
    # Electromagnetic plasma static dissipation noise
    noise = np.random.normal(0, 0.35, num_samples)
    window_size = 20
    static = np.convolve(noise, np.ones(window_size)/window_size, mode='same')
    
    # Envelope
    env = np.exp(-18 * t)
    
    # Fade out
    fade_len = int(num_samples * 0.15)
    fade = np.ones(num_samples)
    fade[-fade_len:] = np.linspace(1.0, 0.0, fade_len)
    
    mono_shield = (surge * 0.65 + static * 0.35) * env * fade
    return make_centered_stereo(mono_shield)

def generate_armor_hit(sample_rate=44100):
    """Heavy direct hull impact thud (massive structural buckling thud), centered and click-free."""
    duration = 0.18
    num_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    
    # Massive hull vibration sweep: 100 Hz down to 25 Hz
    phase = 2 * np.pi * (100 * t + 0.5 * (25 - 100) * t**2 / duration)
    hull_vib = np.sin(phase)
    
    # Low structural crunch noise
    noise = np.random.normal(0, 0.45, num_samples)
    window_size = 24
    crunch = np.convolve(noise, np.ones(window_size)/window_size, mode='same')
    
    # Envelope
    env = np.exp(-15 * t)
    
    # Fade out
    fade_len = int(num_samples * 0.15)
    fade = np.ones(num_samples)
    fade[-fade_len:] = np.linspace(1.0, 0.0, fade_len)
    
    mono_armor = (hull_vib * 0.70 + crunch * 0.30) * env * fade
    return make_centered_stereo(mono_armor)

def generate_music_drone(sample_rate=44100):
    """
    Seamlessly loopable cinematic deep space drone.
    Harmonized multi-oscillator frequencies completing integer cycles over exactly 8 seconds.
    Modulated by loop-synchronized LFOs to create an evolving, immersive stereo soundscape.
    """
    duration = 8.0
    num_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    
    # Define exact frequencies that fit integer cycles in 8 seconds
    # (Cycles = Freq * 8: must be integer)
    # LFOs also fit integer cycles: 0.125 Hz (1 cycle), 0.25 Hz (2 cycles), 0.5 Hz (4 cycles)
    
    # Left channel synthesis
    l_osc1 = np.sin(2 * np.pi * 55.0 * t) * (0.35 + 0.12 * np.sin(2 * np.pi * 0.125 * t))
    l_osc2 = np.sin(2 * np.pi * 110.0 * t) * (0.22 + 0.08 * np.sin(2 * np.pi * 0.25 * t))
    l_osc3 = np.sin(2 * np.pi * 165.0 * t) * (0.15 + 0.05 * np.cos(2 * np.pi * 0.5 * t))
    l_osc4 = np.sin(2 * np.pi * 220.0 * t) * (0.10 + 0.04 * np.sin(2 * np.pi * 0.375 * t))
    l_osc5 = np.sin(2 * np.pi * 440.0 * t) * (0.04 + 0.02 * np.sin(2 * np.pi * 0.125 * t - np.pi/2))
    l_drone = l_osc1 + l_osc2 + l_osc3 + l_osc4 + l_osc5
    
    # Right channel synthesis (different LFO phase shifts for premium spatialized motion)
    r_osc1 = np.sin(2 * np.pi * 55.0 * t) * (0.35 + 0.12 * np.sin(2 * np.pi * 0.125 * t + np.pi/2))
    r_osc2 = np.sin(2 * np.pi * 110.0 * t) * (0.22 + 0.08 * np.sin(2 * np.pi * 0.25 * t - np.pi/4))
    r_osc3 = np.sin(2 * np.pi * 165.0 * t) * (0.15 + 0.05 * np.cos(2 * np.pi * 0.5 * t + np.pi))
    r_osc4 = np.sin(2 * np.pi * 220.0 * t) * (0.10 + 0.04 * np.sin(2 * np.pi * 0.375 * t + np.pi/2))
    r_osc5 = np.sin(2 * np.pi * 440.0 * t) * (0.04 + 0.02 * np.sin(2 * np.pi * 0.125 * t + np.pi/2))
    r_drone = r_osc1 + r_osc2 + r_osc3 + r_osc4 + r_osc5
    
    # Combine to stereo
    drone_stereo = np.column_stack((l_drone, r_drone))
    
    # Smooth envelope overlay to prevent tiny clicks at the wrap-around (crossfade window)
    fade_len = int(sample_rate * 0.05) # 50ms fade
    fade_in = np.linspace(0.0, 1.0, fade_len)
    fade_out = np.linspace(1.0, 0.0, fade_len)
    
    drone_stereo[:fade_len] *= fade_in[:, np.newaxis]
    drone_stereo[-fade_len:] *= fade_out[:, np.newaxis]
    
    # Re-apply matching crossfade blend of raw signal to make the fade completely silent/seamless
    loop_tail = drone_stereo[-fade_len:].copy()
    drone_stereo[:fade_len] += loop_tail * fade_out[:, np.newaxis]
    
    # Scale overall volume down to suitable background level
    return drone_stereo * 0.6

def main():
    print("Initializing procedural SFX generation...")
    
    # Generate all assets
    laser_data = generate_laser()
    missile_data = generate_missile()
    explosion_data = generate_explosion()
    shield_data = generate_shield_hit()
    armor_data = generate_armor_hit()
    bgm_data = generate_music_drone()
    
    # Save as WAV files in assets/sounds/
    save_wav("laser.wav", laser_data)
    save_wav("missile.wav", missile_data)
    save_wav("explosion.wav", explosion_data)
    save_wav("shield_hit.wav", shield_data)
    save_wav("armor_hit.wav", armor_data)
    save_wav("bgm_drone.wav", bgm_data)
    
    print("All audio assets synthesized successfully!")

if __name__ == "__main__":
    main()
