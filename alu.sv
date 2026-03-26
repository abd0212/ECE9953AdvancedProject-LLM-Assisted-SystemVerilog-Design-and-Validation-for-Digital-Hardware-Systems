// alu.sv - 32-bit Arithmetic Logic Unit (Baseline)
// Supports: ADD, SUB, AND, OR, XOR, SLL, SRL, SRA, SLT, SLTU
// Includes overflow detection and zero flag

module alu #(
    parameter WIDTH = 32
) (
    input  logic [WIDTH-1:0]  operand_a,
    input  logic [WIDTH-1:0]  operand_b,
    input  logic [3:0]        alu_op,
    output logic [WIDTH-1:0]  result,
    output logic              zero,
    output logic              overflow,
    output logic              carry_out,
    output logic              negative
);

    // ALU operation encoding
    localparam ALU_ADD  = 4'b0000;
    localparam ALU_SUB  = 4'b0001;
    localparam ALU_AND  = 4'b0010;
    localparam ALU_OR   = 4'b0011;
    localparam ALU_XOR  = 4'b0100;
    localparam ALU_SLL  = 4'b0101;  // Shift left logical
    localparam ALU_SRL  = 4'b0110;  // Shift right logical
    localparam ALU_SRA  = 4'b0111;  // Shift right arithmetic
    localparam ALU_SLT  = 4'b1000;  // Set less than (signed)
    localparam ALU_SLTU = 4'b1001;  // Set less than (unsigned)

    // Internal signals
    logic [WIDTH:0] sum_ext;     // Extended for carry detection
    logic [WIDTH:0] sub_ext;
    logic signed [WIDTH-1:0] signed_a, signed_b;

    assign signed_a = $signed(operand_a);
    assign signed_b = $signed(operand_b);

    always_comb begin
        // Defaults
        result    = '0;
        overflow  = 1'b0;
        carry_out = 1'b0;

        // Extended arithmetic for carry/overflow detection
        sum_ext = {1'b0, operand_a} + {1'b0, operand_b};
        sub_ext = {1'b0, operand_a} - {1'b0, operand_b};

        case (alu_op)
            ALU_ADD: begin
                result    = sum_ext[WIDTH-1:0];
                carry_out = sum_ext[WIDTH];
                // Signed overflow: both same sign, result different sign
                overflow  = (operand_a[WIDTH-1] == operand_b[WIDTH-1]) &&
                            (result[WIDTH-1] != operand_a[WIDTH-1]);
            end

            ALU_SUB: begin
                result    = sub_ext[WIDTH-1:0];
                carry_out = sub_ext[WIDTH];  // Borrow
                overflow  = (operand_a[WIDTH-1] != operand_b[WIDTH-1]) &&
                            (result[WIDTH-1] != operand_a[WIDTH-1]);
            end

            ALU_AND: result = operand_a & operand_b;
            ALU_OR:  result = operand_a | operand_b;
            ALU_XOR: result = operand_a ^ operand_b;

            ALU_SLL: result = operand_a << operand_b[4:0];
            ALU_SRL: result = operand_a >> operand_b[4:0];
            ALU_SRA: result = $unsigned($signed(operand_a) >>> operand_b[4:0]);

            ALU_SLT:  result = {{(WIDTH-1){1'b0}}, (signed_a < signed_b)};
            ALU_SLTU: result = {{(WIDTH-1){1'b0}}, (operand_a < operand_b)};

            default: result = '0;
        endcase
    end

    // Status flags
    assign zero     = (result == '0);
    assign negative = result[WIDTH-1];

endmodule
