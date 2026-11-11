//! Shootout driver (Rust). See shootout/PROTOCOL.md.
//!
//! The runner copies one of the sibling `<kernel>.rs` files next to this one as
//! `kernel.rs`.

mod kernel;

use std::env;
use std::fs;
use std::hint::black_box;
use std::process::ExitCode;
use std::time::Instant;

/// One call of the kernel and how long it took, in nanoseconds.
///
/// The kernel is in this crate, so the optimizer can see into it. `black_box`
/// keeps it from specializing the kernel on this input or folding calls together:
/// every call does the whole job, as it does behind a separate C translation unit.
fn timed_run(data: &[u8]) -> (u64, u64) {
    let start = Instant::now();
    let result = black_box(kernel::run(black_box(data)));
    let ns = u64::try_from(start.elapsed().as_nanos()).unwrap_or(u64::MAX);
    (result, ns)
}

fn main() -> ExitCode {
    let args: Vec<String> = env::args().collect();
    let [_, path, min_ms] = args.as_slice() else {
        let prog = args.first().map_or("prog", String::as_str);
        eprintln!("usage: {prog} <input-file> <min_ms>");
        return ExitCode::from(2);
    };
    let data = match fs::read(path) {
        Ok(data) => data,
        Err(err) => {
            eprintln!("{path}: {err}");
            return ExitCode::from(2);
        }
    };
    let Ok(min_ms) = min_ms.parse::<u64>() else {
        eprintln!("min_ms must be a non-negative integer");
        return ExitCode::from(2);
    };
    let min_ns = min_ms.saturating_mul(1_000_000);

    if min_ns == 0 {
        // Cold mode: one call, no digest.
        let (result, ns) = timed_run(&data);
        println!("RESULT {result} 0 {ns} 1");
        return ExitCode::SUCCESS;
    }

    let warm = black_box(kernel::run(black_box(&data)));
    let mut result = warm;
    let mut best = u64::MAX;
    let mut total = 0u64;
    let mut calls = 0u64;
    while calls < 3 || (total < min_ns && calls < 1_000_000) {
        let ns;
        (result, ns) = timed_run(&data);
        if result != warm {
            eprintln!("result changed between calls");
            return ExitCode::from(3);
        }
        best = best.min(ns);
        total += ns;
        calls += 1;
    }
    println!("RESULT {result} {} {best} {calls}", kernel::digest());
    ExitCode::SUCCESS
}
