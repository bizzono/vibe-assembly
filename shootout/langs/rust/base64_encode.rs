//! base64_encode kernel (Rust). A port of tasks/base64_encode/ref.c.

use std::sync::Mutex;

const ALPHABET: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

/// Writes the Base64 text of `src` to the front of `dst` and returns its length,
/// `4 * ceil(src.len() / 3)`. Panics if `dst` is shorter than that.
fn base64_encode(src: &[u8], dst: &mut [u8]) -> usize {
    let (groups, rest) = src.as_chunks::<3>();
    let (body, tail) = dst.split_at_mut(4 * groups.len());
    let (quads, _) = body.as_chunks_mut::<4>();
    for (&[a, b, c], quad) in groups.iter().zip(quads) {
        let v = u32::from(a) << 16 | u32::from(b) << 8 | u32::from(c);
        *quad = [
            ALPHABET[(v >> 18) as usize],
            ALPHABET[((v >> 12) & 63) as usize],
            ALPHABET[((v >> 6) & 63) as usize],
            ALPHABET[(v & 63) as usize],
        ];
    }
    match *rest {
        [a] => {
            let v = u32::from(a) << 16;
            tail[..4].copy_from_slice(&[
                ALPHABET[(v >> 18) as usize],
                ALPHABET[((v >> 12) & 63) as usize],
                b'=',
                b'=',
            ]);
            body.len() + 4
        }
        [a, b] => {
            let v = u32::from(a) << 16 | u32::from(b) << 8;
            tail[..4].copy_from_slice(&[
                ALPHABET[(v >> 18) as usize],
                ALPHABET[((v >> 12) & 63) as usize],
                ALPHABET[((v >> 6) & 63) as usize],
                b'=',
            ]);
            body.len() + 4
        }
        _ => body.len(),
    }
}

/// The output buffer and how much of it the last `run` filled.
struct Output {
    buf: Vec<u8>,
    len: usize,
}

static OUTPUT: Mutex<Output> = Mutex::new(Output { buf: Vec::new(), len: 0 });

pub fn run(data: &[u8]) -> u64 {
    let mut out = OUTPUT.lock().unwrap();
    let needed = 4 * data.len().div_ceil(3);
    if out.buf.len() < needed {
        out.buf = vec![0; needed]; // allocated on the first call, then reused
    }
    out.len = base64_encode(data, &mut out.buf);
    out.len as u64
}

pub fn digest() -> u64 {
    const FNV_OFFSET_BASIS: u64 = 0xcbf2_9ce4_8422_2325;
    const FNV_PRIME: u64 = 0x0100_0000_01b3;
    let out = OUTPUT.lock().unwrap();
    out.buf[..out.len]
        .iter()
        .fold(FNV_OFFSET_BASIS, |hash, &byte| (hash ^ u64::from(byte)).wrapping_mul(FNV_PRIME))
}
