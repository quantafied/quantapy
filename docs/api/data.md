# Data API

The data layer separates computation from storage. Providers and transformers
return named outputs first. Data is committed to the lineage-aware store only
when calling `DataStore.add_raw()` or `DataStore.add_child()`.

## `Data`

Location: `quantapy.orchestrator.data.Data`

Primary methods:

- `add_provider(category, name, source, **kwargs)`: register a provider from the component registry.
- `add_transformer(category, name, source, **kwargs)`: register a transformer from the component registry.
- `fetch()`: execute registered providers and return `{dataset_name: data}`.
- `transform(dataset_name, data, transformer_name=None)`: execute transformers and return `{output_name: data}`.
- `ingest(name, data)`: wrap manually supplied data as `{name: data}`.

## `DataStore`

Location: `quantapy.core.timeseries.DataStore`

The store keeps committed datasets plus lineage metadata.

Common methods:

- `add_raw(name, data, **metadata)`: add a root dataset.
- `add_child(name, data, parent_ids, kind="derived", **metadata)`: add a derived child dataset.
- `get(name)`: return a `TimeSeries`.
- `get_record(id_or_name)`: return the metadata record.
- `raw()`, `synthetic()`, `derived()`: return filtered record views.
- `parents(id_or_name)`, `children(id_or_name)`: inspect lineage.
- `lineage(id_or_name)`: return a small lineage summary.
- `remove(name, cascade=False)`: remove a dataset, optionally removing children.
- `mark_stale(id_or_name, recursive=True)`: mark downstream data as stale.

## `TimeSeries`

Location: `quantapy.core.timeseries.TimeSeries`

Columnar NumPy-backed time series container with schema metadata.

Common methods:

- `from_dataframe(df)`: create from a pandas DataFrame.
- `from_dict_list(records)`: create from provider-style records.
- `to_dataframe()`: materialize as a DataFrame.
- `append(other)`: append another compatible `TimeSeries`.
- `slice(start, end)`: return a row slice.

