"""
sim_runner.py - Simulation Runner for SystemVerilog

Compiles and simulates SystemVerilog designs using Icarus Verilog or Verilator.
Captures compilation errors, simulation output, and pass/fail status.
"""

import os
import subprocess
import time
import json
import re
import logging
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class Simulator(Enum):
    IVERILOG = "iverilog"
    VERILATOR = "verilator"


@dataclass
class CompilationResult:
    """Result of compiling SystemVerilog source."""
    success: bool
    errors: str = ""
    warnings: str = ""
    command: str = ""
    return_code: int = 0
    compile_time_ms: float = 0.0


@dataclass
class SimulationResult:
    """Result of running a simulation."""
    success: bool
    output: str = ""
    errors: str = ""
    tests_passed: int = 0
    tests_failed: int = 0
    assertions_passed: int = 0
    assertions_failed: int = 0
    sim_time_ms: float = 0.0
    vcd_file: str = ""
    command: str = ""


@dataclass
class FullRunResult:
    """Combined compilation + simulation result."""
    design_name: str
    compilation: CompilationResult
    simulation: Optional[SimulationResult] = None
    total_time_ms: float = 0.0


class SimRunner:
    """Compiles and simulates SystemVerilog designs."""

    def __init__(self, simulator: Simulator = Simulator.IVERILOG,
                 work_dir: str = "sim_work",
                 timeout: int = 60):
        self.simulator = simulator
        self.work_dir = os.path.abspath(work_dir)
        self.timeout = timeout
        os.makedirs(self.work_dir, exist_ok=True)

        # Verify simulator is installed
        self._check_simulator()

    def _check_simulator(self):
        """Verify the simulator is available on PATH."""
        cmd = "iverilog" if self.simulator == Simulator.IVERILOG else "verilator"
        try:
            result = subprocess.run([cmd, "--version"],
                                    capture_output=True, text=True, timeout=5)
            version = result.stdout.strip().split('\n')[0]
            logger.info(f"Simulator: {version}")
        except FileNotFoundError:
            logger.warning(f"{cmd} not found. Install with: "
                           f"{'brew install icarus-verilog' if cmd == 'iverilog' else 'brew install verilator'}")

    def compile(self, sources: list[str], top_module: str = "",
                output_name: str = "sim_out",
                extra_flags: list[str] = None) -> CompilationResult:
        """Compile SystemVerilog sources."""
        if extra_flags is None:
            extra_flags = []

        output_path = os.path.join(self.work_dir, output_name)

        if self.simulator == Simulator.IVERILOG:
            return self._compile_iverilog(sources, output_path, extra_flags)
        else:
            return self._compile_verilator(sources, top_module, output_path, extra_flags)

    def _compile_iverilog(self, sources: list[str], output: str,
                          extra_flags: list[str]) -> CompilationResult:
        """Compile with Icarus Verilog."""
        cmd = ["iverilog", "-g2012", "-Wall", "-o", output] + extra_flags + sources
        cmd_str = " ".join(cmd)
        logger.info(f"Compiling: {cmd_str}")

        start = time.time()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self.timeout, cwd=self.work_dir
            )
            elapsed = (time.time() - start) * 1000

            # Parse warnings and errors
            stderr = result.stderr
            errors = "\n".join(l for l in stderr.splitlines()
                               if "error" in l.lower())
            warnings = "\n".join(l for l in stderr.splitlines()
                                  if "warning" in l.lower())

            return CompilationResult(
                success=(result.returncode == 0),
                errors=errors or stderr if result.returncode != 0 else "",
                warnings=warnings,
                command=cmd_str,
                return_code=result.returncode,
                compile_time_ms=elapsed
            )
        except subprocess.TimeoutExpired:
            return CompilationResult(
                success=False, errors="Compilation timed out",
                command=cmd_str, compile_time_ms=self.timeout * 1000
            )

    def _compile_verilator(self, sources: list[str], top_module: str,
                            output: str, extra_flags: list[str]) -> CompilationResult:
        """Compile with Verilator (lint/compile check)."""
        cmd = (["verilator", "--lint-only", "--sv", "-Wall"] +
               ([f"--top-module", top_module] if top_module else []) +
               extra_flags + sources)
        cmd_str = " ".join(cmd)
        logger.info(f"Linting: {cmd_str}")

        start = time.time()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self.timeout
            )
            elapsed = (time.time() - start) * 1000

            return CompilationResult(
                success=(result.returncode == 0),
                errors=result.stderr if result.returncode != 0 else "",
                warnings=result.stderr if result.returncode == 0 else "",
                command=cmd_str,
                return_code=result.returncode,
                compile_time_ms=elapsed
            )
        except subprocess.TimeoutExpired:
            return CompilationResult(
                success=False, errors="Compilation timed out",
                command=cmd_str, compile_time_ms=self.timeout * 1000
            )

    def simulate(self, executable: str = "sim_out",
                 vcd_file: str = "") -> SimulationResult:
        """Run a compiled simulation (Icarus Verilog only)."""
        exe_path = os.path.join(self.work_dir, executable)

        if not os.path.exists(exe_path):
            return SimulationResult(
                success=False, errors=f"Executable not found: {exe_path}"
            )

        cmd = ["vvp", exe_path]
        cmd_str = " ".join(cmd)
        logger.info(f"Simulating: {cmd_str}")

        start = time.time()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=self.timeout, cwd=self.work_dir
            )
            elapsed = (time.time() - start) * 1000

            output = result.stdout
            errors = result.stderr

            # Parse test results from output
            passed, failed = self._parse_test_results(output)
            a_passed, a_failed = self._parse_assertion_results(output + errors)

            return SimulationResult(
                success=(result.returncode == 0 and failed == 0 and a_failed == 0),
                output=output,
                errors=errors,
                tests_passed=passed,
                tests_failed=failed,
                assertions_passed=a_passed,
                assertions_failed=a_failed,
                sim_time_ms=elapsed,
                vcd_file=vcd_file,
                command=cmd_str
            )
        except subprocess.TimeoutExpired:
            return SimulationResult(
                success=False, errors="Simulation timed out",
                sim_time_ms=self.timeout * 1000, command=cmd_str
            )

    def _parse_test_results(self, output: str) -> tuple[int, int]:
        """Parse pass/fail counts from simulation output."""
        passed = 0
        failed = 0

        # Common patterns in self-checking testbenches
        for line in output.splitlines():
            line_lower = line.lower()
            if "pass" in line_lower and "test" in line_lower:
                nums = re.findall(r'\d+', line)
                if nums:
                    passed += int(nums[0])
            elif "fail" in line_lower and "test" in line_lower:
                nums = re.findall(r'\d+', line)
                if nums:
                    failed += int(nums[0])
            elif "pass" in line_lower:
                passed += 1
            elif "fail" in line_lower or "error" in line_lower:
                failed += 1

        # Look for summary patterns like "Tests: 10 passed, 2 failed"
        summary = re.search(r'(\d+)\s*passed.*?(\d+)\s*failed', output, re.IGNORECASE)
        if summary:
            passed = int(summary.group(1))
            failed = int(summary.group(2))

        return passed, failed

    def _parse_assertion_results(self, output: str) -> tuple[int, int]:
        """Parse SVA assertion results from simulation output."""
        a_passed = len(re.findall(r'Assertion\s+\w+\s+passed', output, re.IGNORECASE))
        a_failed = len(re.findall(r'Assertion\s+\w+\s+failed', output, re.IGNORECASE))
        return a_passed, a_failed

    def run_full(self, sources: list[str], design_name: str,
                 top_module: str = "",
                 extra_flags: list[str] = None) -> FullRunResult:
        """Compile and simulate in one step."""
        start = time.time()

        exe_name = f"{design_name}_sim"
        comp = self.compile(sources, top_module, exe_name, extra_flags)

        sim = None
        if comp.success and self.simulator == Simulator.IVERILOG:
            sim = self.simulate(exe_name)

        total = (time.time() - start) * 1000

        result = FullRunResult(
            design_name=design_name,
            compilation=comp,
            simulation=sim,
            total_time_ms=total
        )

        logger.info(f"Run complete: {design_name} "
                     f"(compile={'OK' if comp.success else 'FAIL'}"
                     f"{', sim=' + ('OK' if sim.success else 'FAIL') if sim else ''}"
                     f", {total:.0f}ms)")

        return result

    def save_results(self, result: FullRunResult, output_dir: str):
        """Save simulation results to JSON."""
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, f"{result.design_name}_results.json")

        data = {
            "design_name": result.design_name,
            "total_time_ms": result.total_time_ms,
            "compilation": {
                "success": result.compilation.success,
                "errors": result.compilation.errors,
                "warnings": result.compilation.warnings,
                "compile_time_ms": result.compilation.compile_time_ms,
            },
        }
        if result.simulation:
            data["simulation"] = {
                "success": result.simulation.success,
                "tests_passed": result.simulation.tests_passed,
                "tests_failed": result.simulation.tests_failed,
                "assertions_passed": result.simulation.assertions_passed,
                "assertions_failed": result.simulation.assertions_failed,
                "sim_time_ms": result.simulation.sim_time_ms,
                "output": result.simulation.output[:2000],  # Truncate
            }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Results saved: {filepath}")
