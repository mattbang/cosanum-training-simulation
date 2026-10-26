# Cosanum Training Operations Simulator

**Language:** English · [Deutsch](README.de.md)

[Read the portfolio case study](https://matthew-bangle-data-portfolio.mattbangle.chatgpt.site/work/logistics-training-simulation) · [Explore the interactive results](https://matthew-bangle-data-portfolio.mattbangle.chatgpt.site/examples/training-simulation/index.html?lang=en)

A Python discrete-event simulation and results explorer developed during the ZHAW CAS Process Digitalization project on logistics training at Cosanum. I built the model and local dashboard to test process rules, self-study and training capacity before treating them as implementation decisions.

**Main finding:** individual practice remains the bottleneck in this model. Across 50 paired synthetic annual demand fixtures, adding a second qualified practice coach and place changes mean full completions from 312.96 to 348.72. This is a model comparison, not an observed operating improvement.

## What is included

- One Python engine, version 0.10.0, with compatible-topic queues, original waiting deadlines, theory-before-practice rules, constrained calendars and separate competence/documentation outcomes.
- A local dashboard, version 0.3.0, that runs new paired experiments and exports their inputs, events, metrics and hashes.
- An English/German static results explorer in [site/](site/), with saved comparisons, a capacity frontier and an interactive 51-factor sensitivity screen.
- Anonymized topic labels, aggregate inputs and synthetic demand. No employee records, original source documents or private repository history are included.

## Saved comparison

All four options use the same 50 annual demand fixtures and 350 assumed person-topic-cycle cases over 365 days. A case is one person's training need for one topic and cycle, not a distinct employee.

| Model option | Mean full completions | Fixtures clearing all 350 cases |
| --- | ---: | ---: |
| Current process (IST) | 310.22 | 1 / 50 |
| Combined proposed process (SOLL) | 312.96 | 3 / 50 |
| SOLL + LMS prepared by a separate project team | 313.50 | 3 / 50 |
| SOLL + second qualified practice coach and place | 348.72 | 46 / 50 |

The LMS and extra-coach options are separate branches from SOLL. The extra-coach option excludes a full additional salary, recruitment and qualification costs, so completions alone do not establish a staffing business case.

The separate sensitivity screen covers 51 factors, two settings, five paired fixtures and four policies: 2,060 conditional outputs including baselines. Those outputs are not independent replications or a reliable ranking of policies. See [method and provenance](docs/METHOD.md).

## Run locally

Python 3.9 or later is sufficient; the engine and dashboard need no third-party packages. Run these commands from the repository root.

**Interactive results explorer** — displays the frozen study results:

```sh
python3 -m http.server 8767 --directory site --bind 127.0.0.1
```

Open [localhost:8767](http://127.0.0.1:8767/). The header switches between English and German.

**Local dashboard** — runs new synthetic experiments:

```sh
python3 dashboard/app.py
```

The launcher opens a loopback-only browser session. New experiments are written to the ignored `local-experiments/` directory.

**Reproducible small workflow** — use a new output directory each time:

```sh
PYTHONPATH=src python3 -m cosanum_sim.cli --full-workflow --output local-runs/example-1
```

**Verification:**

```sh
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src:dashboard python3 -m unittest discover -s dashboard/tests -v
python3 dashboard/app.py --self-test
```

The exported package passes 85 engine tests, 18 dashboard tests and the dashboard self-test. See [validation](docs/VALIDATION.md) for the tested environments and export checks.

## Evidence boundary and implementation

Saved study projections are frozen, with their original source hashes. New public-package runs carry their own inputs and code hashes; a successful smoke test does not recreate or revalidate the historical study. The archived source tables behind the static explorer are not included, so its aggregate assets cannot be rebuilt from this repository alone. The local dashboard can run new comparisons from the included anonymized fixture.

The inputs mix source-derived aggregates, reported estimates and explicit assumptions. They are not a calibrated operational forecast. Costs represent modelled effort, not measured cash savings.

Automated scheduling and digital certification are a separate work-in-progress extension in [cosanum-automation](https://github.com/mattbang/cosanum-automation). An e-learning platform is being evaluated. The completed simulation should not be mistaken for a production training system.

Source is public for portfolio review. This export adds no new licence grant. Source-derived inputs and frozen results retain their attribution; see [data provenance](docs/DATA_PROVENANCE.md).
