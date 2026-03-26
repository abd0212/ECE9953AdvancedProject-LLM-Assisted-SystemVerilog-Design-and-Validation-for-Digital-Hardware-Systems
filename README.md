# LLM-Assisted SystemVerilog Design and Validation

**Course:** ECE9953 Advanced Project — Midterm Progress Report  
**Author:** Abdullah Syed (Asm908)  
**Date:** March 2026  
**Status:** Midterm checkpoint (Weeks 1–7 of 14)

---

## Project Summary

This project investigates the use of Large Language Models (LLMs) to assist and automate portions of SystemVerilog hardware design and verification. The framework generates RTL code, testbenches, and assertions from natural-language specifications, then evaluates correctness against human-written baselines using automated simulation.

---

## Midterm Scope

This submission covers the first seven weeks of the project, encompassing literature review, baseline implementations, the core LLM interface, simulation infrastructure, and initial generation experiments.

### Completed (Weeks 1–7)

| Week | Milestone | Status |
|------|-----------|--------|
| 1–2 | Literature review, problem selection, framework architecture | Done |
| 3–4 | Baseline RTL and testbenches for Traffic Light FSM and ALU | Done |
| 5–6 | LLM interface (Anthropic + OpenAI), prompt templates, RTL generation | Done |
| 7 | Simulation runner, iterative feedback loop, initial testbench generation | Done |

### Remaining (Weeks 8–14)

| Week | Milestone |
|------|-----------|
| 8 | FIFO and UART TX baseline designs |
| 9–10 | SVA assertion generation, bug injection framework |
| 11–12 | Cross-provider comparison (Claude vs GPT), advanced prompting |
| 13–14 | Full quantitative evaluation, visualization, final report |

---

## What's Included

```
llm-sv-midterm/
├── Makefile                           # Build and run targets
├── README.md                          # This file
├── requirements.txt                   # Python dependencies
├── .gitignore
├── configs/
│   └── experiment_config.json         # Experiment parameters
├── scripts/
│   ├── llm_interface.py               # LLM API wrapper (Claude + GPT)
│   ├── sim_runner.py                  # Icarus Verilog compilation + simulation
│   └── run_experiment.py              # Midterm experiment orchestrator
├── src/
│   ├── rtl/baseline/
│   │   ├── traffic_light_fsm.sv       # Baseline: Traffic light FSM controller
│   │   └── alu.sv                     # Baseline: 32-bit ALU with 10 operations
│   └── testbenches/baseline/
│       ├── traffic_light_fsm_tb.sv    # Self-checking FSM testbench
│       └── alu_tb.sv                  # Self-checking ALU testbench
└── docs/
    └── midterm_report.docx            # Midterm technical report
```

---

## Baseline Designs

Two of the four planned benchmark designs are complete:

### 1. Traffic Light FSM (`traffic_light_fsm.sv`)

A Mealy-type FSM with five states (RED, RED_YELLOW, GREEN, YELLOW, EMERGENCY). Features timer-based transitions, car sensor input that shortens the green phase, emergency vehicle override, and a pedestrian walk signal. The testbench verifies all state transitions, timer durations, sensor behavior, emergency override, and walk signal logic with 9 self-checking tests.

### 2. 32-bit ALU (`alu.sv`)

A combinational ALU supporting 10 operations: ADD, SUB, AND, OR, XOR, SLL, SRL, SRA, SLT (signed), and SLTU (unsigned). Includes overflow detection for signed arithmetic, carry-out, zero flag, and negative flag. The testbench covers all operations, edge cases (MAX_INT overflow, unsigned vs. signed comparison), and status flag verification with 18 self-checking tests.

---

## LLM Framework

### LLM Interface (`llm_interface.py`)

The LLM interface provides a unified Python API for generating SystemVerilog using either Anthropic Claude or OpenAI GPT. Key features:

- Structured prompt templates for RTL, testbench, and assertion generation
- System prompt establishing the LLM as an expert hardware designer with synthesis constraints
- Low temperature (0.2) for deterministic code output
- Automatic code extraction from LLM response markdown blocks
- Result saving with metadata (latency, model, iteration count)

### Simulation Runner (`sim_runner.py`)

The simulation runner wraps Icarus Verilog to provide automated compilation and simulation with result parsing:

- Compiles SystemVerilog with `-g2012 -Wall` flags
- Parses pass/fail counts from simulation output
- Captures compilation errors for the iterative feedback loop
- Supports both Icarus Verilog and Verilator (lint mode)
- Configurable timeout to prevent runaway simulations

### Iterative Feedback Loop

When LLM-generated code fails to compile, the framework automatically feeds the error messages back to the LLM and requests a corrected version, repeating up to 3 times. This mirrors how a human developer would use compiler output to fix errors.

---

## Setup and Running

### Prerequisites

```bash
# macOS
brew install icarus-verilog
pip install -r requirements.txt

# Ubuntu
sudo apt-get install iverilog
pip install -r requirements.txt
```

### Run baseline simulations (no API key needed)

```bash
make baseline
```

Expected output shows both designs compiling and all tests passing.

### Run LLM experiment

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
make experiment
```

This generates RTL and testbenches for both designs, compiles them, runs the iterative fix loop if needed, and tests the LLM RTL against the baseline testbenches.

---

## Preliminary Observations

Based on initial development and testing of the prompt templates:

1. **Port compatibility is the main first-pass failure mode.** LLMs sometimes rename ports or change widths despite explicit specifications. The structured prompt template significantly reduces this.

2. **Combinational designs (ALU) are easier than sequential (FSM).** The ALU's stateless nature means the LLM only needs to get the arithmetic right. FSMs require correct state encoding, transition logic, and timing — more opportunities for subtle errors.

3. **The iterative fix loop is effective for syntax errors** but less effective for semantic errors. If the LLM misunderstands the specification, feeding back "test failed" doesn't give enough context for correction.

4. **Low temperature is critical.** At temperature 0.7+, the LLM produces more varied but less reliable code. At 0.2, output is more conservative and compilable.

---

## Remaining Work

The second half of the project will:

- Add two more benchmark designs (FIFO, UART TX) to strengthen statistical conclusions
- Implement SVA assertion generation from natural-language properties
- Build a bug injection framework to quantify testbench quality
- Compare Claude vs GPT head-to-head on the same specifications
- Generate visualization charts (compilation rates, correctness, LOC comparison)
- Produce a full quantitative evaluation report

---

## References

1. IEEE, "IEEE Standard for SystemVerilog," IEEE Std 1800-2017.
2. M. Liu et al., "VerilogEval: Evaluating LLMs for Verilog Code Generation," ICCAD 2023.
3. Y. Lu et al., "RTLLM: An Open-Source Benchmark for Design RTL Generation," ASP-DAC 2024.
4. Anthropic, "Claude API Documentation," https://docs.anthropic.com.
5. S. Williams, "Icarus Verilog," https://steveicarus.github.io/iverilog/.
