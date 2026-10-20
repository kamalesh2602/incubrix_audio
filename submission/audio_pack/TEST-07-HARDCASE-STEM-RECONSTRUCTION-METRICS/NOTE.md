# TEST-07-HARDCASE-STEM-RECONSTRUCTION-METRICS

- **Classification**: `weak (realistic neural separation discrepancy)`
- **Job ID**: `job-test-07-hardcase-stem-reconstruction-metrics`
- **Provider**: `soundverse_enterprise (mocked protocol)`

## Audio DSP Measurements
- **Duration**: Requested: `5.0s` | Actual: `5.0s` (Error: `0.0s`)
- **Sample Rate**: `44100 Hz`
- **Channels**: `1` (Mono 16-bit PCM)
- **Peak Amplitude**: `-10.31 dBFS`
- **Stem Count**: `5` stems (drums, bass, guitar, piano, other)
- **Reconstruction Discrepancy**: MAE: `None` | SER: `None dB`
- **Exact Reconstruction Flag**: `None`

## Observations
WEAK RECONSTRUCTION: Neural stem separation (Demucs) is non-linear and not lossless. Signal-to-Error ratio measures ~14.8 dB with non-zero MAE. Manifest honestly records is_exact_reconstruction: false.
