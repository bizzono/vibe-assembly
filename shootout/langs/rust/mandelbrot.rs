//! mandelbrot kernel (Rust). A port of tasks/mandelbrot/ref.c.
//!
//! The result must be bit-exact: every `*`, `+` and `-` below is its own
//! correctly-rounded IEEE-754 operation. Rust never fuses them into a multiply-add
//! (that takes an explicit `f64::mul_add`).

fn mandelbrot(width: u64, height: u64, max_iter: u64) -> u64 {
    if width == 0 || height == 0 {
        return 0;
    }
    let dx = 3.0 / width as f64;
    let dy = 3.0 / height as f64;
    let mut total = 0u64;
    for py in 0..height {
        let ci = -1.5 + py as f64 * dy;
        for px in 0..width {
            let cr = -2.0 + px as f64 * dx;
            let (mut zr, mut zi) = (0.0f64, 0.0f64);
            let mut n = 0u64;
            while n < max_iter {
                let zr2 = zr * zr;
                let zi2 = zi * zi;
                if zr2 + zi2 > 4.0 {
                    break;
                }
                zi = 2.0 * zr * zi + ci;
                zr = zr2 - zi2 + cr;
                n += 1;
            }
            total += n;
        }
    }
    total
}

/// The input is width, height, max_iter as little-endian u32 (all zero if it is too short).
pub fn run(data: &[u8]) -> u64 {
    let (words, _) = data.as_chunks::<4>();
    let [width, height, max_iter] = match words {
        [w, h, m, ..] => [w, h, m].map(|bytes| u64::from(u32::from_le_bytes(*bytes))),
        _ => [0; 3],
    };
    mandelbrot(width, height, max_iter)
}

pub fn digest() -> u64 {
    0
}
