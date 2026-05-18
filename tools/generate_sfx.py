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

def generate_laser(sample_rate=44100):
    """Muffled dull cockpit thud from firing inside the vacuum, centered and click-free."""
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
    
    # Distribute mono signal equally to both stereo channels (perfect centered thump, no phase/delay mismatch click)
    stereo = np.zeros((len(mono_laser), 2), dtype=np.float32)
    stereo[:, 0] = mono_laser
    stereo[:, 1] = mono_laser
    return stereo

def generate_missile(sample_rate=44100):
    """Combines a rising engine whine with low-frequency thruster roar/rumble."""
    duration = 0.40
    num_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    
    # Rising whine frequency sweep: 80 Hz up to 350 Hz
    phase = 2 * np.pi * (80 * t + 0.5 * (350 - 80) * t**2 / duration)
    whine = np.sin(phase)
    
    # Engine white noise
    noise = np.random.normal(0, 0.4, num_samples)
    # Low-pass filter the noise using a running average (window size 20) for bass rumble
    window_size = 20
    rumble = np.convolve(noise, np.ones(window_size)/window_size, mode='same')
    
    # Envelope: quick linear rise, then gradual decay
    attack_samples = int(sample_rate * 0.05)
    env = np.ones(num_samples)
    env[:attack_samples] = np.linspace(0, 1.0, attack_samples)
    env[attack_samples:] = np.exp(-5.0 * (t[attack_samples:] - 0.05))
    
    mono_missile = (whine * 0.35 + rumble * 0.65) * env
    return make_stereo_with_haas(mono_missile, delay_ms=2.5)

def generate_explosion(sample_rate=44100):
    """Bass-heavy low-pass filtered brown-esque noise explosion."""
    duration = 0.85
    num_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    
    # White noise
    noise = np.random.normal(0, 0.8, num_samples)
    # Heavy low-pass filtering (running average window of 40 samples) to create a massive boom
    window_size = 40
    boom = np.convolve(noise, np.ones(window_size)/window_size, mode='same')
    
    # Rapid attack (0.005s) and slow exponential decay
    attack_samples = int(sample_rate * 0.005)
    env = np.ones(num_samples)
    env[:attack_samples] = np.linspace(0, 1.0, attack_samples)
    env[attack_samples:] = np.exp(-4.5 * (t[attack_samples:] - 0.005))
    
    mono_explosion = boom * env
    # Spatialise with delay for a wide cinematic blast field
    return make_stereo_with_haas(mono_explosion, delay_ms=4.0)

def generate_shield_hit(sample_rate=44100):
    """High-frequency energetic metallic shield ping using ring-modulation."""
    duration = 0.12
    num_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    
    # High-pitch carrier wave (2400 Hz) multiplied by modulator wave (160 Hz)
    carrier = np.sin(2 * np.pi * 2400 * t)
    modulator = np.sin(2 * np.pi * 160 * t)
    ping = carrier * modulator
    
    # Rapid decay envelope
    env = np.exp(-22 * t)
    mono_shield = ping * env
    return make_stereo_with_haas(mono_shield, delay_ms=1.0)

def generate_armor_hit(sample_rate=44100):
    """Metallic dull hull impact thud."""
    duration = 0.18
    num_samples = int(sample_rate * duration)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    
    # Hull frequency sweep: 180 Hz down to 55 Hz
    phase = 2 * np.pi * (180 * t + 0.5 * (55 - 180) * t**2 / duration)
    metallic = np.sin(phase)
    
    # Add a bit of low-pass noise for the crunch of impact
    noise = np.random.normal(0, 0.3, num_samples)
    window_size = 12
    crunch = np.convolve(noise, np.ones(window_size)/window_size, mode='same')
    
    # Envelope
    env = np.exp(-14 * t)
    mono_armor = (metallic * 0.75 + crunch * 0.25) * env
    return make_stereo_with_haas(mono_armor, delay_ms=2.0)

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
