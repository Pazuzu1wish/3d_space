#!/usr/bin/env python3
import os
import wave
import pyttsx3
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

def generate_laser_strained(sample_rate=44100):
    """Labored, heat-stressed cockpit thump — gun struggling above 75% heat.
    
    Differences from normal:
      - Higher freq sweep (200→80 Hz): more metallic resonance, less deep thud
      - Slower decay: gun is working harder, sound lingers
      - Mid-pass noise (not muffled): thermal stress = higher-freq structural noise
      - Soft harmonic clip: adds odd-order distortion, that 'strained' edge
      - Flutter envelope: 3 slight dips mimicking heat-stutter/cycling
      - Slightly longer duration: the firing cycle is slower under load
    """
    duration = 0.22
    num_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, num_samples, endpoint=False)

    # Metallic sweep: 200 Hz down to 80 Hz (higher than normal, less bass)
    phase = 2 * np.pi * (200 * t + 0.5 * (80 - 200) * t**2 / duration)
    vibration = np.sin(phase)

    # Add a second harmonic at 3x (odd harmonic = more gritty/strained)
    phase3 = 2 * np.pi * (600 * t + 0.5 * (240 - 600) * t**2 / duration)
    vibration = vibration * 0.75 + np.sin(phase3) * 0.25

    # Mid-pass filtered noise (thermal stress is NOT muffled — it's higher-freq)
    noise = np.random.normal(0, 0.35, num_samples)
    lp_window = 8   # lighter low-pass = more midrange present
    rumble = np.convolve(noise, np.ones(lp_window)/lp_window, mode='same')

    raw = vibration * 0.65 + rumble * 0.35

    # Soft harmonic clip: rounds the peaks without hard limiting
    # Creates odd-order distortion (tanh shape) — sounds "worked" and hot
    drive = 2.2
    raw = np.tanh(raw * drive) / np.tanh(drive)

    # Slower decay — gun is laboring
    env = np.exp(-14 * t)

    # Flutter: 3 brief amplitude dips at ~20ms intervals simulating heat-cycle stutter
    flutter = np.ones(num_samples)
    for dip_t in [0.04, 0.08, 0.13]:
        dip_center = int(dip_t * sample_rate)
        dip_width = int(0.008 * sample_rate)  # 8ms dip
        start = max(0, dip_center - dip_width // 2)
        end = min(num_samples, dip_center + dip_width // 2)
        dip_env = np.hanning(end - start) * 0.35  # depth of the dip
        flutter[start:end] -= dip_env

    # Click-prevention fade
    fade_len = int(num_samples * 0.12)
    fade = np.ones(num_samples)
    fade[-fade_len:] = np.linspace(1.0, 0.0, fade_len)

    mono_laser = raw * env * flutter * fade
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
    fade_len = int(sample_rate * 0.05) # 50ms fade
    total_samples = num_samples + fade_len
    t = np.linspace(0, total_samples / sample_rate, total_samples, endpoint=False)
    
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
    fade_in = np.linspace(0.0, 1.0, fade_len)
    fade_out = np.linspace(1.0, 0.0, fade_len)
    
    # Extract the main loop sound
    loop_drone = drone_stereo[:num_samples].copy()
    
    # Crossfade the extra trailing tail into the beginning
    loop_drone[:fade_len] = drone_stereo[:fade_len] * fade_in[:, np.newaxis] + drone_stereo[num_samples:num_samples+fade_len] * fade_out[:, np.newaxis]
    
    # Scale overall volume down to suitable background level
    return loop_drone * 0.6

def generate_engine_hum(base_freq, sample_rate=44100):
    """
    Continuous low-frequency hum for the player's ship engine.
    Designed to be played in a loop, with its volume dynamically modulated by thrust state.
    """
    duration = 2.0  # 2 seconds loop
    num_samples = int(sample_rate * duration)
    fade_len = int(sample_rate * 0.05)
    total_samples = num_samples + fade_len
    t = np.linspace(0, total_samples / sample_rate, total_samples, endpoint=False)
    
    # Deep base sub-bass engine frequency: base_freq Hz
    hum1 = np.sin(2 * np.pi * base_freq * t)
    
    # Higher harmonic for character: base_freq * 2 Hz
    hum2 = np.sin(2 * np.pi * (base_freq * 2) * t) * 0.4
    
    # Very low filtered structural rumble
    noise = np.random.normal(0, 0.3, total_samples)
    window_size = 48
    rumble = np.convolve(noise, np.ones(window_size)/window_size, mode='same')
    
    # Combine for a steady, continuous drone
    mono_hum = (hum1 * 0.5 + hum2 * 0.3 + rumble * 0.2)
    
    # Make it a perfect loop: sine waves align perfectly, crossfade the noise rumble
    fade_in = np.linspace(0.0, 1.0, fade_len)
    fade_out = np.linspace(1.0, 0.0, fade_len)
    
    # Extract the main loop sound
    loop_hum = mono_hum[:num_samples].copy()
    
    # Crossfade the extra trailing tail into the beginning
    loop_hum[:fade_len] = mono_hum[:fade_len] * fade_in + mono_hum[num_samples:num_samples+fade_len] * fade_out
    
    return make_centered_stereo(loop_hum * 0.4)

def main():
    print("Initializing procedural SFX generation...")
    
    # Generate all assets
    laser_data = generate_laser()
    laser_strained_data = generate_laser_strained()
    missile_data = generate_missile()
    explosion_data = generate_explosion()
    shield_data = generate_shield_hit()
    armor_data = generate_armor_hit()
    #bgm_data = generate_music_drone() # not used anymore
    
    # Generate multiple engine hum layers for dynamic pitch crossfading
    engine_hum_low = generate_engine_hum(25)
    engine_hum_mid = generate_engine_hum(27)
    engine_hum_high = generate_engine_hum(30)
    engine_hum_overdrive = generate_engine_hum(33)
    engine_hum_data = generate_engine_hum(35) # Original/fallback
    
    # Save as WAV files in assets/sounds/
    save_wav("laser.wav", laser_data)
    save_wav("laser_strained.wav", laser_strained_data)
    save_wav("missile.wav", missile_data)
    save_wav("explosion.wav", explosion_data)
    save_wav("shield_hit.wav", shield_data)
    save_wav("armor_hit.wav", armor_data)
    #save_wav("bgm_drone.wav", bgm_data) not used anymore
    save_wav("engine_hum.wav", engine_hum_data)
    save_wav("engine_hum_low.wav", engine_hum_low)
    save_wav("engine_hum_mid.wav", engine_hum_mid)
    save_wav("engine_hum_high.wav", engine_hum_high)
    save_wav("engine_hum_overdrive.wav", engine_hum_overdrive)
    
    print("All audio assets synthesized successfully!")

if __name__ == "__main__":
    main()
