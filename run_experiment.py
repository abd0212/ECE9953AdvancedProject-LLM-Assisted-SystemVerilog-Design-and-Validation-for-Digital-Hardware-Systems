#!/usr/bin/env python3
"""
run_experiment.py - Midterm Experiment Runner

Current scope (Weeks 1-7):
  - Baseline RTL and testbench validation (traffic_light_fsm, alu)
  - LLM-generated RTL for both designs
  - Compilation testing with iterative feedback loop
  - Initial testbench generation

Remaining for final submission (Weeks 8-14):
  - FIFO and UART TX designs
  - Assertion generation (SVA)
  - Bug injection and testbench quality evaluation
  - Cross-provider comparison (Claude vs GPT)
  - Full quantitative report with charts

Usage:
    python run_experiment.py --provider anthropic --designs all
    python run_experiment.py --baseline-only
"""

import argparse
import json
import os
import sys
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from llm_interface import LLMInterface, LLMProvider, GenerationType
from sim_runner import SimRunner, Simulator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('experiment.log')
    ]
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ===== Design Specifications (Midterm: 2 of 4 designs) =====

DESIGN_SPECS = {
    "traffic_light_fsm": {
        "category": "fsm",
        "description": "A Mealy-type FSM controlling a traffic light intersection with "
                       "states RED, RED_YELLOW, GREEN, YELLOW, and EMERGENCY. Includes "
                       "timer-based transitions, car sensor input, and emergency override.",
        "interface": """
    input  logic       clk,
    input  logic       rst_n,
    input  logic       sensor,      // Car sensor on side road
    input  logic       emergency,   // Emergency vehicle override
    output logic [2:0] light,       // {red, yellow, green}
    output logic       walk_signal  // Pedestrian walk signal
        """,
        "requirements": """
1. Start in RED state after reset
2. Cycle: RED -> RED_YELLOW -> GREEN -> YELLOW -> RED
3. Each state has a timer-based duration (RED=100, RED_YELLOW=20, GREEN=80, YELLOW=30 cycles)
4. Sensor input can shorten GREEN phase (after 50% of green time)
5. Emergency input immediately forces transition to a safe RED state
6. Walk signal active only during RED phase (after initial delay, before end)
7. Walk signal disabled during emergency
        """,
        "baseline_rtl": os.path.join(PROJECT_ROOT, "src/rtl/baseline/traffic_light_fsm.sv"),
        "baseline_tb": os.path.join(PROJECT_ROOT, "src/testbenches/baseline/traffic_light_fsm_tb.sv"),
    },
    "alu": {
        "category": "datapath",
        "description": "A 32-bit ALU supporting arithmetic (ADD, SUB), logical (AND, OR, XOR), "
                       "shift (SLL, SRL, SRA), and comparison (SLT, SLTU) operations with "
                       "overflow detection and status flags.",
        "interface": """
    input  logic [31:0]  operand_a,
    input  logic [31:0]  operand_b,
    input  logic [3:0]   alu_op,
    output logic [31:0]  result,
    output logic         zero,
    output logic         overflow,
    output logic         carry_out,
    output logic         negative
        """,
        "requirements": """
1. Support 10 operations: ADD(0000), SUB(0001), AND(0010), OR(0011), XOR(0100),
   SLL(0101), SRL(0110), SRA(0111), SLT(1000), SLTU(1001)
2. ADD and SUB must detect signed overflow
3. ADD and SUB must produce carry_out
4. SRA must sign-extend (arithmetic shift)
5. SLT compares as signed, SLTU as unsigned
6. Zero flag set when result is 0, negative flag = MSB of result
7. Shift amount taken from lower 5 bits of operand_b
        """,
        "baseline_rtl": os.path.join(PROJECT_ROOT, "src/rtl/baseline/alu.sv"),
        "baseline_tb": os.path.join(PROJECT_ROOT, "src/testbenches/baseline/alu_tb.sv"),
    },
}


def run_baseline_only(design_names: list[str], results_dir: str):
    """Compile and simulate baseline (human-written) designs."""
    sim = SimRunner(Simulator.IVERILOG, work_dir=os.path.join(results_dir, "sim_work"))

    logger.info("=" * 60)
    logger.info("BASELINE VALIDATION RUN")
    logger.info("=" * 60)

    results = {}
    for name in design_names:
        spec = DESIGN_SPECS[name]
        logger.info(f"\n--- {name} ({spec['category']}) ---")

        sources = [spec["baseline_rtl"], spec["baseline_tb"]]
        run = sim.run_full(sources, name)
        sim.save_results(run, results_dir)

        results[name] = {
            "compiles": run.compilation.success,
            "compile_time_ms": run.compilation.compile_time_ms,
        }

        if run.compilation.success:
            logger.info(f"  Compilation: OK ({run.compilation.compile_time_ms:.0f}ms)")
        else:
            logger.error(f"  Compilation: FAILED\n{run.compilation.errors}")

        if run.simulation:
            results[name]["sim_success"] = run.simulation.success
            results[name]["tests_passed"] = run.simulation.tests_passed
            results[name]["tests_failed"] = run.simulation.tests_failed
            logger.info(f"  Simulation: {'PASS' if run.simulation.success else 'FAIL'}")
            logger.info(f"  Tests: {run.simulation.tests_passed} passed, "
                        f"{run.simulation.tests_failed} failed")

    # Save summary
    summary_path = os.path.join(results_dir, "baseline_results.json")
    with open(summary_path, 'w') as f:
        json.dump(results, f, indent=2)
    logger.info(f"\nBaseline results saved: {summary_path}")


def run_llm_experiment(design_names: list[str], provider: LLMProvider,
                       model: str, results_dir: str, max_fix_iters: int = 3):
    """Run LLM generation + compilation experiment (midterm scope)."""
    llm = LLMInterface(provider=provider, model=model)
    sim = SimRunner(Simulator.IVERILOG, work_dir=os.path.join(results_dir, "sim_work"))

    logger.info("=" * 60)
    logger.info(f"LLM EXPERIMENT: provider={provider.value}, model={model}")
    logger.info(f"Designs: {design_names}")
    logger.info("=" * 60)

    results = {}

    for name in design_names:
        spec = DESIGN_SPECS[name]
        logger.info(f"\n{'='*50}")
        logger.info(f"Design: {name} ({spec['category']})")
        logger.info(f"{'='*50}")

        design_results = {"category": spec["category"]}
        start = time.time()

        # --- Phase 1: Generate RTL ---
        logger.info("\n[Phase 1] Generating RTL from specification...")
        rtl_result = llm.generate_rtl(
            module_name=name,
            description=spec["description"],
            interface=spec["interface"],
            requirements=spec["requirements"],
        )
        rtl_dir = os.path.join(PROJECT_ROOT, "src/rtl/llm_generated")
        os.makedirs(rtl_dir, exist_ok=True)
        rtl_path = llm.save_result(rtl_result, rtl_dir)

        design_results["rtl_generated"] = rtl_result.success
        design_results["rtl_latency_ms"] = rtl_result.latency_ms
        design_results["rtl_loc"] = len(rtl_result.code.splitlines()) if rtl_result.code else 0

        # --- Phase 2: Compile RTL ---
        logger.info("\n[Phase 2] Compiling LLM-generated RTL...")
        comp = sim.compile([rtl_path], name, f"{name}_rtl_check")
        iterations_used = 0

        if not comp.success:
            logger.info(f"  First-pass compile FAILED. Entering fix loop...")
            for i in range(max_fix_iters):
                logger.info(f"  Fix iteration {i + 1}/{max_fix_iters}...")
                fix = llm.iterative_fix(name, rtl_result.code, comp.errors)
                if fix.success and fix.code:
                    rtl_result = fix
                    rtl_path = llm.save_result(fix, rtl_dir)
                    comp = sim.compile([rtl_path], name, f"{name}_fix{i}")
                    iterations_used += 1
                    if comp.success:
                        logger.info(f"  Compile succeeded after {iterations_used} fix(es)")
                        break
                else:
                    logger.warning(f"  Fix iteration {i+1} produced no code")
                    break

        design_results["compiles"] = comp.success
        design_results["fix_iterations"] = iterations_used
        design_results["compile_errors"] = comp.errors if not comp.success else ""

        # --- Phase 3: Test against baseline testbench ---
        if comp.success:
            logger.info("\n[Phase 3] Testing LLM RTL against baseline testbench...")
            run = sim.run_full([rtl_path, spec["baseline_tb"]], f"{name}_llm_vs_baseline")
            if run.simulation:
                design_results["tests_passed"] = run.simulation.tests_passed
                design_results["tests_failed"] = run.simulation.tests_failed
                design_results["functionally_correct"] = run.simulation.success
                logger.info(f"  Tests: {run.simulation.tests_passed} passed, "
                            f"{run.simulation.tests_failed} failed")
            else:
                design_results["functionally_correct"] = False
                logger.warning("  Simulation did not produce results")

        # --- Phase 4: Generate testbench (initial, no evaluation yet) ---
        logger.info("\n[Phase 4] Generating testbench (initial)...")
        tb_result = llm.generate_testbench(
            module_name=name,
            interface=spec["interface"],
            behavior=spec["requirements"],
        )
        tb_dir = os.path.join(PROJECT_ROOT, "src/testbenches/llm_generated")
        os.makedirs(tb_dir, exist_ok=True)
        llm.save_result(tb_result, tb_dir)
        design_results["tb_generated"] = tb_result.success
        design_results["tb_loc"] = len(tb_result.code.splitlines()) if tb_result.code else 0

        elapsed = time.time() - start
        design_results["total_time_sec"] = round(elapsed, 2)
        results[name] = design_results

        logger.info(f"\n  Summary: compile={'OK' if design_results.get('compiles') else 'FAIL'}, "
                     f"fixes={iterations_used}, time={elapsed:.1f}s")

    # Save results
    os.makedirs(results_dir, exist_ok=True)
    report_path = os.path.join(results_dir, "midterm_results.json")
    with open(report_path, 'w') as f:
        json.dump(results, f, indent=2)

    # Print summary table
    logger.info("\n" + "=" * 60)
    logger.info("MIDTERM EXPERIMENT SUMMARY")
    logger.info(f"{'Design':<25} {'Compiles':<10} {'Fixes':<7} {'Tests P/F':<12} {'Time'}")
    logger.info("-" * 60)
    for name, r in results.items():
        tp = r.get('tests_passed', '-')
        tf = r.get('tests_failed', '-')
        logger.info(f"{name:<25} "
                     f"{'YES' if r.get('compiles') else 'NO':<10} "
                     f"{r.get('fix_iterations', 0):<7} "
                     f"{tp}/{tf:<10} "
                     f"{r.get('total_time_sec', 0):.1f}s")
    logger.info("=" * 60)
    logger.info(f"Results saved: {report_path}")


def main():
    parser = argparse.ArgumentParser(
        description="LLM-Assisted SystemVerilog - Midterm Experiment"
    )
    parser.add_argument("--provider", choices=["anthropic", "openai"],
                        default="anthropic")
    parser.add_argument("--model", default=None)
    parser.add_argument("--designs", nargs="+", default=["all"],
                        help="Design names or 'all'")
    parser.add_argument("--results-dir", default="results")
    parser.add_argument("--baseline-only", action="store_true")
    parser.add_argument("--max-fix-iterations", type=int, default=3)

    args = parser.parse_args()

    available = list(DESIGN_SPECS.keys())
    if "all" in args.designs:
        design_names = available
    else:
        design_names = [d for d in args.designs if d in DESIGN_SPECS]
        if not design_names:
            print(f"No matching designs. Available: {available}")
            sys.exit(1)

    results_dir = os.path.join(PROJECT_ROOT, args.results_dir)
    os.makedirs(results_dir, exist_ok=True)

    if args.baseline_only:
        run_baseline_only(design_names, results_dir)
    else:
        provider = LLMProvider(args.provider)
        run_llm_experiment(design_names, provider, args.model,
                           results_dir, args.max_fix_iterations)


if __name__ == "__main__":
    main()
