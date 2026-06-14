# Quantapy Artifact Import Samples

Use these files to test artifact import from the GUI or Python scripts.

Suggested GUI tests:

1. Open **Data -> Registered Data Source**.
2. Choose `Dataset` / `Artifact` / `Local`.
3. Use `sample_artifacts/ohlc_sample.csv`, `sample_artifacts/points.json`, `sample_artifacts/forces.dat`, or the whole `sample_artifacts` folder.
4. Click **Fetch Data**.

The importer registers raw file artifacts and parses supported table-like files into normal DataStore records that can be plotted, transformed, and used as simulator inputs.
