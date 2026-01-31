# UPS Harmonics & Power Quality Analyzer

Engineering-focused tool to analyze harmonics, THD, power factor,
and IEEE-519-style compliance risks in data centers with heavy UPS and rectifier loads.

## Goals
- Model nonlinear UPS current waveforms (UPS/rectifier harmonic spectra + time-domain synthesis)
- Compute THD, individual harmonics, distortion PF, true PF
- Evaluate IEEE-519-style compliance at the PCC (Isc/IL current limits)
- Assess transformer/cable heating risk from harmonic currents
- Compare mitigation strategies (filters, UPS topology, source strength)

## Philosophy
Engine-first development:
- Build a correct analysis engine with stable JSON I/O
- Add CLI and report generation
- Add web UI after the engine outputs are stable

## Status
🚧 Initial scaffolding
