// traffic_light_fsm_tb.sv - Testbench for Traffic Light FSM (Baseline)
`timescale 1ns/1ps

module traffic_light_fsm_tb;

    logic       clk, rst_n, sensor, emergency;
    logic [2:0] light;
    logic       walk_signal;

    int pass_count = 0;
    int fail_count = 0;

    // DUT instantiation
    traffic_light_fsm dut (
        .clk(clk), .rst_n(rst_n), .sensor(sensor),
        .emergency(emergency), .light(light), .walk_signal(walk_signal)
    );

    // Clock generation: 10ns period
    initial clk = 0;
    always #5 clk = ~clk;

    // Task: check expected light state
    task check_light(input [2:0] expected, input string msg);
        if (light !== expected) begin
            $display("FAIL [%0t]: %s - expected=%b, got=%b", $time, msg, expected, light);
            fail_count++;
        end else begin
            $display("PASS [%0t]: %s - light=%b", $time, msg, light);
            pass_count++;
        end
    endtask

    // Task: advance N clock cycles
    task advance(input int n);
        repeat(n) @(posedge clk);
    endtask

    initial begin
        $display("=== Traffic Light FSM Testbench ===");
        $dumpfile("traffic_light_fsm.vcd");
        $dumpvars(0, traffic_light_fsm_tb);

        // Initialize
        rst_n = 0; sensor = 0; emergency = 0;
        advance(5);

        // Release reset
        rst_n = 1;
        @(posedge clk);

        // Test 1: After reset, should be RED
        check_light(3'b100, "Reset -> RED");

        // Test 2: Wait for RED duration, should transition to RED_YELLOW
        advance(102);
        check_light(3'b110, "RED -> RED_YELLOW");

        // Test 3: After RED_YELLOW, should go GREEN
        advance(22);
        check_light(3'b001, "RED_YELLOW -> GREEN");

        // Test 4: After GREEN, should go YELLOW
        advance(82);
        check_light(3'b010, "GREEN -> YELLOW");

        // Test 5: After YELLOW, back to RED
        advance(32);
        check_light(3'b100, "YELLOW -> RED");

        // Test 6: Sensor shortens green phase
        advance(102);  // Wait through RED
        advance(22);   // Through RED_YELLOW, now in GREEN
        check_light(3'b001, "In GREEN phase");
        sensor = 1;
        advance(42);   // Should transition early due to sensor
        check_light(3'b010, "Sensor shortens GREEN -> YELLOW");
        sensor = 0;

        // Test 7: Emergency override
        advance(32);   // Back to RED
        advance(50);   // Midway through RED
        emergency = 1;
        advance(5);
        check_light(3'b100, "Emergency -> RED");

        // Test 8: Walk signal during RED (not emergency)
        emergency = 0;
        advance(5);    // Should return to RED
        advance(15);   // Past initial delay
        if (walk_signal) begin
            $display("PASS [%0t]: Walk signal active during RED", $time);
            pass_count++;
        end else begin
            $display("FAIL [%0t]: Walk signal should be active during RED", $time);
            fail_count++;
        end

        // Test 9: No walk signal during emergency
        emergency = 1;
        advance(5);
        if (!walk_signal) begin
            $display("PASS [%0t]: Walk signal off during emergency", $time);
            pass_count++;
        end else begin
            $display("FAIL [%0t]: Walk signal should be off during emergency", $time);
            fail_count++;
        end
        emergency = 0;

        // Summary
        advance(10);
        $display("\n=== Test Summary ===");
        $display("Tests: %0d passed, %0d failed", pass_count, fail_count);
        if (fail_count == 0)
            $display("ALL TESTS PASSED");
        else
            $display("SOME TESTS FAILED");
        $finish;
    end

    // Timeout watchdog
    initial begin
        #500000;
        $display("ERROR: Simulation timeout!");
        $finish;
    end

endmodule
