//! wordcount kernel (Rust). A port of tasks/wordcount/ref.c.

/// Exactly the six ASCII whitespace bytes: space, \t \n \v \f \r.
/// (`u8::is_ascii_whitespace` leaves out \v, so it is not the same set.)
fn is_space(c: u8) -> bool {
    c == b' ' || (b'\t'..=b'\r').contains(&c)
}

fn wordcount(buf: &[u8]) -> u64 {
    let mut words = 0u64;
    let mut in_word = false;
    for &c in buf {
        if is_space(c) {
            in_word = false;
        } else if !in_word {
            in_word = true;
            words += 1;
        }
    }
    words
}

pub fn run(data: &[u8]) -> u64 {
    wordcount(data)
}

pub fn digest() -> u64 {
    0
}
