# Sample data for a live demo

Small, ready-to-upload CSVs so you can try the actual `/upload` -> train -> `/predict` flow
without downloading the full source datasets first. Both are real data (not synthetic),
downsampled to train quickly on a CPU for a live walkthrough.

- **`mitbih_207_sample.csv`** — 10,000 raw signal samples (`signal` column only, no label)
  from MIT-BIH Arrhythmia Database record 207. Upload it, let the router pick an algorithm
  (it will choose the LSTM Autoencoder — the signal has strong autocorrelation and a periodic
  PQRST pattern), train, then upload a second slice of the same file to `/predict` and watch
  it get scored against the calibrated threshold. Source: PhysioNet MIT-BIH Arrhythmia
  Database [16].

- **`nab_ec2_cpu_sample.csv`** — one full NAB (Numenta Anomaly Benchmark) series,
  `ec2_cpu_utilization_24ae8d` (4,032 rows, `timestamp,value`). Upload it to see the router
  pick an algorithm for a very different kind of signal (infrastructure metric with daily/
  weekly seasonality rather than a biological rhythm). Source: NAB, Apache 2.0 licensed [17].

Both files are small excerpts kept for educational/demonstration purposes as part of this
thesis project, with the original datasets cited in the root README and in the thesis
Literature section.
