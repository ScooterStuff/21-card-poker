// Tiny Web Audio FX engine — no asset files, all synthesized.

class Sound {
  constructor() {
    this.enabled = true;
    this.ctx = null;
    this.master = null;
  }
  setEnabled(v) {
    this.enabled = !!v;
    try { localStorage.setItem("poker.sound", this.enabled ? "1" : "0"); } catch {}
  }
  loadPref() {
    try {
      const v = localStorage.getItem("poker.sound");
      if (v !== null) this.enabled = v === "1";
    } catch {}
    return this.enabled;
  }
  _ensure() {
    if (this.ctx) return;
    const AC = window.AudioContext || window.webkitAudioContext;
    if (!AC) return;
    this.ctx = new AC();
    this.master = this.ctx.createGain();
    this.master.gain.value = 0.35;
    this.master.connect(this.ctx.destination);
  }
  resume() {
    this._ensure();
    if (this.ctx && this.ctx.state === "suspended") this.ctx.resume();
  }
  _tone({ freq = 440, dur = 0.15, type = "sine", gain = 0.4, attack = 0.005, release = 0.08, slideTo = null }) {
    if (!this.enabled) return;
    this._ensure();
    if (!this.ctx) return;
    const t = this.ctx.currentTime;
    const osc = this.ctx.createOscillator();
    const g = this.ctx.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, t);
    if (slideTo) osc.frequency.exponentialRampToValueAtTime(slideTo, t + dur);
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(gain, t + attack);
    g.gain.exponentialRampToValueAtTime(0.001, t + dur + release);
    osc.connect(g).connect(this.master);
    osc.start(t);
    osc.stop(t + dur + release + 0.05);
  }
  _noise({ dur = 0.08, gain = 0.25, freq = 1500 }) {
    if (!this.enabled) return;
    this._ensure();
    if (!this.ctx) return;
    const t = this.ctx.currentTime;
    const buf = this.ctx.createBuffer(1, Math.floor(this.ctx.sampleRate * dur), this.ctx.sampleRate);
    const data = buf.getChannelData(0);
    for (let i = 0; i < data.length; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / data.length);
    const src = this.ctx.createBufferSource();
    src.buffer = buf;
    const filt = this.ctx.createBiquadFilter();
    filt.type = "bandpass";
    filt.frequency.value = freq;
    const g = this.ctx.createGain();
    g.gain.setValueAtTime(gain, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + dur);
    src.connect(filt).connect(g).connect(this.master);
    src.start(t);
    src.stop(t + dur);
  }

  // Game events
  deal()  { this._noise({ dur: 0.06, gain: 0.18, freq: 2200 }); }
  click() { this._tone({ freq: 520, dur: 0.04, type: "square", gain: 0.18, release: 0.04 }); }
  check() { this._tone({ freq: 360, dur: 0.08, type: "triangle", gain: 0.22 }); }
  call()  { this._tone({ freq: 440, dur: 0.1, type: "triangle", gain: 0.26 });
            setTimeout(() => this._tone({ freq: 660, dur: 0.1, type: "triangle", gain: 0.22 }), 80); }
  raise() { this._tone({ freq: 320, dur: 0.18, type: "sawtooth", gain: 0.22, slideTo: 760 }); }
  fold()  { this._tone({ freq: 220, dur: 0.25, type: "sine", gain: 0.25, slideTo: 90 }); }
  chip()  { this._tone({ freq: 880, dur: 0.05, type: "square", gain: 0.18 });
            setTimeout(() => this._tone({ freq: 1320, dur: 0.05, type: "square", gain: 0.14 }), 35); }
  win() {
    [523, 659, 784, 1046].forEach((f, i) =>
      setTimeout(() => this._tone({ freq: f, dur: 0.18, type: "triangle", gain: 0.3 }), i * 90));
  }
  lose() {
    [392, 330, 262].forEach((f, i) =>
      setTimeout(() => this._tone({ freq: f, dur: 0.22, type: "sine", gain: 0.28 }), i * 130));
  }
  tie() {
    this._tone({ freq: 523, dur: 0.18, type: "triangle", gain: 0.26 });
    setTimeout(() => this._tone({ freq: 523, dur: 0.18, type: "triangle", gain: 0.22 }), 180);
  }
  start() {
    [523, 784].forEach((f, i) =>
      setTimeout(() => this._tone({ freq: f, dur: 0.12, type: "triangle", gain: 0.3 }), i * 90));
  }
}

export const sound = new Sound();
