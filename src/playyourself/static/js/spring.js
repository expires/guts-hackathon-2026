// Tiny spring animator using Apple-style parameters (dampingRatio + response).
// Integrates per requestAnimationFrame, always continues from the live value,
// accepts an initial velocity and can be re-targeted mid-flight (velocity is kept).

export const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

export class Spring {
  constructor(value = 0, { dampingRatio = 1, response = 0.35, precision = 0.01, onUpdate, onRest } = {}) {
    this.x = value;
    this.v = 0;
    this.target = value;
    this.defaults = { dampingRatio, response };
    this.params = { ...this.defaults };
    this.precision = precision;
    this.onUpdate = onUpdate || (() => {});
    this.onRest = onRest || (() => {});
    this.raf = 0;
    this.last = 0;
    this._tick = this._tick.bind(this);
  }

  get value() {
    return this.x;
  }
  get velocity() {
    return this.v;
  }
  get running() {
    return this.raf !== 0;
  }

  // Jump to a value and stop (used while a finger is driving the value 1:1).
  set(value) {
    this.stop();
    this.x = this.target = value;
    this.v = 0;
    this.onUpdate(this.x);
  }

  // Animate (or re-target) towards `target`, starting from the current value and velocity.
  to(target, { velocity, dampingRatio, response } = {}) {
    if (velocity !== undefined) this.v = velocity;
    this.params = {
      dampingRatio: dampingRatio ?? this.defaults.dampingRatio,
      response: response ?? this.defaults.response,
    };
    this.target = target;
    if (!this.raf) {
      this.last = performance.now();
      this.raf = requestAnimationFrame(this._tick);
    }
    return this;
  }

  stop() {
    if (this.raf) cancelAnimationFrame(this.raf);
    this.raf = 0;
  }

  _tick(now) {
    const dt = Math.min((now - this.last) / 1000, 1 / 20);
    this.last = now;
    const { dampingRatio, response } = this.params;
    const k = (2 * Math.PI / response) ** 2; // stiffness for unit mass
    const c = 2 * dampingRatio * Math.sqrt(k); // damping coefficient
    const steps = Math.max(1, Math.ceil(dt * 240));
    const h = dt / steps;
    for (let i = 0; i < steps; i++) {
      this.v += (-k * (this.x - this.target) - c * this.v) * h;
      this.x += this.v * h;
    }
    if (Math.abs(this.x - this.target) < this.precision && Math.abs(this.v) < this.precision * 10) {
      this.x = this.target;
      this.v = 0;
      this.raf = 0;
      this.onUpdate(this.x);
      this.onRest();
      return;
    }
    this.onUpdate(this.x);
    this.raf = requestAnimationFrame(this._tick);
  }
}

// Where a flick would come to rest (px/s in, px out). Apple's exponential-decay form.
export function project(velocity, decelerationRate = 0.998) {
  return ((velocity / 1000) * decelerationRate) / (1 - decelerationRate);
}

// Progressive resistance past a boundary.
export function rubberband(overshoot, dimension, constant = 0.55) {
  return (overshoot * dimension * constant) / (dimension + constant * Math.abs(overshoot));
}
