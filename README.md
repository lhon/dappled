# dappled

Dappled is an open source project for building and running deployable Jupyter notebooks.

It allows data scientists to easily deploy and share custom data analyses, and collaborators to reuse, reproduce, and customize these analyses in a user friendly manner.

A Dappled notebook bundles software dependencies and customizable parameters together with analysis, which can then be deployed anywhere, whether it be a laptop, server, or the cloud.

Dappled can be used for:

- sharing and collaboration of reproducible analysis workflows
- creating and deploying browser-based self-service data analysis tools
- scaling up data analyses onto larger machines and the cloud

## Getting Started

### Mac and Linux

Install the `dappled` tool by running this:

```
curl https://raw.githubusercontent.com/lhon/dappled/master/install.sh | bash
```

### Windows

To install the `dappled` tool, download [this archive](https://raw.githubusercontent.com/lhon/dappled/master/install-win.zip) and run the batch script inside.

### Conda

If you already have [conda](https://github.com/conda/conda) installed, run this:

```
conda install dappled -c http://conda.dappled.io
```

## Example Usage

To run the notebook published at [https://dappled.io/dappled/hello](https://dappled.io/dappled/hello):

```
dappled run dappled/hello
```

To download the notebook and its corresponding `dappled.yml`:

```
dappled clone dappled/hello
```

View other available options using `dappled -h`.

## Other Notebooks

To get a fuller flavor of what's possible, here are a couple more notebooks to try:

* Besides python as the default language, notebooks can use [bash](https://dappled.io/lhon/7mkz3r/bash-kernel-demo) and [R](https://dappled.io/lhon/2zq76p/r-maps) as the primary language ("kernel" in Jupyter-speak).
* A basic bioinformatics example [determining the QV encoding](https://dappled.io/lhon/3jg5m6/fastq-qv-encoding-report) of some fastq data
* A more elaborate bioinformatics [*de novo* assembly example](https://dappled.io/lhon/68qe98/canu), which has some python-based visualization plus running Canu (written in perl/java/C).

## Licensing

Dappled is licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE) for the full license text.


