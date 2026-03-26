"""
llm_interface.py - LLM Interface for SystemVerilog Generation

This file provides a unified interface to interact with LLMs (Anthropic Claude, OpenAI GPT)
for generating RTL, testbenches, and assertions. Alsoo, Supports iterative refinement
using simulation error feedback.
"""

import os
import json
import time
import logging
from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

try:
    import openai
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class GenerationType(Enum):
    RTL = "rtl"
    TESTBENCH = "testbench"
    ASSERTION = "assertion"
    DEBUG = "debug"


@dataclass
class GenerationRequest:
    """Represents a request to generate SystemVerilog code."""
    prompt: str
    gen_type: GenerationType
    design_name: str
    context: str = ""                    # Additional context (spec, constraints)
    error_feedback: str = ""             # Simulation errors for iterative refinement
    iteration: int = 0
    max_tokens: int = 4096
    temperature: float = 0.2            # Low temperature for code generation


@dataclass
class GenerationResult:
    """Result from an LLM generation request."""
    code: str
    raw_response: str
    model: str
    gen_type: GenerationType
    design_name: str
    iteration: int
    latency_ms: float
    token_count: int = 0
    success: bool = True
    error: str = ""


@dataclass
class ExperimentMetrics:
    """Tracks metrics for experimental evaluation."""
    design_name: str
    gen_type: str
    total_iterations: int = 0
    successful_compilations: int = 0
    failed_compilations: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    total_latency_ms: float = 0.0
    bugs_detected: int = 0
    coverage_percent: float = 0.0
    lines_of_code: int = 0
    human_time_estimate_min: float = 0.0
    llm_time_min: float = 0.0


class LLMInterface:

    def __init__(self, provider: LLMProvider = LLMProvider.ANTHROPIC,
                 model: Optional[str] = None,
                 api_key: Optional[str] = None):
        self.provider = provider
        self.metrics_log: list[ExperimentMetrics] = []

        if provider == LLMProvider.ANTHROPIC:
            if not HAS_ANTHROPIC:
                raise ImportError("anthropic package not installed. Run: pip install anthropic")
            self.model = model or "claude-sonnet-4-20250514"
            key = api_key or os.environ.get("ANTHROPIC_API_KEY")
            if not key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            self.client = anthropic.Anthropic(api_key=key)

        elif provider == LLMProvider.OPENAI:
            if not HAS_OPENAI:
                raise ImportError("openai package not installed. Run: pip install openai")
            self.model = model or "gpt-4o"
            key = api_key or os.environ.get("OPENAI_API_KEY")
            if not key:
                raise ValueError("OPENAI_API_KEY not set")
            self.client = openai.OpenAI(api_key=key)

    def generate(self, request: GenerationRequest) -> GenerationResult:
        """Send a generation request to the LLM and return the result."""
        prompt = self._build_prompt(request)

        start_time = time.time()
        try:
            if self.provider == LLMProvider.ANTHROPIC:
                response = self._call_anthropic(prompt, request)
            else:
                response = self._call_openai(prompt, request)

            latency = (time.time() - start_time) * 1000
            code = self._extract_code(response)

            result = GenerationResult(
                code=code,
                raw_response=response,
                model=self.model,
                gen_type=request.gen_type,
                design_name=request.design_name,
                iteration=request.iteration,
                latency_ms=latency,
            )

            logger.info(f"Generated {request.gen_type.value} for '{request.design_name}' "
                        f"(iter={request.iteration}, {latency:.0f}ms, {len(code)} chars)")
            return result

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(f"Generation failed: {e}")
            return GenerationResult(
                code="", raw_response="", model=self.model,
                gen_type=request.gen_type, design_name=request.design_name,
                iteration=request.iteration, latency_ms=latency,
                success=False, error=str(e)
            )

    def _call_anthropic(self, prompt: str, request: GenerationRequest) -> str:
        """Call Anthropic Claude API."""
        message = self.client.messages.create(
            model=self.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}]
        )
        return message.content[0].text

    def _call_openai(self, prompt: str, request: GenerationRequest) -> str:
        """Call OpenAI API."""
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content

    def _build_prompt(self, request: GenerationRequest) -> str:
        """Construct the full prompt from request and template."""
        if request.gen_type == GenerationType.DEBUG:
            return request.prompt  # Debug prompts are pre-formatted
        elif request.error_feedback:
            # Iterative refinement: include error feedback
            return (f"{request.prompt}\n\n"
                    f"Previous attempt had these errors:\n```\n{request.error_feedback}\n```\n"
                    f"Please fix the issues and provide corrected code.")
        else:
            return request.prompt

    @staticmethod
    def _extract_code(response: str) -> str:
        """Extract SystemVerilog code from LLM response."""
        markers = ["```systemverilog", "```sv", "```verilog", "```"]
        for marker in markers:
            if marker in response:
                parts = response.split(marker)
                if len(parts) >= 2:
                    code_block = parts[1]
                    end_idx = code_block.find("```")
                    if end_idx != -1:
                        return code_block[:end_idx].strip()
                    return code_block.strip()


        return response.strip()

    def generate_rtl(self, module_name: str, description: str,
                     interface: str, requirements: str,
                     context: str = "") -> GenerationResult:
     
        prompt = RTL_TEMPLATE.format(
            module_name=module_name,
            description=description,
            interface=interface,
            requirements=requirements,
            context=context
        )
        request = GenerationRequest(
            prompt=prompt, gen_type=GenerationType.RTL,
            design_name=module_name
        )
        return self.generate(request)

    def generate_testbench(self, module_name: str, interface: str,
                           behavior: str, context: str = "") -> GenerationResult:
        """Convenience method for testbench generation."""
        prompt = TESTBENCH_TEMPLATE.format(
            module_name=module_name,
            interface=interface,
            behavior=behavior,
            context=context
        )
        request = GenerationRequest(
            prompt=prompt, gen_type=GenerationType.TESTBENCH,
            design_name=module_name
        )
        return self.generate(request)

    def generate_assertions(self, module_name: str, interface: str,
                            properties: str, context: str = "") -> GenerationResult:
        """Convenience method for SVA generation."""
        prompt = ASSERTION_TEMPLATE.format(
            module_name=module_name,
            interface=interface,
            properties=properties,
            context=context
        )
        request = GenerationRequest(
            prompt=prompt, gen_type=GenerationType.ASSERTION,
            design_name=module_name
        )
        return self.generate(request)

    def iterative_fix(self, design_name: str, code: str,
                      errors: str, context: str = "",
                      max_iterations: int = 3) -> GenerationResult:
        """Iteratively fix code using error feedback."""
        current_code = code
        current_errors = errors

        for iteration in range(max_iterations):
            prompt = DEBUG_TEMPLATE.format(
                design_name=design_name,
                code=current_code,
                errors=current_errors,
                context=context
            )
            request = GenerationRequest(
                prompt=prompt, gen_type=GenerationType.DEBUG,
                design_name=design_name, iteration=iteration + 1
            )
            result = self.generate(request)

            if result.success and result.code:
                logger.info(f"Fix iteration {iteration + 1}: generated {len(result.code)} chars")
                return result

            current_code = result.code or current_code

        return result

    def save_result(self, result: GenerationResult, output_dir: str):
        """Save generation result to file."""
        os.makedirs(output_dir, exist_ok=True)
        suffix_map = {
            GenerationType.RTL: ".sv",
            GenerationType.TESTBENCH: "_tb.sv",
            GenerationType.ASSERTION: "_sva.sv",
            GenerationType.DEBUG: "_fixed.sv",
        }
        suffix = suffix_map.get(result.gen_type, ".sv")
        filename = f"{result.design_name}{suffix}"
        filepath = os.path.join(output_dir, filename)

        with open(filepath, 'w') as f:
            f.write(f"// Auto-generated by LLM ({result.model})\n")
            f.write(f"// Design: {result.design_name}\n")
            f.write(f"// Type: {result.gen_type.value}\n")
            f.write(f"// Iteration: {result.iteration}\n")
            f.write(f"// Latency: {result.latency_ms:.0f}ms\n\n")
            f.write(result.code)

        # Save metadata
        meta_path = filepath.replace(".sv", "_meta.json")
        meta = {
            "design_name": result.design_name,
            "gen_type": result.gen_type.value,
            "model": result.model,
            "iteration": result.iteration,
            "latency_ms": result.latency_ms,
            "success": result.success,
            "code_lines": len(result.code.splitlines()),
            "code_chars": len(result.code),
        }
        with open(meta_path, 'w') as f:
            json.dump(meta, f, indent=2)

        logger.info(f"Saved: {filepath}")
        return filepath
