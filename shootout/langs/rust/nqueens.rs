//! nqueens kernel (Rust). A port of tasks/nqueens/ref.c: the textbook bitmask
//! backtracking search, one queen per row, every complete placement counted.

fn place(all: u32, cols: u32, diag_l: u32, diag_r: u32) -> u64 {
    if cols == all {
        return 1;
    }
    let mut count = 0;
    let mut open = all & !(cols | diag_l | diag_r);
    while open != 0 {
        let bit = open & open.wrapping_neg(); // lowest free square in this row
        open ^= bit;
        count += place(all, cols | bit, (diag_l | bit) << 1, (diag_r | bit) >> 1);
    }
    count
}

fn nqueens(n: u64) -> u64 {
    if n > 31 {
        return 0;
    }
    let all = ((1u64 << n) - 1) as u32;
    place(all, 0, 0, 0)
}

/// The input is n as a little-endian u32 (0 if it is too short).
pub fn run(data: &[u8]) -> u64 {
    let n = data.first_chunk::<4>().map_or(0, |bytes| u32::from_le_bytes(*bytes));
    nqueens(u64::from(n))
}

pub fn digest() -> u64 {
    0
}
