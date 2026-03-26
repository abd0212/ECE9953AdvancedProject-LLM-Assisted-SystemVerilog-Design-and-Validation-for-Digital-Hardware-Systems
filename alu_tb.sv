// alu_tb.sv - Testbench for 32-bit ALU (Baseline)
`timescale 1ns/1ps

module alu_tb;

    logic [31:0] operand_a, operand_b, result;
    logic [3:0]  alu_op;
    logic        zero, overflow, carry_out, negative;

    int pass_count = 0;
    int fail_count = 0;

    // DUT
    alu #(.WIDTH(32)) dut (
        .operand_a(operand_a), .operand_b(operand_b),
        .alu_op(alu_op), .result(result),
        .zero(zero), .overflow(overflow),
        .carry_out(carry_out), .negative(negative)
    );

    // ALU opcodes
    localparam ADD  = 4'b0000, SUB  = 4'b0001;
    localparam AND_ = 4'b0010, OR_  = 4'b0011, XOR_ = 4'b0100;
    localparam SLL  = 4'b0101, SRL  = 4'b0110, SRA  = 4'b0111;
    localparam SLT  = 4'b1000, SLTU = 4'b1001;

    task check(input [31:0] expected, input string msg);
        #1;
        if (result !== expected) begin
            $display("FAIL: %s | a=%0h b=%0h op=%0b | expected=%0h got=%0h",
                     msg, operand_a, operand_b, alu_op, expected, result);
            fail_count++;
        end else begin
            $display("PASS: %s | result=%0h", msg, result);
            pass_count++;
        end
    endtask

    task check_flag(input logic actual, input logic expected, input string msg);
        #1;
        if (actual !== expected) begin
            $display("FAIL: %s | expected=%b got=%b", msg, expected, actual);
            fail_count++;
        end else begin
            $display("PASS: %s = %b", msg, actual);
            pass_count++;
        end
    endtask

    initial begin
        $display("=== ALU Testbench ===");

        // --- Addition ---
        operand_a = 32'd10; operand_b = 32'd20; alu_op = ADD;
        check(32'd30, "ADD: 10 + 20");

        operand_a = 32'hFFFFFFFF; operand_b = 32'd1; alu_op = ADD;
        check(32'd0, "ADD: 0xFFFFFFFF + 1 (overflow)");
        check_flag(carry_out, 1'b1, "ADD carry_out");
        check_flag(zero, 1'b1, "ADD zero flag");

        // Signed overflow: positive + positive = negative
        operand_a = 32'h7FFFFFFF; operand_b = 32'd1; alu_op = ADD;
        check(32'h80000000, "ADD: MAX_INT + 1");
        check_flag(overflow, 1'b1, "ADD signed overflow");

        // --- Subtraction ---
        operand_a = 32'd50; operand_b = 32'd30; alu_op = SUB;
        check(32'd20, "SUB: 50 - 30");

        operand_a = 32'd0; operand_b = 32'd1; alu_op = SUB;
        check(32'hFFFFFFFF, "SUB: 0 - 1");
        check_flag(negative, 1'b1, "SUB negative flag");

        // --- Logical ---
        operand_a = 32'hFF00FF00; operand_b = 32'h0F0F0F0F; alu_op = AND_;
        check(32'h0F000F00, "AND");

        operand_a = 32'hFF00FF00; operand_b = 32'h0F0F0F0F; alu_op = OR_;
        check(32'hFF0FFF0F, "OR");

        operand_a = 32'hFF00FF00; operand_b = 32'h0F0F0F0F; alu_op = XOR_;
        check(32'hF00FF00F, "XOR");

        // --- Shifts ---
        operand_a = 32'd1; operand_b = 32'd4; alu_op = SLL;
        check(32'd16, "SLL: 1 << 4");

        operand_a = 32'd128; operand_b = 32'd3; alu_op = SRL;
        check(32'd16, "SRL: 128 >> 3");

        operand_a = 32'hF0000000; operand_b = 32'd4; alu_op = SRA;
        check(32'hFF000000, "SRA: sign-extended right shift");

        // --- Comparisons ---
        operand_a = 32'hFFFFFFFF; operand_b = 32'd1; alu_op = SLT;
        check(32'd1, "SLT: -1 < 1 (signed)");

        operand_a = 32'hFFFFFFFF; operand_b = 32'd1; alu_op = SLTU;
        check(32'd0, "SLTU: 0xFFFFFFFF > 1 (unsigned)");

        operand_a = 32'd5; operand_b = 32'd5; alu_op = SLT;
        check(32'd0, "SLT: 5 not < 5");

        // Zero flag test
        operand_a = 32'd100; operand_b = 32'd100; alu_op = SUB;
        check(32'd0, "SUB: 100 - 100 = 0");
        check_flag(zero, 1'b1, "Zero flag on equal subtract");

        // Summary
        #10;
        $display("\n=== Test Summary ===");
        $display("Tests: %0d passed, %0d failed", pass_count, fail_count);
        if (fail_count == 0) $display("ALL TESTS PASSED");
        else $display("SOME TESTS FAILED");
        $finish;
    end

endmodule
