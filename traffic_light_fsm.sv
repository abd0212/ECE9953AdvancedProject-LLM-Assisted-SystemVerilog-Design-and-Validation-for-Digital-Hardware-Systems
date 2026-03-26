// traffic_light_fsm.sv - Traffic Light FSM Controller (Baseline)
// A Mealy-type FSM controlling a traffic light intersection.
// States: RED, RED_YELLOW, GREEN, YELLOW
// Inputs: clk, rst_n, sensor (car detected), emergency
// Outputs: light[2:0] (one-hot: R, Y, G), walk_signal

module traffic_light_fsm (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       sensor,      // Car sensor on side road
    input  logic       emergency,   // Emergency vehicle override
    output logic [2:0] light,       // {red, yellow, green}
    output logic       walk_signal  // Pedestrian walk signal
);

    // State encoding
    typedef enum logic [2:0] {
        S_RED        = 3'b000,
        S_RED_YELLOW = 3'b001,
        S_GREEN      = 3'b010,
        S_YELLOW     = 3'b011,
        S_EMERGENCY  = 3'b100
    } state_t;

    state_t state, next_state;

    // Timer counter for state durations
    logic [7:0] timer, next_timer;

    // State durations (in clock cycles)
    localparam RED_TIME        = 8'd100;
    localparam RED_YELLOW_TIME = 8'd20;
    localparam GREEN_TIME      = 8'd80;
    localparam YELLOW_TIME     = 8'd30;

    // Sequential logic: state and timer registers
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_RED;
            timer <= 8'd0;
        end else begin
            state <= next_state;
            timer <= next_timer;
        end
    end

    // Combinational logic: next state and timer
    always_comb begin
        next_state = state;
        next_timer = timer + 8'd1;

        case (state)
            S_RED: begin
                if (emergency) begin
                    next_state = S_EMERGENCY;
                    next_timer = 8'd0;
                end else if (timer >= RED_TIME) begin
                    next_state = S_RED_YELLOW;
                    next_timer = 8'd0;
                end
            end

            S_RED_YELLOW: begin
                if (emergency) begin
                    next_state = S_EMERGENCY;
                    next_timer = 8'd0;
                end else if (timer >= RED_YELLOW_TIME) begin
                    next_state = S_GREEN;
                    next_timer = 8'd0;
                end
            end

            S_GREEN: begin
                if (emergency) begin
                    next_state = S_YELLOW;
                    next_timer = 8'd0;
                end else if (timer >= GREEN_TIME || (timer >= GREEN_TIME/2 && sensor)) begin
                    next_state = S_YELLOW;
                    next_timer = 8'd0;
                end
            end

            S_YELLOW: begin
                if (timer >= YELLOW_TIME) begin
                    next_state = S_RED;
                    next_timer = 8'd0;
                end
            end

            S_EMERGENCY: begin
                // Stay red until emergency clears
                if (!emergency) begin
                    next_state = S_RED;
                    next_timer = 8'd0;
                end
            end

            default: begin
                next_state = S_RED;
                next_timer = 8'd0;
            end
        endcase
    end

    // Output logic
    always_comb begin
        case (state)
            S_RED:        light = 3'b100;  // Red
            S_RED_YELLOW: light = 3'b110;  // Red + Yellow
            S_GREEN:      light = 3'b001;  // Green
            S_YELLOW:     light = 3'b010;  // Yellow
            S_EMERGENCY:  light = 3'b100;  // Red (all stop)
            default:      light = 3'b100;  // Default red
        endcase

        // Walk signal only during red phase (and not emergency)
        walk_signal = (state == S_RED) && (timer > 8'd10) && (timer < RED_TIME - 8'd10)
                      && !emergency;
    end

endmodule
